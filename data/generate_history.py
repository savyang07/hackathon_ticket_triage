"""
Builds data/weekly_history.json: 8 complete weeks of SYNTHETIC queue history
(Aug 17 – Oct 11, 2026) for the Weekly Digest tab. Values are hand-set to be
plausible and internally consistent; they are illustrative, not measured.

    python data/generate_history.py
"""
import json
from pathlib import Path

WEEKS = ["2026-08-17", "2026-08-24", "2026-08-31", "2026-09-07",
         "2026-09-14", "2026-09-21", "2026-09-28", "2026-10-05"]

TICKETS        = [126, 141, 118, 133, 129, 137, 151, 144]
UNIQUE_ISSUES  = [ 81,  86,  77,  84,  82,  85,  90,  88]
CRITICAL       = [  3,   5,   2,   3,   4,   3,   6,   4]
SLA_BREACHES   = [  7,   9,   5,   8,   6,   8,  11,   9]
NEEDS_INFO     = [ 11,  13,   9,  12,  10,  12,  14,  13]
MISTYPED       = [ 19,  22,  17,  20,  18,  21,  24,  22]   # incidents that should have been requests
MISROUTED      = [  6,   8,   5,   7,   6,   7,   9,   8]   # not Data Engineering work

# Recurring root causes: count of tickets per week tied to each one.
RECURRING = {
    "Cerner ADT nightly load failure": {
        "keywords": ["ADT"],
        "counts": [7, 0, 0, 6, 0, 0, 8, 0],
    },
    "Redshift query queue saturation": {
        "keywords": ["Redshift", "WLM"],
        "counts": [0, 0, 5, 0, 0, 4, 0, 0],
    },
    "Dashboard access requested by email": {
        "keywords": ["access"],
        "counts": [4, 6, 3, 5, 4, 5, 7, 6],
    },
    "Login and password tickets sent to Data Engineering": {
        "keywords": ["Login", "password"],
        "counts": [2, 3, 2, 3, 1, 2, 3, 2],
    },
    "Lab results feed delayed": {
        "keywords": ["Lab"],
        "counts": [0, 3, 0, 0, 4, 0, 0, 0],
    },
}


def main():
    weeks = []
    for i, w in enumerate(WEEKS):
        weeks.append({
            "week_start": w,
            "tickets": TICKETS[i],
            "unique_issues": UNIQUE_ISSUES[i],
            "critical_issues": CRITICAL[i],
            "sla_breaches": SLA_BREACHES[i],
            "needs_info": NEEDS_INFO[i],
            "mistyped_incidents": MISTYPED[i],
            "misrouted": MISROUTED[i],
            "recurring": {k: v["counts"][i] for k, v in RECURRING.items()},
        })
    payload = {
        "_note": "SYNTHETIC history for the demo digest. Illustrative only; not measured data.",
        "recurring_keywords": {k: v["keywords"] for k, v in RECURRING.items()},
        "weeks": weeks,
    }
    out = Path(__file__).parent / "weekly_history.json"
    out.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {len(weeks)} weeks to {out}")


if __name__ == "__main__":
    main()
