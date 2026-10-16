"""
Tests for the Claude triage layer, using a fake client (no API key or network needed).

    pytest -q
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from triage import llm  # noqa: E402

DATA = json.loads((ROOT / "data" / "tickets.json").read_text())
QUEUES = DATA["queues"]
CFG = llm.LLMConfig("anthropic", "claude-test")


class FakeClient:
    """Mimics client.messages.create; `responder(request) -> list of content blocks`."""

    def __init__(self, responder):
        self.requests = []
        self.messages = SimpleNamespace(create=self._create)
        self._responder = responder

    def _create(self, **kw):
        self.requests.append(kw)
        return SimpleNamespace(content=self._responder(kw), stop_reason="tool_use",
                               usage=SimpleNamespace(input_tokens=100, output_tokens=50))


def tool_use(name, data):
    return SimpleNamespace(type="tool_use", name=name, input=data)


def good_triage(**over):
    d = {"summary": "Bed census stale.", "category": "Stale data", "priority_score": 88,
         "suggested_queue": "DE – Pipelines (Talend/ETL)", "suggested_owner": "Dev Patel",
         "confidence": 0.9, "rationale": "ADT load failed.", "should_be_request": False,
         "similar_history": "INC0098812 (2026-08-21) — Dev Patel raised pool size"}
    d.update(over)
    return d


TICKET = DATA["tickets"][0]


def test_request_shape_and_parse():
    c = FakeClient(lambda kw: [tool_use("record_triage", good_triage())])
    res, meta = llm.triage_ticket(c, CFG, TICKET, QUEUES, DATA["demo_now"])
    req = c.requests[0]
    assert req["tool_choice"] == {"type": "auto"}          # 5.5 models reject forced tool_choice
    assert req["tools"][0]["strict"] is True               # Claude API: schema-enforced
    assert req["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert res["queue"] == "DE – Pipelines (Talend/ETL)" and res["score"] == 88
    assert meta["input_tokens"] == 100


def test_bedrock_omits_strict():
    c = FakeClient(lambda kw: [tool_use("record_triage", good_triage())])
    llm.triage_ticket(c, llm.LLMConfig("bedrock", "anthropic.claude-test"), TICKET, QUEUES, DATA["demo_now"])
    assert "strict" not in c.requests[0]["tools"][0]


def test_clamps_and_coerces():
    c = FakeClient(lambda kw: [tool_use("record_triage", good_triage(
        priority_score=140, confidence=87, suggested_owner="Nobody", category="Weird"))])
    res, _ = llm.triage_ticket(c, CFG, TICKET, QUEUES, DATA["demo_now"])
    assert res["score"] == 100
    assert res["confidence"] == 0.87
    assert res["owner"] == QUEUES[res["queue"]]
    assert res["category"] in llm.CATEGORIES


def test_invalid_queue_raises():
    c = FakeClient(lambda kw: [tool_use("record_triage", good_triage(suggested_queue="Facilities"))])
    with pytest.raises(llm.LLMError):
        llm.triage_ticket(c, CFG, TICKET, QUEUES, DATA["demo_now"])


def test_text_json_fallback_and_no_tool():
    blob = json.dumps(good_triage())
    c = FakeClient(lambda kw: [SimpleNamespace(type="text", text=f"Here you go: {blob}")])
    res, _ = llm.triage_ticket(c, CFG, TICKET, QUEUES, DATA["demo_now"])
    assert res["score"] == 88
    c2 = FakeClient(lambda kw: [SimpleNamespace(type="text", text="I can't help with that.")])
    with pytest.raises(llm.LLMError):
        llm.triage_ticket(c2, CFG, TICKET, QUEUES, DATA["demo_now"])


def test_duplicate_detection_enum():
    issues = {"GRP-01": "ADT load failed", "INC0104493": "PHI exposure"}
    c = FakeClient(lambda kw: [tool_use("record_triage", good_triage(duplicate_of="GRP-01"))])
    res, _ = llm.triage_ticket(c, CFG, TICKET, QUEUES, DATA["demo_now"], open_issues=issues)
    schema = c.requests[0]["tools"][0]["input_schema"]
    assert schema["properties"]["duplicate_of"]["enum"] == ["GRP-01", "INC0104493", "none"]
    assert res["duplicate_of"] == "GRP-01"
    c2 = FakeClient(lambda kw: [tool_use("record_triage", good_triage(duplicate_of="GRP-99"))])
    res2, _ = llm.triage_ticket(c2, CFG, TICKET, QUEUES, DATA["demo_now"], open_issues=issues)
    assert res2["duplicate_of"] == "none"


def test_group_cleaning():
    nums = [t["number"] for t in DATA["tickets"]]
    raw = {"groups": [
        {"title": "A", "parent": nums[0], "members": [nums[1], "BOGUS"], "root_cause": "x",
         "recommended_action": "y", "notify": ["Automated", "Nursing"], "comms_draft": "Subject: hi"},
        {"title": "B", "parent": nums[1], "members": [nums[1], nums[2]], "root_cause": "x",
         "recommended_action": "y", "notify": [], "comms_draft": ""},      # nums[1] already used
        {"title": "C", "parent": nums[3], "members": [nums[3]], "root_cause": "x",
         "recommended_action": "y", "notify": [], "comms_draft": ""},      # singleton → dropped
    ]}
    groups = llm.clean_groups(raw, nums)
    assert len(groups) == 1
    g = groups[0]
    assert g["parent"] == nums[0] and g["members"] == [nums[0], nums[1]]
    assert g["notify"] == ["Nursing"]


def test_config_detection(monkeypatch):
    for k in llm.CONFIG_KEYS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(llm, "load_secrets_file", lambda: {})
    assert llm.get_config() is None
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    cfg = llm.get_config("precompute")
    assert cfg.provider == "anthropic" and cfg.model == "claude-sonnet-5-5"
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    cfg = llm.get_config("live")
    assert cfg.provider == "bedrock" and cfg.model == "anthropic.claude-haiku-5-5"


def test_groups_numbered_by_priority(tmp_path):
    from scripts import precompute
    nums = [t["number"] for t in DATA["tickets"]]

    def responder(kw):
        if kw["tools"][0]["name"] == "record_groups":
            mk = lambda a, b, title: {"title": title, "parent": a, "members": [a, b], "root_cause": "",
                                      "recommended_action": "", "notify": [], "comms_draft": ""}
            return [tool_use("record_groups", {"groups": [mk(nums[0], nums[1], "low"),
                                                          mk(nums[2], nums[3], "high")]})]
        hi = any(n in kw["messages"][0]["content"] for n in (f"Number: {nums[2]}", f"Number: {nums[3]}"))
        return [tool_use("record_triage", good_triage(priority_score=95 if hi else 20))]

    payload = precompute.run(client=FakeClient(responder), cfg=CFG, out_path=tmp_path / "o.json",
                             log=lambda *_: None)
    assert payload["groups"]["GRP-01"]["title"] == "high"


def test_precompute_end_to_end(tmp_path):
    from scripts import precompute
    nums = [t["number"] for t in DATA["tickets"]]

    def responder(kw):
        if kw["tools"][0]["name"] == "record_groups":
            return [tool_use("record_groups", {"groups": [
                {"title": "Pair", "parent": nums[1], "members": [nums[0], nums[1]], "root_cause": "rc",
                 "recommended_action": "ra", "notify": ["Ops"], "comms_draft": "Subject: x"}]})]
        return [tool_use("record_triage", good_triage())]

    out = tmp_path / "out.json"
    payload = precompute.run(client=FakeClient(responder), cfg=CFG, out_path=out, log=lambda *_: None)
    assert out.exists() and len(payload["tickets"]) == len(nums)
    assert list(payload["groups"]) == ["GRP-01"]
    roles = {t["number"]: t["group_role"] for t in payload["tickets"]}
    assert roles[nums[1]] == "parent" and roles[nums[0]] == "child"
    assert all(t["scored_by"].startswith("claude-test") for t in payload["tickets"])
    assert not payload["failures"]
