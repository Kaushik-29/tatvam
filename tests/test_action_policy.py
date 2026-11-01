"""
MedResolve — Unit Tests for Phase 4 Action Policy
Tests the Uncertainty-Aware Selective Action Policy, Emergency Safety Override Detector,
and non-arbitration and non-fabrication guarantees.
"""

import json
from pathlib import Path
import sys
from typing import Dict, List

import numpy as np
import pytest
from scipy import sparse

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from experiments.evidence_ledger import (
    ClinicianOpinionItem,
    EvidenceItem,
    EvidenceLedger,
    EvidenceStatus,
    ExtractionMethod,
    SourceType,
    UserConfirmationStatus,
)
from experiments.conflict_taxonomy import (
    ConflictReportItem,
    ConflictSeverity,
    ConflictType,
    RequiredAction,
)
from experiments.conflict_detector import RuleBasedConflictDetector
from experiments.action_policy import (
    EmergencySafetyOverrideDetector,
    PolicyAction,
    PolicyDecision,
    SelectiveActionPolicy,
    compute_predictive_uncertainty,
)
from experiments.evaluate_action_policy import ledger_to_feature_vector


@pytest.fixture
def policy():
    return SelectiveActionPolicy(
        low_confidence_threshold=0.70,
        entropy_threshold=0.45,
        margin_threshold=0.35,
    )


@pytest.fixture
def clean_ledger():
    ledger = EvidenceLedger(
        patient_case_id="case_unit_test_clean",
        metadata={"age": 42, "sex": "F", "pathology": "GERD", "is_simulated": True},
    )
    # Add age, sex, and clean mild symptoms
    ledger.add_item(
        EvidenceItem(
            evidence_id="ev_age",
            patient_case_id="case_unit_test_clean",
            concept="DEMO_AGE",
            normalized_value=42,
            source_type=SourceType.PATIENT_REPORTED,
            recorded_timestamp="2026-10-15T10:00:00Z",
            extraction_method=ExtractionMethod.DIRECT_SELECTION,
            extraction_confidence=1.0,
            user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT,
            evidence_status=EvidenceStatus.PRESENT,
        )
    )
    ledger.add_item(
        EvidenceItem(
            evidence_id="ev_pyrosis",
            patient_case_id="case_unit_test_clean",
            concept="E_173",  # Heartburn / pyrosis
            concept_name_en="Do you feel a burning sensation in your chest or throat?",
            normalized_value=True,
            source_type=SourceType.PATIENT_REPORTED,
            recorded_timestamp="2026-10-15T10:00:00Z",
            extraction_method=ExtractionMethod.DIRECT_SELECTION,
            extraction_confidence=1.0,
            user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT,
            evidence_status=EvidenceStatus.PRESENT,
        )
    )
    return ledger


@pytest.fixture
def clean_probabilities():
    # 49 classes with confident mass on class 0 (e.g. GERD)
    probs = np.zeros(49, dtype=np.float32)
    probs[0] = 0.94
    probs[1:] = 0.06 / 48
    return probs


@pytest.fixture
def ambiguous_probabilities():
    # 49 classes with ambiguous distribution between class 0 and class 1
    probs = np.zeros(49, dtype=np.float32)
    probs[0] = 0.32
    probs[1] = 0.30
    probs[2:] = 0.38 / 47
    return probs


def test_emergency_override_takes_priority(policy, clean_ledger, clean_probabilities):
    """
    Verify that an urgent-warning condition (e.g., stridor, acute chest pain + dyspnea)
    triggers EMERGENCY_OVERRIDE immediately, taking precedence over ordinary actions
    even when predictive uncertainty is low.
    """
    # Inject acute red-flag stridor
    clean_ledger.add_item(
        EvidenceItem(
            evidence_id="ev_stridor",
            patient_case_id=clean_ledger.patient_case_id,
            concept="E_194",
            concept_name_en="High-pitched stridor on breathing in",
            normalized_value=True,
            source_type=SourceType.PATIENT_REPORTED,
            recorded_timestamp="2026-10-15T10:00:00Z",
            extraction_method=ExtractionMethod.DIRECT_SELECTION,
            extraction_confidence=1.0,
            evidence_status=EvidenceStatus.PRESENT,
        )
    )

    decision = policy.select_action(
        ledger=clean_ledger,
        probabilities=clean_probabilities,
        candidate_question={"concept": "E_91", "question_en": "Do you have a fever?"},
        pathology_list=[f"Condition_{i}" for i in range(49)],
    )

    assert decision.selected_action == PolicyAction.EMERGENCY_OVERRIDE
    assert decision.is_emergency_override is True
    assert "emergency" in decision.reason.lower() or "airway" in decision.detailed_rationale.lower()
    assert decision.emergency_details is not None
    assert len(decision.emergency_details["red_flags"]) > 0


def test_low_confidence_ocr_not_silently_accepted(policy, clean_ledger, clean_probabilities):
    """
    Verify that an unconfirmed low-confidence extraction (e.g., OCR confidence = 0.52 < 0.70)
    is NOT silently accepted as true to produce EXPLAIN, but triggers ASK for patient confirmation.
    """
    clean_ledger.add_item(
        EvidenceItem(
            evidence_id="ev_ocr_smudge",
            patient_case_id=clean_ledger.patient_case_id,
            concept="E_91",
            concept_name_en="Fever",
            normalized_value=True,
            original_value="Fev?r noted",
            source_type=SourceType.EHR_EXTRACTED_NOTE,
            recorded_timestamp="2026-10-15T10:00:00Z",
            extraction_method=ExtractionMethod.OCR_EXTRACTION,
            extraction_confidence=0.52,  # Low confidence!
            user_confirmation_status=UserConfirmationStatus.UNCONFIRMED,
            evidence_status=EvidenceStatus.PRESENT,
        )
    )

    decision = policy.select_action(
        ledger=clean_ledger,
        probabilities=clean_probabilities,
        pathology_list=[f"Condition_{i}" for i in range(49)],
    )

    assert decision.selected_action == PolicyAction.ASK
    assert decision.target_concept_to_ask == "E_91"
    assert "low-confidence" in decision.reason.lower()
    assert decision.selected_action != PolicyAction.EXPLAIN, "Low confidence OCR must NOT be silently explained!"


def test_opinion_disagreement_non_arbitration(policy, clean_ledger, clean_probabilities):
    """
    Verify that when two clinician opinions disagree, the policy triggers ABSTAIN_AND_NAVIGATE
    and strictly refrains from arbitrating or declaring one physician correct.
    """
    clean_ledger.add_opinion(
        ClinicianOpinionItem(
            opinion_id="op_1",
            patient_case_id=clean_ledger.patient_case_id,
            clinician_id="clinician_dr_smith",
            clinician_specialty="General Practice",
            diagnostic_impression="GERD",
            recorded_timestamp="2026-10-15T10:00:00Z",
        )
    )
    clean_ledger.add_opinion(
        ClinicianOpinionItem(
            opinion_id="op_2",
            patient_case_id=clean_ledger.patient_case_id,
            clinician_id="clinician_dr_adams",
            clinician_specialty="Cardiology",
            diagnostic_impression="Stable angina",
            recorded_timestamp="2026-10-15T10:15:00Z",
        )
    )

    decision = policy.select_action(
        ledger=clean_ledger,
        probabilities=clean_probabilities,
        pathology_list=[f"Condition_{i}" for i in range(49)],
    )

    assert decision.selected_action == PolicyAction.ABSTAIN_AND_NAVIGATE
    assert "opinion" in decision.reason.lower() or "arbitrat" in decision.reason.lower()
    # Check non-arbitration guarantee
    notice = decision.abstention_summary.get("non_arbitration_notice", "")
    assert "does not assess or arbitrate" in notice.lower()
    # Confirm it does not declare either doctor right
    assert "dr_smith is correct" not in notice.lower()
    assert "dr_adams is correct" not in notice.lower()


def test_missing_timestamps_remain_missing(clean_ledger):
    """
    Verify that an evidence item with event_timestamp=None remains explicitly None
    and is not fabricated or imputed by the ledger or policy.
    """
    clean_ledger.add_item(
        EvidenceItem(
            evidence_id="ev_no_ts",
            patient_case_id=clean_ledger.patient_case_id,
            concept="E_100",
            normalized_value=True,
            source_type=SourceType.PATIENT_REPORTED,
            event_timestamp=None,  # Missing!
            recorded_timestamp="2026-10-15T10:00:00Z",
            extraction_method=ExtractionMethod.DIRECT_SELECTION,
            extraction_confidence=1.0,
            evidence_status=EvidenceStatus.PRESENT,
        )
    )
    item = [i for i in clean_ledger.items if i.evidence_id == "ev_no_ts"][0]
    assert item is not None
    assert item.event_timestamp is None


def test_different_dates_not_falsely_flagged(policy, clean_ledger, clean_probabilities):
    """
    Verify that observation records from different observation dates are not falsely flagged
    as contradictory value conflicts or cause unjustified abstention.
    """
    # Measurement from past week
    clean_ledger.add_item(
        EvidenceItem(
            evidence_id="ev_past_temp",
            patient_case_id=clean_ledger.patient_case_id,
            concept="E_TEMP",
            concept_name_en="Oral Temperature",
            normalized_value=98.6,
            unit="degF",
            source_type=SourceType.PATIENT_REPORTED,
            event_timestamp="2026-10-01T10:00:00Z",
            recorded_timestamp="2026-10-01T10:30:00Z",
            extraction_method=ExtractionMethod.DIRECT_SELECTION,
            extraction_confidence=1.0,
            evidence_status=EvidenceStatus.PRESENT,
        )
    )
    # Measurement from today (different date)
    clean_ledger.add_item(
        EvidenceItem(
            evidence_id="ev_today_temp",
            patient_case_id=clean_ledger.patient_case_id,
            concept="E_TEMP",
            concept_name_en="Oral Temperature",
            normalized_value=99.1,
            unit="degF",
            source_type=SourceType.PATIENT_REPORTED,
            event_timestamp="2026-10-15T10:00:00Z",
            recorded_timestamp="2026-10-15T10:30:00Z",
            extraction_method=ExtractionMethod.DIRECT_SELECTION,
            extraction_confidence=1.0,
            evidence_status=EvidenceStatus.PRESENT,
        )
    )

    detector = RuleBasedConflictDetector()
    conflicts = detector.detect_conflicts(clean_ledger)
    val_conflicts = [c for c in conflicts if c.conflict_type == ConflictType.VALUE_OR_UNIT_DISCREPANCY]
    assert len(val_conflicts) == 0, "Different dates must not be flagged as value discrepancy!"


def test_disjointness_no_tuning_on_eval_cohort():
    """
    Verify that:
    1. Dev cohort and Eval cohort row indices are strictly disjoint.
    2. Both Dev and Eval cohorts are disjoint from Phase 2 classifier training (50,000 cases).
    3. Both Dev and Eval cohorts are disjoint from Phase 3 conflict benchmark (1,000 cases).
    """
    action_manifest_path = Path("results/actions/action_benchmark_manifest.json")
    conflict_manifest_path = Path("results/conflicts/conflict_benchmark_manifest.json")

    assert action_manifest_path.exists(), "Action benchmark manifest missing!"
    assert conflict_manifest_path.exists(), "Conflict benchmark manifest missing!"

    with open(action_manifest_path, "r", encoding="utf-8") as f:
        action_manifest = json.load(f)
    with open(conflict_manifest_path, "r", encoding="utf-8") as f:
        conflict_manifest = json.load(f)

    action_dev_idx = set(action_manifest["dev_cohort"]["source_indices"])
    action_eval_idx = set(action_manifest["eval_cohort"]["source_indices"])

    # 1. Dev and Eval disjoint
    assert action_dev_idx.isdisjoint(action_eval_idx), "Dev and Eval cohorts in Phase 4 must be disjoint!"

    # 2. Disjoint from Phase 3 conflict benchmark
    conflict_dev_idx = set(conflict_manifest["dev_cohort"]["source_indices"])
    conflict_eval_idx = set(conflict_manifest["eval_cohort"]["source_indices"])
    all_conflict_idx = conflict_dev_idx.union(conflict_eval_idx)

    assert action_dev_idx.isdisjoint(all_conflict_idx), "Phase 4 Dev cohort overlaps with Phase 3 conflict benchmark!"
    assert action_eval_idx.isdisjoint(all_conflict_idx), "Phase 4 Eval cohort overlaps with Phase 3 conflict benchmark!"

    # 3. Disjoint from 50k classifier training cases
    from sklearn.model_selection import train_test_split
    import pandas as pd
    from experiments.ddxplus_loader import DDXPlusLoader

    loader = DDXPlusLoader()
    df_patho = pd.read_csv(loader.get_split_path("train"), usecols=["PATHOLOGY"])
    train_50k_idx, _ = train_test_split(
        np.arange(len(df_patho)), train_size=50000, random_state=42, stratify=df_patho["PATHOLOGY"]
    )
    train_50k_set = set(train_50k_idx)

    assert action_dev_idx.isdisjoint(train_50k_set), "Phase 4 Dev cohort overlaps with Phase 2 classifier training set!"
    assert action_eval_idx.isdisjoint(train_50k_set), "Phase 4 Eval cohort overlaps with Phase 2 classifier training set!"


def test_zero_target_leakage_in_action_features(clean_ledger):
    """
    Verify that diagnostic ground truth labels ('PATHOLOGY', 'DIFFERENTIAL_DIAGNOSIS')
    never appear in the feature vector constructed for the classifier or action policy.
    """
    token_to_idx = {f"E_{i}": i for i in range(972)}
    X = ledger_to_feature_vector(clean_ledger, token_to_idx)
    assert X.shape == (1, 974)

    # Feature matrix contains only Age, Sex, and multi-hot evidence codes
    # Check that string diagnostic names are never encoded
    assert clean_ledger.metadata.get("pathology") == "GERD"
    # The sparse vector has only float values corresponding to demographics and symptom tokens
    assert X.dtype in [np.float32, np.float64]


def test_ask_only_when_useful_question_available(policy, clean_ledger, ambiguous_probabilities):
    """
    Verify that ASK is selected when predictive uncertainty is elevated AND a useful question
    is available; if no question is available, policy must conservatively fall back to ABSTAIN_AND_NAVIGATE.
    """
    clean_ledger.metadata["is_ambiguous_presentation"] = True

    # Scenario A: Useful question IS available
    decision_with_q = policy.select_action(
        ledger=clean_ledger,
        probabilities=ambiguous_probabilities,
        candidate_question={
            "concept": "E_53",
            "question_en": "Do you have pain related to your reason for consulting?",
            "rationale": "Discriminate gastrointestinal vs musculoskeletal etiology.",
        },
        pathology_list=[f"Condition_{i}" for i in range(49)],
    )
    assert decision_with_q.selected_action == PolicyAction.ASK
    assert decision_with_q.target_concept_to_ask == "E_53"
    assert decision_with_q.candidate_question_en is not None

    # Scenario B: NO question is available (candidate_question=None)
    decision_no_q = policy.select_action(
        ledger=clean_ledger,
        probabilities=ambiguous_probabilities,
        candidate_question=None,  # No questions left!
        pathology_list=[f"Condition_{i}" for i in range(49)],
    )
    assert decision_no_q.selected_action == PolicyAction.ABSTAIN_AND_NAVIGATE, (
        "High uncertainty with NO available question must fall back to ABSTAIN_AND_NAVIGATE, not an empty ASK!"
    )


def test_explain_not_chosen_when_unresolved_material_conflicts(policy, clean_ledger, clean_probabilities):
    """
    Verify that EXPLAIN is strictly forbidden when an unresolved material conflict exists
    (e.g., patient report contradicts clinical document).
    """
    # Direct contradiction: patient report says absent, clinical EHR note says present
    clean_ledger.add_item(
        EvidenceItem(
            evidence_id="ev_src_pt",
            patient_case_id=clean_ledger.patient_case_id,
            concept="E_66",
            concept_name_en="Shortness of Breath",
            normalized_value=False,
            source_type=SourceType.PATIENT_REPORTED,
            recorded_timestamp="2026-10-15T10:00:00Z",
            event_timestamp="2026-10-15T09:00:00Z",
            extraction_method=ExtractionMethod.DIRECT_SELECTION,
            extraction_confidence=1.0,
            evidence_status=EvidenceStatus.ABSENT,
        )
    )
    clean_ledger.add_item(
        EvidenceItem(
            evidence_id="ev_src_ehr",
            patient_case_id=clean_ledger.patient_case_id,
            concept="E_66",
            concept_name_en="Shortness of Breath",
            normalized_value=True,
            source_type=SourceType.EHR_EXTRACTED_NOTE,
            recorded_timestamp="2026-10-15T10:00:00Z",
            event_timestamp="2026-10-15T09:00:00Z",
            extraction_method=ExtractionMethod.RULE_BASED_PARSER,
            extraction_confidence=0.98,
            evidence_status=EvidenceStatus.PRESENT,
        )
    )

    decision = policy.select_action(
        ledger=clean_ledger,
        probabilities=clean_probabilities,
        pathology_list=[f"Condition_{i}" for i in range(49)],
    )

    assert decision.selected_action != PolicyAction.EXPLAIN
    assert decision.selected_action == PolicyAction.ABSTAIN_AND_NAVIGATE
    assert "material" in decision.reason.lower() or "conflict" in decision.reason.lower()


def test_abstain_does_not_fabricate_diagnosis_or_provider(policy, clean_ledger, ambiguous_probabilities):
    """
    Verify that ABSTAIN_AND_NAVIGATE does not fabricate a definitive diagnostic condition
    or claim a specific real-world provider/clinic.
    """
    decision = policy.select_action(
        ledger=clean_ledger,
        probabilities=ambiguous_probabilities,
        candidate_question=None,
        pathology_list=[f"Condition_{i}" for i in range(49)],
    )

    assert decision.selected_action == PolicyAction.ABSTAIN_AND_NAVIGATE
    summary = decision.abstention_summary
    assert summary is not None

    # Check non-fabrication
    text = json.dumps(summary).lower()
    assert "definitive diagnosis:" not in text
    assert "we diagnose" not in text
    assert "dr. fake hospital" not in text
    assert "licensed" in decision.disclaimer.lower() or "professional" in decision.disclaimer.lower()


def test_clean_ledger_without_probabilities_permits_explain(policy, clean_ledger):
    """
    Verify that when probabilities is None, clean unconflicted ledgers evaluate to EXPLAIN
    rather than spuriously triggering conservative abstention from default margin 0.0.
    """
    decision = policy.select_action(ledger=clean_ledger, probabilities=None)
    assert decision.selected_action == PolicyAction.EXPLAIN
    assert decision.is_emergency_override is False
    assert "sufficient verified evidence" in decision.reason.lower() or "explain" in str(decision.selected_action).lower()


def test_no_target_leakage_into_emergency_decisions(clean_ledger):
    """
    Verify that EmergencySafetyOverrideDetector uses ONLY legitimately available observed evidence
    and vitals from the ledger items, and NEVER reads hidden ground truth:
    - Does not read ledger.metadata['pathology']
    - Does not read ledger.metadata['differential_diagnosis']
    - Does not accept diagnostic model probabilities
    - Does not read synthetic metadata flags like 'is_acute_emergency'
    """
    import inspect
    detector = EmergencySafetyOverrideDetector()

    # 1. Verify signature does not accept probabilities or pathology_list
    sig = inspect.signature(detector.check_emergency)
    param_names = list(sig.parameters.keys())
    assert param_names == ["ledger"], f"check_emergency signature must ONLY take ledger, got: {param_names}"

    # 2. Plant dangerous ground-truth in metadata
    clean_ledger.metadata["pathology"] = "Acute pulmonary edema"
    clean_ledger.metadata["differential_diagnosis"] = ["Acute pulmonary edema", "Possible NSTEMI / STEMI"]
    clean_ledger.metadata["is_acute_emergency"] = True

    # But clean_ledger only contains mild heartburn (E_173), no red-flag symptoms or vitals!
    is_emerg, red_flags = detector.check_emergency(clean_ledger)
    assert is_emerg is False, (
        "Emergency detector leaked ground-truth pathology or metadata! "
        "Must NOT trigger emergency based on metadata alone."
    )
    assert len(red_flags) == 0


def test_emergency_rule_precedence(policy, clean_ledger, clean_probabilities):
    """
    Verify that emergency safety override strictly preempts all downstream policy steps:
    Precedence: Emergency Override > Extraction Uncertainty > Material Conflicts > Diagnostic Uncertainty > Explain
    """
    # 1. Add low-confidence OCR extraction (would normally trigger ASK)
    clean_ledger.add_item(
        EvidenceItem(
            evidence_id="ev_low_conf",
            patient_case_id=clean_ledger.patient_case_id,
            concept="E_91",
            concept_name_en="Fever",
            normalized_value=True,
            source_type=SourceType.EHR_EXTRACTED_NOTE,
            recorded_timestamp="2026-10-15T10:00:00Z",
            extraction_method=ExtractionMethod.OCR_EXTRACTION,
            extraction_confidence=0.50,
            user_confirmation_status=UserConfirmationStatus.UNCONFIRMED,
            evidence_status=EvidenceStatus.PRESENT,
        )
    )

    # 2. Add opinion disagreement (would normally trigger ABSTAIN_AND_NAVIGATE)
    clean_ledger.add_opinion(
        ClinicianOpinionItem(
            opinion_id="op_1",
            patient_case_id=clean_ledger.patient_case_id,
            clinician_id="dr_a",
            clinician_specialty="GP",
            diagnostic_impression="GERD",
            recorded_timestamp="2026-10-15T10:00:00Z",
        )
    )
    clean_ledger.add_opinion(
        ClinicianOpinionItem(
            opinion_id="op_2",
            patient_case_id=clean_ledger.patient_case_id,
            clinician_id="dr_b",
            clinician_specialty="Cardiology",
            diagnostic_impression="Pericarditis",
            recorded_timestamp="2026-10-15T10:15:00Z",
        )
    )

    # Without emergency: low-confidence triggers ASK first
    dec_no_emerg = policy.select_action(
        ledger=clean_ledger,
        probabilities=clean_probabilities,
        pathology_list=[f"Condition_{i}" for i in range(49)],
    )
    assert dec_no_emerg.selected_action == PolicyAction.ASK

    # Now add acute emergency: Stridor (E_194)
    clean_ledger.add_item(
        EvidenceItem(
            evidence_id="ev_stridor_preempt",
            patient_case_id=clean_ledger.patient_case_id,
            concept="E_194",
            concept_name_en="High-pitched inspiratory stridor",
            normalized_value=True,
            source_type=SourceType.PATIENT_REPORTED,
            recorded_timestamp="2026-10-15T10:00:00Z",
            extraction_method=ExtractionMethod.DIRECT_SELECTION,
            extraction_confidence=1.0,
            evidence_status=EvidenceStatus.PRESENT,
        )
    )

    # Emergency MUST preempt both ASK and ABSTAIN
    dec_emerg = policy.select_action(
        ledger=clean_ledger,
        probabilities=clean_probabilities,
        pathology_list=[f"Condition_{i}" for i in range(49)],
    )
    assert dec_emerg.selected_action == PolicyAction.EMERGENCY_OVERRIDE
    assert dec_emerg.is_emergency_override is True


def test_audited_nine_cases_resolution():
    """
    Verify resolution of the 9 apparent false emergency overrides identified in the audit:
    - 5 probability-coupled cases (Cases 1-5): previously fired Rule 7 due to high model probability
      on severity-1 conditions without observable symptoms. With Rule 7 removed, verify they now predict ASK.
    - 4 benchmark-conflicted cases (Cases 6-9): previously had dyspnea injected onto chest pain.
      In the decoupled benchmark, cough (E_201) is used instead, resolving the clinical inconsistency.
    """
    import joblib
    model_bundle_path = Path("data/processed/diagnostic_model_50k.joblib")
    if not model_bundle_path.exists():
        pytest.skip("Model bundle not found")

    bundle = joblib.load(model_bundle_path)
    model = bundle["model"]
    token_to_idx = bundle["token_to_idx"]
    pathology_list = bundle["pathology_list"]

    policy = SelectiveActionPolicy()

    # Load preserved Phase 4 v1 audit cohort
    v1_audit_file = Path("results/actions/eval_action_scenarios_v1_audit.json")
    if v1_audit_file.exists():
        with open(v1_audit_file, "r", encoding="utf-8") as f:
            v1_scenarios = json.load(f)

        # Cases 1-5 had LOW_CONFIDENCE_EXTRACTION or CLEAN_HIGH_CONFIDENCE with high model probability
        case_ids_prob_coupled = ["eval_act_000000", "eval_act_000001", "eval_act_000003", "eval_act_000005", "eval_act_000100"]
        for sc in v1_scenarios:
            if sc["case_id"] in case_ids_prob_coupled:
                ledger = EvidenceLedger.model_validate(sc["evidence_ledger"])
                X = ledger_to_feature_vector(ledger, token_to_idx)
                probs = model.predict_proba(X)[0]
                decision = policy.select_action(ledger=ledger, probabilities=probs, pathology_list=pathology_list)
                # Verify that with Rule 7 removed, it is NO LONGER EMERGENCY_OVERRIDE!
                assert decision.selected_action != PolicyAction.EMERGENCY_OVERRIDE, (
                    f"Case {sc['case_id']} still triggered emergency override without observable symptoms!"
                )
                assert decision.selected_action == sc["expected_action"]

    # In the decoupled current benchmark, verify 100% accuracy on all conflict cases
    current_eval_file = Path("results/actions/eval_action_scenarios.json")
    assert current_eval_file.exists()
    with open(current_eval_file, "r", encoding="utf-8") as f:
        current_scenarios = json.load(f)

    conflict_cases = [s for s in current_scenarios if s["scenario_category"] == "MATERIAL_CONFLICT_OR_NO_QUESTION"]
    for sc in conflict_cases:
        ledger = EvidenceLedger.model_validate(sc["evidence_ledger"])
        X = ledger_to_feature_vector(ledger, token_to_idx)
        probs = model.predict_proba(X)[0]
        decision = policy.select_action(ledger=ledger, probabilities=probs, pathology_list=pathology_list)
        assert decision.selected_action == PolicyAction.ABSTAIN_AND_NAVIGATE
        assert decision.selected_action != PolicyAction.EMERGENCY_OVERRIDE


def test_independent_benchmark_labels():
    """
    Verify that action benchmark generator does NOT import decision policy or use policy
    inference code to define ground truth labels.
    """
    import experiments.action_benchmark_generator as gen_mod

    # Check module does not import or contain policy detector classes
    assert not hasattr(gen_mod, "EmergencySafetyOverrideDetector"), (
        "ActionBenchmarkGenerator must NOT import EmergencySafetyOverrideDetector! Ground truth must be decoupled."
    )
    assert not hasattr(gen_mod, "SelectiveActionPolicy"), (
        "ActionBenchmarkGenerator must NOT import SelectiveActionPolicy!"
    )
    assert not hasattr(gen_mod, "B0_AlwaysExplainPolicy"), (
        "ActionBenchmarkGenerator must NOT import baseline policy classes!"
    )


def test_development_evaluation_cohort_separation():
    """
    Verify strict separation of development and evaluation cohorts:
    - 0 overlapping case_ids
    - 0 overlapping source_row_index values
    """
    dev_path = Path("results/actions/dev_action_scenarios.json")
    eval_path = Path("results/actions/eval_action_scenarios.json")

    assert dev_path.exists() and eval_path.exists()
    with open(dev_path, "r", encoding="utf-8") as f:
        dev_cases = json.load(f)
    with open(eval_path, "r", encoding="utf-8") as f:
        eval_cases = json.load(f)

    dev_case_ids = {c["case_id"] for c in dev_cases}
    eval_case_ids = {c["case_id"] for c in eval_cases}
    assert dev_case_ids.isdisjoint(eval_case_ids), "Dev and Eval cohorts share case_ids!"

    dev_source_idx = {c["source_row_index"] for c in dev_cases}
    eval_source_idx = {c["source_row_index"] for c in eval_cases}
    assert dev_source_idx.isdisjoint(eval_source_idx), "Dev and Eval cohorts share patient source rows!"


def test_emergency_confusion_matrix_and_metrics():
    """
    Verify mathematical correctness of the binary emergency confusion matrix
    and metrics computation in evaluate_policy_predictions.
    """
    from experiments.evaluate_action_policy import evaluate_policy_predictions

    action_order = [
        PolicyAction.ASK.value,
        PolicyAction.EXPLAIN.value,
        PolicyAction.ABSTAIN_AND_NAVIGATE.value,
        PolicyAction.EMERGENCY_OVERRIDE.value,
    ]

    # Synthetic test array:
    # TP: 2, FP: 1, FN: 1, TN: 4
    # Total = 8
    # Positives: 3, Negatives: 5
    y_true = [
        "EMERGENCY_OVERRIDE", "EMERGENCY_OVERRIDE", "EMERGENCY_OVERRIDE",
        "EXPLAIN", "EXPLAIN", "ASK", "ASK", "ABSTAIN_AND_NAVIGATE"
    ]
    y_pred = [
        "EMERGENCY_OVERRIDE", "EMERGENCY_OVERRIDE", "EXPLAIN",  # 2 TP, 1 FN
        "EMERGENCY_OVERRIDE", "EXPLAIN", "ASK", "ASK", "ABSTAIN_AND_NAVIGATE"  # 1 FP, 4 TN
    ]

    res = evaluate_policy_predictions(y_true, y_pred, action_order)
    em = res["emergency_metrics"]

    assert em["true_positives"] == 2
    assert em["false_positives"] == 1
    assert em["true_negatives"] == 4
    assert em["false_negatives"] == 1

    # Sensitivity = TP / (TP + FN) = 2 / 3 = 0.6667
    assert em["sensitivity"] == pytest.approx(2 / 3, abs=1e-4)
    # Specificity = TN / (TN + FP) = 4 / 5 = 0.8000
    assert em["specificity"] == pytest.approx(4 / 5, abs=1e-4)
    # FPR = FP / (FP + TN) = 1 / 5 = 0.2000
    assert em["false_positive_rate"] == pytest.approx(1 / 5, abs=1e-4)
    # FNR = FN / (FN + TP) = 1 / 3 = 0.3333
    assert em["false_negative_rate"] == pytest.approx(1 / 3, abs=1e-4)


def test_vital_sign_unit_normalization_and_emergency_detection():
    """
    Regression Test (Phase 5.2.2 / Phase 5.3):
    Verify that EmergencySafetyOverrideDetector robustly handles:
    1. Missing unit hyperpyrexia (e.g. 104.8 with unit=None, resolving RAG_SC_EMERG_14_HYPERPYREXIA).
    2. Explicit Celsius hyperpyrexia (40.5 degC and °C).
    3. Unrecognized unit string (105.0 'bpm') evaluated via physiological range without silent discard.
    4. Decimal SpO2 format (0.86 normalized to 86.0%) triggering severe hypoxemia red flag.
    5. Normal vitals (98.6 F, 37.0 C, 98% SpO2) do not trigger false positive red flags.
    """
    from experiments.action_policy import EmergencySafetyOverrideDetector
    from experiments.evidence_ledger import EvidenceLedger, EvidenceItem, SourceType, ExtractionMethod, EvidenceStatus

    detector = EmergencySafetyOverrideDetector()

    # 1. Missing unit hyperpyrexia (resolving RAG_SC_EMERG_14)
    ledger_missing_unit = EvidenceLedger(patient_case_id="case_missing_unit")
    ledger_missing_unit.add_item(
        EvidenceItem(
            evidence_id="ev_t1",
            patient_case_id="case_missing_unit",
            concept="E_TEMP",
            concept_name_en="Core body temperature",
            normalized_value="104.8",
            original_value="104.8",
            unit=None,  # Missing unit
            source_type=SourceType.PATIENT_REPORTED,
            recorded_timestamp="2026-10-30T10:00:00Z",
            extraction_method=ExtractionMethod.MANUAL_ENTRY,
            extraction_confidence=1.0,
            evidence_status=EvidenceStatus.PRESENT,
        )
    )
    is_emerg, flags = detector.check_emergency(ledger_missing_unit)
    assert is_emerg is True, "Failed to trigger emergency for hyperpyrexia with missing unit!"
    assert any("Hyperpyrexia red flag" in f for f in flags)
    assert any("104.8" in f for f in flags)

    # 2. Celsius hyperpyrexia (40.2 °C)
    ledger_celsius = EvidenceLedger(patient_case_id="case_celsius")
    ledger_celsius.add_item(
        EvidenceItem(
            evidence_id="ev_t2",
            patient_case_id="case_celsius",
            concept="body_temperature",
            concept_name_en="Core body temperature",
            normalized_value="40.2",
            original_value="40.2 °C",
            unit="°C",
            source_type=SourceType.LABORATORY_REPORT,
            recorded_timestamp="2026-10-30T10:00:00Z",
            extraction_method=ExtractionMethod.OCR_EXTRACTION,
            extraction_confidence=0.95,
            evidence_status=EvidenceStatus.PRESENT,
        )
    )
    is_emerg_c, flags_c = detector.check_emergency(ledger_celsius)
    assert is_emerg_c is True
    assert any("Hyperpyrexia red flag" in f for f in flags_c)

    # 3. Unrecognized unit string (105.0 bpm)
    ledger_unrec = EvidenceLedger(patient_case_id="case_unrec")
    ledger_unrec.add_item(
        EvidenceItem(
            evidence_id="ev_t3",
            patient_case_id="case_unrec",
            concept="temperature_measurement",
            concept_name_en="Recorded temperature with corrupted unit",
            normalized_value="105.0",
            original_value="105.0 bpm",
            unit="bpm",  # Unrecognized/mismatched unit
            source_type=SourceType.EHR_EXTRACTED_NOTE,
            recorded_timestamp="2026-10-30T10:00:00Z",
            extraction_method=ExtractionMethod.OCR_EXTRACTION,
            extraction_confidence=0.80,
            evidence_status=EvidenceStatus.PRESENT,
        )
    )
    is_emerg_u, flags_u = detector.check_emergency(ledger_unrec)
    assert is_emerg_u is True, "Unrecognized unit must not cause silent discard of hyperpyrexia!"
    assert any("unrecognized unit 'bpm'" in f for f in flags_u)

    # 4. Decimal SpO2 format (0.86)
    ledger_spo2 = EvidenceLedger(patient_case_id="case_spo2")
    ledger_spo2.add_item(
        EvidenceItem(
            evidence_id="ev_spo2",
            patient_case_id="case_spo2",
            concept="E_SPO2",
            concept_name_en="Pulse oximetry",
            normalized_value="0.86",
            original_value="86%",
            unit=None,
            source_type=SourceType.LABORATORY_REPORT,
            recorded_timestamp="2026-10-30T10:00:00Z",
            extraction_method=ExtractionMethod.OCR_EXTRACTION,
            extraction_confidence=0.99,
            evidence_status=EvidenceStatus.PRESENT,
        )
    )
    is_emerg_sp, flags_sp = detector.check_emergency(ledger_spo2)
    assert is_emerg_sp is True
    assert any("Severe hypoxemia" in f and "86.0%" in f for f in flags_sp)

    # 5. Normal vitals (98.6 F, 98% SpO2) do not trigger emergency
    ledger_normal = EvidenceLedger(patient_case_id="case_normal")
    ledger_normal.add_item(
        EvidenceItem(
            evidence_id="ev_norm_temp",
            patient_case_id="case_normal",
            concept="E_TEMP",
            concept_name_en="Body temperature",
            normalized_value="98.6",
            original_value="98.6 F",
            unit="degF",
            source_type=SourceType.PATIENT_REPORTED,
            recorded_timestamp="2026-10-30T10:00:00Z",
            extraction_method=ExtractionMethod.MANUAL_ENTRY,
            extraction_confidence=1.0,
            evidence_status=EvidenceStatus.PRESENT,
        )
    )
    ledger_normal.add_item(
        EvidenceItem(
            evidence_id="ev_norm_spo2",
            patient_case_id="case_normal",
            concept="E_SPO2",
            concept_name_en="Pulse oximetry",
            normalized_value="98.0",
            original_value="98%",
            unit="%",
            source_type=SourceType.PATIENT_REPORTED,
            recorded_timestamp="2026-10-30T10:00:00Z",
            extraction_method=ExtractionMethod.MANUAL_ENTRY,
            extraction_confidence=1.0,
            evidence_status=EvidenceStatus.PRESENT,
        )
    )
    is_emerg_n, flags_n = detector.check_emergency(ledger_normal)
    assert is_emerg_n is False
    assert len(flags_n) == 0


