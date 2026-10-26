"""
Tests for triage/offline_engine.py (the stand-in for a live model on the "Triage a new ticket" tab).
Ticket text is now scored as written, so mentioning a patient's MRN must not look like a PHI exposure.
All identifiers below are fictional.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from triage.offline_engine import SimilarityIndex, triage  # noqa: E402

DATA = json.loads((ROOT / "data" / "tickets.json").read_text())
IDX = SimilarityIndex(DATA["tickets"])


def _run(text):
    return triage(text, IDX, DATA["queues"])


def test_patient_details_alone_are_not_a_phi_exposure():
    r = _run("Bed census still lists patient Maria Delgado (MRN 004518823, DOB 03/14/1958) on 7 West "
             "after discharge yesterday. FIN 70112345. Please fix before the bed huddle.")
    assert r["category"] != "Security / PHI"
    assert r["queue"] != "DE – Data Access & Security"


def test_real_exposure_still_escalates():
    r = _run("A workbook in the All Staff project shows patient names and MRN numbers; "
             "I think everyone can see it.")
    assert r["category"] == "Security / PHI"
    assert r["queue"] == "DE – Data Access & Security"
    assert r["score"] >= 70
