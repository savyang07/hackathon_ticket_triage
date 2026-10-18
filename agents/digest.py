"""
Weekly Leadership Digest

Turns the triaged queue (this week) and the weekly history (trend) into a short
summary a manager can forward: headline numbers, what needs attention, recurring
problems worth a permanent fix, and estimated time saved.

Demo: assembled offline from the numbers by a template, so every figure is
traceable to the data. Production: the same numbers would be handed to the
language model to write the narrative, with the numbers table attached so a
reviewer can check every claim before it is sent.

Input:  tickets (list of dicts), groups (dict), history (dict from
        weekly_history.json), manual_min / review_min (sidebar assumptions), now
Output: dict with "headline", "metrics", "attention", "recurring", "clinical",
        "hours_saved_week", "markdown"
"""
from datetime import datetime


def _issues(tickets: list, groups: dict) -> list:
    """One entry per issue: a duplicate group counts once, at its highest score."""
    out = []
    for gid, g in groups.items():
        members = [t for t in tickets if t.get("group_id") == gid]
        if not members:
            continue
        top = max(members, key=lambda t: t["ai_priority_score"])
        parent = next((t for t in members if t.get("group_role") == "parent"), top)
        out.append({
            "key": gid, "title": g["title"], "score": top["ai_priority_score"],
            "label": top["ai_priority"], "queue": parent["ai_route_queue"], "n": len(members),
            "patient_safety": max(t.get("ai_patient_safety", 0) for t in members),
            "needs_info": any(t.get("ai_needs_more_info") for t in members),
        })
    for t in tickets:
        if not t.get("group_id"):
            out.append({
                "key": t["number"], "title": t["ai_summary"], "score": t["ai_priority_score"],
                "label": t["ai_priority"], "queue": t["ai_route_queue"], "n": 1,
                "patient_safety": t.get("ai_patient_safety", 0),
                "needs_info": bool(t.get("ai_needs_more_info")),
            })
    return sorted(out, key=lambda i: -i["score"])


def build_digest(tickets: list, groups: dict, history: dict, manual_min: float, review_min: float,
                 now: datetime, critical_label: str = "Critical") -> dict:
    issues = _issues(tickets, groups)
    weeks = history.get("weeks", [])
    last4 = weeks[-4:] if weeks else []

    n_tickets, n_issues = len(tickets), len(issues)
    critical = [i for i in issues if i["label"] == critical_label]
    needs_info = sum(1 for t in tickets if t.get("ai_needs_more_info"))
    mistyped = sum(1 for t in tickets if t.get("ai_should_be_request"))
    misrouted = sum(1 for t in tickets if "not DE" in str(t.get("ai_route_queue", "")))
    phi_reports = [t for t in tickets if t.get("ai_category") == "Security / PHI"]
    clinical = [i for i in issues if i["patient_safety"] >= 3]

    avg_tickets = sum(w["tickets"] for w in last4) / len(last4) if last4 else n_tickets
    avg_unique = sum(w["unique_issues"] for w in last4) / len(last4) if last4 else n_issues
    hours_saved_week = max(0.0, (avg_tickets * manual_min - avg_unique * review_min) / 60)

    # Recurring root causes: weeks seen in history, plus whether it's in today's queue.
    recurring = []
    kw = history.get("recurring_keywords", {})
    for name, words in kw.items():
        counts = [w["recurring"].get(name, 0) for w in weeks]
        in_queue = [g for g in groups.values()
                    if any(x.lower() in g["title"].lower() for x in words)]
        recurring.append({
            "name": name,
            "weeks_seen": sum(1 for c in counts if c) + (1 if in_queue else 0),
            "of_weeks": len(weeks) + 1,
            "tickets_8wk": sum(counts),
            "in_queue_now": bool(in_queue),
        })
    recurring.sort(key=lambda r: (-r["weeks_seen"], -r["tickets_8wk"]))

    phi_keys = {t["number"] for t in phi_reports}
    attention = []
    for i in critical:
        line = (f"**{i['title'].rstrip('.')}**: {i['label']} ({i['score']}), {i['n']} ticket"
                f"{'s' if i['n'] != 1 else ''}, routed to {i['queue']}.")
        rec = next((r for r in recurring if r["in_queue_now"] and r["weeks_seen"] >= 3 and any(
            w.lower() in i["title"].lower() for w in kw.get(r["name"], []))), None)
        if rec:
            line += (f" This has happened in {rec['weeks_seen']} of the last {rec['of_weeks']} weeks; "
                     "a permanent fix would stop the repeat tickets.")
        if i["key"] in phi_keys:
            line += " Privacy Office should be informed."
        attention.append(line)
    for t in phi_reports:
        if t["number"] not in {i["key"] for i in critical}:
            attention.append(f"**Possible PHI exposure reported** ({t['number']}). Escalated to Data Access & "
                             "Security; Privacy Office should be informed.")
    if mistyped or misrouted:
        attention.append(
            f"**{mistyped + misrouted} tickets arrived as the wrong type or for the wrong team**: {mistyped} requests "
            f"filed as incidents (mostly by email, starting the wrong SLA clock) and {misrouted} that belong to the "
            "IT Service Desk. Both patterns repeat every week; a portal request form and a help-desk routing "
            "rule would prevent most of them.")

    headline = (f"{n_tickets} open tickets collapse into {n_issues} unique issues; "
                f"{len(critical)} critical, {needs_info} waiting on the requester.")

    md = [f"# Weekly triage digest: Data Engineering queue",
          f"_Prepared {now:%a %b %d, %Y} for review before sending. Trend figures are synthetic._", "",
          f"**{headline}**", "",
          "## Headline numbers",
          f"- Open tickets: {n_tickets} (unique issues: {n_issues}; duplicates collapsed: {n_tickets - n_issues})",
          f"- Critical issues: {len(critical)}",
          f"- Waiting on requester: {needs_info}",
          f"- Filed as the wrong type or sent to the wrong team: {mistyped + misrouted}",
          f"- Estimated on-call triage time saved: ~{hours_saved_week:.1f} hours/week "
          f"(assumes {manual_min:g} min manual per ticket vs {review_min:g} min review per issue)", "",
          "## Needs attention"] + [f"- {a}" for a in attention] + ["",
          "## Patient-care related issues"] + [f"- {i['title'].rstrip('.')} ({i['label']}, {i['score']})" for i in clinical] + ["",
          "## Recurring problems (last 9 weeks)"] + [
          f"- {r['name']}: {r['weeks_seen']} of {r['of_weeks']} weeks, {r['tickets_8wk']} tickets in prior 8 weeks"
          + (" (in queue now)" if r["in_queue_now"] else "") for r in recurring]

    return {
        "headline": headline,
        "metrics": {"tickets": n_tickets, "issues": n_issues, "duplicates": n_tickets - n_issues,
                    "critical": len(critical), "needs_info": needs_info, "mistyped": mistyped,
                    "misrouted": misrouted, "avg_tickets_4wk": avg_tickets, "avg_unique_4wk": avg_unique},
        "attention": attention,
        "critical": critical,
        "clinical": clinical,
        "recurring": recurring,
        "hours_saved_week": hours_saved_week,
        "markdown": "\n".join(md),
    }
