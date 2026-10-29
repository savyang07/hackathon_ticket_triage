"""
System Architecture tab

How the production system would work: ServiceNow MCP server for reading and
writing tickets, four agents on Azure OpenAI inside Keck's Azure tenant, and a
person approving every write-back. Ported from the implementation demo
(feature/implementation-demo) and aligned with the rest of the app:
write-back happens only after approval, never automatically.
"""
import streamlit as st


def render_architecture() -> None:
    st.markdown("### How it works")
    st.markdown(
        "Triage Copilot connects to ServiceNow through an **MCP server**, runs four AI agents on "
        "**Azure OpenAI** inside Keck's Azure tenant, and writes results back to ServiceNow "
        "**only after a person approves them**. The on-call engineer reviews a pre-prioritized "
        "queue instead of reading raw tickets one by one."
    )

    # ── Data flow ───────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Data flow")
    col_sn, a1, col_az, a2, col_out = st.columns([2.2, 0.35, 3.2, 0.35, 2.2], gap="small")

    with col_sn:
        st.markdown("""
<div class="arch-col cardinal">
  <div style="font-size:1.5rem;">🏥</div>
  <div class="t">ServiceNow (system of record)</div>
  <div class="b">
    <b>MCP tools used:</b><br>
    <code>list_incidents()</code><br>
    <code>get_incident(number)</code><br>
    <code>update_incident(number, fields)</code>
    <br><br>
    Pulls open tickets for the target assignment groups through a least-privilege
    integration account. Updates are written back only after a reviewer approves.
  </div>
</div>""", unsafe_allow_html=True)

    a1.markdown('<div class="arch-arrow">⇄</div>', unsafe_allow_html=True)

    with col_az:
        st.markdown("""
<div class="arch-col gold">
  <div style="font-size:1.5rem;">☁️</div>
  <div class="t">Azure OpenAI (Keck's Microsoft tenant)</div>
  <div class="b">
    <b>Deployment:</b> gpt-4o behind a private endpoint, reached through Azure API Management<br>
    <b>Covered by:</b> Keck's HIPAA business associate agreement, US region<br><br>
    <b>Four agents run in sequence:</b>
  </div>
  <div class="agent-grid">
    <div><b>① Summarizer</b><br>Plain-English summary of each ticket</div>
    <div><b>② ERWG Scorer</b><br>0–4 ratings on 5 dimensions; the formula computes the score</div>
    <div><b>③ Router</b><br>Queue and owner, with confidence and a reason</div>
    <div><b>④ Grouping</b><br>Finds duplicates and their root cause</div>
  </div>
</div>""", unsafe_allow_html=True)

    a2.markdown('<div class="arch-arrow">→</div>', unsafe_allow_html=True)

    with col_out:
        st.markdown("""
<div class="arch-col slate">
  <div style="font-size:1.5rem;">📋</div>
  <div class="t">Triage queue</div>
  <div class="b">
    The on-call engineer sees a pre-prioritized, de-duplicated queue:<br><br>
    ✅ AI summaries (no reading raw tickets)<br>
    ✅ ERWG priority scores with rationale<br>
    ✅ Duplicate groups collapsed<br>
    ✅ Suggested queue and owner<br>
    ✅ Approve, override or reroute<br><br>
    <b>Approved</b> results are written back to ServiceNow, and every decision is logged.
  </div>
</div>""", unsafe_allow_html=True)

    # ── Security model ──────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Security model")
    s1, s2, s3 = st.columns(3, gap="medium")
    s1.markdown("""
<div class="step-card">
  <div style="font-size:1.3rem;">🔒</div>
  <div class="h">Private Azure endpoint</div>
  <div class="b">Azure OpenAI runs in Keck's own Azure tenant behind a private endpoint, so calls stay on
  Keck's network and never cross the public internet. Azure API Management handles authentication,
  rate limits and usage logs.</div>
</div>""", unsafe_allow_html=True)
    s2.markdown("""
<div class="step-card">
  <div style="font-size:1.3rem;">🏥</div>
  <div class="h">HIPAA-covered model, no redaction</div>
  <div class="b">The model is covered by Keck's HIPAA business associate agreement, in a US region, with
  Microsoft's prompt storage for abuse review turned off. Ticket text isn't redacted: staff need the MRN and
  patient details to work tickets. Only the fields triage needs are sent (minimum necessary).</div>
</div>""", unsafe_allow_html=True)
    s3.markdown("""
<div class="step-card">
  <div style="font-size:1.3rem;">🙋</div>
  <div class="h">The AI can't change tickets on its own</div>
  <div class="b">The agents only get read tools. <code>update_incident</code> is called by our code after a
  reviewer approves, never by the model. The model must answer in a fixed format that the code checks, so
  instructions hidden in ticket text can't trigger a change.</div>
</div>""", unsafe_allow_html=True)

    # ── Implementation steps ────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Implementation steps")
    steps = [
        ("1", "ServiceNow MCP server",
         "Use ServiceNow's MCP support or a small server on the Table API, hosted in Azure, with an "
         "integration account scoped to the target assignment groups."),
        ("2", "Azure OpenAI deployment",
         "Deploy gpt-4o in Keck's Azure subscription (US region) behind a private endpoint and API "
         "Management; confirm BAA coverage and turn off abuse-monitoring storage."),
        ("3", "Agent orchestration",
         "Run the four agents in Python on Azure Functions or AKS. Each agent calls Azure OpenAI and "
         "returns a fixed-format result that the code validates."),
        ("4", "Approval, then write-back",
         "Reviewers approve, override or reroute in the dashboard. Only then does the orchestrator call "
         "update_incident; every decision is logged."),
        ("5", "Triage dashboard",
         "Host this Streamlit dashboard on Azure App Service as an internal tool for on-call, with Keck "
         "single sign-on."),
    ]
    cols = st.columns(5, gap="small")
    for col, (num, title, desc) in zip(cols, steps):
        col.markdown(f"""
<div class="step-card" style="text-align:center;">
  <div class="step-num">{num}</div>
  <div class="h">{title}</div>
  <div class="b">{desc}</div>
</div>""", unsafe_allow_html=True)

    # ── Tech stack + API call shape ─────────────────────────────────────────
    st.markdown("---")
    left, right = st.columns([1, 2])
    with left:
        st.markdown("#### Tech stack")
        st.markdown("""
| Component | Technology |
|-----------|------------|
| Ticket source | ServiceNow MCP server |
| AI model | Azure OpenAI gpt-4o |
| Orchestration | Python · Azure Functions or AKS |
| Gateway | Azure API Management |
| Write-back | ServiceNow MCP, after approval |
| Dashboard | Streamlit · Azure App Service |
| Scores, history and audit | Redshift |
""")
    with right:
        st.markdown("#### API call shape (ServiceNow MCP)")
        st.code("""# 1. Fetch open, unassigned tickets (read tool)
tickets = mcp.call("servicenow", "list_incidents", {
    "state": "open",
    "assignment_group": "Data Engineering",
    "fields": ["number", "short_description", "description",
               "priority", "opened_at"],
})

# 2. Agents run on Azure OpenAI; results go to the review dashboard.

# 3. Only after a reviewer approves: write the agreed fields back
mcp.call("servicenow", "update_incident", {
    "number": "INC0104511",
    "assignment_group": "DE - Pipelines (Talend/ETL)",
    "assigned_to": "Dev Patel",
    "work_notes": "Triage Copilot (approved by J. Lee): ERWG 87, Critical. "
                  "Nightly Cerner ADT load failed; bed census and ED reports stale.",
    # optional custom fields, if the ServiceNow team adds them:
    "u_ai_priority_score": 87,
    "u_ai_duplicate_group": "GRP-01",
})""", language="python")

    st.caption("Demo: ServiceNow and Azure OpenAI calls are simulated; the dashboard runs offline on "
               "38 synthetic tickets.")
