"""
Triage Copilot  ServiceNow ticket triage demo for the Data Engineering team.

Top-level tabs:
  Before (Manual Process)  raw inbox, pain points, manual Excel sheet
  After  (AI Triage Agent)  agents: minimize, summarize, score, route, group (with API trace)
  System Architecture       ServiceNow MCP + Azure OpenAI design, security model, steps
  Audit Trail               every AI suggestion and human decision, exportable
  Weekly Digest             leadership summary + 8-week trends

Runs fully offline on synthetic data in data/tickets.json. No API key needed.
    streamlit run app.py
"""
import base64
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from ui.components import CSS
from ui.before_tab import render_before
from ui.after_tab import render_after, build_issues
from ui.architecture_tab import render_architecture
from ui.audit_tab import render_audit
from ui.digest_tab import render_digest
from ui.state import init_state, REVIEWERS
from agents.pipeline import triage_queue

ROOT = Path(__file__).parent

st.set_page_config(page_title="Triage Copilot · Keck Medicine of USC", page_icon="🎫", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)

# Keck Medicine of USC branding: wordmark in the sidebar and the page header (full logo kept in assets/).
WORDMARK = ROOT / "assets" / "keck_medicine_wordmark.png"
st.logo(str(WORDMARK), size="large", icon_image=str(WORDMARK))
_WORDMARK_B64 = base64.b64encode(WORDMARK.read_bytes()).decode()


# ---------------------------------------------------------------------------
# Data  loaded once and cached
# ---------------------------------------------------------------------------
@st.cache_data
def load():
    d = json.loads((ROOT / "data" / "tickets.json").read_text())
    # Every AI column the UI shows comes from the agents (minimize → summarize → score →
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
    st.markdown("### 🔌 Integrations")
    st.markdown(
        '<div class="conn-card"><div class="conn-title">ServiceNow MCP server<span class="sim-tag">SIMULATED</span></div>'
        '<div class="conn-sub">list / get / update incidents · least-privilege account</div></div>'
        '<div class="conn-card gold"><div class="conn-title">Azure OpenAI · gpt-4o<span class="sim-tag">SIMULATED</span></div>'
        '<div class="conn-sub">Keck Microsoft tenant · US region · private endpoint</div></div>'
        '<div class="conn-card slate"><div class="conn-title">Azure API Management<span class="sim-tag">SIMULATED</span></div>'
        '<div class="conn-sub">Gateway: auth, rate limits, usage logs</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="sidebar-note"><b>🔒 Security model</b><br>Tickets, patient details included, are processed '
        "by Azure OpenAI in Keck's tenant under Keck's HIPAA BAA. Only the fields triage needs are sent, and "
        "nothing is written back to ServiceNow until a person approves.</div>",
        unsafe_allow_html=True,
    )
    st.divider()
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
    st.markdown("**Agents:** Minimizer → Summarizer → Scorer → Router → Grouping, called by "
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
    '<div class="brand">'
    f'<img src="data:image/png;base64,{_WORDMARK_B64}" alt="Keck Medicine of USC">'
    '<div class="divider"></div>'
    '<div><h1>Triage Copilot</h1>'
    '<div class="sub">AI-assisted ServiceNow ticket triage · ServiceNow MCP + Azure OpenAI · '
    '<b>Data Engineering</b> · Hackathon demo</div>'
    '</div></div>',
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Two top-level tabs
# ---------------------------------------------------------------------------
tab_before, tab_after, tab_arch, tab_audit, tab_digest = st.tabs([
    "⬛ Before: Manual Process",
    "🟢 After: AI Triage Agent",
    "🏗️ System Architecture",
    "🧾 Audit Trail",
    "📈 Weekly Digest",
])

with tab_before:
    render_before(DF, NOW, manual_min=manual_min)

with tab_after:
    render_after(DATA, DF, NOW, manual_min=manual_min, review_min=review_min)

with tab_arch:
    render_architecture()

with tab_audit:
    render_audit(len(build_issues(DF, DATA["groups"])))

with tab_digest:
    render_digest(DATA, DF, NOW, manual_min=manual_min, review_min=review_min)
