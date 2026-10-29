"""
Features ported from feature/implementation-demo: System Architecture tab, API trace on
Run Triage, simulated integration cards, ServiceNow MCP badge. Write-back must always be
shown as happening after approval, never automatically.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import agents.pipeline as pipeline  # noqa: E402
from ui.after_tab import _trace_lines  # noqa: E402

DATA = json.loads((ROOT / "data" / "tickets.json").read_text())


def _app():
    from streamlit.testing.v1 import AppTest
    import streamlit as st
    st.cache_data.clear()
    return AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()


def test_trace_shows_real_agent_results_and_holds_write_back():
    steps = pipeline.triage_queue(DATA["tickets"], DATA["queues"], DATA["groups"])["steps"]
    text = " ".join(l for _, lines in _trace_lines(len(DATA["tickets"]), steps) for l in lines)
    assert "list_incidents" in text and "chat/completions" in text
    for _, name, desc in steps:
        assert desc.split(":")[0][:20] in text, name          # each agent's real result appears
    assert "waits for a reviewer" in text and "nothing is written" in text


def test_no_screen_claims_automatic_write_back():
    for f in ["app.py", "ui/after_tab.py", "ui/architecture_tab.py"]:
        assert "written back to ServiceNow automatically" not in (ROOT / f).read_text(), f


def test_architecture_tab_and_sidebar_cards_render():
    at = _app()
    assert not at.exception
    assert "🏗️ System Architecture" in [t.label for t in at.tabs]
    side = " ".join(m.value for m in at.sidebar.markdown)
    for name in ("ServiceNow MCP server", "Azure OpenAI", "Azure API Management"):
        assert name in side
    assert side.count("SIMULATED") == 3                         # never shown as a live connection
    body = " ".join(m.value for m in at.markdown)
    assert "only after a person approves them" in body and "Security model" in body


def test_cards_carry_the_servicenow_mcp_badge():
    at = _app()
    next(b for b in at.button if "Run Triage" in b.label).click().run()
    assert not at.exception
    assert any('class="src-badge">ServiceNow MCP<' in m.value for m in at.markdown)
