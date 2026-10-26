"""
Summarizer Agent

Reads each ticket and produces a short, plain-English summary of what the
user is reporting. Called by agents/pipeline.py for every ticket.

Demo mode returns the stored model summary from tickets.json. In production
this agent calls Azure OpenAI in Keck's Microsoft tenant (covered by Keck's
HIPAA BAA) and returns the same shape, so the app needs no changes.

The model receives the minimized payload from agents/minimizer.minimize_ticket():
only the fields triage needs, text unchanged (patient details included). The
model runs under Keck's HIPAA business associate agreement.

Input:  ticket dict (from tickets.json), minimized payload dict
Output: {"summary": str}
"""

# True: return stored demo summaries. False: call the model in _call_llm().
DEMO_MODE = True


def summarize(ticket: dict, payload: dict | None = None) -> dict:
    """
    Return a short summary for a single ticket.

    `payload` is the minimized payload from minimize_ticket(); it is the only thing
    a live model call may use.
    """
    if DEMO_MODE:
        return {"summary": ticket.get("ai_summary") or ticket.get("short_description", "")}
    if payload is None:
        raise ValueError("Live summarization needs the minimized payload from minimize_ticket().")
    return _call_llm(payload)  # pragma: no cover


def _call_llm(payload: dict) -> dict:  # pragma: no cover
    """
    Production implementation: summarize the minimized payload.

    Prompt pattern:
        "Summarize this ServiceNow ticket in one plain sentence (max 20 words),
         focusing on what is broken or needed. Ticket: {payload['short_description']}
         {payload['description']}"

    Send it to Azure OpenAI, then return {"summary": text}.
    """
    raise NotImplementedError("Set DEMO_MODE=False only after adding the model call here.")
