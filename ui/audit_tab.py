"""
Audit Trail tab

Every AI suggestion and every human decision, in one exportable log:
  - who decided (AI or a named reviewer), when, what changed, and why
  - how often reviewers agreed with the AI (the routing/scoring accuracy KPI)
"""
import pandas as pd
import streamlit as st

from agents.audit import COLUMNS, review_stats
from ui.state import REVIEWERS


def render_audit(n_issues: int) -> None:
    entries = st.session_state.get("audit", [])
    st.markdown(
        "**The AI suggests; a person decides; everything is recorded.** Each score and route the AI "
        "proposes is logged, along with every approval, override, reroute and request for more "
        "information, with who made it, when, and why. Nothing is written back to ServiceNow until a "
        "person approves it."
    )

    if not entries:
        st.info("No activity yet. Go to **After: AI Triage Agent**, click **Run Triage**, then approve or "
                "override a few cards. Every action shows up here.", icon="🧾")
        return

    stats = review_stats(entries, n_issues)
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Reviewed by a person", f"{stats['reviewed']} / {n_issues}")
    k2.metric("Approved as suggested", stats["approved"])
    k3.metric("Overridden", stats["overridden"])
    k4.metric("Rerouted", stats["rerouted"])
    k5.metric("AI–reviewer agreement",
              f"{stats['agreement']:.0%}" if stats["agreement"] is not None else "–",
              help="Approved as suggested ÷ reviewed. In a pilot this becomes the accuracy KPI that decides "
                   "when (and for which ticket types) the AI can be trusted with less review.")

    log = pd.DataFrame(entries)[COLUMNS].iloc[::-1]  # newest first
    f1, f2, f3 = st.columns([1, 1, 2])
    who = f1.selectbox("Actor", ["Everyone", "AI only", "People only"], key="audit_who")
    # A plain dropdown (not a multiselect) so new action types are never hidden by a stale selection.
    act = f2.selectbox("Action", ["All actions"] + sorted(log.action.unique()), key="audit_act")
    q = f3.text_input("Search ticket or text", key="audit_q", placeholder="e.g. INC0104493 or GRP-01")

    view = log if act == "All actions" else log[log.action == act]
    if who == "AI only":
        view = view[view.actor_type == "AI"]
    elif who == "People only":
        view = view[view.actor_type == "Human"]
    if q.strip():
        mask = view.apply(lambda r: q.strip().lower() in " ".join(map(str, r.values)).lower(), axis=1)
        view = view[mask]

    st.dataframe(
        view.rename(columns={"time": "Time", "actor": "Actor", "actor_type": "Type", "action": "Action",
                             "target": "Issue", "ticket": "Ticket", "before": "Before", "after": "After",
                             "reason": "Reason / rationale"}),
        hide_index=True, use_container_width=True, height=420,
    )
    st.download_button("⬇️ Download audit log (CSV)", view.to_csv(index=False), "triage_audit_log.csv",
                       "text/csv")

    with st.expander("How this works in production"):
        st.markdown(
            "- **Append-only storage:** entries go to an audit table that cannot be edited (for example a "
            "Redshift table with insert-only permissions), and each approval is mirrored to the ticket as a "
            "ServiceNow work note.\n"
            "- **Named reviewers:** the reviewer comes from single sign-on, not a dropdown. "
            f"The demo lets you switch between {', '.join(r.split(' (')[0] for r in REVIEWERS)} in the sidebar.\n"
            "- **Required reasons:** an override can't be saved without one, which gives the team labelled "
            "examples to recalibrate the scoring weights.\n"
            "- **Agreement tracking:** agreement rate by ticket type shows where the AI is reliable and "
            "where people should keep reviewing everything."
        )
    st.caption("Demo: the log lives in this browser session and resets with ↺ Reset. Synthetic data only.")
