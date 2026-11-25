export type Action = 'ASK' | 'EXPLAIN' | 'GENERAL_OPTIONS' | 'ABSTAIN_AND_NAVIGATE' | 'EMERGENCY_OVERRIDE';

export interface PatientProfile {
  patient_id: string;
  source: string;
  given_name: string | null;
  family_name: string | null;
  birth_date: string | null;
  gender: string | null;
  city: string | null;
  state?: string | null;
  deceased_date?: string | null;
  onboarding_complete: boolean;
  is_synthetic: boolean;
  record_count: number;
}

export interface DemoPatient {
  patient_id: string;
  label: string;
  gender: string;
  birth_date: string;
  city: string;
}

export interface LeafDef {
  path: string;
  number: string;
  title: string;
  description: string;
  in_spec: boolean;
  virtual: boolean;
  editable: boolean;
}

export interface TocNode {
  path: string;
  number: string;
  title: string;
  count: number;
  date_range: string | null;
  children: TocNode[];
}

export interface RecordItem {
  record_id: string;
  patient_id: string;
  leaf_path: string;
  group_path: string;
  resource_type: string;
  fhir_resource_id: string | null;
  encounter_id: string | null;
  source_document: string | null;
  source_system: string;
  concept_display: string;
  concept_key: string;
  effective_start: string | null;
  effective_end: string | null;
  recorded_date: string | null;
  value_num: number | null;
  value_text: string | null;
  unit: string | null;
  normalized_value: number | null;
  normalized_unit: string | null;
  clinical_status: string | null;
  verification_status: string;
  confidence: number | null;
  provenance: Record<string, unknown>;
  text: string;
}

export interface EvidenceItem extends RecordItem {
  alias: string;
  epistemic_status: 'CONFIRMED' | 'PATIENT-REPORTED' | 'EXTRACTED-UNCONFIRMED' | 'DERIVED' | 'UNCONFIRMED';
}

export interface ReferenceItem {
  alias: string;
  evidence_id: string;
  text: string;
  path: string;
  source: string;
  chapter: string;
  section: string;
  subsection: string;
  url: string;
  organization: string | null;
  license: string;
  access_date: string | null;
  score: number;
  method: string;
}

export interface Finding {
  finding_type: string;
  severity: 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';
  description: string;
  evidence_ids: string[];
  recommended_action: string;
}

export interface ClaimResult {
  claim_id: string;
  text: string;
  claim_type: string;
  cited_evidence: string[];
  cited_references: string[];
  status: string;
  permitted: boolean;
  rationale: string;
}

export interface Consultation {
  consultation_id: string;
  patient_id: string;
  query: string;
  variant: string;
  intake: Record<string, unknown>;
  action: Action;
  action_reason: string;
  final_text: string;
  raw_generation?: string;
  engine: string;
  evidence: EvidenceItem[];
  references: ReferenceItem[];
  findings: Finding[];
  verification: { claims: ClaimResult[]; withheld: ClaimResult[]; stats: Record<string, number> } | null;
  retrieval_trace: {
    method: string;
    selected_leaves: [string, number][];
    selected_groups: [string, number][];
    invalid_paths: string[];
    structured_ops: string[];
    selector_backend: string | null;
  } | null;
  query_understanding?: Record<string, unknown>;
  record_offer?: RecordOffer;
  timings: Record<string, number>;
  model_config?: Record<string, unknown>;
}

export interface ConsultationSummary {
  consultation_id: string;
  created_at: string;
  query: string;
  action: Action;
  latency_s: number | null;
  preview: string;
}

export interface ConsultInput {
  query: string;
  symptoms?: string[];
  onset?: string;
  duration?: string;
  severity?: string;
  temperature_c?: number;
  notes?: string;
}

export interface TimelineEvent {
  date: string;
  end: string | null;
  leaf_path: string;
  title: string;
  text: string;
  record_ids: string[];
  status: string | null;
  source_system: string;
  verification_status: string;
}

export interface DocumentSummary {
  document_id: string;
  title: string;
  leaf_path: string;
  doc_date: string | null;
  source_system: string;
  ocr_status: string;
  has_file: boolean;
  preview: string;
}

export interface SystemStatus {
  llm: { model: string; available: boolean };
  embedding_model: string;
  stair: { configured_backend: string; adapter: Record<string, unknown> | null };
  datasets: Record<string, unknown>;
  disclaimer: string;
}

export type StreamEvent =
  | { event: 'stage'; data: { stage: string; is_emergency?: boolean } }
  | { event: 'evidence'; data: { evidence: EvidenceItem[]; references: ReferenceItem[]; findings: Finding[] } }
  | { event: 'answer_chunk'; data: { text: string } }
  | { event: 'done'; data: Consultation }
  | { event: 'error'; data: { message: string } };

/** After an answer about a new problem, the patient chooses whether to add it to their record. */
export interface RecordOffer {
  status: 'pending' | 'saved' | 'declined';
  suggested: string;
  display?: string;
  record_id?: string;
}
