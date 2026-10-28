"""
Triage Copilot — Implementation Demo

Shows how the production system works using:
  - ServiceNow MCP  for ticket ingestion and result write-back
  - Azure OpenAI API (gpt-4o) for AI agent processing
  - Azure API Management for secure data transport

No before/after tabs. Pure after-state demo focused on the integration architecture.
    streamlit run app.py
"""
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from ui.components import CSS
from ui.architecture_tab import render_architecture
from ui.triage_tab import render_triage

ROOT = Path(__file__).parent

st.set_page_config(
    page_title="Triage Copilot · Implementation",
    page_icon="🎫",
    layout="wide",
)
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_data
def load():
    d = json.loads((ROOT / "data" / "tickets.json").read_text())
    df = pd.DataFrame(d["tickets"])
    now = datetime.strptime(d["demo_now"], "%Y-%m-%d %H:%M")
    df["opened_dt"] = pd.to_datetime(df["opened_at"])
    df["age_hrs"] = (now - df["opened_dt"]).dt.total_seconds() / 3600
    return d, df, now


DATA, DF, NOW = load()

# ---------------------------------------------------------------------------
# Sidebar — integration status + settings
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🔌 Integration Status")

    st.markdown("""
<div class="conn-card conn-green">
  <div class="conn-title">● ServiceNow MCP</div>
  <div class="conn-sub">prod-snow.keck.usc.edu · v2.8.1</div>
</div>""", unsafe_allow_html=True)

    st.markdown("""
<div class="conn-card conn-blue">
  <div class="conn-title">● Azure OpenAI API</div>
  <div class="conn-sub">keck-de.openai.azure.com · gpt-4o</div>
</div>""", unsafe_allow_html=True)

    st.markdown("""
<div class="conn-card conn-purple">
  <div class="conn-title">● Azure API Management</div>
  <div class="conn-sub">Private endpoint · Keck USC tenant</div>
</div>""", unsafe_allow_html=True)

    st.divider()
    st.markdown("### ⚙️ Settings")
    review_min = st.slider(
        "Review time per AI-triaged issue (min)", 0.5, 5.0, 1.5, 0.5,
        help="Time to skim the AI summary and accept or reroute.",
    )
    st.divider()

    st.markdown("""
<div class="sidebar-note">
<b>🔒 Security model</b><br>
Ticket data — including patient-identifiable fields — is processed exclusively within
Keck's private Azure tenant. Azure OpenAI uses a private endpoint: no data leaves the
Azure environment.
</div>""", unsafe_allow_html=True)

    st.divider()
    st.markdown(
        "<span style='font-size:.78rem; color:#6B7684;'>"
        "⚑ Demo uses 38 synthetic tickets. No real ServiceNow data or PHI.</span>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------
st.markdown(
    '<div class="hdr"><div>'
    '<h1>🎫 Triage Copilot</h1>'
    '<div class="sub">'
    'Agentic AI for ServiceNow ticket triage · '
    'ServiceNow MCP + Azure OpenAI API · '
    'Keck Medicine of USC · Data Engineering'
    '</div>'
    '</div></div>',
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Main tabs — Architecture + Live Agent
# ---------------------------------------------------------------------------
tab_arch, tab_triage = st.tabs([
    "🏗️ System Architecture",
    "🤖 AI Triage Agent",
])

with tab_arch:
    render_architecture()

with tab_triage:
    render_triage(DATA, DF, NOW, review_min=review_min)
