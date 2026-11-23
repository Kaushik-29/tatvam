"""
STAIR-Clinical / longitudinal memory tests: FHIR mapping, provenance, derived records,
patient isolation, ToC + path validation, medication exposure rule, retrieval.
"""

import collections
import json

import pytest

from backend.fhir_ingestion.synthea_ingest import BundleMapper
from backend.patient_memory import db as dbmod
from backend.patient_memory.db import session_scope
from backend.patient_memory.models import ClinicalRecord, Document, Patient
from backend.patient_memory.repository import PatientMemory
from backend.rag.query_understanding import understand
from backend.stair_retriever.selector import StructuralSelector
from backend.structured_retrieval.patient_retriever import PatientRetriever
from tests.fixtures.fhir_fixture import bundle


@pytest.fixture()
def memdb(tmp_path):
    dbmod.get_engine(f"sqlite:///{(tmp_path / 't.db').as_posix()}")
    stats, issues = collections.Counter(), collections.Counter()
    with session_scope() as s:
        for pid, pre in (("pat-a", "a"), ("pat-b", "b")):
            p, recs, docs = BundleMapper(f"fixture/{pid}.json", stats, issues).map_bundle(bundle(pid, pre))
            s.add(Patient(**p))
            s.flush()
            s.bulk_insert_mappings(ClinicalRecord, recs)
            s.bulk_insert_mappings(Document, docs)
    yield
    dbmod._engine = None


def test_fhir_mapping_preserves_provenance(memdb):
    with session_scope() as s:
        m = PatientMemory(s, "pat-a")
        htn = m.get("Condition/a-cond-htn")
        assert htn["leaf_path"] == "medical_history/diagnoses"
        assert htn["fhir_resource_id"] == "a-cond-htn" and htn["patient_id"] == "pat-a"
        assert htn["encounter_id"] == "a-enc-1" and htn["verification_status"] == "confirmed"
        assert htn["provenance"]["fhir_resource_type"] == "Condition"
        assert m.get("Condition/a-cond-dizzy")["leaf_path"] == "clinical_encounters/previous_symptoms"
        assert m.get("Condition/a-cond-job")["leaf_path"] == "medical_history/social_history"
        assert m.get("MedicationRequest/a-med-3")["leaf_path"] == "medication_history/current_medications"
        assert m.get("MedicationRequest/a-med-1")["leaf_path"] == "medication_history/previous_medications"
        sbp = m.get("Observation/a-bp#8480-6")
        assert sbp["value_num"] == 148 and sbp["unit"] == "mm[Hg]"
        assert m.get("Observation/a-bp#8462-4")["value_num"] == 92
        note = m.get("DocumentReference/a-note-1")
        assert note["leaf_path"] == "medical_documents/clinical_notes"
        cc = m.get("DocumentReference/a-note-1#cc0")
        assert cc["concept_display"] == "Dizziness" and cc["verification_status"] == "patient_reported"


def test_derived_records_cite_sources(memdb):
    with session_scope() as s:
        m = PatientMemory(s, "pat-a")
        changes = m.records(leaves=["medication_history/medication_changes"])
        dose = [c for c in changes if c["clinical_status"] == "dose_changed"]
        assert len(dose) == 1 and "10 MG" in dose[0]["value_text"] and "20 MG" in dose[0]["value_text"]
        assert set(dose[0]["provenance"]["derived_from"]) == {"MedicationRequest/a-med-1", "MedicationRequest/a-med-2"}
        assert dose[0]["verification_status"] == "derived"
        trend = m.records(leaves=["laboratory_observations/historical_trends"])
        cr = [t for t in trend if "creatinine" in t["concept_key"]][0]
        assert cr["value_text"] == "increasing" and cr["provenance"]["n_sources"] == 3


def test_patient_isolation(memdb):
    with session_scope() as s:
        b = PatientMemory(s, "pat-b")
        assert b.get("Condition/a-cond-htn") is None                   # A's record invisible to B
        assert all(r["patient_id"] == "pat-b" for r in b.records())
        assert b.update_record("Condition/a-cond-htn", concept_display="x") is None
        assert b.delete_record("Condition/a-cond-htn") is False
        recs, invalid = b.resolve_paths(["medical_history/diagnoses/essential_hypertension",
                                         "medical_history/diagnoses/made_up_condition", "not/a/path"])
        assert all(r["patient_id"] == "pat-b" for r in recs) and len(recs) >= 1
        assert set(invalid) == {"medical_history/diagnoses/made_up_condition", "not/a/path"}
    with pytest.raises(ValueError):
        PatientMemory(None, "")


def test_toc_contains_only_real_paths(memdb):
    with session_scope() as s:
        m = PatientMemory(s, "pat-a")
        valid = m.valid_group_paths()
        toc = m.toc()
        groups = [g.path for n in toc for leaf in ([n] + n.children) for g in leaf.children if g.path in valid]
        assert "laboratory_observations/laboratory_results/creatinine_mass_volume_in_serum_or_plasma" in groups
        all_child_paths = [g.path for n in toc for leaf in ([n] + n.children) for g in leaf.children
                           if g.path.count("/") >= 2]
        assert all(p in valid for p in all_child_paths)


def test_medication_exposure_rule(memdb):
    with session_scope() as s:
        m = PatientMemory(s, "pat-a")
        at = {iv["record_id"] for iv in m.medications_active_at("2018-12-01T09:00:00")}
        assert "MedicationRequest/a-med-2" in at                      # chronic refill gap < 400 days
        assert "MedicationRequest/a-med-amox" not in at
        ivs = {iv["record_id"]: iv for iv in m.medication_intervals()}
        assert ivs["MedicationRequest/a-med-1"]["end_uncertain"] is True    # 3-year gap > 400-day cap
        assert ivs["MedicationRequest/a-med-2"]["end_uncertain"] is False
        assert ivs["MedicationRequest/a-med-3"]["interval_end"] is None     # active: open-ended
        assert not m.medications_active_at("2016-06-01T00:00:00") or all(
            iv["end_uncertain"] is False for iv in m.medications_active_at("2016-06-01T00:00:00"))


def test_stair_structural_retrieval_end_to_end(memdb):
    with session_scope() as s:
        m = PatientMemory(s, "pat-a")
        q = "Find my previous kidney-related laboratory results"
        qu = understand(q)
        recs, trace = PatientRetriever(m).stair(q, qu, StructuralSelector(embedder=None))
        assert trace.invalid_paths == []
        assert any("creatinine" in r["concept_key"] for r in recs)
        assert all(r["patient_id"] == "pat-a" for r in recs)
        q2 = "What medications was I taking when I had dizziness in March 2019?"
        qu2 = understand(q2)
        assert qu2.temporal_relation == "during_episode" and qu2.time_start == "2019-03-01"
        recs2, trace2 = PatientRetriever(m).stair(q2, qu2, StructuralSelector(embedder=None))
        ids = [r["record_id"] for r in recs2]
        assert "MedicationRequest/a-med-3" in ids                      # lisinopril 20 MG authored 2019-01-05, active
        assert any("medications_active_at" in op for op in trace2.structured_ops)


def test_bm25_baseline_scoped(memdb):
    with session_scope() as s:
        hits = PatientRetriever(PatientMemory(s, "pat-b")).bm25("creatinine", k=10)
        assert hits and all(h["patient_id"] == "pat-b" for h in hits)


def test_recorded_medication_end_date_is_used_not_estimated(memdb):
    with session_scope() as s:
        m = PatientMemory(s, "pat-a")
        r = m.add_patient_entry("medication_history/previous_medications", "Elodper",
                                start="2021-11-01", end="2022-01-31", status="completed")
        iv = {iv["record_id"]: iv for iv in m.medication_intervals()}[r["record_id"]]
        assert iv["interval_end"].startswith("2022-01-31") and iv["end_uncertain"] is False
