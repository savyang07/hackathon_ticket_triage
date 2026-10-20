"""Tests for agents/phi_shield.py. All identifiers are fictional."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.phi_shield import SENT_FIELDS, shield, shield_ticket  # noqa: E402

DATA = json.loads((Path(__file__).resolve().parent.parent / "data" / "tickets.json").read_text())


def test_redacts_each_identifier_type():
    text = ("Bed census still lists patient Maria Delgado (MRN 004518823, DOB 03/14/1958). "
            "FIN 70112345. SSN 123-45-6789. Call 323-555-0148 or angela.brooks@example.org")
    r = shield(text)
    for typ in ("PATIENT", "MRN", "DOB", "FIN", "SSN", "PHONE", "EMAIL"):
        assert r["counts"].get(typ) == 1, typ
    for raw in ("Maria Delgado", "004518823", "03/14/1958", "70112345", "123-45-6789",
                "323-555-0148", "angela.brooks@example.org"):
        assert raw not in r["text"], raw
    assert "[MRN_1]" in r["text"] and "[PATIENT_1]" in r["text"]


def test_same_value_same_placeholder_different_values_differ():
    r = shield("FIN 55120934 and FIN 55120935, then FIN 55120934 again")
    assert r["text"] == "FIN [FIN_1] and FIN [FIN_2], then FIN [FIN_1] again"


def test_no_false_positives_on_ordinary_ticket_language():
    for text in ["The Patient Flow team needs access to the dashboard.",
                 "patient names visible to all staff in the workbook",
                 "Talend job CERNER_ADT_DAILY failed at 02:14 with exit code 1",
                 "September case volume is 1,412 but SurgiNet shows 1,438"]:
        assert shield(text)["findings"] == [], text


def test_staff_names_masked_only_when_given():
    assert shield("Thanks, Angela")["findings"] == []
    r = shield("Thanks, Angela", ["Angela"])
    assert r["text"] == "Thanks, [STAFF_1]" and r["counts"] == {"STAFF": 1}


def test_ticket_payload_withholds_caller_and_keeps_only_sent_fields():
    t = next(x for x in DATA["tickets"] if x["number"] == "INC0104520")
    r = shield_ticket(t)
    assert set(r["payload"]) <= set(SENT_FIELDS)
    assert "caller" not in r["payload"]
    assert "Angela" not in r["payload"]["description"]   # caller's sign-off masked
    assert r["phi_count"] == 0 and r["staff_count"] >= 1


def test_synthetic_queue_contains_no_patient_identifiers():
    assert sum(shield_ticket(t)["phi_count"] for t in DATA["tickets"]) == 0


# ── Coverage of common identifier formats (each was missed by the first version) ──────────
import pytest  # noqa: E402

FORMATS = [
    ("MRN 004518823 on 7 West", "004518823"),
    ("MRN: E004518823 on 7 West", "E004518823"),
    ("MR# 004518823 on 7 West", "004518823"),
    ("Patient 004518823 still on census", "004518823"),
    ("DOB 03-14-1958", "03-14-1958"),
    ("D.O.B. 03/14/1958", "03/14/1958"),
    ("seen on 03/14/1958 in clinic", "03/14/1958"),
    ("DOB March 14, 1958", "March 14, 1958"),
    ("call (323) 555-0148", "555-0148"),
    ("call 3235550148", "3235550148"),
    ("call +1 323 555 0148", "555 0148"),
    ("SSN 123456789", "123456789"),
    ("SSN 123 45 6789", "123 45 6789"),
    ("patient: Delgado, Maria", "Delgado"),
    ("Mrs. Delgado is still listed", "Delgado"),
    ("Maria Delgado was discharged yesterday", "Maria Delgado"),
    ("patient maria delgado", "maria delgado"),
    ("Acct # 88231457 billing wrong", "88231457"),
    ("lives at 1200 N State St, Los Angeles 90033", "1200 N State St"),
    ("ZIP 90033", "90033"),
    ("reply to angela.brooks@example.org", "angela.brooks@example.org"),
]


@pytest.mark.parametrize("text,raw", FORMATS)
def test_common_formats_are_redacted(text, raw):
    r = shield(text)
    assert r["findings"], text
    assert raw not in r["text"], (text, r["text"])


ORDINARY = [
    "The Patient Flow team needs access to the dashboard.",
    "patient names visible to all staff in the workbook",
    "Patient Safety Indicator report is blank",
    "patient census report on 7 West",
    "patient is still listed after discharge",
    "pt count is wrong on 5 North",
    "Talend job CERNER_ADT_DAILY failed at 02:14 with exit code 1",
    "September case volume is 1,412 but SurgiNet shows 1,438",
    "Last refresh time says 10/14 11:58 PM. Submission due 10/20.",
    "WLMQueueWaitTime > 300000 ms for 3 datapoints",
    "Error: [Amazon](500150) Error setting/closing connection",
    "Load latest Athena vocabulary (Aug 2026). SNOMED codes from 2026",
    "Task timed out after 900.00 seconds",
    "Bed Capacity dashboard in Tableau",
]


@pytest.mark.parametrize("text", ORDINARY)
def test_ordinary_ticket_language_is_left_alone(text):
    assert shield(text)["findings"] == [], shield(text)["text"]


def test_clinician_names_are_staff_not_patients():
    r = shield("Dr. Hannah Cole requested a sandbox")
    assert r["counts"] == {"STAFF": 1}
