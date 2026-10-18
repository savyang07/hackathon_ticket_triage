"""
Audit Trail

Every decision about a ticket is recorded: what the AI suggested, and what a
person did with it (approved, overrode, rerouted, asked the requester for more
information). Nothing is written back to ServiceNow until a person approves.

Demo: entries live in the Streamlit session and can be exported to CSV.
Production: entries would be appended to an immutable table (e.g. a Redshift
audit table) and mirrored as ServiceNow work notes, so every score has a
traceable "who decided, when, and why".

Entry shape:
{
  "time": "2026-10-15 09:00:03", "actor": "Triage AI v0.3", "actor_type": "AI" | "Human",
  "target": "INC0104493" or "GRP-01", "ticket": "INC0104493",
  "action": "Scored" | "Grouped" | "Approved" | "Overrode priority" | "Rerouted" | "Requested info",
  "before": str, "after": str, "reason": str,
}
"""
from datetime import datetime

ACTIONS_HUMAN = ("Approved", "Overrode priority", "Rerouted", "Requested info")
COLUMNS = ["time", "actor", "actor_type", "action", "target", "ticket", "before", "after", "reason"]


def make_entry(time, actor, actor_type, action, target, ticket="", before="", after="", reason=""):
    if isinstance(time, datetime):
        time = time.strftime("%Y-%m-%d %H:%M:%S")
    return {"time": time, "actor": actor, "actor_type": actor_type, "action": action,
            "target": target, "ticket": ticket or target, "before": before, "after": after,
            "reason": reason}


def seed_ai_entries(tickets: list, groups: dict, when: datetime, ai_version: str) -> list:
    """The AI's own suggestions become the first entries of the trail."""
    out, sec = [], 0
    for t in sorted(tickets, key=lambda x: x["number"]):
        sec += 1
        if t.get("ai_needs_more_info"):
            after = "Not scored: needs more information from requester"
        else:
            after = f"{t['ai_priority']} ({t['ai_priority_score']}) → {t['ai_route_queue']} / {t['ai_route_owner']}"
        out.append(make_entry(_at(when, sec), ai_version, "AI", "Scored", t["number"], t["number"],
                              "", after, t.get("ai_rationale", "")))
    for gid, g in sorted(groups.items()):
        sec += 1
        members = [t["number"] for t in tickets if t.get("group_id") == gid]
        parent = next((t["number"] for t in tickets
                       if t.get("group_id") == gid and t.get("group_role") == "parent"), "")
        out.append(make_entry(_at(when, sec), ai_version, "AI", "Grouped", gid, parent, "",
                              f"{len(members)} tickets: {', '.join(members)}", g.get("title", "")))
    return out


def review_stats(entries: list, n_issues: int) -> dict:
    """
    How people responded to the AI. The latest human decision per target counts.
    Agreement = issues approved as suggested ÷ issues reviewed (approved, overridden or rerouted).
    """
    latest = {}
    for e in entries:
        if e["actor_type"] == "Human" and e["action"] in ("Approved", "Overrode priority", "Rerouted"):
            latest[e["target"]] = e["action"]
    reviewed = len(latest)
    approved = sum(1 for a in latest.values() if a == "Approved")
    info = len({e["target"] for e in entries if e["action"] == "Requested info"})
    return {
        "reviewed": reviewed,
        "pending": max(0, n_issues - reviewed),
        "approved": approved,
        "overridden": sum(1 for a in latest.values() if a == "Overrode priority"),
        "rerouted": sum(1 for a in latest.values() if a == "Rerouted"),
        "info_requested": info,
        "agreement": (approved / reviewed) if reviewed else None,
    }


def _at(when: datetime, seconds: int) -> str:
    from datetime import timedelta
    return (when + timedelta(seconds=seconds)).strftime("%Y-%m-%d %H:%M:%S")
