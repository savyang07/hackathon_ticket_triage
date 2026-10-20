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


def _clean_env(monkeypatch):
    for k in llm.CONFIG_KEYS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(llm, "load_secrets_file", lambda: {})


def test_config_detection(monkeypatch):
    _clean_env(monkeypatch)
    assert llm.get_config() is None                      # nothing configured → offline rules
    monkeypatch.setenv("AWS_REGION", "us-west-2")         # Bedrock is the default provider
    cfg = llm.get_config("live")
    assert cfg.provider == "bedrock" and cfg.model == "anthropic.claude-haiku-5-5"
    monkeypatch.delenv("AWS_REGION")
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    assert llm.get_config("precompute").model == "anthropic.claude-sonnet-5-5"


def test_public_api_refused_without_explicit_opt_in(monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")    # a key alone must not turn it on
    with pytest.raises(llm.LLMError, match="off by default"):
        llm.get_config()
    monkeypatch.setenv("ALLOW_PUBLIC_API", "yes")          # anything but the exact value is refused
    with pytest.raises(llm.LLMError):
        llm.get_config()
    monkeypatch.setenv("ALLOW_PUBLIC_API", "synthetic-data-only")
    cfg = llm.get_config("precompute")
    assert cfg.provider == "anthropic" and cfg.model == "claude-sonnet-5-5"
    assert "synthetic data only" in cfg.label


# ── PHI safeguards ─────────────────────────────────────────────────────────────────────
# All identifiers below are fictional (555 number, textbook values).
PHI_TICKET = {**TICKET, "number": "NEW", "caller": "Angela Brooks", "caller_dept": "Nursing – 7 West",
              "short_description": "Census still lists discharged patient",
              "description": "Bed census still lists patient Maria Delgado (MRN 004518823, DOB 03/14/1958) "
                             "after discharge. FIN 70112345. Call me at 323-555-0148. Thanks, Angela"}
RAW_VALUES = ["Maria Delgado", "004518823", "03/14/1958", "70112345", "323-555-0148", "Angela"]


def _sent(client):
    return "\n".join(r["messages"][0]["content"] for r in client.requests)


def test_outgoing_prompt_is_shielded_and_minimized():
    c = FakeClient(lambda kw: [tool_use("record_triage", good_triage())])
    _, meta = llm.triage_ticket(c, CFG, PHI_TICKET, QUEUES, DATA["demo_now"])
    sent = _sent(c)
    for raw in RAW_VALUES:
        assert raw not in sent, raw
    for ph in ("[PATIENT_1]", "[MRN_1]", "[DOB_1]", "[FIN_1]", "[PHONE_1]"):
        assert ph in sent, ph
    assert "Caller department: Nursing – 7 West" in sent   # routing still gets the department
    assert "Opened:" not in sent and "Age:" in sent         # a date becomes an age
    assert meta["phi_shield"]["MRN"] == 1 and meta["sent_text"] == sent


def test_context_from_earlier_output_is_shielded_too():
    c = FakeClient(lambda kw: [tool_use("record_triage", good_triage())])
    llm.triage_ticket(c, CFG, TICKET, QUEUES, DATA["demo_now"],
                      group_context="Root cause mentions MRN 004518823",
                      open_issues={"GRP-01": "Census lists patient Maria Delgado"})
    sent = _sent(c)
    assert "004518823" not in sent and "Maria Delgado" not in sent


def test_grouping_call_is_shielded():
    nums = [t["number"] for t in DATA["tickets"]]
    c = FakeClient(lambda kw: [tool_use("record_groups", {"groups": []})])
    _, meta = llm.group_tickets(c, CFG, DATA["tickets"] + [PHI_TICKET], DATA["demo_now"])
    sent = _sent(c)
    for raw in RAW_VALUES:
        assert raw not in sent, raw
    for t in DATA["tickets"]:
        if t["caller_dept"] != "Automated":
            assert f"Caller: {t['caller']}" not in sent and t["caller"] not in sent, t["caller"]
    assert meta["phi_shield"].get("PATIENT") == 1 and nums


def test_fail_closed_blocks_before_anything_is_sent():
    with pytest.raises(llm.PHIBlocked) as e:
        llm.assert_no_phi("Census lists MRN 004518823")
    assert "004518823" not in str(e.value)                  # error names the type, not the value
    c = FakeClient(lambda kw: [tool_use("record_triage", good_triage())])
    with pytest.raises(llm.PHIBlocked):
        llm.call_tool(c, CFG, "system", "raw text with MRN 004518823", "record_triage", {})
    assert c.requests == []                                 # the client was never called


def test_synthetic_queue_passes_the_fail_closed_check():
    for t in DATA["tickets"]:
        llm.assert_no_phi(llm.ticket_block(t, DATA["demo_now"]))


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
    assert "phi_shield" in payload and "never stored" in payload["phi_shield"]["note"]


def test_precompute_sends_no_caller_names(tmp_path):
    from scripts import precompute
    c = FakeClient(lambda kw: [tool_use("record_groups", {"groups": []})]
                   if kw["tools"][0]["name"] == "record_groups" else [tool_use("record_triage", good_triage())])
    precompute.run(client=c, cfg=CFG, out_path=tmp_path / "o.json", log=lambda *_: None)
    sent = _sent(c)
    for t in DATA["tickets"]:
        if t["caller_dept"] != "Automated":
            assert t["caller"] not in sent, t["caller"]


def test_blocked_ticket_is_not_retried(tmp_path, monkeypatch):
    from scripts import precompute
    calls = []

    def blocked(*a, **k):
        calls.append(1)
        raise llm.PHIBlocked("Blocked before sending: 1 MRN identifier(s).")

    monkeypatch.setattr(llm, "triage_ticket", blocked)
    c = FakeClient(lambda kw: [tool_use("record_groups", {"groups": []})])
    payload = precompute.run(client=c, cfg=CFG, limit=1, out_path=tmp_path / "o.json", log=lambda *_: None)
    assert len(calls) == 1 and payload["failures"] == [DATA["tickets"][0]["number"]]
    assert payload["tickets"][0]["scored_by"].startswith("Offline rules")
