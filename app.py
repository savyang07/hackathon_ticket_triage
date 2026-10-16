"""
Triage Copilot — ServiceNow ticket triage demo for the Data Engineering team.

Data: 38 dummy tickets. If data/tickets_llm.json exists (made by scripts/precompute.py),
the dashboard shows Claude's triage of them; otherwise it shows the hand-written sample.
Tab ⑤ calls Claude live when a key is configured and falls back to offline rules otherwise.
    streamlit run app.py
"""
import html
import json
import os
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from triage import llm
from triage.offline_engine import SimilarityIndex, triage

ROOT = Path(__file__).parent
st.set_page_config(page_title="Triage Copilot", page_icon="🎫", layout="wide")

# Keys can live in .streamlit/secrets.toml instead of the shell environment.
try:
    for _k in llm.CONFIG_KEYS:
        if _k in st.secrets and not os.environ.get(_k):
            os.environ[_k] = str(st.secrets[_k])
except Exception:  # no secrets file — fine
    pass

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
SOURCES = {}
if (ROOT / "data" / "tickets_llm.json").exists():
    SOURCES["✨ Claude-generated"] = ROOT / "data" / "tickets_llm.json"
SOURCES["Hand-written sample"] = ROOT / "data" / "tickets.json"


@st.cache_data
def load(path, mtime):  # mtime in the cache key → re-running precompute shows up on refresh
    d = json.loads(Path(path).read_text())
    df = pd.DataFrame(d["tickets"])
    now = datetime.strptime(d["demo_now"], "%Y-%m-%d %H:%M")
    df["opened_dt"] = pd.to_datetime(df["opened_at"])
    df["age_hrs"] = (now - df["opened_dt"]).dt.total_seconds() / 3600
    return d, df, now


with st.sidebar:
    st.markdown("### ✨ AI")
    source = st.radio("Triage results shown", list(SOURCES), key="source",
                      help="Claude-generated = scripts/precompute.py output. "
                           "Hand-written sample = the original mock answers.")

DATA, DF, NOW = load(str(SOURCES[source]), SOURCES[source].stat().st_mtime)
IS_LLM_DATA = "generated_by" in DATA
try:
    LIVE_CFG = llm.get_config("live")
    LIVE_ERR = None
except llm.LLMError as e:
    LIVE_CFG, LIVE_ERR = None, str(e)
QUEUES, GROUPS = DATA["queues"], DATA["groups"]

PCOLOR = {"P1": "#C8322F", "P2": "#E07B24", "P3": "#C99A06", "P4": "#5E7A8C"}
PBG = {"P1": "#FCE9E8", "P2": "#FDF0E4", "P3": "#FBF5DE", "P4": "#EDF2F5"}

if "decisions" not in st.session_state:
    st.session_state.decisions = {}      # ticket/group key -> {"status", "queue"}
if "linked" not in st.session_state:
    st.session_state.linked = set()      # group ids whose children were linked
if "notified" not in st.session_state:
    st.session_state.notified = set()    # group ids whose callers were notified

# ---------------------------------------------------------------------------
# Styling helpers
# ---------------------------------------------------------------------------
st.markdown("""
<style>
.block-container {padding-top: 1.6rem; max-width: 1400px;}
.hdr {display:flex; justify-content:space-between; align-items:flex-end; margin-bottom:.4rem;}
.hdr h1 {font-size:1.9rem; margin:0; letter-spacing:-.02em;}
.hdr .sub {color:#5A6573; font-size:.92rem; margin-top:.15rem;}
.clock {background:#fff; border:1px solid #E1E5EA; border-radius:10px; padding:.45rem .8rem;
        font-size:.85rem; color:#3A4552; white-space:nowrap;}
.kpis {display:grid; grid-template-columns:repeat(5,1fr); gap:.7rem; margin:.8rem 0 1rem;}
.kpi {background:#fff; border:1px solid #E1E5EA; border-radius:12px; padding:.75rem .9rem;}
.kpi .lbl {font-size:.74rem; text-transform:uppercase; letter-spacing:.05em; color:#6B7684;}
.kpi .val {font-size:1.6rem; font-weight:700; margin-top:.1rem; color:#1C2430;}
.kpi .val small {font-size:.9rem; font-weight:500; color:#6B7684;}
.kpi .delta {font-size:.8rem; color:#0F6E6E; margin-top:.1rem;}
.pill {display:inline-block; padding:.12rem .5rem; border-radius:999px; font-size:.72rem;
       font-weight:600; margin-right:.3rem; white-space:nowrap;}
.score {width:58px; height:58px; border-radius:12px; display:flex; flex-direction:column;
        align-items:center; justify-content:center; font-weight:700; line-height:1.05;}
.score .n {font-size:1.35rem;} .score .p {font-size:.68rem; font-weight:600;}
.summ {font-size:1.0rem; font-weight:600; color:#1C2430; margin-bottom:.15rem;}
.orig {font-size:.82rem; color:#6B7684; margin-bottom:.3rem;}
.route {font-size:.88rem;} .route b {color:#0F6E6E;}
.conf {height:6px; background:#E8ECF0; border-radius:4px; margin-top:.35rem; overflow:hidden;}
.conf > div {height:100%; background:#0F6E6E;}
.muted {color:#6B7684; font-size:.8rem;}
.callout {background:#FCE9E8; border:1px solid #F2C4C2; border-radius:10px; padding:.7rem .9rem;
          color:#7A1F1D; font-size:.9rem; margin:.4rem 0 .8rem;}
.gcard-h {font-size:1.05rem; font-weight:700;}
.mini td, .mini th {font-size:.82rem;}
</style>
""", unsafe_allow_html=True)


def pkey(label):
    return label.split(" ")[0]  # "P1 – Critical" -> "P1"


def pill(text, fg, bg):
    return f'<span class="pill" style="color:{fg};background:{bg}">{html.escape(text)}</span>'


def score_box(score, plabel):
    k = pkey(plabel)
    return (f'<div class="score" style="background:{PBG[k]};color:{PCOLOR[k]};'
            f'border:1.5px solid {PCOLOR[k]}"><span class="n">{score}</span>'
            f'<span class="p">{k}</span></div>')


def age(hrs):
    return f"{int(hrs * 60)}m" if hrs < 1 else (f"{hrs:.0f}h" if hrs < 48 else f"{hrs / 24:.1f}d")


def plabel_for(score):
    return ("P1 – Critical" if score >= 85 else "P2 – High" if score >= 65
            else "P3 – Medium" if score >= 40 else "P4 – Low")


# ---------------------------------------------------------------------------
# Issue-level view: one row per duplicate group (parent) + each singleton
# ---------------------------------------------------------------------------
def build_issues(df):
    rows = []
    for gid, g in df[df.group_id != ""].groupby("group_id"):
        parent = g[g.group_role == "parent"].iloc[0].to_dict()
        top = g.ai_priority_score.max()
        rows.append({**parent, "key": gid, "is_group": True, "n": len(g),
                     "members": g.number.tolist(), "ai_priority_score": int(top),
                     "ai_priority": plabel_for(top), "ai_summary": GROUPS[gid]["title"],
                     "oldest_hrs": g.age_hrs.max(),
                     "n_request": int(g.ai_should_be_request.sum())})
    for _, r in df[df.group_id == ""].iterrows():
        rows.append({**r.to_dict(), "key": r.number, "is_group": False, "n": 1,
                     "members": [r.number], "oldest_hrs": r.age_hrs,
                     "n_request": int(r.ai_should_be_request)})
    return pd.DataFrame(rows).sort_values("ai_priority_score", ascending=False)


ISSUES = build_issues(DF)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    if IS_LLM_DATA:
        fails = len(DATA.get("failures", []))
        st.caption(f"Generated by **{DATA['generated_by']}** on {DATA['generated_at']}"
                   + (f" · ⚠️ {fails} ticket(s) fell back to rules" if fails else ""))
    else:
        st.caption("Mock answers written by hand. Run `python scripts/precompute.py` "
                   "with a key to have Claude generate them.")
    if LIVE_CFG:
        st.success(f"Live AI on · {LIVE_CFG.label}", icon="🟢")
    else:
        st.info(LIVE_ERR or "Live AI off — no API key. Tab ⑤ uses offline rules.", icon="⚪")
    st.divider()
    st.markdown("### ⚙️ Demo settings")
    manual_min = st.slider("Manual triage time per ticket (min)", 2, 15, 6,
                           help="Read, summarize, label, prioritize and route one raw ticket.")
    review_min = st.slider("Review time per AI-triaged issue (min)", 0.5, 5.0, 1.5, 0.5,
                           help="Skim the summary and accept or reroute.")
    st.divider()
    st.markdown(f"**Data:** {len(DF)} dummy ServiceNow tickets, all fictional.")
    if st.button("↺ Reset demo state", use_container_width=True):
        st.session_state.decisions = {}
        st.session_state.linked = set()
        st.session_state.notified = set()
        st.rerun()

# ---------------------------------------------------------------------------
# Header + KPIs
# ---------------------------------------------------------------------------
st.markdown(f"""
<div class="hdr">
  <div><h1>🎫 Triage Copilot</h1>
  <div class="sub">Generative-AI triage for the Data Engineering ServiceNow queue — summarize, group, prioritize, route.</div></div>
  <div class="clock">🕘 {NOW:%a %b %d}, {NOW.hour % 12 or 12}:{NOW:%M %p} · on-call shift start · queue: <b>Data Engineering</b></div>
</div>""", unsafe_allow_html=True)

n_tickets, n_issues = len(DF), len(ISSUES)
n_dupes = n_tickets - n_issues
n_misrouted = int((DF.ai_route_queue == "IT Service Desk (not DE)").sum())
n_req = int(DF.ai_should_be_request.sum())
n_p1 = int((ISSUES.ai_priority.str.startswith("P1")).sum())
before_min = n_tickets * manual_min
after_min = n_issues * review_min
decided = len(st.session_state.decisions)

st.markdown(f"""
<div class="kpis">
 <div class="kpi"><div class="lbl">Tickets in queue</div><div class="val">{n_tickets}</div>
   <div class="delta">all unassigned</div></div>
 <div class="kpi"><div class="lbl">Unique issues</div><div class="val">{n_issues}</div>
   <div class="delta">↓ {n_dupes} duplicates collapsed ({n_dupes / n_tickets:.0%})</div></div>
 <div class="kpi"><div class="lbl">Critical issues</div><div class="val">{n_p1}</div>
   <div class="delta">surfaced to the top</div></div>
 <div class="kpi"><div class="lbl">Wrong ticket type / team</div><div class="val">{n_req + n_misrouted}</div>
   <div class="delta">{n_req} should be requests · {n_misrouted} not DE</div></div>
 <div class="kpi"><div class="lbl">Triage time</div>
   <div class="val">{after_min:.0f}<small> min</small></div>
   <div class="delta">vs {before_min / 60:.1f} hrs manual (−{1 - after_min / before_min:.0%})</div></div>
</div>""", unsafe_allow_html=True)

tabs = st.tabs(["① Before: raw queue", "② Triage queue", "③ Duplicate groups",
                "④ Routing", "⑤ Triage a new ticket", "⑥ Data table"])

# ---------------------------------------------------------------------------
# ① Before
# ---------------------------------------------------------------------------
with tabs[0]:
    raw = DF.sort_values("opened_dt", ascending=False)
    # The ticket to call out: the PHI one if the model found it, otherwise the most urgent ticket.
    phi_rows = DF[DF.ai_category == "Security / PHI"]
    phi = (phi_rows if len(phi_rows) else DF).sort_values("ai_priority_score", ascending=False).iloc[0]
    what = "possible PHI exposure" if len(phi_rows) else "most urgent ticket"
    phi_pos = list(raw.number).index(phi.number) + 1
    st.markdown(f"""<div class="callout">⚠️ This is what on-call sees today: {n_tickets} unassigned tickets,
    newest first, no summaries. The <b>{what}</b> ({phi.number}) is row
    <b>#{phi_pos}</b>, filed as <b>{phi.snow_priority}</b> by {phi.channel.lower()}, and has sat unassigned for
    <b>{phi.age_hrs:.0f} hours</b>.</div>""", unsafe_allow_html=True)
    show = raw[["number", "opened_at", "short_description", "caller", "channel",
                "snow_priority", "assignment_group", "assigned_to", "state"]].rename(columns={
        "number": "Number", "opened_at": "Opened", "short_description": "Short description",
        "caller": "Caller", "channel": "Channel", "snow_priority": "Priority",
        "assignment_group": "Assignment group", "assigned_to": "Assigned to", "state": "State"})
    show["Assigned to"] = "(empty)"

    def hl(row):
        on = row["Number"] == phi.number
        return ["background-color:#FCE9E8" if on else ""] * len(row)

    st.dataframe(show.style.apply(hl, axis=1), hide_index=True, use_container_width=True,
                 height=560)

# ---------------------------------------------------------------------------
# ② Triage queue
# ---------------------------------------------------------------------------
with tabs[1]:
    c1, c2, c3 = st.columns([1.1, 2, 2])
    collapse = c1.toggle("Collapse duplicates", value=True)
    pf = c2.multiselect("Priority", ["P1", "P2", "P3", "P4"], default=["P1", "P2", "P3", "P4"])
    qf = c3.multiselect("Suggested queue", list(QUEUES), placeholder="All queues")

    if collapse:
        view = ISSUES.copy()
    else:
        view = DF.copy()
        view["key"] = view["number"]
        view["is_group"] = False
        view["n"] = 1
        view["oldest_hrs"] = view["age_hrs"]
        view = view.sort_values("ai_priority_score", ascending=False)
    view = view[view.ai_priority.str[:2].isin(pf)]
    if qf:
        view = view[view.ai_route_queue.isin(qf)]

    st.caption(f"{len(view)} {'issues' if collapse else 'tickets'} · sorted by AI priority score · "
               f"{decided} routed so far")

    for _, r in view.iterrows():
        k = r["key"]
        dec = st.session_state.decisions.get(k)
        with st.container(border=True):
            a, b, c = st.columns([0.55, 5.2, 3.2], vertical_alignment="center")
            a.markdown(score_box(r.ai_priority_score, r.ai_priority), unsafe_allow_html=True)

            badges = pill(r.ai_category, "#3A4552", "#EEF1F4")
            if r.is_group:
                badges += pill(f"🔗 {r.n} tickets grouped", "#0F6E6E", "#E2F2F1")
            if r.get("n_request", 0) or r.ai_should_be_request:
                badges += pill("↻ Should be a Request", "#7A4B00", "#FFF1D6")
            if r.ai_route_queue == "IT Service Desk (not DE)":
                badges += pill("✕ Not Data Engineering", "#7A1F1D", "#FCE9E8")
            if not r.is_group and r.snow_priority.startswith("4") and r.ai_priority_score >= 85:
                badges += pill("⚑ Filed as Low", "#7A1F1D", "#FCE9E8")
            b.markdown(f'<div class="summ">{html.escape(r.ai_summary)}</div>'
                       f'<div class="orig">{r.number} · “{html.escape(r.short_description)}” · '
                       f'{html.escape(r.caller_dept)} · open {age(r.oldest_hrs)}</div>{badges}',
                       unsafe_allow_html=True)

            queue = dec["queue"] if dec else r.ai_route_queue
            owner = QUEUES[queue] if (dec and dec["queue"] != r.ai_route_queue) else r.ai_route_owner
            status = {"accepted": "✅ Routed", "rerouted": "✏️ Rerouted"}.get(
                dec["status"] if dec else "", "Suggested")
            c.markdown(f'<div class="route"><span class="muted">{status} →</span><br>'
                       f'<b>{html.escape(queue)}</b><br>👤 {html.escape(owner)}</div>'
                       f'<div class="conf"><div style="width:{r.ai_confidence * 100:.0f}%"></div></div>'
                       f'<div class="muted">confidence {r.ai_confidence:.0%}</div>',
                       unsafe_allow_html=True)

            with st.expander("Why this score & route · details"):
                d1, d2 = st.columns([3, 2])
                with d1:
                    st.markdown(f"**Rationale:** {r.ai_rationale}")
                    if r.ai_similar_history:
                        st.markdown(f"**Who's handled this before:** {r.ai_similar_history}")
                    if r.is_group:
                        g = GROUPS[k]
                        st.markdown(f"**Likely root cause:** {g['root_cause']}")
                        st.markdown(f"**Recommended action:** {g['recommended_action']}")
                        members = DF[DF.number.isin(r.members)][
                            ["number", "type", "channel", "short_description", "caller",
                             "ai_priority_score"]].sort_values("ai_priority_score", ascending=False)
                        st.dataframe(members, hide_index=True, use_container_width=True)
                    else:
                        st.markdown("**Original description**")
                        st.code(r.description, language=None, wrap_lines=True)
                with d2:
                    st.markdown(f"**Scored by:** {r.scored_by}")
                    st.markdown(f"**Filed as:** {r.type} · {r.snow_priority} via {r.channel}")
                    st.markdown(f"**Caller:** {r.caller} ({r.caller_dept})")
                    x1, x2 = st.columns(2)
                    if x1.button("✅ Accept route", key=f"acc_{k}", use_container_width=True):
                        st.session_state.decisions[k] = {"status": "accepted",
                                                         "queue": r.ai_route_queue}
                        st.rerun()
                    new_q = x2.selectbox("Reroute to", list(QUEUES), key=f"rq_{k}",
                                         index=list(QUEUES).index(queue),
                                         label_visibility="collapsed")
                    if new_q != queue:
                        st.session_state.decisions[k] = {"status": "rerouted", "queue": new_q}
                        st.rerun()

# ---------------------------------------------------------------------------
# ③ Duplicate groups
# ---------------------------------------------------------------------------
with tabs[2]:
    st.markdown(f"**{n_tickets} tickets → {n_issues} issues.** "
                f"{len(GROUPS)} groups absorb {sum(len(DF[DF.group_id == g]) for g in GROUPS)} tickets. "
                "Fix the root once, link the rest, and send one update to everyone affected.")
    gsum = (ISSUES[ISSUES.is_group].sort_values("ai_priority_score", ascending=False))
    for _, r in gsum.iterrows():
        gid, g = r["key"], GROUPS[r["key"]]
        members = DF[DF.group_id == gid].sort_values("opened_dt")
        k = pkey(r.ai_priority)
        with st.container(border=True):
            h1, h2 = st.columns([6, 2], vertical_alignment="center")
            h1.markdown(
                f'<div class="gcard-h">{pill(k, PCOLOR[k], PBG[k])} {html.escape(g["title"])}</div>'
                f'<div class="muted">{gid} · {len(members)} tickets · '
                f'{(members.channel == "Monitoring").sum()} automated alerts · '
                f'{members.caller_dept[members.caller_dept != "Automated"].nunique()} affected teams · '
                f'first seen {age(members.age_hrs.max())} ago</div>', unsafe_allow_html=True)
            h2.markdown(f'<div class="route" style="text-align:right">→ <b>{html.escape(r.ai_route_queue)}</b>'
                        f'<br>👤 {html.escape(r.ai_route_owner)}</div>', unsafe_allow_html=True)

            l, rcol = st.columns([3, 2])
            with l:
                st.markdown(f"**Root cause:** {g['root_cause']}")
                st.markdown(f"**Do this:** {g['recommended_action']}")
                tbl = members[["number", "group_role", "channel", "short_description", "caller",
                               "age_hrs"]].copy()
                tbl["age_hrs"] = tbl.age_hrs.map(age)
                tbl["group_role"] = tbl.group_role.map({"parent": "⭐ parent", "child": "child"})
                tbl.columns = ["Number", "Role", "Channel", "Original short description", "Caller", "Age"]
                st.dataframe(tbl, hide_index=True, use_container_width=True)
            with rcol:
                st.markdown("**Update for affected teams:** " + ", ".join(g["notify"]))
                st.text_area("Draft", g["comms_draft"], height=190, key=f"comms_{gid}",
                             label_visibility="collapsed")
                b1, b2 = st.columns(2)
                linked = gid in st.session_state.linked
                if b1.button("✓ Children linked" if linked else f"🔗 Link {len(members) - 1} to parent",
                             key=f"link_{gid}", disabled=linked, use_container_width=True):
                    st.session_state.linked.add(gid)
                    st.toast(f"Linked {len(members) - 1} tickets to {r.number} (demo)")
                    st.rerun()
                sent = gid in st.session_state.notified
                if b2.button("✓ Update sent" if sent else "✉️ Send update", key=f"send_{gid}",
                             disabled=sent, use_container_width=True):
                    st.session_state.notified.add(gid)
                    st.toast("Update posted to linked tickets (demo — nothing actually sent)")
                    st.rerun()

# ---------------------------------------------------------------------------
# ④ Routing
# ---------------------------------------------------------------------------
with tabs[3]:
    st.markdown("**Before:** every ticket lands in one shared *Data Engineering* queue. "
                "**After:** each issue goes straight to the team that owns it, with a suggested owner "
                "based on who has fixed similar tickets.")
    eff_queue = ISSUES.apply(lambda r: st.session_state.decisions.get(r["key"], {}).get(
        "queue", r.ai_route_queue), axis=1)
    counts = pd.DataFrame({
        "Tickets": DF.ai_route_queue.value_counts(),
        "Unique issues": eff_queue.value_counts(),
    }).fillna(0).astype(int).loc[list(QUEUES)]
    counts.index = [q.split("–", 1)[-1].strip().replace(" (not DE)", "") for q in counts.index]
    m1, m2 = st.columns([3, 2])
    with m1:
        st.bar_chart(counts, horizontal=True, stack=False, height=320,
                     color=["#9FB4C2", "#0F6E6E"])
    with m2:
        acc = sum(1 for d in st.session_state.decisions.values() if d["status"] == "accepted")
        rer = sum(1 for d in st.session_state.decisions.values() if d["status"] == "rerouted")
        st.metric("Routing decisions made", f"{acc + rer} / {n_issues}")
        st.metric("AI route accepted as-is", f"{acc / (acc + rer):.0%}" if acc + rer else "—",
                  help="Live proxy for the routing-accuracy KPI.")
        st.metric("Sent back to IT Service Desk", n_misrouted,
                  help="Tickets that never belonged to Data Engineering.")

    st.divider()
    cols = st.columns(3)
    for i, q in enumerate(QUEUES):
        sub = ISSUES[eff_queue == q]
        with cols[i % 3].container(border=True):
            st.markdown(f"**{q}**  \n<span class='muted'>👤 {QUEUES[q]} · {len(sub)} issues</span>",
                        unsafe_allow_html=True)
            for _, r in sub.iterrows():
                k = pkey(r.ai_priority)
                tag = f" · {r.n} tickets" if r.is_group else ""
                st.markdown(f"{pill(k, PCOLOR[k], PBG[k])} {html.escape(r.ai_summary[:70])}"
                            f"{'…' if len(r.ai_summary) > 70 else ''}"
                            f"<span class='muted'>{tag}</span>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# ⑤ Triage a new ticket
# ---------------------------------------------------------------------------
SAMPLES = {
    "Duplicate of an open issue (bed census)":
        "Hi team, the bed census report on 6 North still shows yesterday's numbers. We need it for the bed huddle. Thanks!",
    "Access request filed as incident":
        "Can I get access to the Bed Capacity dashboard in Tableau? I get permission denied.",
    "Not Data Engineering":
        "My laptop VPN keeps disconnecting and I'm locked out of email.",
    "Possible PHI exposure":
        "A workbook in the All Staff project shows patient names and MRN numbers — I think everyone can see it.",
    "New pipeline failure":
        "Talend job RADIOLOGY_ORDERS_DAILY failed overnight with a null pointer in tMap_2. Radiology volume report is blank.",
}

@st.cache_resource
def live_client(provider, model, region):
    return llm.make_client(llm.LLMConfig(provider, model, region), timeout=20, max_retries=1)


def open_issue_index():
    """What the model sees as 'already in the queue' when checking a new ticket for duplicates."""
    return {r["key"]: f"{r['ai_summary']} [{r['n']} ticket(s); {r['ai_route_queue']}]"
            for _, r in ISSUES.iterrows()}


def run_live(text):
    cfg = LIVE_CFG
    ticket = {"number": "NEW", "type": "Incident", "channel": "Email",
              "opened_at": NOW.strftime("%Y-%m-%d %H:%M"), "caller": "(new caller)",
              "caller_dept": "Unknown", "snow_priority": "4 - Low",
              "short_description": text.strip().split("\n")[0][:90], "description": text.strip()}
    res, meta = llm.triage_ticket(live_client(cfg.provider, cfg.model, cfg.region), cfg, ticket,
                                  QUEUES, NOW.strftime("%Y-%m-%d %H:%M"),
                                  open_issues=open_issue_index())
    dup, gm = res["duplicate_of"], None
    if dup in GROUPS:
        gm = DF[(DF.group_id == dup) & (DF.group_role == "parent")].iloc[0].to_dict()
    elif dup in set(DF.number):
        gm = DF[DF.number == dup].iloc[0].to_dict()
    if gm is not None:   # duplicates go where the existing issue already went
        res["queue"], res["owner"] = gm["ai_route_queue"], gm["ai_route_owner"]
    return {**res, "group_match": gm, "meta": meta}


with tabs[4]:
    st.markdown("Paste or pick a ticket the way it would arrive from email or the portal. "
                + ("**Claude** reads it, writes the summary, scores and routes it, and checks it against "
                   "every open issue for duplicates." if LIVE_CFG else
                   "No API key is set, so this tab uses the **offline rules** (keywords + text similarity)."))
    s = st.selectbox("Sample ticket", list(SAMPLES))
    text = st.text_area("Ticket text", SAMPLES[s], height=110, key=f"txt_{s}")
    if st.button("⚡ Triage it", type="primary"):
        index = SimilarityIndex(DF.to_dict("records"))
        res, engine, err = None, "offline", None
        if LIVE_CFG:
            try:
                with st.spinner(f"Asking {LIVE_CFG.model}…"):
                    res = run_live(text)
                engine = "live"
            except Exception as e:  # never break on stage — fall back
                err = e
        if res is None:
            res = triage(text, index, QUEUES)
        similar = index.top(text)

        if engine == "live":
            m = res["meta"]
            st.caption(f"✨ Generated live by **{LIVE_CFG.label}** in {m['seconds']}s"
                       + (f" · {m['input_tokens']:,} in / {m['output_tokens']:,} out tokens"
                          if m.get("input_tokens") else ""))
        elif err is not None:
            st.warning(f"Live AI call failed ({type(err).__name__}: {str(err)[:160]}) — "
                       "showing the offline rules result instead.")
        pl = plabel_for(res["score"])
        with st.container(border=True):
            a, b, c = st.columns([0.55, 5.2, 3.2], vertical_alignment="center")
            a.markdown(score_box(res["score"], pl), unsafe_allow_html=True)
            badges = pill(res["category"], "#3A4552", "#EEF1F4")
            gm = res["group_match"]
            if gm is not None:
                badges += pill(f"🔗 Duplicate → {gm['group_id'] or gm['number']}", "#0F6E6E", "#E2F2F1")
            if res["should_be_request"]:
                badges += pill("↻ Should be a Request", "#7A4B00", "#FFF1D6")
            if res["queue"] == "IT Service Desk (not DE)":
                badges += pill("✕ Not Data Engineering", "#7A1F1D", "#FCE9E8")
            b.markdown(f'<div class="summ">{html.escape(res["summary"])}</div>{badges}',
                       unsafe_allow_html=True)
            c.markdown(f'<div class="route"><span class="muted">Suggested →</span><br>'
                       f'<b>{html.escape(res["queue"])}</b><br>👤 {html.escape(res["owner"])}</div>'
                       f'<div class="conf"><div style="width:{res["confidence"] * 100:.0f}%"></div></div>'
                       f'<div class="muted">confidence {res["confidence"]:.0%}</div>',
                       unsafe_allow_html=True)
            st.markdown(f"**Why:** {res['rationale']}")
            if res.get("similar_history"):
                st.markdown(f"**Who's handled this before:** {res['similar_history']}")
            if gm is not None and gm["group_id"]:
                g = GROUPS[gm["group_id"]]
                st.success(f"Would be linked to **{g['title']}** — no new investigation needed. "
                           f"Caller gets the existing status update automatically.")
            elif gm is not None:
                st.warning(f"Same issue as open ticket **{gm['number']}** — "
                           f"would start a new duplicate group with it instead of a second investigation.")
        st.markdown("**Most similar open tickets** (text similarity)")
        st.dataframe(pd.DataFrame([{
            "Similarity": round(sc, 2), "Number": t["number"],
            "Short description": t["short_description"], "Group": t["group_id"] or "—",
        } for sc, t in similar]), hide_index=True, use_container_width=True)

    with st.expander("🔍 See exactly what the model is told"):
        st.markdown("**System prompt** — queue definitions, scoring rubric, rules, and resolved-ticket "
                    "history used for 'who's handled this before'.")
        st.code(llm.triage_system_prompt(QUEUES, llm.load_history(), NOW.strftime("%Y-%m-%d %H:%M")),
                language=None, wrap_lines=True)
        st.markdown("**Output schema** — the model must answer through this tool; the app then "
                    "re-validates every field before showing it.")
        st.json(llm.triage_schema(QUEUES, llm.owner_roster(QUEUES, llm.load_history()),
                                  list(open_issue_index())), expanded=False)

# ---------------------------------------------------------------------------
# ⑥ Data table (the 'one queryable table' the BI team asked for)
# ---------------------------------------------------------------------------
with tabs[5]:
    st.markdown("The single queryable table developers asked for — every ticket with its score, "
                "summary, owner and status. In production this lands in Redshift so the team can query it directly.")
    out = DF[["number", "type", "ai_priority_score", "ai_priority", "ai_summary", "ai_category",
              "ai_route_queue", "ai_route_owner", "ai_confidence", "group_id", "ai_should_be_request",
              "opened_at", "state", "scored_by"]].sort_values("ai_priority_score", ascending=False)
    st.dataframe(out, hide_index=True, use_container_width=True, height=440, column_config={
        "ai_priority_score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100,
                                                             format="%d"),
        "ai_confidence": st.column_config.NumberColumn("Confidence", format="percent"),
    })
    st.download_button("⬇️ Download CSV", out.to_csv(index=False), "ticket_triage.csv", "text/csv")
    with st.expander("Proposed Redshift table"):
        st.code("""CREATE TABLE de_triage.ticket_scores (
    ticket_number        VARCHAR(20)  NOT NULL,
    ticket_type          VARCHAR(20),
    priority_score       SMALLINT,
    priority_label       VARCHAR(20),
    ai_summary           VARCHAR(500),
    category             VARCHAR(50),
    suggested_queue      VARCHAR(100),
    suggested_owner      VARCHAR(100),
    confidence           DECIMAL(3,2),
    duplicate_group_id   VARCHAR(20),
    should_be_request    BOOLEAN,
    opened_at            TIMESTAMP,
    status               VARCHAR(20),
    scored_by            VARCHAR(50),
    scored_at            TIMESTAMP DEFAULT GETDATE()
)
DISTKEY(ticket_number) SORTKEY(priority_score, opened_at);""", language="sql")
