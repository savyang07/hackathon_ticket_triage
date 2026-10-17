"""
Tests for agents/scorer.py

The scorer takes a precomputed ticket and a scoring config, and returns a
priority label plus a factor-by-factor breakdown that sums to the ticket's
precomputed score. These tests ensure the breakdown is consistent and the
thresholds are applied correctly.
"""
import json
import sys
from pathlib import Path

# Make sure the repo root is on the path when running via pytest from any dir
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.scorer import score_ticket

# Load the real config so tests use the same thresholds as the app
_config = json.loads((Path(__file__).parent.parent / "config" / "scoring.json").read_text())


def _ticket(score: int, category: str = "Pipeline failure") -> dict:
    """Minimal synthetic ticket dict for testing."""
    return {
        "ai_priority_score": score,
        "ai_category": category,
        "ai_priority": "P1 – Critical",  # will be overridden by scorer
        "ai_should_be_request": False,
    }


# ── Threshold tests ──────────────────────────────────────────────────────────

def test_score_at_p1_threshold_returns_p1():
    result = score_ticket(_ticket(85), _config)
    assert result["label"] == "P1 – Critical", f"Expected P1 for score 85, got {result['label']}"


def test_score_just_below_p1_returns_p2():
    result = score_ticket(_ticket(84), _config)
    assert result["label"] == "P2 – High", f"Expected P2 for score 84, got {result['label']}"


def test_score_at_p2_threshold_returns_p2():
    result = score_ticket(_ticket(65), _config)
    assert result["label"] == "P2 – High", f"Expected P2 for score 65, got {result['label']}"


def test_score_at_p3_threshold_returns_p3():
    result = score_ticket(_ticket(40), _config)
    assert result["label"] == "P3 – Medium", f"Expected P3 for score 40, got {result['label']}"


def test_score_below_p3_returns_p4():
    result = score_ticket(_ticket(20), _config)
    assert result["label"] == "P4 – Low", f"Expected P4 for score 20, got {result['label']}"


# ── Breakdown tests ──────────────────────────────────────────────────────────

def test_breakdown_has_one_entry_per_factor():
    result = score_ticket(_ticket(72), _config)
    n_factors = len(_config["factors"])
    assert len(result["breakdown"]) == n_factors, (
        f"Expected {n_factors} breakdown entries, got {len(result['breakdown'])}"
    )


def test_breakdown_entries_have_required_keys():
    result = score_ticket(_ticket(55), _config)
    for entry in result["breakdown"]:
        assert "label" in entry, f"Breakdown entry missing 'label': {entry}"
        assert "points" in entry, f"Breakdown entry missing 'points': {entry}"
        assert "weight" in entry, f"Breakdown entry missing 'weight': {entry}"


def test_breakdown_points_sum_equals_score():
    """Breakdown points must sum to exactly the ticket's precomputed score."""
    ticket = _ticket(72)
    result = score_ticket(ticket, _config)
    total = sum(e["points"] for e in result["breakdown"])
    assert total == ticket["ai_priority_score"], (
        f"Breakdown sum {total} != score {ticket['ai_priority_score']}"
    )


def test_breakdown_points_sum_equals_score_for_p1():
    ticket = _ticket(97)
    result = score_ticket(ticket, _config)
    total = sum(e["points"] for e in result["breakdown"])
    assert total == 97, f"Breakdown sum {total} != 97"


def test_score_passthrough_matches_input():
    """The returned 'score' field must equal the ticket's ai_priority_score."""
    ticket = _ticket(63)
    result = score_ticket(ticket, _config)
    assert result["score"] == 63
