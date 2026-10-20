"""
Guards for data/tickets.json: rebuilding must not lose ERWG fields, and every stored
score must match the ERWG formula in agents/scorer.py.
"""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.scorer import score_ticket  # noqa: E402

DATA = json.loads((ROOT / "data" / "tickets.json").read_text())
CONFIG = json.loads((ROOT / "config" / "scoring.json").read_text())
RATINGS = ["ai_org_impact", "ai_patient_safety", "ai_compliance", "ai_financial", "ai_utilization"]
INTAKE = ["justification_text", "when_needed", "is_recurring", "frequency", "analytics_type",
          "ai_needs_more_info", "ai_info_requests"]


def _generator():
    spec = importlib.util.spec_from_file_location("generate_tickets", ROOT / "data" / "generate_tickets.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_rebuild_reproduces_committed_data():
    """Running data/generate_tickets.py must give exactly the committed tickets.json."""
    assert _generator().build_payload() == DATA


def test_every_ticket_has_erwg_ratings_and_intake_fields():
    for t in DATA["tickets"]:
        for f in RATINGS:
            assert isinstance(t.get(f), int) and 0 <= t[f] <= 4, (t["number"], f)
        for f in INTAKE:
            assert f in t, (t["number"], f)


def test_stored_score_and_label_match_the_formula():
    for t in DATA["tickets"]:
        r = score_ticket(t, CONFIG)
        assert t["ai_priority_score"] == r["score"], t["number"]
        assert t["ai_priority"] == r["label"], t["number"]


def test_needs_more_info_tickets_have_questions():
    for t in DATA["tickets"]:
        if t["ai_needs_more_info"]:
            assert t["ai_info_requests"], t["number"]
