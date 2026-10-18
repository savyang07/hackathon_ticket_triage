"""
Shared session state for all tabs.

Keys:
  triage_done   bool       whether Run Triage has been played
  decisions     dict       routing decisions per issue key (existing behaviour)
  reviews       dict       human review per issue key: {"status", "label"?, "by", "reason"}
  audit         list       audit trail entries (agents/audit.py shape)
  linked        set        group ids whose children were linked
  notified      set        group ids whose update was sent
  session_start datetime   real time the session started (drives the audit clock)
"""
from datetime import datetime

import streamlit as st

from agents.audit import make_entry

REVIEWERS = ["Jordan Lee (Business Analyst)", "Priya Raman (Business Analyst)", "Dev Patel (On-call engineer)"]


def init_state() -> None:
    defaults = {
        "triage_done": False,
        "decisions": {},
        "reviews": {},
        "audit": [],
        "linked": set(),
        "notified": set(),
        "session_start": datetime.now(),
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def reset_state() -> None:
    st.session_state.triage_done = False
    st.session_state.decisions = {}
    st.session_state.reviews = {}
    st.session_state.audit = []
    st.session_state.linked = set()
    st.session_state.notified = set()
    st.session_state.session_start = datetime.now()
    # Clear per-card widget values too, or a leftover "Reroute to" choice would re-fire after reset.
    for key in list(st.session_state.keys()):
        if str(key).startswith(("rq_", "ovl_", "ovr_", "comms_")):
            del st.session_state[key]


def demo_time(now: datetime) -> datetime:
    """The demo clock is frozen at 9:00 AM; human actions are stamped 9:00 + time elapsed in the session."""
    return now + (datetime.now() - st.session_state.session_start)


def reviewer() -> str:
    return st.session_state.get("reviewer", REVIEWERS[0])


def log(now: datetime, action: str, target: str, ticket: str = "", before: str = "",
        after: str = "", reason: str = "") -> None:
    st.session_state.audit.append(make_entry(demo_time(now), reviewer(), "Human", action, target,
                                             ticket, before, after, reason))
