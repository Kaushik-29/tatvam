"""
MedResolve — Unit Tests for Conflict Detector & Benchmark Integrity
Tests conflict detection across all 6 taxonomy categories, verifies false-positive resistance,
checks benchmark non-overlap with Phase 2 classifier training cases, and ensures source traceability.
"""

import json
from pathlib import Path
import pytest

from experiments.conflict_detector import RuleBasedConflictDetector
from experiments.conflict_taxonomy import ConflictSeverity, ConflictType, RequiredAction
from experiments.evidence_ledger import (
    ClinicianOpinionItem,
    EvidenceItem,
    EvidenceLedger,
    EvidenceStatus,
    ExtractionMethod,
    SourceType,
    UserConfirmationStatus,
)


@pytest.fixture(scope="module")
def detector():
    return RuleBasedConflictDetector(low_confidence_threshold=0.70)


def test_detect_value_or_unit_discrepancy(detector):
    """Verify detection of conflicting quantitative values within overlapping timeframes."""
    ledger = EvidenceLedger(patient_case_id="case_test_val")
    # Patient reports 98.6 F
    ledger.add_item(
        EvidenceItem(
            evidence_id="ev_val_1",
            patient_case_id="case_test_val",
            concept="E_53",
            concept_name_en="Temperature",
            normalized_value=98.6,
            unit="degF",
            source_type=SourceType.PATIENT_REPORTED,
            recorded_timestamp="2026-10-15T10:00:00Z",
            event_timestamp="2026-10-15T09:30:00Z",
            extraction_method=ExtractionMethod.MANUAL_ENTRY,
            extraction_confidence=1.0,
            evidence_status=EvidenceStatus.PRESENT,
        )
    )
    # Triage lab reports 103.8 F on same morning
    ledger.add_item(
        EvidenceItem(
            evidence_id="ev_val_2",
            patient_case_id="case_test_val",
            concept="E_53",
            concept_name_en="Temperature",
            normalized_value=103.8,
            unit="degF",
            source_type=SourceType.LABORATORY_REPORT,
            recorded_timestamp="2026-10-15T10:15:00Z",
            event_timestamp="2026-10-15T09:30:00Z",
            extraction_method=ExtractionMethod.RULE_BASED_PARSER,
            extraction_confidence=0.98,
            evidence_status=EvidenceStatus.PRESENT,
        )
    )

    reports = detector.detect_conflicts(ledger)
    conflict_types = [r.conflict_type for r in reports]
    assert ConflictType.VALUE_OR_UNIT_DISCREPANCY in conflict_types
    val_report = next(r for r in reports if r.conflict_type == ConflictType.VALUE_OR_UNIT_DISCREPANCY)
    assert "ev_val_1" in val_report.affected_evidence_ids
    assert "ev_val_2" in val_report.affected_evidence_ids
    assert val_report.severity == ConflictSeverity.HIGH


def test_different_dates_not_falsely_flagged_as_value_conflict(detector):
    """Verify that different values on different dates (> 24h apart) are NOT flagged as contradictions."""
    ledger = EvidenceLedger(patient_case_id="case_test_progression")
    # Day 1: normal temp 98.6 F
    ledger.add_item(
        EvidenceItem(
            evidence_id="ev_d1",
            patient_case_id="case_test_progression",
            concept="E_53",
            normalized_value=98.6,
            unit="degF",
            source_type=SourceType.PATIENT_REPORTED,
            recorded_timestamp="2026-10-10T10:00:00Z",
            event_timestamp="2026-10-10T09:00:00Z",
            extraction_method=ExtractionMethod.MANUAL_ENTRY,
            extraction_confidence=1.0,
            evidence_status=EvidenceStatus.PRESENT,
        )
    )
    # Day 5: fever onset 103.0 F (disease evolution, not a contradiction!)
    ledger.add_item(
        EvidenceItem(
            evidence_id="ev_d5",
            patient_case_id="case_test_progression",
            concept="E_53",
            normalized_value=103.0,
            unit="degF",
            source_type=SourceType.LABORATORY_REPORT,
            recorded_timestamp="2026-10-15T10:00:00Z",
            event_timestamp="2026-10-15T09:00:00Z",
            extraction_method=ExtractionMethod.RULE_BASED_PARSER,
            extraction_confidence=0.95,
            evidence_status=EvidenceStatus.PRESENT,
        )
    )

    reports = detector.detect_conflicts(ledger)
    val_conflicts = [r for r in reports if r.conflict_type == ConflictType.VALUE_OR_UNIT_DISCREPANCY]
    assert len(val_conflicts) == 0, "Different dates should not be flagged as value discrepancy"


def test_detect_temporal_discrepancy(detector):
    """Verify detection of impossible future event timestamp relative to ingestion."""
    ledger = EvidenceLedger(patient_case_id="case_test_temp")
    ledger.add_item(
        EvidenceItem(
            evidence_id="ev_future",
            patient_case_id="case_test_temp",
            concept="E_201",
            normalized_value=True,
            source_type=SourceType.EHR_EXTRACTED_NOTE,
            recorded_timestamp="2026-10-15T10:00:00Z",
            event_timestamp="2026-10-30T10:00:00Z",  # In the future!
            extraction_method=ExtractionMethod.RULE_BASED_PARSER,
            extraction_confidence=0.95,
            evidence_status=EvidenceStatus.PRESENT,
        )
    )

    reports = detector.detect_conflicts(ledger)
    types = [r.conflict_type for r in reports]
    assert ConflictType.TEMPORAL_DISCREPANCY in types


def test_detect_source_statement_disagreement(detector):
    """Verify detection of patient self-report ABSENT vs clinical note PRESENT."""
    ledger = EvidenceLedger(patient_case_id="case_test_src")
    ledger.add_item(
        EvidenceItem(
            evidence_id="ev_pt_dyspnea",
            patient_case_id="case_test_src",
            concept="E_50",
            normalized_value=False,
            source_type=SourceType.PATIENT_REPORTED,
            recorded_timestamp="2026-10-15T10:00:00Z",
            event_timestamp="2026-10-15T09:00:00Z",
            extraction_method=ExtractionMethod.DIRECT_SELECTION,
            extraction_confidence=1.0,
            evidence_status=EvidenceStatus.ABSENT,
        )
    )
    ledger.add_item(
        EvidenceItem(
            evidence_id="ev_ehr_dyspnea",
            patient_case_id="case_test_src",
            concept="E_50",
            normalized_value=True,
            source_type=SourceType.EHR_EXTRACTED_NOTE,
            recorded_timestamp="2026-10-15T10:15:00Z",
            event_timestamp="2026-10-15T09:00:00Z",
            extraction_method=ExtractionMethod.RULE_BASED_PARSER,
            extraction_confidence=0.90,
            evidence_status=EvidenceStatus.PRESENT,
        )
    )

    reports = detector.detect_conflicts(ledger)
    types = [r.conflict_type for r in reports]
    assert ConflictType.SOURCE_STATEMENT_DISAGREEMENT in types


def test_detect_low_confidence_extraction(detector):
    """
    Verify low extraction confidence is flagged as LOW_CONFIDENCE_EXTRACTION
    and NOT as a clinical falsehood.
    """
    ledger = EvidenceLedger(patient_case_id="case_test_ocr")
    ledger.add_item(
        EvidenceItem(
            evidence_id="ev_low_ocr",
            patient_case_id="case_test_ocr",
            concept="E_LAB_01",
            normalized_value=12.5,
            source_type=SourceType.LABORATORY_REPORT,
            recorded_timestamp="2026-10-15T10:00:00Z",
            extraction_method=ExtractionMethod.OCR_EXTRACTION,
            extraction_confidence=0.45,  # Low
            evidence_status=EvidenceStatus.PRESENT,
        )
    )

    reports = detector.detect_conflicts(ledger)
    types = [r.conflict_type for r in reports]
    assert ConflictType.LOW_CONFIDENCE_EXTRACTION in types
    ocr_rep = next(r for r in reports if r.conflict_type == ConflictType.LOW_CONFIDENCE_EXTRACTION)
    assert "document-processing uncertainty" in ocr_rep.reason


def test_detect_missing_information(detector):
    """Verify detection of quantitative lab result missing essential unit."""
    ledger = EvidenceLedger(patient_case_id="case_test_missing")
    ledger.add_item(
        EvidenceItem(
            evidence_id="ev_missing_unit",
            patient_case_id="case_test_missing",
            concept="E_LAB_POTASSIUM",
            normalized_value=6.0,
            unit=None,  # Missing
            source_type=SourceType.LABORATORY_REPORT,
            recorded_timestamp="2026-10-15T10:00:00Z",
            extraction_method=ExtractionMethod.RULE_BASED_PARSER,
            extraction_confidence=0.95,
            evidence_status=EvidenceStatus.PRESENT,
        )
    )

    reports = detector.detect_conflicts(ledger)
    types = [r.conflict_type for r in reports]
    assert ConflictType.MISSING_INFORMATION in types


def test_detect_opinion_disagreement(detector):
    """
    Verify differing clinician diagnostic impressions are flagged as
    ENTERED_OPINION_DISAGREEMENT without declaring which clinician is correct.
    """
    ledger = EvidenceLedger(patient_case_id="case_test_opinion")
    ledger.add_opinion(
        ClinicianOpinionItem(
            opinion_id="op_1",
            patient_case_id="case_test_opinion",
            clinician_id="clinician_01",
            clinician_specialty="General Practice",
            diagnostic_impression="Acute bronchitis",
            recorded_timestamp="2026-10-15T10:00:00Z",
        )
    )
    ledger.add_opinion(
        ClinicianOpinionItem(
            opinion_id="op_2",
            patient_case_id="case_test_opinion",
            clinician_id="clinician_02",
            clinician_specialty="Cardiology",
            diagnostic_impression="Pericarditis",
            recorded_timestamp="2026-10-15T10:30:00Z",
        )
    )

    reports = detector.detect_conflicts(ledger)
    types = [r.conflict_type for r in reports]
    assert ConflictType.ENTERED_OPINION_DISAGREEMENT in types
    op_rep = next(r for r in reports if r.conflict_type == ConflictType.ENTERED_OPINION_DISAGREEMENT)
    assert "does not assess or arbitrate clinical correctness" in op_rep.reason


def test_clean_ledger_zero_false_positives(detector):
    """Verify that an unperturbed clean patient ledger produces exactly zero conflict detections."""
    ledger = EvidenceLedger(patient_case_id="case_clean_001")
    ledger.add_item(
        EvidenceItem(
            evidence_id="ev_clean_1",
            patient_case_id="case_clean_001",
            concept="E_53",
            normalized_value=True,
            source_type=SourceType.PATIENT_REPORTED,
            recorded_timestamp="2026-10-15T10:00:00Z",
            event_timestamp="2026-10-15T08:00:00Z",
            extraction_method=ExtractionMethod.DIRECT_SELECTION,
            extraction_confidence=1.0,
            evidence_status=EvidenceStatus.PRESENT,
        )
    )
    ledger.add_opinion(
        ClinicianOpinionItem(
            opinion_id="op_clean_1",
            patient_case_id="case_clean_001",
            clinician_id="clinician_01",
            clinician_specialty="General Practice",
            diagnostic_impression="Influenza",
            recorded_timestamp="2026-10-15T10:00:00Z",
        )
    )

    reports = detector.detect_conflicts(ledger)
    assert len(reports) == 0, f"Expected 0 false alarms on clean ledger, got: {reports}"


def test_benchmark_cohort_disjointness_with_classifier_training():
    """
    Verify that ALL row indices in the conflict benchmark manifest are strictly disjoint
    from the 50,000 cases used to train the Phase 2 classifier.
    """
    manifest_path = Path("results/conflicts/conflict_benchmark_manifest.json")
    assert manifest_path.exists(), "Benchmark manifest does not exist"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    dev_indices = set(manifest["dev_cohort"]["source_indices"])
    eval_indices = set(manifest["eval_cohort"]["source_indices"])

    # 1. Dev and Eval must be disjoint
    assert dev_indices.isdisjoint(eval_indices), "Dev and Eval cohorts must be strictly disjoint!"

    # 2. Must be disjoint from the 50,000 classifier training indices
    from sklearn.model_selection import train_test_split
    import pandas as pd
    from experiments.ddxplus_loader import DDXPlusLoader
    import numpy as np

    loader = DDXPlusLoader()
    df_patho = pd.read_csv(loader.get_split_path("train"), usecols=["PATHOLOGY"])
    train_50k_indices, _ = train_test_split(
        np.arange(len(df_patho)), train_size=50000, random_state=42, stratify=df_patho["PATHOLOGY"]
    )
    train_50k_set = set(train_50k_indices)

    assert dev_indices.isdisjoint(train_50k_set), "Dev cohort overlaps with classifier training set!"
    assert eval_indices.isdisjoint(train_50k_set), "Eval cohort overlaps with classifier training set!"
