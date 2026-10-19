"""
PHI Shield tab

Shows how ticket text is de-identified and minimized before any model sees it:
  1. A try-it panel with fictional tickets that contain patient identifiers
  2. Exactly which fields are sent to the model and which are withheld
  3. A scan of the current queue (identifiers found per ticket)
  4. How this maps to the production architecture
"""
import html

import pandas as pd
import streamlit as st

from agents.phi_shield import (LABELS, SENT_FIELDS, WITHHELD_FIELDS, highlight_html, shield,
                               shield_ticket)
from ui.components import pill

# All identifiers below are fictional (555 phone numbers, example.org, the textbook fake SSN).
SAMPLES = {
    "Stale census with patient details":
        "Bed census still lists patient Maria Delgado (MRN 004518823, DOB 03/14/1958) on 7 West after "
        "discharge yesterday. FIN 70112345. Please fix before the 8am huddle. Call me at 323-555-0148. Thanks, Angela",
    "Missing lab result":
        "Lab results are missing in the warehouse for pt John Rivera, MRN: 88231457. The result posted in "
        "PowerChart at 6:10. Reply to angela.brooks@example.org when the feed is fixed.",
    "Duplicate encounters in a report":
        "Readmissions report double counts FIN 55120934 and FIN 55120935 for the same patient. "
        "The face sheet shows SSN 123-45-6789 and DOB 1958-03-14.",
    "No identifiers (passes through unchanged)":
        "Talend job CERNER_ADT_DAILY failed at 02:14 with a Redshift connection timeout. Bed census is stale.",
}


def render_phi(df: pd.DataFrame) -> None:
    st.markdown(
        "**Patient identifiers never reach the model.** Before any ticket text is summarized or scored, "
        "the PHI shield replaces each identifier with a placeholder, and only the fields needed for "
        "triage are sent. The model can still understand *a patient's MRN is wrong on 7 West*, "
        "without ever knowing who the patient is."
    )

    # ── 1. Try it ────────────────────────────────────────────────────────────
    st.markdown("#### Try it")
    s = st.selectbox("Example ticket (fictional identifiers)", list(SAMPLES), key="phi_sample")
    text = st.text_area("Ticket text", SAMPLES[s], height=100, key=f"phi_txt_{s}")
    staff = st.toggle("Also mask staff names in sign-offs (not PHI, but minimized)", value=True,
                      key="phi_staff")
    res = shield(text, ["Angela", "Angela Brooks"] if staff else [])

    counts = res["counts"]
    n_phi = sum(v for t, v in counts.items() if t != "STAFF")
    badge_html = "".join(
        pill(f"{v} × {LABELS[t]}", "#7A1F1D" if t != "STAFF" else "#52514E",
             "#FCE9E8" if t != "STAFF" else "#F0F2F5") for t, v in counts.items()
    ) or pill("No identifiers found", "#0B5D2A", "#E3F4E8")
    st.markdown(f"**{n_phi} patient identifier{'s' if n_phi != 1 else ''} removed** &nbsp; {badge_html}",
                unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1.container(border=True):
        st.markdown("<span class='muted'>Submitted to ServiceNow</span>", unsafe_allow_html=True)
        st.markdown(highlight_html(text, res["findings"], "original"), unsafe_allow_html=True)
    with c2.container(border=True):
        st.markdown("<span class='muted'>What the model receives</span>", unsafe_allow_html=True)
        st.markdown(highlight_html(res["text"], [], "redacted"), unsafe_allow_html=True)
    if res["findings"]:
        st.caption("The same value always gets the same placeholder, so the model can still tell that two "
                   "mentions refer to the same patient or encounter. The mapping never leaves Keck's systems.")

    # ── 2. Data minimization ─────────────────────────────────────────────────
    st.markdown("#### Only the fields triage needs are sent")
    m1, m2 = st.columns(2)
    with m1.container(border=True):
        st.markdown("**Sent to the model** (free text shielded first)")
        st.markdown("\n".join(f"- `{f}`" for f in SENT_FIELDS))
    with m2.container(border=True):
        st.markdown("**Never sent**")
        st.markdown("\n".join(f"- `{f}`: {why}" for f, why in WITHHELD_FIELDS.items()))

    # ── 3. Queue scan ────────────────────────────────────────────────────────
    st.markdown("#### Scan of the current queue")
    rows, phi_total, staff_total = [], 0, 0
    for t in df.to_dict("records"):
        r = shield_ticket(t)
        phi_total += r["phi_count"]
        staff_total += r["staff_count"]
        rows.append({
            "Ticket": t["number"],
            "Short description": t["short_description"],
            "Patient identifiers removed": r["phi_count"],
            "Staff names masked": r["staff_count"],
            "Reports a PHI exposure": "Yes" if t.get("ai_category") == "Security / PHI" else "",
        })
    flagged = [r for r in rows if r["Reports a PHI exposure"]]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Tickets scanned", len(rows))
    k2.metric("Patient identifiers removed", phi_total)
    k3.metric("Staff names masked", staff_total)
    k4.metric("Tickets reporting a PHI exposure", len(flagged),
              help="Routed to Data Access & Security and flagged for the Privacy Office.")
    st.caption(
        f"The synthetic tickets contain no patient identifiers, so nothing is removed here; the examples "
        f"above show what happens when they do. "
        + (f"{', '.join(r['Ticket'] for r in flagged)} *describes* a PHI exposure in a shared workbook and is "
           f"escalated, but its text contains no identifiers itself." if flagged else "")
    )
    with st.expander("Per-ticket scan results"):
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    # ── 4. Production path ───────────────────────────────────────────────────
    with st.expander("How this works in production"):
        st.markdown(
            "1. **Read tickets through a scoped, read-only ServiceNow account** that returns only the "
            "fields listed above (no attachments, comments or caller contact details).\n"
            "2. **Run the PHI shield inside Keck's network** before any model call; log identifier "
            "*types and counts* only, never the values.\n"
            "3. **Call the model inside an approved environment** (for example, a model hosted in Keck's own "
            "cloud account). Confirm the setup with Information Security and the Privacy Office.\n"
            "4. **Pattern rules + a clinical de-identification model** in production; this demo uses "
            "pattern rules only.\n"
            "5. **Nothing is written back** to ServiceNow until a person approves it (see Audit trail)."
        )
    st.caption("All identifiers on this page are fictional.")
