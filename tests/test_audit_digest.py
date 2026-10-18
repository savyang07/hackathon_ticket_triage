"""Tests for agents/audit.py and agents/digest.py."""
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.audit import make_entry, review_stats, seed_ai_entries  # noqa: E402
from agents.digest import build_digest  # noqa: E402

DATA = json.loads((ROOT / "data" / "tickets.json").read_text())
HISTORY = json.loads((ROOT / "data" / "weekly_history.json").read_text())
NOW = datetime(2026, 10, 15, 9, 0)


# ── audit ───────────────────────────────────────────────────────────────────
def test_seed_has_one_scored_entry_per_ticket_and_one_grouped_per_group():
    e = seed_ai_entries(DATA["tickets"], DATA["groups"], NOW, "Triage AI")
    assert sum(1 for x in e if x["action"] == "Scored") == len(DATA["tickets"])
    assert sum(1 for x in e if x["action"] == "Grouped") == len(DATA["groups"])
    assert all(x["actor_type"] == "AI" for x in e)
    needs_info = [x for x in e if x["action"] == "Scored" and x["after"].startswith("Not scored")]
    assert len(needs_info) == sum(1 for t in DATA["tickets"] if t.get("ai_needs_more_info"))


def test_review_stats_uses_latest_human_decision_per_issue():
    h = lambda action, target: make_entry(NOW, "Jordan Lee", "Human", action, target)
    entries = [h("Approved", "GRP-01"), h("Overrode priority", "INC0104493"),
               h("Approved", "INC0104430"), h("Rerouted", "INC0104430"),   # latest wins: rerouted
               h("Requested info", "INC0104533")]
    s = review_stats(entries, 22)
    assert s["reviewed"] == 3 and s["pending"] == 19
    assert (s["approved"], s["overridden"], s["rerouted"]) == (1, 1, 1)
    assert s["info_requested"] == 1
    assert abs(s["agreement"] - 1 / 3) < 1e-9


def test_review_stats_empty():
    assert review_stats([], 22)["agreement"] is None


# ── digest ──────────────────────────────────────────────────────────────────
def test_digest_numbers_match_the_queue():
    d = build_digest(DATA["tickets"], DATA["groups"], HISTORY, 6, 1.5, NOW)
    m = d["metrics"]
    n_grouped = sum(1 for t in DATA["tickets"] if t.get("group_id"))
    assert m["tickets"] == len(DATA["tickets"])
    assert m["issues"] == len(DATA["groups"]) + (len(DATA["tickets"]) - n_grouped)
    assert m["needs_info"] == sum(1 for t in DATA["tickets"] if t.get("ai_needs_more_info"))
    assert m["critical"] == len(d["critical"]) and all(i["label"] == "Critical" for i in d["critical"])


def test_digest_hours_saved_follows_the_assumptions():
    lo = build_digest(DATA["tickets"], DATA["groups"], HISTORY, 3, 3, NOW)["hours_saved_week"]
    hi = build_digest(DATA["tickets"], DATA["groups"], HISTORY, 10, 1, NOW)["hours_saved_week"]
    assert 0 <= lo < hi


def test_digest_flags_recurring_adt_failure_and_phi_report():
    d = build_digest(DATA["tickets"], DATA["groups"], HISTORY, 6, 1.5, NOW)
    text = " ".join(d["attention"])
    assert "Cerner ADT" in text and "of the last 9 weeks" in text
    assert "Privacy Office" in text
    assert d["markdown"].startswith("# Weekly triage digest")
