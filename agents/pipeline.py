"""
Triage pipeline: the one place the app calls the agents.

Runs every ticket through the agents in order and returns what the UI displays:

    1. PHI shield   (agents/phi_shield.py)  minimized, de-identified payload per ticket
    2. Summarizer   (agents/summarizer.py)  one-line summary
    3. Scorer       (agents/scorer.py)      ERWG score, label, needs-more-info questions
    4. Router       (agents/router.py)      queue, owner, confidence, rationale
    5. Grouping     (agents/grouper.py)     duplicate-group assignments + group details

The app never reads ai_summary / ai_route_* / group_id straight from tickets.json any
more: every one of those columns is whatever the agent returned. In demo mode the
agents return stored model outputs; switch an agent's DEMO_MODE off and the app shows
the live result with no UI changes. Agents that would call a model only ever receive
the shielded payload, never the raw ticket.
"""
import json
from collections import Counter
from pathlib import Path

from agents.grouper import find_groups
from agents.phi_shield import shield_ticket
from agents.router import route_ticket
from agents.scorer import score_ticket
from agents.summarizer import summarize

ROOT = Path(__file__).resolve().parent.parent


def load_scoring_config() -> dict:
    return json.loads((ROOT / "config" / "scoring.json").read_text())


def triage_queue(tickets: list, queues: dict, groups: dict, config: dict | None = None) -> dict:
    """
    Run all agents over the queue.

    Returns {"tickets": [...], "groups": {...}, "steps": [...]} where each ticket carries the
    agents' outputs in the ai_* / group_* fields the UI reads, and `steps` is one line of
    real results per agent (shown in the Run Triage animation).
    """
    config = config or load_scoring_config()
    out, phi_total, staff_total = [], 0, 0

    for t in tickets:
        shielded = shield_ticket(t)                                    # 1. PHI shield
        phi_total += shielded["phi_count"]
        staff_total += shielded["staff_count"]
        payload = shielded["payload"]

        summary = summarize(t, payload)                                # 2. Summarizer
        score = score_ticket(t, config)                                # 3. Scorer
        route = route_ticket(t, queues, payload)                       # 4. Router

        out.append({
            **t,
            "ai_summary": summary["summary"],
            "ai_priority_score": score["score"],
            "ai_priority": score["label"],
            "ai_needs_more_info": score["needs_more_info"],
            "ai_info_requests": score["info_requests"],
            "ai_route_queue": route["queue"],
            "ai_route_owner": route["owner"],
            "ai_confidence": route["confidence"],
            "ai_rationale": route["rationale"],
        })

    grouping = find_groups(out, groups)                                # 5. Grouping
    for t in out:
        gid = grouping["assignments"].get(t["number"])
        t["group_id"] = gid or ""
        if not gid:
            t["group_role"] = ""
    found = {g: d for g, d in grouping["groups"].items() if d["member_count"] > 0}

    n = len(out)
    grouped = sum(d["member_count"] for d in found.values())
    labels = Counter(t["ai_priority"] for t in out)
    route_counts = Counter(t["ai_route_queue"] for t in out)
    misrouted = route_counts.get("IT Service Desk (not DE)", 0)
    steps = [
        ("🛡️", "PHI shield",
         f"{n} tickets minimized and scanned: {phi_total} patient identifiers removed, "
         f"{staff_total} staff name{'' if staff_total == 1 else 's'} masked."),
        ("🔍", "Summarizer", f"{n} plain-English summaries written."),
        ("⚖️", "Priority scorer",
         "ERWG scores computed: " + ", ".join(f"{labels.get(k, 0)} {k}"
                                             for k in ("Critical", "High", "Medium", "Low")) + "."),
        ("📬", "Routing agent",
         f"{n} tickets matched to {len(route_counts)} queues"
         + (f"; {misrouted} sent back to the IT Service Desk." if misrouted else ".")),
        ("🔗", "Grouping agent",
         f"{len(found)} duplicate groups absorb {grouped} tickets → {n - grouped + len(found)} unique issues."),
    ]
    return {"tickets": out, "groups": found, "steps": steps}
