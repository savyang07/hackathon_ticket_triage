"""
Triage Copilot  ServiceNow ticket triage demo for the Data Engineering team.

Top-level tabs:
  Before (Manual Process)  raw inbox, pain points, manual Excel sheet
  After  (AI Triage Agent)  agents: PHI shield, summarize, group, score, route
  PHI Shield                how identifiers are removed before any model call
  Audit Trail               every AI suggestion and human decision, exportable
  Weekly Digest             leadership summary + 8-week trends

Runs fully offline on synthetic data in data/tickets.json. No API key needed.
    streamlit run app.py
"""
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from ui.components import CSS
from ui.before_tab import render_before
from ui.after_tab import render_after, build_issues
from ui.phi_tab import render_phi
from ui.audit_tab import render_audit
from ui.digest_tab import render_digest
from ui.state import init_state, REVIEWERS
from agents.pipeline import triage_queue

ROOT = Path(__file__).parent

st.set_page_config(page_title="Triage Copilot", page_icon="🎫", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Data  loaded once and cached
# ---------------------------------------------------------------------------
@st.cache_data
def load():
    d = json.loads((ROOT / "data" / "tickets.json").read_text())
    # Every AI column the UI shows comes from the agents (shield → summarize → score →
    # route → group), not straight from the JSON file.
    result = triage_queue(d["tickets"], d["queues"], d["groups"])
    d = {**d, "tickets": result["tickets"], "groups": result["groups"], "agent_steps": result["steps"]}
    df = pd.DataFrame(d["tickets"])
    now = datetime.strptime(d["demo_now"], "%Y-%m-%d %H:%M")
    df["opened_dt"] = pd.to_datetime(df["opened_at"])
    df["age_hrs"] = (now - df["opened_dt"]).dt.total_seconds() / 3600
    return d, df, now


DATA, DF, NOW = load()
init_state()


# ---------------------------------------------------------------------------
# Sidebar  shared settings (affect both tabs' estimates)
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### ⚙️ Demo settings")
    manual_min = st.slider(
        "Manual triage time per ticket (min)", 2, 15, 6,
        help="Read, summarize, label, prioritize and route one raw ticket manually.",
    )
    review_min = st.slider(
        "Review time per AI-triaged issue (min)", 0.5, 5.0, 1.5, 0.5,
        help="Skim the AI summary and accept or reroute.",
    )
    st.selectbox(
        "Reviewing as", REVIEWERS, key="reviewer",
        help="Who approvals and overrides are logged under. In production this comes from single sign-on.",
    )
    st.divider()
    st.markdown("**Data:** 38 synthetic ServiceNow tickets, all fictional, no PHI.")
    st.markdown("**Agents:** PHI shield → Summarizer → Scorer → Router → Grouping, called by "
                "`agents/pipeline.py` on every load.")
    st.markdown("**Demo mode:** agents return stored model outputs (`Triage AI v0.3`), "
                "so it runs offline with no API key.")
    st.divider()
    st.markdown(
        "⚑ *This is a hackathon prototype. The mock MCP layer and scoring weights "
        "are placeholders. See `config/scoring.json` and `tools/servicenow_mock.py`.*"
    )


# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------
st.markdown(
    '<div class="hdr"><div>'
    '<h1>🎫 Triage Copilot</h1>'
    '<div class="sub">Agentic AI for ServiceNow ticket triage: '
    'Keck Medicine of USC · Data Engineering · Hackathon Demo</div>'
    '</div></div>',
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Two top-level tabs
# ---------------------------------------------------------------------------
tab_before, tab_after, tab_phi, tab_audit, tab_digest = st.tabs([
    "⬛ Before: Manual Process",
    "🟢 After: AI Triage Agent",
    "🛡️ PHI Shield",
    "🧾 Audit Trail",
    "📈 Weekly Digest",
])

with tab_before:
    render_before(DF, NOW, manual_min=manual_min)

with tab_after:
    render_after(DATA, DF, NOW, manual_min=manual_min, review_min=review_min)

with tab_phi:
    render_phi(DF)

with tab_audit:
    render_audit(len(build_issues(DF, DATA["groups"])))

with tab_digest:
    render_digest(DATA, DF, NOW, manual_min=manual_min, review_min=review_min)
