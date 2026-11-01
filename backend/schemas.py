"""
MedResolve — FastAPI Backend Request and Response Schemas
Typed Pydantic contracts for frontend integration preserving the core research structures.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from experiments.evidence_ledger import (
    SourceType,
    ExtractionMethod,
    UserConfirmationStatus,
    EvidenceStatus,
)
from experiments.action_policy import PolicyAction


class PatientProfile(BaseModel):
    patient_id: str
    name: str
    age: int
    sex: str
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    relevant_background: Optional[str] = None
    reported_diagnoses: List[str] = Field(default_factory=list)
    allergies: List[str] = Field(default_factory=list)
    current_medications: List[Dict[str, Any]] = Field(default_factory=list)
    past_medical_history: List[str] = Field(default_factory=list)
    is_synthetic: bool = True
    synthetic_case_archetype: str


class EvidenceItemDTO(BaseModel):
    evidence_id: str
    patient_case_id: str
    concept: str
    concept_name_en: Optional[str] = None
    normalized_value: Any
    original_value: Optional[str] = None
    unit: Optional[str] = None
    source_type: SourceType
    source_document_id: Optional[str] = None
    source_page: Optional[int] = None
    event_timestamp: Optional[str] = None
    recorded_timestamp: str
    extraction_method: ExtractionMethod
    extraction_confidence: float
    user_confirmation_status: UserConfirmationStatus
    evidence_status: EvidenceStatus
    is_simulated: bool = True
    notes: Optional[str] = None


class ClinicianOpinionDTO(BaseModel):
    opinion_id: str
    patient_case_id: str
    clinician_id: str
    clinician_specialty: str
    diagnostic_impression: str
    confidence_assessment: Optional[str] = "PROBABLE"
    recorded_timestamp: str
    source_document_id: Optional[str] = None
    is_simulated: bool = True
    notes: Optional[str] = None


class ConflictItemDTO(BaseModel):
    conflict_id: str
    conflict_category: str
    category_name: str
    is_material: bool
    description: str
    involved_evidence_ids: List[str] = Field(default_factory=list)
    involved_opinion_ids: List[str] = Field(default_factory=list)
    resolution_status: str = "UNRESOLVED"
    resolution_action: str
    clinical_risk: str


class RetrievedPassageDTO(BaseModel):
    passage_id: str
    document_id: str
    document_title: str
    organization: str
    publication_date: str
    license: str
    source_url: str
    section_heading: str
    text: str
    score: float
    dense_score: Optional[float] = None
    bm25_score: Optional[float] = None
    citation: str


class PolicyDecisionDTO(BaseModel):
    selected_action: PolicyAction
    is_emergency_override: bool
    reason: str
    detailed_rationale: str
    uncertainty_signals: Dict[str, Any] = Field(default_factory=dict)
    detected_conflicts_count: int = 0
    target_concept_to_ask: Optional[str] = None
    candidate_question_en: Optional[str] = None
    question_rationale: Optional[str] = None
    explanation_summary: Optional[Dict[str, Any]] = None
    abstention_summary: Optional[Dict[str, Any]] = None
    emergency_details: Optional[Dict[str, Any]] = None
    disclaimer: str


class ClaimVerificationItemDTO(BaseModel):
    claim_id: str
    claim_text: str
    claim_type: str
    cited_passage_ids: List[str] = Field(default_factory=list)
    supporting_passage_ids: List[str] = Field(default_factory=list)
    reference_verification_status: str
    patient_consistency_status: str
    is_permitted_in_final: bool
    reference_rationale: str
    patient_consistency_rationale: str


class AssessmentResultDTO(BaseModel):
    assessment_id: str
    patient_id: str
    timestamp: str
    workflow_stage: str
    policy_decision: PolicyDecisionDTO
    retrieved_passages: List[RetrievedPassageDTO] = Field(default_factory=list)
    verified_claims: List[ClaimVerificationItemDTO] = Field(default_factory=list)
    generated_text: str
    execution_engine: str
    generation_latency_seconds: float
    is_emergency_override: bool


class DocumentUploadResponseDTO(BaseModel):
    document_id: str
    filename: str
    file_type: str
    extracted_items_count: int
    unconfirmed_items_count: int
    extracted_items: List[EvidenceItemDTO]
    processing_latency_ms: Optional[float] = None
    full_text_preview: Optional[str] = None


class OcrObservationDTO(BaseModel):
    concept: str
    concept_name_en: str
    raw_text: str
    normalized_value: str
    unit: Optional[str] = None
    unit_status: str  # EXPLICIT, NORMALIZED, INFERRED, MISSING, INVALID
    reference_range: Optional[str] = None
    document_date: Optional[str] = None
    page_number: int
    confidence: float
    extraction_method: str
    requires_confirmation: bool
    confirmation_reason: Optional[str] = None


class DocumentReviewDTO(BaseModel):
    document_id: str
    patient_id: str
    filename: str
    document_type: str
    file_size_bytes: int
    uploaded_timestamp: str
    total_pages: int = 1
    full_text: str
    processing_latency_ms: float
    structured_items: List[OcrObservationDTO] = Field(default_factory=list)


class EmergencyContactDTO(BaseModel):
    code: str
    name: str
    primary: str
    ambulance: str


class EmergencyConfigDTO(BaseModel):
    region: str
    region_display: str
    primary_emergency_number: str
    ambulance_emergency_number: str
    emergency_service_name: str
    available_regions: List[EmergencyContactDTO] = Field(default_factory=list)

