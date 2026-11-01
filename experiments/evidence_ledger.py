"""
MedResolve — Source-Aware Evidence Ledger
Defines the schema and data models for structured patient evidence tracking,
including source provenance, timestamps, extraction uncertainty, confirmation status,
and raw-to-normalized value traceability.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class SourceType(str, Enum):
    """Provenance category for clinical observations."""
    PATIENT_REPORTED = "PATIENT_REPORTED"
    EHR_EXTRACTED_NOTE = "EHR_EXTRACTED_NOTE"
    LABORATORY_REPORT = "LABORATORY_REPORT"
    PRIOR_PRESCRIPTION = "PRIOR_PRESCRIPTION"
    ENTERED_CLINICIAN_OPINION = "ENTERED_CLINICIAN_OPINION"


class ExtractionMethod(str, Enum):
    """Method utilized to obtain the evidence record."""
    DIRECT_SELECTION = "DIRECT_SELECTION"
    MANUAL_ENTRY = "MANUAL_ENTRY"
    OCR_EXTRACTION = "OCR_EXTRACTION"
    RULE_BASED_PARSER = "RULE_BASED_PARSER"
    LLM_EXTRACTION = "LLM_EXTRACTION"


class UserConfirmationStatus(str, Enum):
    """Status of verification by user or medical professional."""
    UNCONFIRMED = "UNCONFIRMED"
    CONFIRMED_BY_PATIENT = "CONFIRMED_BY_PATIENT"
    REJECTED_BY_PATIENT = "REJECTED_BY_PATIENT"
    CONFIRMED_BY_CLINICIAN = "CONFIRMED_BY_CLINICIAN"


class EvidenceStatus(str, Enum):
    """Clinical assertion status of the evidence finding."""
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    UNCERTAIN = "UNCERTAIN"
    UNKNOWN = "UNKNOWN"


class EvidenceItem(BaseModel):
    """
    Individual evidence entry within a patient's evidence ledger.
    Maintains provenance, timestamps, raw vs. normalized values, and confidence.
    """
    evidence_id: str = Field(description="Unique identifier for this evidence observation")
    patient_case_id: str = Field(description="Identifier for the patient case")
    concept: str = Field(description="Standardized clinical concept or token code (e.g. E_53, E_54_@_V_180)")
    concept_name_en: Optional[str] = Field(default=None, description="Human-readable concept description in English")
    normalized_value: Any = Field(description="Canonical normalized value (bool, string code, float)")
    original_value: Optional[str] = Field(default=None, description="Raw unnormalized extracted text")
    unit: Optional[str] = Field(default=None, description="Measurement unit (e.g. degF, degC, mg/dL) or None if dimensionless")
    source_type: SourceType = Field(description="Provenance source of the evidence")
    source_document_id: Optional[str] = Field(default=None, description="Identifier of source document or report")
    source_page: Optional[int] = Field(default=None, description="Page number in source document")
    event_timestamp: Optional[str] = Field(default=None, description="ISO 8601 timestamp when clinical event occurred")
    recorded_timestamp: str = Field(description="ISO 8601 timestamp when observation was ingested/recorded")
    extraction_method: ExtractionMethod = Field(description="Method used to extract the observation")
    extraction_confidence: float = Field(ge=0.0, le=1.0, description="Extraction confidence score in [0.0, 1.0]")
    user_confirmation_status: UserConfirmationStatus = Field(
        default=UserConfirmationStatus.UNCONFIRMED,
        description="Patient or clinician confirmation state"
    )
    evidence_status: EvidenceStatus = Field(description="Clinical status: PRESENT, ABSENT, UNCERTAIN, UNKNOWN")
    is_simulated: bool = Field(default=True, description="Flag indicating simulated or benchmark data")
    notes: Optional[str] = Field(default=None, description="Optional contextual notes")

    @field_validator("extraction_confidence")
    def validate_confidence_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"extraction_confidence must be between 0.0 and 1.0, got {v}")
        return float(v)


class ClinicianOpinionItem(BaseModel):
    """
    Structured record of an entered clinician diagnostic or clinical opinion.
    Tracks provenance without declaring clinical truth.
    """
    opinion_id: str = Field(description="Unique identifier for the entered opinion")
    patient_case_id: str = Field(description="Identifier for the patient case")
    clinician_id: str = Field(description="Identifier or pseudonym of the clinician")
    clinician_specialty: str = Field(description="Medical specialty (e.g., General Practice, Cardiology)")
    diagnostic_impression: str = Field(description="Diagnostic condition name or impression")
    confidence_assessment: Optional[str] = Field(default="PROBABLE", description="Stated certainty level")
    recorded_timestamp: str = Field(description="ISO 8601 timestamp when opinion was entered")
    source_document_id: Optional[str] = Field(default=None, description="Source consultation letter or note ID")
    is_simulated: bool = Field(default=True, description="Flag indicating simulated data")
    notes: Optional[str] = Field(default=None, description="Contextual clinical summary")


class EvidenceLedger(BaseModel):
    """
    Container ledger for all evidence items and clinician opinions for a patient case.
    """
    patient_case_id: str = Field(description="Unique patient case identifier")
    items: List[EvidenceItem] = Field(default_factory=list, description="List of evidence observations")
    opinions: List[ClinicianOpinionItem] = Field(default_factory=list, description="List of entered clinician opinions")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Case-level metadata")

    def add_item(self, item: EvidenceItem) -> None:
        """Appends an evidence item to the ledger."""
        self.items.append(item)

    def add_opinion(self, opinion: ClinicianOpinionItem) -> None:
        """Appends a clinician opinion to the ledger."""
        self.opinions.append(opinion)

    def get_items_by_concept(self, concept: str) -> List[EvidenceItem]:
        """Returns all evidence items matching the given concept code."""
        return [item for item in self.items if item.concept == concept]

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the ledger to a plain dictionary."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceLedger":
        """Reconstructs an EvidenceLedger from a dictionary."""
        return cls.model_validate(data)
