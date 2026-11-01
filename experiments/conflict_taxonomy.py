"""
MedResolve — Conflict Taxonomy & Specifications
Defines the observable clinical data conflict categories, operational definitions,
severity scales, required actions, and structured conflict report schemas.
"""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class ConflictType(str, Enum):
    """Observable conflict categories in patient evidence ledgers."""
    VALUE_OR_UNIT_DISCREPANCY = "VALUE_OR_UNIT_DISCREPANCY"
    TEMPORAL_DISCREPANCY = "TEMPORAL_DISCREPANCY"
    SOURCE_STATEMENT_DISAGREEMENT = "SOURCE_STATEMENT_DISAGREEMENT"
    LOW_CONFIDENCE_EXTRACTION = "LOW_CONFIDENCE_EXTRACTION"
    MISSING_INFORMATION = "MISSING_INFORMATION"
    ENTERED_OPINION_DISAGREEMENT = "ENTERED_OPINION_DISAGREEMENT"


class ConflictSeverity(str, Enum):
    """Priority level for resolving the detected discrepancy."""
    HIGH = "HIGH"        # Involves critical acute symptoms, vital signs, or divergent units
    MEDIUM = "MEDIUM"    # Involves uncertain extractions, non-acute symptoms, or differing opinions
    LOW = "LOW"          # Involves minor temporal gaps or non-critical missing metadata


class RequiredAction(str, Enum):
    """Action pathway recommended to address the conflict."""
    USER_CONFIRMATION = "USER_CONFIRMATION"               # Patient asked to verify or clarify finding
    QUALIFIED_CLINICAL_REVIEW = "QUALIFIED_CLINICAL_REVIEW" # Requires clinical judgment; outside patient scope


class ConflictTaxonomyItem(BaseModel):
    """Documented definition and clinical boundary for each conflict category."""
    conflict_type: ConflictType
    title: str
    definition: str
    clinical_example: str
    boundary_constraints: str


TAXONOMY_SPECIFICATIONS: Dict[ConflictType, ConflictTaxonomyItem] = {
    ConflictType.VALUE_OR_UNIT_DISCREPANCY: ConflictTaxonomyItem(
        conflict_type=ConflictType.VALUE_OR_UNIT_DISCREPANCY,
        title="Value or Unit Discrepancy",
        definition=(
            "Two or more records for the same clinical concept and same observation window "
            "contain conflicting values, incompatible units, or mutually exclusive categorical choices."
        ),
        clinical_example=(
            "Patient reports oral temperature of 99.0 °F, while a concurrent outpatient clinic "
            "triage record lists core body temperature as 103.5 °F (39.7 °C) for the same visit."
        ),
        boundary_constraints=(
            "Measurements taken on different dates or hours reflect temporal disease progression "
            "and must NOT be classified as value discrepancies without overlapping observation windows."
        )
    ),
    ConflictType.TEMPORAL_DISCREPANCY: ConflictTaxonomyItem(
        conflict_type=ConflictType.TEMPORAL_DISCREPANCY,
        title="Temporal Discrepancy",
        definition=(
            "Contradictions in event chronology, such as an event timestamp recorded in the future "
            "relative to the ingestion timestamp, or impossible duration sequences."
        ),
        clinical_example=(
            "A clinical document dated 2026-03-10 records symptom onset date as 2026-03-25."
        ),
        boundary_constraints=(
            "Different observation dates are not automatically contradictory. A medication timeline "
            "must never be assumed to prove medical causation of an adverse event."
        )
    ),
    ConflictType.SOURCE_STATEMENT_DISAGREEMENT: ConflictTaxonomyItem(
        conflict_type=ConflictType.SOURCE_STATEMENT_DISAGREEMENT,
        title="Source Statement Disagreement",
        definition=(
            "Direct contradiction between patient-reported statements and objective clinical documents "
            "regarding the presence or absence of a symptom during the same encounter."
        ),
        clinical_example=(
            "Patient answers 'No' to experiencing dyspnea (status=ABSENT), but an emergency department "
            "physician note from the same day documents 'severe resting dyspnea observed' (status=PRESENT)."
        ),
        boundary_constraints=(
            "Neither source is assumed to be objectively correct. Patient perception and clinician observation "
            "diverge legitimately due to recall, symptom intermittency, or terminology differences."
        )
    ),
    ConflictType.LOW_CONFIDENCE_EXTRACTION: ConflictTaxonomyItem(
        conflict_type=ConflictType.LOW_CONFIDENCE_EXTRACTION,
        title="Low-Confidence Extraction",
        definition=(
            "An automated extraction method (e.g. OCR or document parser) yielded an extraction "
            "confidence score below an operational threshold (e.g., < 0.70)."
        ),
        clinical_example=(
            "An OCR parser scans a laboratory report and extracts Platelet Count as '150 x10^3/uL' "
            "with a character-level confidence score of 0.45 due to an ink smudge."
        ),
        boundary_constraints=(
            "Low extraction confidence indicates document-processing uncertainty, NOT medical abnormality "
            "or clinical error. It must never be treated as evidence of an erroneous clinical finding."
        )
    ),
    ConflictType.MISSING_INFORMATION: ConflictTaxonomyItem(
        conflict_type=ConflictType.MISSING_INFORMATION,
        title="Missing Information",
        definition=(
            "Absence of an essential clinical attribute where one is strictly necessary for interpretation, "
            "such as a numerical lab value without its unit of measurement or a missing event timestamp."
        ),
        clinical_example=(
            "A document extraction captures Serum Potassium as '6.2' with unit=None, precluding safe "
            "clinical assessment of hyperkalemia without unit verification."
        ),
        boundary_constraints=(
            "Missing fields must be explicitly preserved as None/unknown. Default or imputed values "
            "must never be fabricated."
        )
    ),
    ConflictType.ENTERED_OPINION_DISAGREEMENT: ConflictTaxonomyItem(
        conflict_type=ConflictType.ENTERED_OPINION_DISAGREEMENT,
        title="Entered Clinician Opinion Disagreement",
        definition=(
            "Two distinct external clinician entries or consult letters record differing diagnostic impressions "
            "or differential diagnoses for the same patient presentation."
        ),
        clinical_example=(
            "Urgent care clinician records impression of 'Acute Viral Bronchitis', while a cardiology "
            "consult letter from the same presentation documents 'Congestive Heart Failure Exacerbation'."
        ),
        boundary_constraints=(
            "Opinion disagreement indicates diagnostic ambiguity; the system must NEVER declare which clinician "
            "is correct or arbitrate clinical truth."
        )
    )
}


class ConflictReportItem(BaseModel):
    """Structured report item emitted by the conflict detection engine."""
    conflict_type: ConflictType
    affected_evidence_ids: List[str] = Field(description="Evidence IDs directly involved in the conflict")
    affected_concepts: List[str] = Field(description="Standardized concept codes involved")
    reason: str = Field(description="Objective clinical rationale explaining the discrepancy")
    supporting_sources: List[str] = Field(description="Sources contributing to the conflict")
    severity: ConflictSeverity = Field(description="Justified priority level (HIGH, MEDIUM, LOW)")
    required_action: RequiredAction = Field(description="Recommended action pathway")
    disclaimer: str = Field(
        default=(
            "Conflict detection identifies observable data discrepancies only; "
            "it does not determine clinical ground truth, causation, or diagnostic accuracy."
        ),
        description="Standard medical safety disclaimer"
    )
