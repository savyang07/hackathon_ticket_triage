"""
Before Tab — "Manual Process"

Shows the raw ServiceNow inbox as on-call would see it today:
  - Unsorted, unscored tickets
  - The pain points made visible on screen
  - A mock of the Excel manual scoring sheet
  - A manual effort counter

This tab deliberately has no color-coding or AI output. The contrast with
the After tab is the whole point.
"""
import html

import pandas as pd
import streamlit as st

from ui.components import age


def render_before(df: pd.DataFrame, now, manual_min: int = 6) -> None:
    """
    Render the Before (Manual Process) tab.

    Args:
        df:          Full ticket DataFrame (no AI columns shown here).
        now:         The demo's reference datetime.
        manual_min:  Estimated minutes to triage one ticket manually.
    """
    n_tickets = len(df)
    raw = df.sort_values("opened_dt", ascending=False)

    # ── Header ───────────────────────────────────────────────────────────────
    st.markdown(
        '<div class="before-header">'
        f'<b>📥 On-call inbox — {now:%a %b %d, %I:%M %p}</b> &nbsp;·&nbsp; '
        f'{n_tickets} unassigned tickets, newest first &nbsp;·&nbsp; '
        '<span style="color:#C8322F">No priority scores. No summaries. No grouping.</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Pain-point callouts ───────────────────────────────────────────────────
    phi = df[df.ai_category == "Security / PHI"]
    if not phi.empty:
        phi_row = phi.iloc[0]
        phi_pos = list(raw.number).index(phi_row.number) + 1
        st.markdown(
            f'<div class="callout">⚠️ <b>Pain point 1 — Hidden critical ticket:</b> '
            f'A possible PHI exposure ({html.escape(phi_row.number)}) came in by email, '
            f'so ServiceNow auto-filed it as <b>{html.escape(phi_row.snow_priority)}</b>. '
            f'It is currently row <b>#{phi_pos}</b> and has been unassigned for '
            f'<b>{phi_row.age_hrs:.0f} hours</b>. Nobody knows it is critical.</div>',
            unsafe_allow_html=True,
        )

    # Count duplicates (tickets with a non-empty group_id)
    n_grouped = len(df[df.group_id != ""])
    st.markdown(
        f'<div class="callout-warn">🔁 <b>Pain point 2 — Invisible duplicates:</b> '
        f'{n_grouped} of these {n_tickets} tickets are about the same underlying problems. '
        f'Without grouping, on-call will investigate each one separately — '
        f'and callers will receive separate, possibly contradictory responses.</div>',
        unsafe_allow_html=True,
    )

    n_mistyped = int(df.ai_should_be_request.sum())
    st.markdown(
        f'<div class="callout-info">📋 <b>Pain point 3 — Wrong ticket type / wrong team:</b> '
        f'{n_mistyped} tickets filed as Incidents should be Requests (different SLA clock). '
        f'Finding and converting them is a manual step done ticket-by-ticket.</div>',
        unsafe_allow_html=True,
    )

    # ── Raw ticket table ──────────────────────────────────────────────────────
    show = raw[[
        "number", "opened_at", "short_description", "caller",
        "channel", "snow_priority", "assignment_group", "assigned_to", "state",
    ]].rename(columns={
        "number": "Number",
        "opened_at": "Opened",
        "short_description": "Short description",
        "caller": "Caller",
        "channel": "Channel",
        "snow_priority": "Priority",
        "assignment_group": "Assignment group",
        "assigned_to": "Assigned to",
        "state": "State",
    }).copy()

    show["Assigned to"] = "(empty)"
    show["Priority"] = show["Priority"].str.replace("4 - Low", "4 – Low", regex=False)

    def highlight_phi(row):
        if not phi.empty and row["Number"] == phi.iloc[0].number:
            return ["background-color:#FCE9E8"] * len(row)
        return [""] * len(row)

    st.dataframe(
        show.style.apply(highlight_phi, axis=1),
        hide_index=True,
        use_container_width=True,
        height=400,
    )

    # ── Manual effort counter ─────────────────────────────────────────────────
    est_hrs = n_tickets * manual_min / 60
    st.markdown(
        f'<div class="callout-info">⏱️ <b>Manual triage time (estimate):</b> '
        f'{n_tickets} tickets × ~{manual_min} min each = '
        f'<b>~{est_hrs:.1f} hours</b> of on-call time just to read, score, '
        f'and route — before anyone fixes anything. '
        f'<span style="color:#6B7684;font-size:.85em;">'
        f'(Estimate based on a 2024 DE team time-study average)</span></div>',
        unsafe_allow_html=True,
    )

    # ── Mock Excel scoring sheet ──────────────────────────────────────────────
    with st.expander("📊 See the manual scoring sheet (what the analyst does today)"):
        st.markdown(
            "The on-call analyst opens a shared Excel file and fills in a score "
            "for each metric by hand. The spreadsheet then calculates the total. "
            "**There is no record of who scored a ticket, no consistency check, "
            "and no way to re-run it automatically.**"
        )
        sample = raw.head(5)[["number", "short_description", "snow_priority"]].copy()
        sample.columns = ["Ticket", "Description", "Reported priority"]
        sample["Users affected (0-5)"] = ""
        sample["Clinical impact (0-5)"] = ""
        sample["Urgency (0-5)"] = ""
        sample["SLA risk (0-5)"] = ""
        sample["Total score"] = ""
        sample["Scored by"] = ""
        st.dataframe(sample, hide_index=True, use_container_width=True)
        st.caption(
            "⚑ This is a demo mockup of the manual scoring process. "
            "The real sheet has additional columns — replace config/scoring.json "
            "with the actual metrics before going live."
        )

    st.caption("Synthetic data only — no PHI, no real Keck tickets.")
