export type PolicyAction =
  | 'ASK'
  | 'EXPLAIN'
  | 'ABSTAIN_AND_NAVIGATE'
  | 'EMERGENCY_OVERRIDE';

export type SourceType =
  | 'PATIENT_REPORTED'
  | 'EHR_EXTRACTED_NOTE'
  | 'LABORATORY_REPORT'
  | 'PRIOR_PRESCRIPTION'
  | 'ENTERED_CLINICIAN_OPINION';

export type UserConfirmationStatus =
  | 'UNCONFIRMED'
  | 'CONFIRMED_BY_PATIENT'
  | 'REJECTED_BY_PATIENT'
  | 'CONFIRMED_BY_CLINICIAN';

export type EvidenceStatus =
  | 'PRESENT'
  | 'ABSENT'
  | 'UNCERTAIN'
  | 'UNKNOWN';

export interface Medication {
  name: string;
  dose: string;
  duration: string;
  indication: string;
}

export interface PatientProfile {
  patient_id: string;
  name: string;
  age: number;
  sex: string;
  height_cm?: number;
  weight_kg?: number;
  relevant_background?: string;
  reported_diagnoses: string[];
  allergies: string[];
  current_medications: Medication[];
  past_medical_history: string[];
  synthetic_case_archetype: string;
  archetype_display: string;
  expected_action: PolicyAction;
  clinical_narrative: string;
  documents_count: number;
  evidence_count: number;
  conflicts_count: number;
}

export interface EvidenceItem {
  evidence_id: string;
  patient_case_id: string;
  concept: string;
  concept_name_en?: string;
  normalized_value: any;
  original_value?: string;
  unit?: string;
  source_type: SourceType;
  source_document_id?: string;
  source_page?: number;
  event_timestamp?: string;
  recorded_timestamp: string;
  extraction_method: string;
  extraction_confidence: number;
  user_confirmation_status: UserConfirmationStatus;
  evidence_status: EvidenceStatus;
  is_simulated: boolean;
  notes?: string;
}

export interface ClinicianOpinion {
  opinion_id: string;
  patient_case_id: string;
  clinician_id: string;
  clinician_specialty: string;
  diagnostic_impression: string;
  confidence_assessment?: string;
  recorded_timestamp: string;
  source_document_id?: string;
  is_simulated: boolean;
  notes?: string;
}

export interface ConflictItem {
  conflict_id: string;
  conflict_category: string;
  category_name: string;
  is_material: boolean;
  description: string;
  involved_evidence_ids: string[];
  involved_opinion_ids: string[];
  resolution_status: string;
  resolution_action: string;
  clinical_risk: string;
}

export interface RetrievedPassage {
  passage_id: string;
  document_id: string;
  document_title: string;
  organization: string;
  publication_date: string;
  license: string;
  source_url: string;
  section_heading: string;
  text: string;
  score: number;
  dense_score?: number;
  citation: string;
}

export interface PolicyDecision {
  selected_action: PolicyAction;
  is_emergency_override: boolean;
  reason: string;
  detailed_rationale: string;
  uncertainty_signals: Record<string, any>;
  detected_conflicts_count: number;
  target_concept_to_ask?: string;
  candidate_question_en?: string;
  question_rationale?: string;
  explanation_summary?: Record<string, any>;
  abstention_summary?: Record<string, any>;
  emergency_details?: Record<string, any>;
  disclaimer: string;
}

export interface ClaimVerificationItem {
  claim_id: string;
  claim_text: string;
  claim_type: string;
  cited_passage_ids: string[];
  supporting_passage_ids: string[];
  reference_verification_status: string;
  patient_consistency_status: string;
  is_permitted_in_final: boolean;
  reference_rationale: string;
  patient_consistency_rationale: string;
}

export interface AssessmentResult {
  assessment_id: string;
  patient_id: string;
  timestamp: string;
  workflow_stage: string;
  policy_decision: PolicyDecision;
  retrieved_passages: RetrievedPassage[];
  verified_claims: ClaimVerificationItem[];
  generated_text: string;
  execution_engine: string;
  generation_latency_seconds: number;
  is_emergency_override: boolean;
}

export interface DocumentUploadResponse {
  document_id: string;
  filename: string;
  document_type: string;
  status: string;
  extracted_items_count: number;
  unconfirmed_items_count: number;
  extracted_items: EvidenceItem[];
}
