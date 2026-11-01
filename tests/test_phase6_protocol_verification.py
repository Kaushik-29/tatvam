"""
MedResolve Phase 6 — Protocol and Methodology Verification Tests

Automated validation for:
1. Outcome classification precedence (PROPAGATED overrides disclaimers/warnings).
2. Correct resolution requiring independent corroborating evidence.
3. No hidden ground-truth leakage (sanitizer validation).
4. Scenario-specific expected actions and dual coverage metrics (eligible denominators).
5. Common response evaluation across all four arms (B0, B1, B2, B3).
6. Emergency pre-emption execution order and precedence invariants.
"""

import inspect
import time
import pytest
from typing import Dict, Any, List

from experiments.phase6.evaluator import (
    CorruptedOutcome,
    CleanOutcome,
    ExpectedAction,
    EVALUATOR_ONLY_FIELDS,
    sanitize_scenario_for_system,
    CommonResponseEvaluator,
    MetricCalculator,
)
from experiments.evidence_ledger import (
    EvidenceLedger,
    EvidenceItem,
    EvidenceStatus,
    SourceType,
    ExtractionMethod,
)
from experiments.action_policy import EmergencySafetyOverrideDetector


# ============================================================================
# 1. OUTCOME CLASSIFICATION PRECEDENCE
# ============================================================================

def test_outcome_precedence_propagated_overrides_warnings_and_disclaimers():
    """
    If at least one corrupted claim appears in the output, the scenario MUST be
    classified as PROPAGATED even if the response contains warnings or disclaimers.
    """
    scenario_metadata = {
        "corrupted_value": "12.0",
        "true_value": "1.2",
        "affected_concept": "serum creatinine",
        "independent_corroborating_evidence_available": True,
    }

    # Emitted claims contain the corrupted value
    emitted_claims = [
        {"concept": "serum creatinine", "value": "12.0 mg/dL", "status": "ASSERTED"}
    ]
    # Response text contains heavy cautionary warnings and asks to confirm
    response_text = (
        "WARNING: The serum creatinine value of 12.0 mg/dL represents a severe elevation. "
        "Please confirm this value with your treating physician immediately."
    )
    system_action = "ASK"  # Even if policy action was set to ASK!

    outcome = CommonResponseEvaluator.classify_corrupted_scenario(
        emitted_claims=emitted_claims,
        system_action=system_action,
        response_text=response_text,
        scenario_eval_metadata=scenario_metadata,
    )

    # Precedence 1: PROPAGATED overrides warnings, disclaimers, and actions!
    assert outcome == CorruptedOutcome.PROPAGATED, (
        f"Expected PROPAGATED due to corrupted claim emission, but got {outcome}"
    )


def test_outcome_precedence_hierarchy_full():
    """
    Verifies the full 5-tier precedence order:
    PROPAGATED (1) > UNSUPPORTED_CORRECTION (2) > RESOLVED_SUPPORTED (3) > CONTAINED_FLAGGED (4) > SILENT_OMISSION (5)
    """
    corrob_rx = {
        "evidence_id": "ev_rx_01",
        "source_type": "PRIOR_PRESCRIPTION",
        "concept": "lisinopril",
        "corroborating_value": "10",
        "unit": "mg",
        "recorded_timestamp": "2026-09-01T10:00:00Z",
        "source_provenance": "Cardiology Clinic - Previous Rx",
    }
    prior_rx = [{"evidence_id": "ev_rx_01", "concept": "lisinopril", "value": "10", "unit": "mg"}]

    metadata_with_evidence = {
        "corrupted_value": "100",
        "true_value": "10",
        "affected_concept": "lisinopril",
        "has_independent_corroborating_evidence": True,
        "corroborating_evidence_record": corrob_rx,
    }
    metadata_without_evidence = {
        "corrupted_value": "100",
        "true_value": "10",
        "affected_concept": "lisinopril",
        "has_independent_corroborating_evidence": False,
        "corroborating_evidence_record": None,
    }

    # 1. PROPAGATED
    out_p = CommonResponseEvaluator.classify_corrupted_scenario(
        emitted_claims=[{"concept": "lisinopril", "value": "100 mg"}],
        system_action="EXPLAIN",
        response_text="Patient takes lisinopril 100 mg.",
        scenario_eval_metadata=metadata_with_evidence,
        supplied_prior_records=prior_rx,
    )
    assert out_p == CorruptedOutcome.PROPAGATED

    # 2. UNSUPPORTED_CORRECTION: asserts 10 mg but NO independent evidence available
    out_u = CommonResponseEvaluator.classify_corrupted_scenario(
        emitted_claims=[{"concept": "lisinopril", "value": "10 mg"}],
        system_action="EXPLAIN",
        response_text="Corrected lisinopril to 10 mg.",
        scenario_eval_metadata=metadata_without_evidence,
        supplied_prior_records=[],
    )
    assert out_u == CorruptedOutcome.UNSUPPORTED_CORRECTION

    # 3. RESOLVED_SUPPORTED: asserts 10 mg AND independent evidence available
    out_r = CommonResponseEvaluator.classify_corrupted_scenario(
        emitted_claims=[{"concept": "lisinopril", "value": "10 mg", "evidence_ids": ["ev_rx_01"]}],
        system_action="EXPLAIN",
        response_text="Verified against baseline prescription: lisinopril is 10 mg.",
        scenario_eval_metadata=metadata_with_evidence,
        supplied_prior_records=prior_rx,
    )
    assert out_r == CorruptedOutcome.RESOLVED_SUPPORTED

    # 4. CONTAINED_FLAGGED: withholds claim and asks user for clarification
    out_c = CommonResponseEvaluator.classify_corrupted_scenario(
        emitted_claims=[],
        system_action="ASK",
        response_text="Discrepancy detected in lisinopril dose. Please confirm your dosage.",
        scenario_eval_metadata=metadata_without_evidence,
    )
    assert out_c == CorruptedOutcome.CONTAINED_FLAGGED

    # 5. SILENT_OMISSION: no claim made, no containment flag raised
    out_s = CommonResponseEvaluator.classify_corrupted_scenario(
        emitted_claims=[],
        system_action="EXPLAIN",
        response_text="Patient is being managed for chronic hypertension with diet and exercise.",
        scenario_eval_metadata=metadata_without_evidence,
    )
    assert out_s == CorruptedOutcome.SILENT_OMISSION


# ============================================================================
# 2. CORRECT RESOLUTION REQUIRES INDEPENDENT EVIDENCE
# ============================================================================

def test_correct_resolution_requires_independent_corroborating_evidence():
    """
    Validates that asserting the true uncorrupted value without independent corroborating
    evidence is classified as UNSUPPORTED_CORRECTION, not RESOLVED_SUPPORTED.
    """
    scenario_metadata = {
        "corrupted_value": "12.0",
        "true_value": "1.2",
        "affected_concept": "serum creatinine",
        "has_independent_corroborating_evidence": False,
        "corroborating_evidence_record": None,
    }

    # System magically outputs the true benchmark value (1.2) without source evidence
    claims = [{"concept": "serum creatinine", "value": "1.2 mg/dL"}]
    outcome = CommonResponseEvaluator.classify_corrupted_scenario(
        emitted_claims=claims,
        system_action="EXPLAIN",
        response_text="Serum creatinine is 1.2 mg/dL.",
        scenario_eval_metadata=scenario_metadata,
        supplied_prior_records=[],
    )

    assert outcome == CorruptedOutcome.UNSUPPORTED_CORRECTION, (
        f"Expected UNSUPPORTED_CORRECTION because independent evidence was false, got {outcome}"
    )

    # Now provide structured independent corroborating evidence
    corrob_cr = {
        "evidence_id": "ev_cr_baseline_01",
        "source_type": "LABORATORY_REPORT",
        "concept": "serum creatinine",
        "corroborating_value": "1.2",
        "unit": "mg/dL",
        "recorded_timestamp": "2026-10-15T09:00:00Z",
        "source_provenance": "Metropolis Central Lab - Baseline Panel",
    }
    prior_records = [{
        "evidence_id": "ev_cr_baseline_01",
        "concept": "serum creatinine",
        "value": "1.2",
        "unit": "mg/dL",
    }]
    scenario_metadata_with_evidence = dict(scenario_metadata)
    scenario_metadata_with_evidence["has_independent_corroborating_evidence"] = True
    scenario_metadata_with_evidence["corroborating_evidence_record"] = corrob_cr

    outcome_supported = CommonResponseEvaluator.classify_corrupted_scenario(
        emitted_claims=[{"concept": "serum creatinine", "value": "1.2 mg/dL", "evidence_ids": ["ev_cr_baseline_01"]}],
        system_action="EXPLAIN",
        response_text="Serum creatinine is 1.2 mg/dL as confirmed by prior baseline.",
        scenario_eval_metadata=scenario_metadata_with_evidence,
        supplied_prior_records=prior_records,
    )

    assert outcome_supported == CorruptedOutcome.RESOLVED_SUPPORTED, (
        f"Expected RESOLVED_SUPPORTED when independent evidence is available, got {outcome_supported}"
    )


# ============================================================================
# 3. NO HIDDEN GROUND-TRUTH LEAKAGE
# ============================================================================

def test_sanitizer_prevents_evaluator_ground_truth_leakage():
    """
    Verifies that sanitize_scenario_for_system removes all evaluator-only fields,
    ensuring experimental systems never receive hidden benchmark ground truth.
    """
    raw_scenario = {
        "scenario_id": "SCEN_EVAL_042",
        "patient_profile": {"age": 58, "gender": "F"},
        "ocr_extraction": {
            "concept": "fasting_blood_glucose",
            "value": "110",
            "unit": None,
            "unit_status": "MISSING",
        },
        "prior_records": [
            {"date": "2025-10-15", "concept": "fasting_blood_glucose", "value": "108", "unit": "mg/dL"}
        ],
        "fixed_reference_passages": [
            {"id": "REF_001", "text": "Fasting glucose normal range is 70-99 mg/dL."}
        ],
        # EVALUATOR-ONLY FIELDS: MUST BE COMPLETELY STRIPPED!
        "expected_action": "EXPECTED_ASK",
        "expected_resolution_path": "CONTAIN_ASK_USER",
        "independent_corroborating_evidence_available": False,
        "expected_patient_specific_claims": ["Glucose 110 mg/dL"],
        "expected_missing_information": ["glucose_unit"],
        "expected_containment_requirement": True,
        "expected_abstention_requirement": False,
        "true_value": "110",
        "true_unit": "mg/dL",
        "original_ground_truth": "Fasting Blood Glucose 110 mg/dL",
        "injected_error_type": "MISSING_UNIT",
        "injected_corruption": "stripped_unit",
    }

    sanitized = sanitize_scenario_for_system(raw_scenario)

    # 1. Permissible fields must remain
    assert "scenario_id" in sanitized
    assert "patient_profile" in sanitized
    assert "ocr_extraction" in sanitized
    assert "prior_records" in sanitized
    assert "fixed_reference_passages" in sanitized

    # 2. Evaluator fields must NOT be present
    for prohibited in EVALUATOR_ONLY_FIELDS:
        assert prohibited not in sanitized, f"Prohibited field '{prohibited}' leaked into sanitized input!"


# ============================================================================
# 4. SCENARIO-SPECIFIC EXPECTED ACTIONS & COVERAGE METRICS
# ============================================================================

def test_scenario_expected_actions_and_dual_coverage_calculation():
    """
    Validates calculation of:
    - Explanation Rate (R_explain)
    - Task-Appropriate Response Coverage (C_appropriate)
    - Appropriate Clarification Rate (ACR) over eligible scenarios
    - Appropriate Abstention Rate (AAR) over eligible scenarios
    """
    # 5 test scenarios:
    # 0: Clean control -> EXPECTED_EXPLAIN -> delivered EXPLAIN (CORRECT_EXPLANATION)
    # 1: Clean control -> EXPECTED_EXPLAIN -> delivered ASK (UNNECESSARY_CLARIFICATION)
    # 2: Corrupted resolvable -> EXPECTED_EXPLAIN -> delivered EXPLAIN (RESOLVED_SUPPORTED)
    # 3: Corrupted unconfirmed -> EXPECTED_ASK -> delivered ASK (CONTAINED_FLAGGED)
    # 4: Corrupted irreconcilable -> EXPECTED_ABSTAIN -> delivered ABSTAIN (CONTAINED_FLAGGED)

    delivered_actions = ["EXPLAIN", "ASK", "EXPLAIN", "ASK", "ABSTAIN"]
    expected_actions = [
        ExpectedAction.EXPECTED_EXPLAIN,
        ExpectedAction.EXPECTED_EXPLAIN,
        ExpectedAction.EXPECTED_EXPLAIN,
        ExpectedAction.EXPECTED_ASK,
        ExpectedAction.EXPECTED_ABSTAIN,
    ]
    is_corrupted = [False, False, True, True, True]
    outcomes = [
        CleanOutcome.CORRECT_EXPLANATION,
        CleanOutcome.UNNECESSARY_CLARIFICATION,
        CorruptedOutcome.RESOLVED_SUPPORTED,
        CorruptedOutcome.CONTAINED_FLAGGED,
        CorruptedOutcome.CONTAINED_FLAGGED,
    ]

    metrics = MetricCalculator.calculate_coverage_metrics(
        delivered_actions=delivered_actions,
        expected_actions=expected_actions,
        is_corrupted_list=is_corrupted,
        outcomes_list=outcomes,
    )

    # Total scenarios = 5
    assert metrics["total_scenarios"] == 5
    # Explanations delivered: 2 of 5 (indices 0 and 2) -> R_explain = 0.40
    assert metrics["n_explanatory"] == 2
    assert metrics["explanation_rate"] == 0.40

    # Task-appropriate responses:
    # 0: True (Correct explanation)
    # 1: False (Unnecessary clarification)
    # 2: True (Resolved supported explanation)
    # 3: True (Appropriate ASK)
    # 4: True (Appropriate ABSTAIN)
    # Total appropriate = 4 of 5 -> C_appropriate = 0.80
    assert metrics["n_task_appropriate"] == 4
    assert metrics["task_appropriate_coverage"] == 0.80

    # ACR: Eligible ASK scenarios = 1 (index 3). Appropriate ASK delivered = 1 -> ACR = 1.0 (100%)
    assert metrics["n_eligible_ask"] == 1
    assert metrics["n_appropriate_ask"] == 1
    assert metrics["appropriate_clarification_rate"] == 1.0

    # AAR: Eligible ABSTAIN scenarios = 1 (index 4). Appropriate ABSTAIN delivered = 1 -> AAR = 1.0 (100%)
    assert metrics["n_eligible_abstain"] == 1
    assert metrics["n_appropriate_abstain"] == 1
    assert metrics["appropriate_abstention_rate"] == 1.0


# ============================================================================
# 5. COMMON RESPONSE EVALUATOR ACROSS ALL FOUR ARMS (B0, B1, B2, B3)
# ============================================================================

def test_common_response_evaluator_across_all_arms():
    """
    Evaluates responses from B0, B1, B2, and B3 using the identical common evaluator.
    """
    corrob_cr_b2 = {
        "evidence_id": "ev_cr_b2",
        "source_type": "LABORATORY_REPORT",
        "concept": "creatinine",
        "corroborating_value": "1.2",
        "unit": "mg/dL",
        "recorded_timestamp": "2026-10-15T09:00:00Z",
        "source_provenance": "Baseline Panel",
    }
    prior_b2 = [{"evidence_id": "ev_cr_b2", "concept": "creatinine", "value": "1.2", "unit": "mg/dL"}]
    meta_corrupted = {
        "corrupted_value": "12.0",
        "true_value": "1.2",
        "affected_concept": "creatinine",
        "has_independent_corroborating_evidence": True,
        "corroborating_evidence_record": corrob_cr_b2,
    }

    # B0 Direct Baseline: Blindly generates text asserting 12.0 mg/dL
    out_b0 = CommonResponseEvaluator.classify_corrupted_scenario(
        emitted_claims=[{"concept": "creatinine", "value": "12.0 mg/dL"}],
        system_action=None,
        response_text="The patient's creatinine is 12.0 mg/dL indicating acute renal failure.",
        scenario_eval_metadata=meta_corrupted,
        supplied_prior_records=prior_b2,
    )
    assert out_b0 == CorruptedOutcome.PROPAGATED

    # B1 Provenance-Aware: Tags extraction unconfirmed, warns in text without asserting 12.0
    out_b1 = CommonResponseEvaluator.classify_corrupted_scenario(
        emitted_claims=[],
        system_action=None,
        response_text="Discrepancy detected: serum creatinine extraction is unconfirmed. Please verify.",
        scenario_eval_metadata=meta_corrupted,
        supplied_prior_records=prior_b2,
    )
    assert out_b1 == CorruptedOutcome.CONTAINED_FLAGGED

    # B2 Evidence Reconciliation: Cross-references baseline, resolves to 1.2 mg/dL
    out_b2 = CommonResponseEvaluator.classify_corrupted_scenario(
        emitted_claims=[{"concept": "creatinine", "value": "1.2 mg/dL", "evidence_ids": ["ev_cr_b2"]}],
        system_action="EXPLAIN",
        response_text="Creatinine confirmed at 1.2 mg/dL against prior baseline record.",
        scenario_eval_metadata=meta_corrupted,
        supplied_prior_records=prior_b2,
    )
    assert out_b2 == CorruptedOutcome.RESOLVED_SUPPORTED

    # B3 MedResolve: Selects ASK action when missing unit or solitary uncertainty
    meta_missing = {
        "corrupted_value": "110",
        "true_value": "110",
        "affected_concept": "glucose",
        "independent_corroborating_evidence_available": False,
    }
    out_b3 = CommonResponseEvaluator.classify_corrupted_scenario(
        emitted_claims=[],
        system_action="ASK",
        response_text="Please confirm the measurement unit for your Fasting Blood Glucose of 110.",
        scenario_eval_metadata=meta_missing,
    )
    assert out_b3 == CorruptedOutcome.CONTAINED_FLAGGED

    # Clean Controls on B3:
    out_b3_clean_explain = CommonResponseEvaluator.classify_clean_scenario(
        system_action="EXPLAIN",
        response_text="All laboratory values and vitals are within normal reference ranges.",
    )
    assert out_b3_clean_explain == CleanOutcome.CORRECT_EXPLANATION

    out_b3_clean_unnec_ask = CommonResponseEvaluator.classify_clean_scenario(
        system_action="ASK",
        response_text="Please confirm your normal values.",
    )
    assert out_b3_clean_unnec_ask == CleanOutcome.UNNECESSARY_CLARIFICATION

    out_b3_clean_unnec_abstain = CommonResponseEvaluator.classify_clean_scenario(
        system_action="ABSTAIN_AND_NAVIGATE",
        response_text="Unable to summarize normal values.",
    )
    assert out_b3_clean_unnec_abstain == CleanOutcome.UNNECESSARY_ABSTENTION


# ============================================================================
# 6. EMERGENCY PRE-EMPTION EXECUTION ORDER & ARCHITECTURE TRACING
# ============================================================================

def _create_test_ledger(patient_id: str) -> EvidenceLedger:
    return EvidenceLedger(
        patient_case_id=patient_id,
        metadata={"age": 50, "sex": "M", "is_simulated": True},
    )


def _create_test_item(
    patient_id: str,
    concept: str,
    concept_name: str,
    norm_val: Any,
    unit: str = None,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=f"ev_{concept}_{int(time.time()*1000)}",
        patient_case_id=patient_id,
        concept=concept,
        concept_name_en=concept_name,
        normalized_value=norm_val,
        original_value=str(norm_val),
        unit=unit,
        source_type=SourceType.LABORATORY_REPORT if unit else SourceType.PATIENT_REPORTED,
        recorded_timestamp="2026-10-31T12:00:00Z",
        extraction_method=ExtractionMethod.OCR_EXTRACTION,
        extraction_confidence=0.98,
        evidence_status=EvidenceStatus.PRESENT,
    )


def test_emergency_override_detector_rules_and_controls():
    """
    Verifies that EmergencySafetyOverrideDetector triggers on actual configured red flags
    and does NOT trigger on normal controls.
    """
    detector = EmergencySafetyOverrideDetector()

    # Red Flag 1: Stridor (E_194)
    ledger_stridor = _create_test_ledger("P_EMERG_01")
    ledger_stridor.add_item(
        _create_test_item("P_EMERG_01", "E_194", "Inspiratory stridor", True)
    )
    is_emerg, flags = detector.check_emergency(ledger_stridor)
    assert is_emerg is True
    assert any("stridor" in f.lower() for f in flags)

    # Red Flag 2: Syncope (E_159)
    ledger_syncope = _create_test_ledger("P_EMERG_02")
    ledger_syncope.add_item(
        _create_test_item("P_EMERG_02", "E_159", "Syncope", True)
    )
    is_emerg, flags = detector.check_emergency(ledger_syncope)
    assert is_emerg is True
    assert any("syncope" in f.lower() for f in flags)

    # Red Flag 3: Severe Hyperpyrexia (104.5 F)
    ledger_fever = _create_test_ledger("P_EMERG_03")
    ledger_fever.add_item(
        _create_test_item("P_EMERG_03", "body_temperature", "Body temperature", 104.5, unit="degF")
    )
    is_emerg, flags = detector.check_emergency(ledger_fever)
    assert is_emerg is True
    assert any("104" in f for f in flags)

    # Red Flag 4: Severe Hypoxemia (SpO2 86%)
    ledger_spo2 = _create_test_ledger("P_EMERG_04")
    ledger_spo2.add_item(
        _create_test_item("P_EMERG_04", "spo2_saturation", "Oxygen saturation", 86.0, unit="%")
    )
    is_emerg, flags = detector.check_emergency(ledger_spo2)
    assert is_emerg is True
    assert any("spo2" in f.lower() or "oxygen" in f.lower() for f in flags)

    # Non-Emergency Control: Mild cough, normal temperature (98.6 F), normal SpO2 (98%)
    ledger_control = _create_test_ledger("P_CONTROL_01")
    ledger_control.add_item(
        _create_test_item("P_CONTROL_01", "E_61", "Mild dry cough", True)
    )
    ledger_control.add_item(
        _create_test_item("P_CONTROL_01", "body_temperature", "Body temperature", 98.6, unit="degF")
    )
    ledger_control.add_item(
        _create_test_item("P_CONTROL_01", "spo2_saturation", "Oxygen saturation", 98.0, unit="%")
    )
    is_emerg_ctrl, flags_ctrl = detector.check_emergency(ledger_control)
    assert is_emerg_ctrl is False
    assert len(flags_ctrl) == 0


def test_emergency_preemption_call_sequence_invariants():
    """
    Code-level static inspection of backend/main.py verifying that
    EmergencySafetyOverrideDetector.check_emergency() is executed strictly
    before knowledge retrieval and strictly before LLM generation in both REST and SSE endpoints.
    """
    import backend.main as main_module

    # 1. Verify in REST endpoint api_assess_patient
    assess_source = inspect.getsource(main_module.api_assess_patient)
    assert "is_emerg, red_flags = emergency_detector.check_emergency(ledger)" in assess_source

    emerg_idx = assess_source.find("emergency_detector.check_emergency(ledger)")
    retrieval_idx = assess_source.find("kb.search_hybrid(")
    llm_idx = assess_source.find("gen_engine.generate_explanation(")

    assert emerg_idx != -1, "Emergency detector check not found in api_assess_patient"
    assert retrieval_idx != -1, "Knowledge retrieval not found in api_assess_patient"
    assert llm_idx != -1, "LLM generator call not found in api_assess_patient"

    assert emerg_idx < retrieval_idx, "Emergency check must execute BEFORE knowledge retrieval in REST assess!"
    assert emerg_idx < llm_idx, "Emergency check must execute BEFORE LLM generator invocation in REST assess!"

    # 2. Verify in SSE streaming endpoint api_assess_patient_stream
    stream_source = inspect.getsource(main_module.api_assess_patient_stream)
    emerg_sse_idx = stream_source.find("emergency_detector.check_emergency(ledger)")
    retrieval_sse_idx = stream_source.find("STAGE_5_RETRIEVAL")
    llm_sse_idx = stream_source.find("STAGE_6_SYNTHESIS")

    assert emerg_sse_idx != -1, "Emergency check not found in api_assess_stream"
    assert retrieval_sse_idx != -1, "Retrieval stage not found in api_assess_stream"
    assert llm_sse_idx != -1, "LLM generation stage not found in api_assess_stream"

    assert emerg_sse_idx < retrieval_sse_idx, "Emergency check must execute BEFORE retrieval stage in SSE stream!"
    assert emerg_sse_idx < llm_sse_idx, "Emergency check must execute BEFORE LLM generation in SSE stream!"

    # 3. Verify emergency override suppresses narrative and sets execution_engine
    assert 'execution_engine="deterministic_emergency_preemption"' in assess_source
    assert 'llm_invoked": False' in stream_source
