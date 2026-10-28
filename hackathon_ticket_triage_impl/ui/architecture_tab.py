"""
System Architecture Tab

Shows how the production system works:
  1. ServiceNow MCP fetches open tickets
  2. Azure OpenAI API runs four agents in sequence
  3. Results are written back to ServiceNow via MCP
  4. Triage queue is shown in the AI Triage Agent tab

Security model: all data stays inside Keck's Azure private tenant.
No data is routed to external endpoints.
"""
import streamlit as st


def render_architecture() -> None:
    st.markdown("### How It Works")
    st.markdown(
        "Triage Copilot connects to ServiceNow via MCP, runs four AI agents on Azure OpenAI, "
        "and writes the results back — all within Keck's private Azure environment. "
        "The on-call engineer reviews a pre-prioritized queue instead of reading raw tickets one by one."
    )

    # ── Main flow diagram ───────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Data Flow")

    col_sn, col_arrow1, col_az, col_arrow2, col_out = st.columns(
        [2.2, 0.4, 3.2, 0.4, 2.2], gap="small"
    )

    with col_sn:
        st.markdown("""
<div style="border:2px solid #A5D6A7; border-radius:14px; background:#F1F8E9; padding:1rem 1.1rem; height:100%;">
  <div style="font-size:1.6rem; margin-bottom:.3rem;">🏥</div>
  <div style="font-weight:700; font-size:1rem; color:#1B5E20; margin-bottom:.5rem;">ServiceNow</div>
  <div style="font-size:.82rem; color:#33691E; line-height:1.5;">
    <b>MCP Tools used:</b><br>
    <code style="background:#E8F5E9; padding:.1rem .3rem; border-radius:4px;">list_incidents()</code><br>
    <code style="background:#E8F5E9; padding:.1rem .3rem; border-radius:4px;">get_incident(number)</code><br>
    <code style="background:#E8F5E9; padding:.1rem .3rem; border-radius:4px;">update_incident(number, fields)</code>
    <br><br>
    Pulls open tickets from the Data Engineering queue. Writes AI summaries, priority scores, and suggested owners back when done.
  </div>
</div>
""", unsafe_allow_html=True)

    with col_arrow1:
        st.markdown(
            '<div style="display:flex;align-items:center;justify-content:center;height:100%;font-size:2rem;color:#0F6E6E;">⇄</div>',
            unsafe_allow_html=True,
        )

    with col_az:
        st.markdown("""
<div style="border:2px solid #90CAF9; border-radius:14px; background:#E3F2FD; padding:1rem 1.1rem; height:100%;">
  <div style="font-size:1.6rem; margin-bottom:.3rem;">☁️</div>
  <div style="font-weight:700; font-size:1rem; color:#0D47A1; margin-bottom:.5rem;">Azure OpenAI API</div>
  <div style="font-size:.82rem; color:#1565C0; line-height:1.5;">
    <b>Deployment:</b> gpt-4o on Keck private endpoint<br>
    <b>Endpoint:</b> <code style="background:#E3F2FD; padding:.1rem .3rem; border-radius:4px;">keck-de.openai.azure.com</code>
    <br><br>
    <b>Four agents run in sequence:</b>
  </div>
  <div style="margin-top:.5rem; display:grid; grid-template-columns:1fr 1fr; gap:.4rem;">
    <div style="background:#fff; border:1px solid #90CAF9; border-radius:8px; padding:.4rem .6rem; font-size:.78rem; color:#0D47A1;">
      <b>① Summarizer</b><br>Plain-English summaries of each ticket
    </div>
    <div style="background:#fff; border:1px solid #90CAF9; border-radius:8px; padding:.4rem .6rem; font-size:.78rem; color:#0D47A1;">
      <b>② Grouping</b><br>Detects duplicates &amp; clusters related issues
    </div>
    <div style="background:#fff; border:1px solid #90CAF9; border-radius:8px; padding:.4rem .6rem; font-size:.78rem; color:#0D47A1;">
      <b>③ ERWG Scorer</b><br>Assigns 0–4 scores on 5 dimensions
    </div>
    <div style="background:#fff; border:1px solid #90CAF9; border-radius:8px; padding:.4rem .6rem; font-size:.78rem; color:#0D47A1;">
      <b>④ Router</b><br>Matches each issue to the right queue &amp; owner
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

    with col_arrow2:
        st.markdown(
            '<div style="display:flex;align-items:center;justify-content:center;height:100%;font-size:2rem;color:#0F6E6E;">→</div>',
            unsafe_allow_html=True,
        )

    with col_out:
        st.markdown("""
<div style="border:2px solid #CE93D8; border-radius:14px; background:#F3E5F5; padding:1rem 1.1rem; height:100%;">
  <div style="font-size:1.6rem; margin-bottom:.3rem;">📋</div>
  <div style="font-weight:700; font-size:1rem; color:#4A148C; margin-bottom:.5rem;">Triage Queue</div>
  <div style="font-size:.82rem; color:#6A1B9A; line-height:1.5;">
    On-call engineer sees a pre-prioritized, deduplicated queue:<br><br>
    ✅ AI summaries (no reading raw tickets)<br>
    ✅ ERWG priority scores with rationale<br>
    ✅ Duplicate groups collapsed<br>
    ✅ Suggested queue &amp; owner<br>
    ✅ One-click accept or reroute<br><br>
    Results are written back to ServiceNow automatically.
  </div>
</div>
""", unsafe_allow_html=True)

    # ── Security model ───────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Security Model")

    sec1, sec2, sec3 = st.columns(3, gap="medium")

    with sec1:
        st.markdown("""
<div class="step-card">
  <div style="font-size:1.4rem; margin-bottom:.4rem;">🔒</div>
  <div style="font-weight:700; color:#1C2430; margin-bottom:.4rem;">Private Azure Endpoint</div>
  <div style="font-size:.85rem; color:#5A6573; line-height:1.55;">
    Azure OpenAI is deployed on Keck's private Azure tenant with a private endpoint.
    All API calls stay within the Azure VNet — no traffic routes over the public internet.
  </div>
</div>
""", unsafe_allow_html=True)

    with sec2:
        st.markdown("""
<div class="step-card">
  <div style="font-size:1.4rem; margin-bottom:.4rem;">🏢</div>
  <div style="font-weight:700; color:#1C2430; margin-bottom:.4rem;">Data Stays in Azure</div>
  <div style="font-size:.85rem; color:#5A6573; line-height:1.55;">
    Ticket text — including patient-identifiable fields needed by developers to locate issues —
    is processed entirely within Azure. No data is stripped or redacted before reaching the model.
    The model is the boundary, not the data.
  </div>
</div>
""", unsafe_allow_html=True)

    with sec3:
        st.markdown("""
<div class="step-card">
  <div style="font-size:1.4rem; margin-bottom:.4rem;">🚫</div>
  <div style="font-weight:700; color:#1C2430; margin-bottom:.4rem;">No External Leakage</div>
  <div style="font-size:.85rem; color:#5A6573; line-height:1.55;">
    Azure API Management enforces policy rules that prevent the model from echoing raw patient data
    in its output. AI summaries, scores, and routing decisions are what surface to the engineer —
    not the raw ticket text.
  </div>
</div>
""", unsafe_allow_html=True)

    # ── Implementation steps ──────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Implementation Steps")

    steps_cols = st.columns(5, gap="small")
    steps = [
        ("1", "ServiceNow MCP Server",
         "Deploy the ServiceNow MCP server on-prem or in Azure. Configure it with a service account scoped to the Data Engineering queue."),
        ("2", "Azure OpenAI Deployment",
         "Deploy gpt-4o on Keck's private Azure subscription. Configure a private endpoint so the model is reachable only from within the Azure VNet."),
        ("3", "Agent Orchestration",
         "Deploy the four-agent orchestration layer (Python + Azure Functions or AKS). Each agent calls Azure OpenAI with the relevant tool definition."),
        ("4", "ServiceNow Write-Back",
         "After scoring and routing, the MCP client calls update_incident() to write AI fields back. Engineers see results directly in ServiceNow."),
        ("5", "Triage UI (Optional)",
         "The Streamlit dashboard shown in the AI Triage Agent tab can be hosted on Azure App Service as an internal tool for the on-call team."),
    ]

    for col, (num, title, desc) in zip(steps_cols, steps):
        with col:
            st.markdown(f"""
<div class="step-card" style="text-align:center;">
  <div class="step-num" style="margin:0 auto .5rem auto;">{num}</div>
  <div style="font-weight:700; font-size:.88rem; color:#1C2430; margin-bottom:.4rem;">{title}</div>
  <div style="font-size:.78rem; color:#5A6573; line-height:1.5;">{desc}</div>
</div>
""", unsafe_allow_html=True)

    # ── Tech stack ────────────────────────────────────────────────────────
    st.markdown("---")
    c_stack = st.columns([1, 2])
    with c_stack[0]:
        st.markdown("#### Tech Stack")
        st.markdown("""
| Component | Technology |
|-----------|------------|
| Ticket source | ServiceNow MCP |
| AI model | Azure OpenAI gpt-4o |
| Orchestration | Python · Azure Functions |
| Transport | Azure API Management |
| Write-back | ServiceNow MCP |
| Dashboard | Streamlit · Azure App Service |
| Data store | Redshift (scores + history) |
""")
    with c_stack[1]:
        st.markdown("#### API Call Shape (ServiceNow MCP)")
        st.code("""# Fetch open tickets
tickets = mcp.call("servicenow", "list_incidents", {
    "state": "open",
    "assignment_group": "Data Engineering",
    "fields": ["number", "short_description", "description",
               "caller_id", "priority", "opened_at"]
})

# Write AI result back
mcp.call("servicenow", "update_incident", {
    "number": "INC0034521",
    "u_ai_summary": "Nightly Talend ETL pipeline failed...",
    "u_ai_priority_score": 82,
    "u_ai_suggested_queue": "DE – Pipelines (Talend/ETL)",
    "u_ai_suggested_owner": "Dev Patel",
    "u_ai_duplicate_group": "GRP-01"
})""", language="python")
