"""
Weekly Digest tab

A leadership-ready summary of the queue: headline numbers, what needs
attention, recurring problems, patient-care items, and 8-week trends.
Built by agents/digest.py; trend data comes from data/weekly_history.json
(synthetic, labelled as such on screen).
"""
import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from agents.digest import build_digest
from ui.components import priority_pill

_HISTORY_PATH = Path(__file__).parent.parent / "data" / "weekly_history.json"

# Validated categorical pair (dataviz palette slots 1 and 2): passes CVD and contrast checks.
SERIES_1, SERIES_2 = "#991B1E", "#B38600"   # Keck cardinal, USC gold (dark, for contrast)
GRID, AXIS, INK_2 = "#E8ECF0", "#6B7684", "#52514E"


def _load_history() -> dict:
    return json.loads(_HISTORY_PATH.read_text()) if _HISTORY_PATH.exists() else {"weeks": []}


def _volume_chart(weeks: pd.DataFrame) -> alt.Chart:
    share = 1 - weeks["Unique issues"].sum() / weeks["Tickets received"].sum()
    title = f"About {round(share * 10)} in 10 tickets repeat an issue that's already open"
    long = weeks.melt(id_vars=["Week"], value_vars=["Tickets received", "Unique issues"],
                      var_name="Series", value_name="Count")
    color = alt.Color("Series:N", scale=alt.Scale(domain=["Tickets received", "Unique issues"],
                                                  range=[SERIES_1, SERIES_2]),
                      legend=alt.Legend(orient="top", title=None, labelColor=INK_2))
    x = alt.X("Week:O", title=None, sort=list(weeks.Week),
              axis=alt.Axis(labelAngle=0, labelColor=AXIS, tickColor=GRID, domainColor=GRID))
    y = alt.Y("Count:Q", title="Tickets", scale=alt.Scale(zero=True),
              axis=alt.Axis(gridColor=GRID, labelColor=AXIS, titleColor=AXIS, domain=False, tickCount=5))
    tip = [alt.Tooltip("Week:O"), alt.Tooltip("Series:N"), alt.Tooltip("Count:Q")]
    base = alt.Chart(long).encode(x=x, y=y, color=color)
    lines = base.mark_line(strokeWidth=2)
    points = base.mark_point(filled=True, size=64, stroke="white", strokeWidth=2).encode(tooltip=tip)
    last = long[long.Week == weeks.Week.iloc[-1]]
    labels = alt.Chart(last).mark_text(align="left", dx=8, fontSize=11, color=INK_2).encode(
        x=x, y=y, text=alt.Text("Count:Q"))
    return (lines + points + labels).properties(height=240, title=alt.TitleParams(
        title,
        anchor="start", fontSize=13, color="#1C2430", fontWeight=600))


def _critical_chart(weeks: pd.DataFrame) -> alt.Chart:
    x = alt.X("Week:O", title=None, sort=list(weeks.Week), axis=alt.Axis(labelAngle=0, labelColor=AXIS, tickColor=GRID, domainColor=GRID))
    y = alt.Y("Critical issues:Q", title="Critical issues", scale=alt.Scale(zero=True),
              axis=alt.Axis(gridColor=GRID, labelColor=AXIS, titleColor=AXIS, domain=False, tickMinStep=1))
    bars = alt.Chart(weeks).mark_bar(color=SERIES_1, cornerRadiusTopLeft=4, cornerRadiusTopRight=4,
                                     size=22).encode(
        x=x, y=y, tooltip=[alt.Tooltip("Week:O"), alt.Tooltip("Critical issues:Q"), alt.Tooltip("SLA breaches:Q")])
    return bars.properties(height=240, title=alt.TitleParams(
        "Critical issues per week", anchor="start", fontSize=13, color="#1C2430", fontWeight=600))


def render_digest(data: dict, df: pd.DataFrame, now, manual_min: float = 6, review_min: float = 1.5) -> None:
    history = _load_history()
    d = build_digest(df.to_dict("records"), data["groups"], history, manual_min, review_min, now)
    m = d["metrics"]

    st.markdown(
        f'<div class="before-header"><b>📈 Weekly triage digest: Data Engineering queue</b> &nbsp;·&nbsp; '
        f'prepared {now:%a %b %d}, {now.hour % 12 or 12}:{now:%M %p} &nbsp;·&nbsp; '
        f'<span style="color:#6B7684">draft for a manager to review before sending</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(f"#### {d['headline']}")

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Open tickets", m["tickets"])
    k2.metric(f"Unique issues ({m['duplicates']} duplicates folded in)", m["issues"])
    k3.metric("Critical", m["critical"])
    k4.metric("Wrong type / team", m["mistyped"] + m["misrouted"])
    k5.metric("Triage time saved", f"~{d['hours_saved_week']:.0f} h/week",
              help=f"4-week average volume ({m['avg_tickets_4wk']:.0f} tickets → {m['avg_unique_4wk']:.0f} issues) × "
                   f"the sidebar assumptions ({manual_min:g} min manual per ticket vs {review_min:g} min review "
                   "per issue). An estimate, not a measurement.")

    left, right = st.columns([3, 2])
    with left:
        st.markdown("**Needs attention**")
        for a in d["attention"]:
            st.markdown(f"- {a}")
    with right:
        with st.container(border=True):
            st.markdown("**Patient-care related issues**")
            for i in d["clinical"]:
                st.markdown(f"{priority_pill(i['label'])} {i['title'].rstrip('.')}", unsafe_allow_html=True)
            if not d["clinical"]:
                st.caption("None this week.")

    st.markdown("**Trends, last 8 weeks** <span class='muted'>(synthetic history, illustrative)</span>",
                unsafe_allow_html=True)
    weeks = pd.DataFrame(history.get("weeks", []))
    if not weeks.empty:
        weeks["Week"] = pd.to_datetime(weeks.week_start).dt.strftime("%b %d")
        weeks = weeks.rename(columns={"tickets": "Tickets received", "unique_issues": "Unique issues",
                                      "critical_issues": "Critical issues", "sla_breaches": "SLA breaches"})
        c1, c2 = st.columns([3, 2])
        c1.altair_chart(_volume_chart(weeks), use_container_width=True)
        c2.altair_chart(_critical_chart(weeks), use_container_width=True)
        with st.expander("Trend data as a table"):
            st.dataframe(weeks[["Week", "Tickets received", "Unique issues", "Critical issues", "SLA breaches",
                                "needs_info", "mistyped_incidents", "misrouted"]].rename(columns={
                "needs_info": "Needed more info", "mistyped_incidents": "Requests filed as incidents",
                "misrouted": "Not DE work"}), hide_index=True, use_container_width=True)

    st.markdown("**Recurring problems** <span class='muted'>(prior 8 weeks + this week)</span>",
                unsafe_allow_html=True)
    rec = pd.DataFrame(d["recurring"])
    if not rec.empty:
        rec["Weeks seen"] = rec.weeks_seen.astype(str) + " of " + rec.of_weeks.astype(str)
        rec["In queue now"] = rec.in_queue_now.map({True: "Yes", False: ""})
        st.dataframe(rec[["name", "Weeks seen", "tickets_8wk", "In queue now"]].rename(columns={
            "name": "Problem", "tickets_8wk": "Tickets (prior 8 weeks)"}), hide_index=True,
            use_container_width=True)

    b1, b2 = st.columns([1, 3])
    b1.download_button("⬇️ Download digest (Markdown)", d["markdown"], "weekly_triage_digest.md", "text/markdown",
                       use_container_width=True)
    with b2.expander("Email preview"):
        st.markdown(d["markdown"])

    st.caption(
        "Demo: this summary is assembled offline from the numbers above, so every figure traces back to the data. "
        "In production the language model writes the narrative from the same numbers, and a manager reviews it "
        "before it goes out. Trend history is synthetic."
    )
