"""
Tests for agents/pipeline.py: the app must get its AI columns from the agents,
and agents that would call a model receive the minimized payload: full text, triage fields only.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import agents.pipeline as pipeline  # noqa: E402
from agents import router, summarizer  # noqa: E402

DATA = json.loads((ROOT / "data" / "tickets.json").read_text())
AI_FIELDS = ["ai_summary", "ai_priority_score", "ai_priority", "ai_needs_more_info", "ai_info_requests",
             "ai_route_queue", "ai_route_owner", "ai_confidence", "ai_rationale", "group_id"]


def _run():
    return pipeline.triage_queue(DATA["tickets"], DATA["queues"], DATA["groups"])


def test_demo_mode_reproduces_the_stored_results():
    r = _run()
    for out, src in zip(r["tickets"], DATA["tickets"]):
        for f in AI_FIELDS:
            assert out[f] == src[f], (src["number"], f)
    assert set(r["groups"]) == set(DATA["groups"])


def test_every_agent_runs_once_per_ticket_in_order(monkeypatch):
    calls = []

    def spy(name, fn):
        def wrapper(*a, **k):
            calls.append(name)
            return fn(*a, **k)
        return wrapper

    for name in ("minimize_ticket", "summarize", "score_ticket", "route_ticket", "find_groups"):
        monkeypatch.setattr(pipeline, name, spy(name, getattr(pipeline, name)))
    _run()
    n = len(DATA["tickets"])
    assert calls[:4] == ["minimize_ticket", "summarize", "score_ticket", "route_ticket"]
    assert calls.count("summarize") == n and calls.count("route_ticket") == n
    assert calls.count("minimize_ticket") == n and calls.count("score_ticket") == n
    assert calls[-1] == "find_groups" and calls.count("find_groups") == 1


def test_ui_columns_are_whatever_the_agents_return(monkeypatch):
    monkeypatch.setattr(pipeline, "summarize", lambda t, p=None: {"summary": "FROM AGENT"})
    monkeypatch.setattr(pipeline, "route_ticket", lambda t, q, p=None: {
        "queue": "DE – Pipelines (Talend/ETL)", "owner": "Agent Owner", "confidence": 0.5, "rationale": "r"})
    r = _run()
    assert {t["ai_summary"] for t in r["tickets"]} == {"FROM AGENT"}
    assert {t["ai_route_owner"] for t in r["tickets"]} == {"Agent Owner"}


def test_model_gets_full_text_but_only_triage_fields(monkeypatch):
    """No de-identification (the model is under Keck's BAA), but minimum necessary still applies."""
    from agents.minimizer import TRIAGE_FIELDS
    seen = []
    monkeypatch.setattr(pipeline, "summarize", lambda t, p=None: seen.append(p) or {"summary": "s"})
    text = "Census lists patient Maria Delgado, MRN 004518823."     # fictional
    t = {**DATA["tickets"][0], "description": text, "caller_email": "someone@example.org",
         "work_notes": "internal note"}
    pipeline.triage_queue([t], DATA["queues"], {})
    payload = seen[0]
    assert payload["description"] == text                      # MRN and name reach the model as written
    assert set(payload) <= set(TRIAGE_FIELDS)
    assert "caller_email" not in payload and "work_notes" not in payload


def test_reviewers_keep_the_full_ticket():
    """The ticket rows the dashboard shows keep every original field, patient details included."""
    t = {**DATA["tickets"][0], "description": "Census lists patient Maria Delgado, MRN 004518823."}
    out = pipeline.triage_queue([t], DATA["queues"], {})["tickets"][0]
    for k, v in t.items():
        if not k.startswith("ai_") and k not in ("group_id", "group_role"):
            assert out[k] == v, k


def test_live_mode_refuses_without_a_minimized_payload(monkeypatch):
    monkeypatch.setattr(summarizer, "DEMO_MODE", False)
    monkeypatch.setattr(router, "DEMO_MODE", False)
    with pytest.raises(ValueError):
        summarizer.summarize(DATA["tickets"][0])
    with pytest.raises(ValueError):
        router.route_ticket(DATA["tickets"][0], DATA["queues"])


def test_step_lines_report_real_results():
    steps = {name: text for _, name, text in _run()["steps"]}
    assert list(steps) == ["Data minimization", "Summarizer", "Priority scorer", "Routing agent",
                           "Grouping agent"]
    n_crit = sum(t["ai_priority"] == "Critical" for t in DATA["tickets"])
    assert f"{n_crit} Critical" in steps["Priority scorer"]
    assert f"{len(DATA['groups'])} duplicate groups" in steps["Grouping agent"]


def test_app_dataframe_comes_from_the_pipeline(monkeypatch):
    """Run the real app headless with a patched summarizer and check the UI data changed."""
    from streamlit.testing.v1 import AppTest
    import streamlit as st

    monkeypatch.setattr(pipeline, "summarize", lambda t, p=None: {"summary": "FROM AGENT"})
    st.cache_data.clear()
    try:
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
        assert not at.exception
        assert any("Minimizer → Summarizer" in m.value for m in at.sidebar.markdown)
        assert not any("PHI Shield" in t.label for t in at.tabs)
        next(b for b in at.button if "Run Triage" in b.label).click().run()
        assert not at.exception
        assert any("FROM AGENT" in m.value for m in at.markdown)       # triage queue cards
    finally:
        st.cache_data.clear()
