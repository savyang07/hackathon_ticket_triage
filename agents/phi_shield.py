"""
PHI Shield Agent

Runs BEFORE any ticket text reaches a language model. It finds patient
identifiers in free text and replaces each one with a placeholder such as
[MRN_1], so the model can still reason about the ticket ("a patient's MRN is
wrong on 7 West") without ever seeing who the patient is.

It also applies data minimization: only the fields the model needs are sent;
caller identity, attachments and work notes are withheld entirely.

This demo version is pattern-based and runs fully offline. In production it
would sit in front of every model call, ideally combined with a dedicated
de-identification service (pattern rules + a clinical NER model), and its
findings would be logged (types and counts only, never the values).

Input:  text (str), optional extra names to mask (e.g. known staff names)
Output: {
    "text":     str,                 # redacted text, safe to send
    "findings": [                    # one per identifier found
        {"type": "MRN", "label": "Medical record number",
         "placeholder": "[MRN_1]", "start": int, "end": int, "original": str}
    ],
    "counts":   {"MRN": 1, ...},
}
"original" is kept only so the demo can show a side-by-side; production
logging would drop it.
"""
import re

# (type, human label, compiled pattern, group index holding the identifier)
# Order matters: specific labelled identifiers first, generic formats last.
_RULES = [
    ("MRN", "Medical record number",
     re.compile(r"\b(?:MRN|medical record (?:number|no\.?|#))\s*[:#]?\s*(\d{6,10})\b", re.I), 1),
    ("FIN", "Encounter / FIN number",
     re.compile(r"\b(?:FIN|encounter(?: number| no\.?| #)?)\s*[:#]?\s*(\d{6,10})\b", re.I), 1),
    ("DOB", "Date of birth",
     re.compile(r"\b(?:DOB|date of birth|born(?: on)?)\s*[:#]?\s*"
                r"(\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2})", re.I), 1),
    ("SSN", "Social Security number",
     re.compile(r"\b(\d{3}-\d{2}-\d{4})\b"), 1),
    ("PHONE", "Phone number",
     re.compile(r"(\(?\b\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b)"), 1),
    ("EMAIL", "Email address",
     re.compile(r"\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b"), 1),
    ("PATIENT", "Patient name",
     re.compile(r"\b(?:patient|pt\.?)(?: name)?[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)"), 1),
]

LABELS = {t: label for t, label, _, _ in _RULES}
LABELS["STAFF"] = "Staff name (minimized, not PHI)"

# Fields the model needs vs. fields it never receives.
SENT_FIELDS = ["short_description", "description", "type", "channel", "caller_dept",
               "justification_text", "when_needed", "is_recurring", "frequency", "analytics_type"]
WITHHELD_FIELDS = {
    "caller": "Caller name: routing uses the department, not the person",
    "caller_email / phone": "Contact details are never needed to triage",
    "attachments": "Screenshots and files can contain PHI; excluded entirely",
    "work_notes / comments": "Internal notes can quote patient details; excluded",
}


def shield(text: str, staff_names=None) -> dict:
    """Redact identifiers in `text`. The same value always gets the same placeholder."""
    text = text or ""
    spans = []  # (start, end, type, original)
    for typ, _label, pat, grp in _RULES:
        for m in pat.finditer(text):
            s, e = m.span(grp)
            if any(s < pe and e > ps for ps, pe, _, _ in spans):
                continue  # already covered by a more specific rule
            spans.append((s, e, typ, m.group(grp)))
    for name in sorted({n for n in (staff_names or []) if n and len(n) > 2}, key=len, reverse=True):
        for m in re.finditer(r"\b" + re.escape(name) + r"\b", text):
            s, e = m.span()
            if not any(s < pe and e > ps for ps, pe, _, _ in spans):
                spans.append((s, e, "STAFF", m.group(0)))
    spans.sort()

    placeholders, counters, findings, out, pos = {}, {}, [], [], 0
    for s, e, typ, orig in spans:
        key = (typ, orig.lower())
        if key not in placeholders:
            counters[typ] = counters.get(typ, 0) + 1
            placeholders[key] = f"[{typ}_{counters[typ]}]"
        ph = placeholders[key]
        out.append(text[pos:s])
        out.append(ph)
        pos = e
        findings.append({"type": typ, "label": LABELS[typ], "placeholder": ph,
                         "start": s, "end": e, "original": orig})
    out.append(text[pos:])

    counts = {}
    for f in findings:
        counts[f["type"]] = counts.get(f["type"], 0) + 1
    return {"text": "".join(out), "findings": findings, "counts": counts}


def shield_ticket(ticket: dict, staff_names=None) -> dict:
    """
    Build exactly what the model would receive for one ticket: only SENT_FIELDS,
    with free-text fields redacted. Returns the payload plus all findings.
    """
    names = list(staff_names or [])
    if ticket.get("caller") and ticket.get("caller_dept") != "Automated":
        names.append(str(ticket["caller"]))
        names.extend(p for p in str(ticket["caller"]).replace("Dr.", "").split() if len(p) > 2)
    payload, findings = {}, []
    for f in SENT_FIELDS:
        if f not in ticket:
            continue
        v = ticket[f]
        if isinstance(v, str) and f in ("short_description", "description", "justification_text"):
            r = shield(v, names)
            payload[f] = r["text"]
            findings.extend({**x, "field": f} for x in r["findings"])
        else:
            payload[f] = v
    phi = [x for x in findings if x["type"] != "STAFF"]
    return {"payload": payload, "findings": findings, "phi_count": len(phi),
            "staff_count": len(findings) - len(phi)}


def highlight_html(text: str, findings: list, mode: str = "original") -> str:
    """
    Render text with identifiers highlighted (original) or placeholders highlighted
    (redacted). Used only for the demo's side-by-side view.
    """
    import html
    if mode == "redacted":
        parts = re.split(r"(\[[A-Z]+_\d+\])", text)
        return "".join(
            f'<mark style="background:#E2F2F1;color:#0F6E6E;border-radius:4px;padding:0 3px;'
            f'font-weight:600">{html.escape(p)}</mark>' if re.fullmatch(r"\[[A-Z]+_\d+\]", p)
            else html.escape(p) for p in parts)
    out, pos = [], 0
    for f in sorted(findings, key=lambda x: x["start"]):
        out.append(html.escape(text[pos:f["start"]]))
        out.append(f'<mark style="background:#FCE9E8;color:#7A1F1D;border-radius:4px;padding:0 3px" '
                   f'title="{html.escape(f["label"])}">{html.escape(text[f["start"]:f["end"]])}</mark>')
        pos = f["end"]
    out.append(html.escape(text[pos:]))
    return "".join(out)
