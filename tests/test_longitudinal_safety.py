"""Safety-layer tests: emergency pre-emption, reconciliation, claim verification, query understanding."""

from backend.claim_verification.verifier import LongitudinalClaimVerifier
from backend.evidence_reconciliation.emergency import screen_text
from backend.evidence_reconciliation.reconcile import reconcile
from backend.rag.query_understanding import understand


def _rec(rid, leaf, display, **kw):
    base = dict(record_id=rid, patient_id="p", leaf_path=leaf, concept_display=display,
                concept_key=kw.pop("key", display.lower()), source_system="synthea_fhir_r4",
                verification_status="confirmed", clinical_status=None, effective_start="2020-01-01",
                effective_end=None, value_num=None, unit=None, value_text=None, text=display, confidence=1.0)
    base.update(kw)
    return base


# ------------------------------------------------------------------ emergency
def test_emergency_red_flags_detected():
    assert screen_text("I have crushing chest pain and I'm short of breath").is_emergency
    assert screen_text("my face is drooping and I have slurred speech").is_emergency
    assert screen_text("I have been thinking about ending it, I want to kill myself").is_emergency
    assert screen_text("my lips and tongue are swelling after a bee sting").is_emergency


def test_emergency_negation_and_benign():
    assert not screen_text("I have a mild headache since yesterday").is_emergency
    assert not screen_text("No chest pain, just a cough for two days").is_emergency
    assert not screen_text("chest pain when I press on my rib, no shortness of breath").is_emergency


# ------------------------------------------------------------ reconciliation
def test_allergy_medication_conflict():
    allergy = _rec("A1", "allergy_history", "Penicillin V (substance)", clinical_status="active")
    med = _rec("M1", "medication_history/current_medications", "amoxicillin 500 MG Oral Capsule", key="amoxicillin")
    f = reconcile([], allergies=[allergy], current_meds=[med])
    assert any(x.finding_type == "ALLERGY_MEDICATION_CONFLICT" and x.severity == "HIGH" for x in f)
    f2 = reconcile([], allergies=[allergy], current_meds=[], query_drug_terms=["amoxicillin"])
    assert any(x.finding_type == "ALLERGY_MEDICATION_CONFLICT" for x in f2)


def test_unit_discrepancy_and_unconfirmed_extraction():
    a = _rec("L1", "laboratory_observations/laboratory_results", "eGFR", key="egfr", value_num=80, unit="mL/min")
    b = _rec("L2", "laboratory_observations/laboratory_results", "eGFR", key="egfr", value_num=75, unit="mL/min/{1.73_m2}")
    c = _rec("L3", "laboratory_observations/laboratory_results", "Glucose", key="glucose", value_num=180, unit=None,
             source_system="ocr_extracted", verification_status="unconfirmed", confidence=0.6)
    types = {x.finding_type for x in reconcile([a, b, c])}
    assert {"UNIT_DISCREPANCY", "UNCONFIRMED_EXTRACTION", "MISSING_INFORMATION"} <= types


def test_missing_section_reported_not_invented():
    f = reconcile([], needed_leaves=["allergy_history"], leaf_counts={"allergy_history": 0})
    assert any("Absence of a record" in x.description for x in f)


# ------------------------------------------------------------ claim verifier
EVID = {"E1": _rec("Condition/1", "medical_history/diagnoses", "Essential hypertension (disorder)",
                   effective_start="2015-01-10", text="Diagnoses: Essential hypertension on 2015-01-10 [status: active]"),
        "E2": _rec("MedicationRequest/2", "medication_history/current_medications", "lisinopril 20 MG Oral Tablet",
                   effective_start="2019-01-05", text="Current Medications: lisinopril 20 MG Oral Tablet on 2019-01-05")}
REFS = {"R1": {"text": "Dizziness can be caused by low blood pressure, dehydration, inner ear problems or medicines "
                       "that lower blood pressure."}}
V = LongitudinalClaimVerifier(["essential hypertension", "lisinopril", "metformin", "type 2 diabetes"])


def test_supported_patient_claim_passes():
    r = V.verify("Your record shows essential hypertension diagnosed on 2015-01-10 [E1].", EVID, REFS)
    assert r.claims[0].status == "SUPPORTED" and r.claims[0].permitted


def test_invented_number_entity_and_citation_blocked():
    r = V.verify("\n".join([
        "Your lisinopril dose was increased to 40 MG in 2021 [E2].",          # number not in evidence
        "You were also diagnosed with type 2 diabetes [E1].",                 # entity not in evidence
        "You take metformin daily [E9].",                                     # citation not in context
        "You have hypertension, which causes dizziness [R1].",                # guideline as patient fact
    ]), EVID, REFS)
    assert [c.permitted for c in r.claims] == [False, False, False, False]
    assert {c.status for c in r.claims} == {"UNSUPPORTED", "INVALID_CITATION"}
    assert "40" not in r.final_text and "metformin" not in r.final_text and "diabetes" not in r.final_text
    assert r.stats["unsupported_patient_claim_rate"] == 1.0


def test_general_claims_need_reference_support_and_safety_allowed():
    r = V.verify("In general, dizziness can be caused by dehydration or medicines that lower blood pressure [R1].\n"
                 "Aliens cause most cases of dizziness [R1].\n"
                 "Please contact your doctor if symptoms worsen.", EVID, REFS)
    assert [c.status for c in r.claims] == ["SUPPORTED", "UNSUPPORTED", "SAFETY_ALLOWED"]


def test_auto_attribution_supports_uncited_true_claims_but_not_inventions():
    r = V.verify("\n".join([
        "The patient has essential hypertension diagnosed on 2015-01-10.",   # true, uncited -> attributed to E1
        "You have been taking lisinopril 20 MG since 2019.",                 # true (year from ISO date) -> E2
        "The patient has type 2 diabetes since 2015.",                       # invented entity -> withheld
        "Your lisinopril was increased to 40 MG in 2021.",                   # invented numbers -> withheld
        "You have been dizzy for three days when standing.",                 # restates current report
    ]), EVID, REFS, current_report="I have been dizzy for three days when standing up")
    st = [c.status for c in r.claims]
    assert st[0] == "SUPPORTED_AUTO_ATTRIBUTED" and "[E1]" in r.claims[0].text
    assert st[1] == "SUPPORTED_AUTO_ATTRIBUTED" and "[E2]" in r.claims[1].text
    assert not r.claims[2].permitted and not r.claims[3].permitted
    assert r.claims[4].claim_type == "PATIENT_REPORTED_NOW" and r.claims[4].permitted
    assert "diabetes" not in r.final_text and "40" not in r.final_text


def test_navigation_advice_and_record_gaps_released_but_not_decisions_or_facts():
    r = V.verify("\n".join([
        "Discuss your allergy history with your dentist before they prescribe an antibiotic.",  # where to go -> allowed
        "Seek medical care if you notice bleeding from the nose or gums [R1].",               # navigation -> allowed
        "Talk to your doctor about whether to stop lisinopril.",                              # decision -> withheld
        "Ask your doctor about starting metformin.",                                          # unrecorded drug -> withheld
        "In general, dizziness can be caused by dehydration or medicines that lower blood pressure [R1].",
        "Nothing in your records appears directly related to this question.",
        "No allergy history is recorded, and absence of a record does not mean absence of the condition.",
        "You have hypertension, which causes dizziness [R1].",                                # guideline as fact
    ]), EVID, REFS, findings_text="No allergy history are recorded. Absence of a record does not mean absence of the condition.")
    assert [c.permitted for c in r.claims] == [True, True, False, False, True, True, True, False]
    assert r.claims[4].claim_type == "GENERAL" and r.claims[6].claim_type == "RECORD_GAP"
    assert "metformin" not in r.final_text and "stop lisinopril" not in r.final_text


# ------------------------------------------------------- query understanding
def test_query_understanding():
    qu = understand("I've started feeling dizzy and lightheaded since yesterday. Could my lisinopril be related?",
                    known_medications=["lisinopril", "metformin"])
    assert "dizziness" in qu.symptoms and qu.medications == ["lisinopril"] and qu.is_new_concern
    assert "hypertension" in qu.expanded_terms
    qu2 = understand("Show my kidney blood tests from 2021")
    assert qu2.organ_systems == ["kidney"] and qu2.time_start == "2021-01-01" and qu2.time_end == "2022-01-01"
    assert "creatinine" in qu2.expanded_terms


def test_date_shifted_records_are_not_future_dated_against_record_time():
    """MIMIC dates are privacy-shifted (2100+): against the wall clock every record is 'future-dated',
    which flooded B5's context. The pipeline passes the patient's latest record date as 'today'."""
    from types import SimpleNamespace
    from backend.rag.pipeline import _record_today
    r = _rec("L1", "laboratory_observations/laboratory_results", "MCV", key="mcv", effective_start="2155-11-23T08:00:00")
    assert any("Future-dated" in f.description for f in reconcile([r], today="2026-11-20"))
    assert not any("Future-dated" in f.description for f in reconcile([r], today="2155-11-23"))
    mem = SimpleNamespace(records=lambda limit=None: [r])
    assert _record_today(mem, SimpleNamespace(source="mimic_iv_fhir_demo")) == "2155-11-23"
    assert _record_today(mem, SimpleNamespace(source="synthea_fhir_r4")) is None
