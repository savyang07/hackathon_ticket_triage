"""
PHI Shield Agent

Runs BEFORE any ticket text reaches a language model. It finds patient
identifiers in free text and replaces each one with a placeholder such as
[MRN_1], so the model can still reason about the ticket ("a patient's MRN is
wrong on 7 West") without ever seeing who the patient is.

It also applies data minimization: only the fields the model needs are sent;
caller identity, attachments and work notes are withheld entirely.

Covers: MRN / MR# (with letter prefixes), FIN / CSN / encounter and account numbers,
SSNs (dashed, spaced or plain), dates of birth and any full date, phone numbers (with or
without separators), emails, street addresses, ZIP codes, patient names (after a
"patient"/"pt" cue, "Last, First", Mr./Mrs./Ms., or a common first name + surname), and
any bare 7+ digit number. Clinician names ("Dr. ...") and known staff are masked as STAFF.

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

_MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?"
# A full date (day + year). Dates without a year ("10/14") are left alone.
_DATE = (r"(?:\d{1,2}[/-]\d{1,2}[/-](?:\d{4}|\d{2})"
         r"|\d{4}-\d{2}-\d{2}"
         rf"|{_MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}"
         rf"|\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTH},?\s+\d{{4}})")
_STREET = r"(?:St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Dr|Drive|Ln|Lane|Way|Ct|Court|Pl|Place|Pkwy|Parkway|Hwy|Terrace|Ter)"
_NAME = r"[A-Z][a-z'\-]+"
_CUE = r"(?i:\b(?:patient|pt\.?)(?:'s)?(?:\s+name)?\s*[:\-]?\s*)"

# (type, human label, compiled pattern, group index holding the identifier)
# Order matters: a span claimed by an earlier rule is never re-labelled by a later one,
# so specific labelled identifiers come first and generic catch-alls last.
_RULES = [
    ("MRN", "Medical record number",
     re.compile(r"\b(?:MRN|MR\s?#|MR\s?No\.?|medical record(?:\s+(?:number|no\.?|#))?)\s*[:#]?\s*"
                r"([A-Z]{0,3}-?\d{5,12})\b", re.I), 1),
    ("FIN", "Encounter / FIN number",
     re.compile(r"\b(?:FIN|CSN|encounter(?:\s+(?:number|no\.?|#))?|visit\s+(?:number|no\.?|#))\s*[:#]?\s*"
                r"([A-Z]{0,3}\d{6,12})\b", re.I), 1),
    ("ACCOUNT", "Account number",
     re.compile(r"\b(?:acct|account)(?:\s+(?:number|no\.?|#))?\s*[:#]?\s*([A-Z]{0,3}\d{5,14})\b", re.I), 1),
    ("SSN", "Social Security number",
     re.compile(r"\b(?:SSN|social security(?:\s+(?:number|no\.?|#))?)\s*[:#]?\s*(\d{3}[-\s]?\d{2}[-\s]?\d{4})\b",
                re.I), 1),
    ("SSN", "Social Security number",
     re.compile(r"\b(\d{3}-\d{2}-\d{4})\b"), 1),
    ("DOB", "Date of birth",
     re.compile(r"(?:\bDOB|\bD\.O\.B\.?|\bdate of birth|\bbirth\s?date|\bborn(?: on)?)\s*[:#]?\s*(" + _DATE + r")",
                re.I), 1),
    ("DATE", "Full date (day and year)",
     re.compile(r"\b(" + _DATE + r")(?!\d)", re.I), 1),
    ("PHONE", "Phone number",
     re.compile(r"((?:\+?1[-.\s]?)?\(?\b\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b)"), 1),
    ("PHONE", "Phone number",
     re.compile(r"\b(?:call|phone|tel|cell|mobile|pager|fax|ph)\.?\s*[:#]?\s*(?:me\s+)?(?:at\s+)?(\+?1?\d{10})\b", re.I), 1),
    ("EMAIL", "Email address",
     re.compile(r"\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b"), 1),
    ("ADDRESS", "Street address",
     re.compile(r"\b(\d{1,6}\s+(?:[NSEW]\.?\s+)?(?:[A-Z0-9][A-Za-z0-9]*\s+){0,3}" + _STREET + r"\b\.?"
                r"(?:,?\s+(?:Apt|Unit|Ste|Suite|#)\.?\s*\w+)?"
                r"(?:,\s*[A-Z][a-z]+(?:\s[A-Z][a-z]+)*)?(?:,?\s*[A-Z]{2})?(?:\s+\d{5}(?:-\d{4})?)?)"), 1),
    ("ZIP", "ZIP code",
     re.compile(r"\b(?:zip|zip code|postal code)\s*[:#]?\s*(\d{5}(?:-\d{4})?)\b", re.I), 1),
    ("PATIENT", "Patient name",   # patient: Delgado, Maria
     re.compile(_CUE + r"(" + _NAME + r",\s*" + _NAME + r")"), 1),
    ("PATIENT", "Patient name",   # patient Maria (J.) Delgado
     re.compile(_CUE + r"(" + _NAME + r"(?:\s+[A-Z]\.)?(?:\s+" + _NAME + r")+)"), 1),
    ("PATIENT", "Patient name",   # Mrs. Delgado / Mr. John Rivera
     re.compile(r"\b(?:Mr|Mrs|Ms|Miss|Mx)\.?\s+(" + _NAME + r"(?:\s+" + _NAME + r")?)"), 1),
    ("PATIENT", "Patient name",   # patient maria delgado (lowercase; filtered by _LOWER_STOP)
     re.compile(r"(?i:\b(?:patient|pt\.?)(?:'s)?(?:\s+name)?\s*[:\-]?\s*)([a-z][a-z'\-]+\s+[a-z][a-z'\-]+)"), 1),
    ("STAFF", "Staff name (minimized, not PHI)",   # Dr. Hannah Cole: a clinician, not a patient
     re.compile(r"\bDr\.?\s+(" + _NAME + r"(?:\s+" + _NAME + r")?)"), 1),
    ("NAME", "Person name",       # Maria Delgado (known first name + capitalized surname, no cue)
     re.compile(r"\b(" + _NAME + r"\s+" + _NAME + r")\b"), 1),
    ("ID", "Long ID number (possible MRN / account)",
     re.compile(r"(?<![\d.,])\b(\d{7,})\b(?![.,]\d)"), 1),
]

# Capitalized words that follow "patient" in ordinary ticket language and are not names.
_CAP_STOP = {"flow", "safety", "access", "care", "experience", "census", "portal", "services", "service",
             "relations", "satisfaction", "transport", "transfer", "registration", "financial", "accounts",
             "information", "advocacy", "record", "records", "data", "report", "reports", "dashboard",
             "list", "id", "name", "names", "count", "counts", "level", "status", "tracking", "tracker",
             "volume", "volumes", "summary", "details", "identifiers", "team", "unit", "center", "office",
             "management", "logistics", "engagement", "outcomes", "throughput", "placement", "intake",
             "scheduling", "communication", "communications", "education", "liaison", "navigation"}
# Common words that can follow a lowercase "patient ..." and mean it's not a name.
_LOWER_STOP = _CAP_STOP | {
    "is", "was", "has", "had", "in", "on", "at", "the", "a", "an", "and", "or", "to", "from", "with", "without",
    "who", "that", "which", "still", "not", "no", "can", "could", "should", "would", "will", "may", "might",
    "does", "did", "doesn't", "didn't", "are", "were", "be", "been", "being", "for", "of", "by", "as", "if",
    "room", "rooms", "bed", "beds", "transfers", "discharge", "discharged", "admission", "admissions", "admit",
    "admitted", "survey", "results", "result", "labs", "lab", "notes", "note", "population", "populations",
    "cohort", "cohorts", "numbers", "number", "demographics", "address", "addresses", "phone", "email",
    "dob", "age", "ages", "rows", "row", "table", "tables", "chart", "charts", "encounter", "encounters",
    "visit", "visits", "mrn", "mrns", "level", "levels", "types", "type", "class", "classes", "counts",
    "days", "day", "stays", "stay", "load", "loads", "feed", "feeds", "file", "files", "extract", "extracts",
    "facing", "specific", "related", "level", "identifiable", "ids", "info", "details", "detail", "this",
    "these", "those", "his", "her", "their", "its", "my", "our", "your", "seen", "shows", "showing", "listed",
}
# A small list of common first names: enough to catch "Maria Delgado was discharged" with no cue.
# Production would use a clinical de-identification model instead of a name list.
_FIRST_NAMES = set("""
james john robert michael william david richard joseph thomas charles christopher daniel matthew anthony mark
donald steven paul andrew joshua kenneth kevin brian george timothy ronald edward jason jeffrey ryan jacob gary
nicholas eric jonathan stephen larry justin scott brandon benjamin samuel gregory alexander frank patrick
raymond jack dennis jerry tyler aaron jose adam nathan henry douglas zachary peter kyle noah ethan jeremy
walter christian keith roger terry austin sean gerald carl harold dylan arthur lawrence jordan jesse bryan
billy bruce gabriel joe logan alan juan albert willie elijah wayne randy vincent mason roy ralph bobby russell
bradley philip eugene luis carlos miguel jorge alejandro ricardo victor manuel francisco antonio javier
mary patricia jennifer linda elizabeth barbara susan jessica sarah karen lisa nancy betty sandra margaret ashley
kimberly emily donna michelle carol amanda melissa deborah stephanie dorothy rebecca sharon laura cynthia amy
kathleen angela shirley brenda emma anna pamela nicole samantha katherine christine helen debra rachel carolyn
janet maria catherine heather diane olivia julie joyce victoria ruth virginia lauren kelly christina joan
evelyn judith andrea hannah megan cheryl jacqueline martha madison teresa gloria sara janice ann kathryn
abigail sophia frances jean alice judy isabella julia grace amber denise danielle marilyn beverly charlotte
natalie theresa diana brittany doris kayla alexis lori marie rosa ana carmen sofia lucia elena gabriela
priya ravi sam dev luis jordan angela omar linda brian nadia
""".split())

LABELS = {}
for _t, _label, _, _ in _RULES:
    LABELS.setdefault(_t, _label)
LABELS.setdefault("STAFF", "Staff name (minimized, not PHI)")

# Fields the model needs vs. fields it never receives.
SENT_FIELDS = ["short_description", "description", "type", "channel", "caller_dept",
               "justification_text", "when_needed", "is_recurring", "frequency", "analytics_type"]
WITHHELD_FIELDS = {
    "caller": "Caller name: routing uses the department, not the person",
    "caller_email / phone": "Contact details are never needed to triage",
    "attachments": "Screenshots and files can contain PHI; excluded entirely",
    "work_notes / comments": "Internal notes can quote patient details; excluded",
}


def _keep(typ: str, value: str) -> bool:
    """Filters that stop ordinary ticket language from being masked as a name."""
    words = [w.strip(",.").lower() for w in value.replace(",", " ").split()]
    if typ == "PATIENT":
        if value[:1].islower():                       # lowercase form: neither word may be common
            return not any(w in _LOWER_STOP for w in words)
        return not any(w in _CAP_STOP for w in words)
    if typ == "NAME":                                 # no cue: first word must be a known first name
        return words[0] in _FIRST_NAMES and words[-1] not in _CAP_STOP
    return True


def shield(text: str, staff_names=None) -> dict:
    """Redact identifiers in `text`. The same value always gets the same placeholder."""
    text = text or ""
    spans = []  # (start, end, type, original)

    def overlaps(s, e):
        return any(s < pe and e > ps for ps, pe, _, _ in spans)

    # Known staff names first, so a caller's own name is labelled as staff, not as a patient.
    for name in sorted({n for n in (staff_names or []) if n and len(n) > 2}, key=len, reverse=True):
        for m in re.finditer(r"\b" + re.escape(name) + r"\b", text):
            if not overlaps(*m.span()):
                spans.append((*m.span(), "STAFF", m.group(0)))
    for typ, _label, pat, grp in _RULES:
        for m in pat.finditer(text):
            s, e = m.span(grp)
            value = m.group(grp)
            if typ in ("PATIENT", "NAME", "STAFF") and value.endswith("'s"):
                value, e = value[:-2], e - 2   # keep the possessive: "[PATIENT_1]'s daughter"
            if overlaps(s, e) or not _keep(typ, value):
                continue  # already covered by a more specific rule, or ordinary language
            spans.append((s, e, typ, value))
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
