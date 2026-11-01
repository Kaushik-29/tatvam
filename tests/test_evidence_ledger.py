"""
MedResolve — Unit Tests for Source-Aware Evidence Ledger
Verifies schema enforcement, source provenance, timestamp preservation,
missing value handling, and serialization integrity.
"""

import pytest
from pydantic import ValidationError

from experiments.evidence_ledger import (
    ClinicianOpinionItem,
    EvidenceItem,
    EvidenceLedger,
    EvidenceStatus,
    ExtractionMethod,
    SourceType,
    UserConfirmationStatus,
)


def test_evidence_item_schema_validation():
    """Verify field type checking and valid confidence bounds [0.0, 1.0]."""
    item = EvidenceItem(
        evidence_id="ev_001",
        patient_case_id="case_001",
        concept="E_53",
        concept_name_en="Fever",
        normalized_value=True,
        original_value="Yes, high fever",
        unit=None,
        source_type=SourceType.PATIENT_REPORTED,
        recorded_timestamp="2026-10-15T10:00:00Z",
        event_timestamp="2026-10-15T08:00:00Z",
        extraction_method=ExtractionMethod.DIRECT_SELECTION,
        extraction_confidence=1.0,
        user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT,
        evidence_status=EvidenceStatus.PRESENT,
        is_simulated=True,
    )
    assert item.evidence_id == "ev_001"
    assert item.extraction_confidence == 1.0

    # Invalid confidence score > 1.0
    with pytest.raises(ValidationError):
        EvidenceItem(
            evidence_id="ev_inv",
            patient_case_id="case_001",
            concept="E_53",
            normalized_value=True,
            source_type=SourceType.PATIENT_REPORTED,
            recorded_timestamp="2026-10-15T10:00:00Z",
            extraction_method=ExtractionMethod.DIRECT_SELECTION,
            extraction_confidence=1.5,  # Invalid
            evidence_status=EvidenceStatus.PRESENT,
        )


def test_source_and_timestamp_preservation():
    """Verify that source provenance and exact timestamps are preserved intact."""
    item = EvidenceItem(
        evidence_id="ev_ehr_01",
        patient_case_id="case_002",
        concept="E_50",
        normalized_value=True,
        source_type=SourceType.EHR_EXTRACTED_NOTE,
        source_document_id="doc_ed_discharge_99",
        source_page=2,
        recorded_timestamp="2026-09-01T14:30:00Z",
        event_timestamp="2026-09-01T12:00:00Z",
        extraction_method=ExtractionMethod.RULE_BASED_PARSER,
        extraction_confidence=0.92,
        user_confirmation_status=UserConfirmationStatus.UNCONFIRMED,
        evidence_status=EvidenceStatus.PRESENT,
        is_simulated=True,
    )

    assert item.source_type == SourceType.EHR_EXTRACTED_NOTE
    assert item.source_document_id == "doc_ed_discharge_99"
    assert item.source_page == 2
    assert item.recorded_timestamp == "2026-09-01T14:30:00Z"
    assert item.event_timestamp == "2026-09-01T12:00:00Z"


def test_missing_values_remain_explicitly_none():
    """Assert that omitted units and timestamps remain explicitly None (no default fabrication)."""
    item = EvidenceItem(
        evidence_id="ev_003",
        patient_case_id="case_003",
        concept="E_LAB_POTASSIUM",
        normalized_value=4.5,
        original_value="4.5",
        unit=None,  # Intentionally missing unit
        source_type=SourceType.LABORATORY_REPORT,
        recorded_timestamp="2026-10-15T10:00:00Z",
        event_timestamp=None,  # Intentionally missing event time
        extraction_method=ExtractionMethod.RULE_BASED_PARSER,
        extraction_confidence=0.95,
        evidence_status=EvidenceStatus.PRESENT,
        is_simulated=True,
    )

    assert item.unit is None
    assert item.event_timestamp is None
    assert item.source_document_id is None
    assert item.source_page is None


def test_raw_and_normalized_value_separation():
    """Verify that raw source strings and canonical normalized values are maintained separately."""
    item = EvidenceItem(
        evidence_id="ev_004",
        patient_case_id="case_004",
        concept="E_TEMP",
        normalized_value=101.4,
        original_value="101.4 deg Fahrenheit orally",
        unit="degF",
        source_type=SourceType.PATIENT_REPORTED,
        recorded_timestamp="2026-10-15T10:00:00Z",
        extraction_method=ExtractionMethod.MANUAL_ENTRY,
        extraction_confidence=1.0,
        evidence_status=EvidenceStatus.PRESENT,
    )

    assert isinstance(item.normalized_value, float)
    assert item.normalized_value == 101.4
    assert item.original_value == "101.4 deg Fahrenheit orally"
    assert item.unit == "degF"


def test_evidence_ledger_roundtrip_serialization():
    """Verify dictionary and JSON roundtrip serialization of an EvidenceLedger."""
    ledger = EvidenceLedger(patient_case_id="case_roundtrip_001")
    ledger.add_item(
        EvidenceItem(
            evidence_id="ev_rt_1",
            patient_case_id="case_roundtrip_001",
            concept="E_53",
            normalized_value=True,
            source_type=SourceType.PATIENT_REPORTED,
            recorded_timestamp="2026-10-15T10:00:00Z",
            extraction_method=ExtractionMethod.DIRECT_SELECTION,
            extraction_confidence=1.0,
            evidence_status=EvidenceStatus.PRESENT,
        )
    )
    ledger.add_opinion(
        ClinicianOpinionItem(
            opinion_id="op_rt_1",
            patient_case_id="case_roundtrip_001",
            clinician_id="clinician_01",
            clinician_specialty="Internal Medicine",
            diagnostic_impression="Influenza",
            recorded_timestamp="2026-10-15T10:30:00Z",
        )
    )

    ledger_dict = ledger.to_dict()
    reconstructed = EvidenceLedger.from_dict(ledger_dict)

    assert reconstructed.patient_case_id == "case_roundtrip_001"
    assert len(reconstructed.items) == 1
    assert reconstructed.items[0].concept == "E_53"
    assert len(reconstructed.opinions) == 1
    assert reconstructed.opinions[0].diagnostic_impression == "Influenza"
