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
