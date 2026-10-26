"""
Data minimization

Builds what the model receives for one ticket: only the fields triage needs, with the
text exactly as the requester wrote it (patient details included). The model runs under
Keck's HIPAA business associate agreement (BAA), so ticket text is not de-identified;
HIPAA's minimum-necessary rule still applies, so fields triage doesn't use are not sent.

Reviewers are not affected: they see the full ticket in ServiceNow and in the dashboard.

Input:  ticket dict (from tickets.json / ServiceNow)
Output: dict with only TRIAGE_FIELDS
"""

TRIAGE_FIELDS = ["short_description", "description", "type", "channel", "caller_dept",
                 "justification_text", "when_needed", "is_recurring", "frequency", "analytics_type"]

NOT_SENT = {
    "caller_email / phone": "Contact details aren't needed to triage",
    "attachments": "Screenshots and files aren't needed to triage",
    "work_notes / comments": "Internal notes aren't needed to triage",
}


def minimize_ticket(ticket: dict) -> dict:
    """Return only the fields triage needs, values unchanged."""
    return {f: ticket[f] for f in TRIAGE_FIELDS if f in ticket}
