"""
Routing Agent

Decides which queue and owner each ticket should go to, based on its
category, content, and who has resolved similar tickets in the past.
Called by agents/pipeline.py for every ticket.

Demo mode returns the stored routing decision from tickets.json
(ai_route_queue, ai_route_owner, ai_confidence, ai_rationale).

In production, this agent would:
  1. Pull the team calendar and current workload from ServiceNow (read-only).
  2. Look up who resolved similar past tickets.
  3. Ask the model in Keck's approved AWS account to weigh those signals.
The model only ever receives the PHI-shielded payload from
agents/phi_shield.shield_ticket(), never the raw ticket.

Input:  ticket dict, queues dict (queue name → default owner), shielded payload
Output: {
    "queue": str,
    "owner": str,
    "confidence": float,
    "rationale": str,
}
"""

DEMO_MODE = True


def route_ticket(ticket: dict, queues: dict, payload: dict | None = None) -> dict:
    """
    Return the routing decision for a single ticket.

    `payload` is the shielded payload from shield_ticket(); it is the only ticket
    content a live model call may use.
    """
    if DEMO_MODE:
        queue = ticket.get("ai_route_queue") or next(iter(queues))
        return {
            "queue": queue,
            "owner": ticket.get("ai_route_owner") or queues.get(queue, "Unassigned"),
            "confidence": float(ticket.get("ai_confidence", 0.75)),
            "rationale": ticket.get("ai_rationale", ""),
        }
    if payload is None:
        raise ValueError("Live routing needs the PHI-shielded payload, not the raw ticket.")
    return _call_llm(payload, queues)  # pragma: no cover


def _call_llm(payload: dict, queues: dict) -> dict:  # pragma: no cover
    """
    Production implementation: route via the model.

    Send the shielded payload + queue descriptions + workload signals to the model
    in Keck's AWS account and validate that the returned queue is one of `queues`.
    """
    raise NotImplementedError("Set DEMO_MODE=False only after adding the model call here.")
