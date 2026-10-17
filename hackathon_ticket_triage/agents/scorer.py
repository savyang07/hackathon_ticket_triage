"""
Priority Scorer Agent

In the demo, every ticket already has a precomputed ai_priority_score
(0–100) baked into tickets.json. This module's job is to:
  1. Return that score and the correct priority label.
  2. Generate a factor-by-factor BREAKDOWN so judges can see how the
     score is explained — this is the explainability story.

The breakdown allocates the precomputed total across the config factors
using their relative weights. In production, this agent would receive raw
ticket data and compute each factor score from real signals (ticket metadata,
SLA data, on-call calendars). The output shape stays identical.

Input:  ticket dict (from tickets.json), scoring config dict (from
        config/scoring.json)
Output: {
    "score": int,            # same as ticket["ai_priority_score"]
    "label": str,            # e.g. "P1 – Critical"
    "breakdown": [           # one entry per config factor
        {"key": str, "label": str, "weight": int, "points": int}
    ]
}
"""
import json
from pathlib import Path


def score_ticket(ticket: dict, config: dict) -> dict:
    """
    Return score, label, and a weighted breakdown for a single ticket.

    The breakdown splits the precomputed score proportionally across the
    config factors. This makes scoring explainable without changing any
    scores in the demo data.
    """
    score = int(ticket["ai_priority_score"])
    label = _label_for_score(score, config["thresholds"], config["labels"])
    breakdown = _build_breakdown(score, config["factors"])
    return {"score": score, "label": label, "breakdown": breakdown}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _label_for_score(score: int, thresholds: dict, labels: dict) -> str:
    if score >= thresholds["p1_min"]:
        return labels["P1"]
    if score >= thresholds["p2_min"]:
        return labels["P2"]
    if score >= thresholds["p3_min"]:
        return labels["P3"]
    return labels["P4"]


def _build_breakdown(score: int, factors: list) -> list:
    """
    Allocate `score` points across factors proportionally by weight.

    Uses integer division + largest-remainder to ensure sum == score exactly.
    """
    total_weight = sum(f["weight"] for f in factors)
    if total_weight == 0 or score == 0:
        return [{"key": f["key"], "label": f["label"], "weight": f["weight"], "points": 0}
                for f in factors]

    # Raw proportional allocation (may not be integer)
    raw = [score * f["weight"] / total_weight for f in factors]

    # Floor each value
    floored = [int(r) for r in raw]
    remainder = score - sum(floored)

    # Distribute remaining points to the factors with the largest fractional parts
    fractions = sorted(
        range(len(factors)),
        key=lambda i: raw[i] - floored[i],
        reverse=True,
    )
    for i in range(remainder):
        floored[fractions[i]] += 1

    return [
        {
            "key": factors[i]["key"],
            "label": factors[i]["label"],
            "weight": factors[i]["weight"],
            "points": floored[i],
        }
        for i in range(len(factors))
    ]
