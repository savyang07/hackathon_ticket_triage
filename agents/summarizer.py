"""
Summarizer Agent

Reads each ticket and produces a short, plain-English summary of what the
user is reporting. Called by agents/pipeline.py for every ticket.

Demo mode returns the stored model summary from tickets.json. In production
this agent calls a model hosted in Keck's approved AWS account (for example
Amazon Bedrock) and returns the same shape, so the app needs no changes.

The model only ever receives the PHI-shielded payload built by
agents/phi_shield.shield_ticket(): the minimized fields, with patient
identifiers replaced by placeholders. It never receives the raw ticket.

Input:  ticket dict (from tickets.json), shielded payload dict
Output: {"summary": str}
"""

# True: return stored demo summaries. False: call the model in _call_llm().
DEMO_MODE = True


def summarize(ticket: dict, payload: dict | None = None) -> dict:
    """
    Return a short summary for a single ticket.

    `payload` is the shielded payload from shield_ticket(); it is the only thing
    a live model call may use.
    """
    if DEMO_MODE:
        return {"summary": ticket.get("ai_summary") or ticket.get("short_description", "")}
    if payload is None:
        raise ValueError("Live summarization needs the PHI-shielded payload, not the raw ticket.")
    return _call_llm(payload)  # pragma: no cover


def _call_llm(payload: dict) -> dict:  # pragma: no cover
    """
    Production implementation: summarize the shielded payload.

    Prompt pattern:
        "Summarize this ServiceNow ticket in one plain sentence (max 20 words),
         focusing on what is broken or needed. Ticket: {payload['short_description']}
         {payload['description']}"

    Send it to the model in Keck's AWS account, then return {"summary": text}.
    """
    raise NotImplementedError("Set DEMO_MODE=False only after adding the model call here.")
