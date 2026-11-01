import {
  PatientProfile,
  EvidenceItem,
  ClinicianOpinion,
  ConflictItem,
  RetrievedPassage,
  AssessmentResult,
  DocumentUploadResponse,
} from '../types';

const BASE_URL = '/api';

export async function fetchHealth(): Promise<any> {
  const res = await fetch(`${BASE_URL}/health`);
  if (!res.ok) throw new Error('Failed to fetch system health');
  return res.json();
}

export async function fetchPatients(): Promise<PatientProfile[]> {
  const res = await fetch(`${BASE_URL}/patients`);
  if (!res.ok) throw new Error('Failed to fetch synthetic patients');
  return res.json();
}

export async function fetchPatient(patientId: string): Promise<PatientProfile> {
  const res = await fetch(`${BASE_URL}/patients/${patientId}`);
  if (!res.ok) throw new Error(`Failed to fetch patient ${patientId}`);
  return res.json();
}

export async function fetchEvidenceLedger(patientId: string): Promise<{
  patient_case_id: string;
  items: EvidenceItem[];
  opinions: ClinicianOpinion[];
  total_items: number;
  total_opinions: number;
}> {
  const res = await fetch(`${BASE_URL}/evidence-ledger/${patientId}`);
  if (!res.ok) throw new Error(`Failed to fetch evidence ledger for ${patientId}`);
  return res.json();
}

export async function confirmLedgerItem(
  patientId: string,
  evidenceId: string,
  action: 'CONFIRM' | 'REJECT'
): Promise<any> {
  const formData = new FormData();
  formData.append('evidence_id', evidenceId);
  formData.append('action', action);

  const res = await fetch(`${BASE_URL}/evidence-ledger/${patientId}/confirm-item`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error('Failed to update confirmation status');
  return res.json();
}

export async function addLedgerItem(
  patientId: string,
  concept: string,
  conceptName: string,
  value: string,
  unit?: string,
  status = 'PRESENT',
  notes?: string
): Promise<any> {
  const formData = new FormData();
  formData.append('concept', concept);
  formData.append('concept_name', conceptName);
  formData.append('value', value);
  if (unit) formData.append('unit', unit);
  formData.append('status', status);
  if (notes) formData.append('notes', notes);

  const res = await fetch(`${BASE_URL}/evidence-ledger/${patientId}/add-item`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error('Failed to add evidence item');
  return res.json();
}

export async function fetchConflicts(patientId: string): Promise<{
  patient_id: string;
  total_conflicts: number;
  material_conflicts_count: number;
  conflicts: ConflictItem[];
}> {
  const res = await fetch(`${BASE_URL}/conflicts/${patientId}`);
  if (!res.ok) throw new Error(`Failed to fetch conflicts for ${patientId}`);
  return res.json();
}

export async function fetchKnowledgeBase(): Promise<{
  corpus_version: string;
  total_passages: number;
  passages: any[];
}> {
  const res = await fetch(`${BASE_URL}/knowledge-base`);
  if (!res.ok) throw new Error('Failed to fetch knowledge base');
  return res.json();
}

export async function queryKnowledge(query: string, topK = 5): Promise<{
  query: string;
  retrieval_method: string;
  top_k: number;
  results: RetrievedPassage[];
}> {
  const formData = new FormData();
  formData.append('query', query);
  formData.append('top_k', topK.toString());

  const res = await fetch(`${BASE_URL}/retrieval/query`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error('Failed to query knowledge retriever');
  return res.json();
}

export async function assessPatient(patientId: string): Promise<AssessmentResult> {
  const res = await fetch(`${BASE_URL}/assess/${patientId}`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`Failed to assess patient ${patientId}`);
  return res.json();
}

export async function uploadDocument(
  patientId: string,
  file: File,
  documentType: string
): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append('patient_id', patientId);
  formData.append('document_type', documentType);
  formData.append('file', file);

  const res = await fetch(`${BASE_URL}/documents/upload`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error('Failed to upload document');
  return res.json();
}

export async function fetchPatientDocuments(patientId: string): Promise<{
  patient_id: string;
  documents: any[];
}> {
  const res = await fetch(`${BASE_URL}/documents/${patientId}`);
  if (!res.ok) throw new Error(`Failed to fetch documents for ${patientId}`);
  return res.json();
}

export async function fetchAssessmentHistory(): Promise<{
  total_records: number;
  history: AssessmentResult[];
}> {
  const res = await fetch(`${BASE_URL}/assessment-history`);
  if (!res.ok) throw new Error('Failed to fetch assessment history');
  return res.json();
}

export async function fetchResearchMetrics(): Promise<any> {
  const res = await fetch(`${BASE_URL}/research/metrics`);
  if (!res.ok) throw new Error('Failed to fetch research metrics');
  return res.json();
}

export async function fetchDocumentDetails(
  patientId: string,
  documentId: string
): Promise<any> {
  const res = await fetch(`${BASE_URL}/documents/${patientId}/${documentId}`);
  if (!res.ok) throw new Error(`Failed to fetch document details for ${documentId}`);
  return res.json();
}

export function getDocumentFileUrl(patientId: string, documentId: string): string {
  return `${BASE_URL}/documents/${patientId}/${documentId}/file`;
}

export async function updateLedgerItem(
  patientId: string,
  evidenceId: string,
  action: 'CONFIRM' | 'REJECT' | 'CORRECT' | 'MARK_UNREADABLE',
  correctedValue?: string,
  correctedUnit?: string,
  notes?: string
): Promise<any> {
  const formData = new FormData();
  formData.append('evidence_id', evidenceId);
  formData.append('action', action);
  if (correctedValue !== undefined) formData.append('corrected_value', correctedValue);
  if (correctedUnit !== undefined) formData.append('corrected_unit', correctedUnit);
  if (notes) formData.append('notes', notes);

  const res = await fetch(`${BASE_URL}/evidence-ledger/${patientId}/update-item`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error(`Failed to update evidence item: ${res.statusText}`);
  return res.json();
}

export async function fetchEmergencyConfig(): Promise<{
  region: string;
  region_display: string;
  primary_emergency_number: string;
  ambulance_emergency_number: string;
  emergency_service_name: string;
  available_regions: Array<{ code: string; name: string; primary: string; ambulance: string }>;
}> {
  const res = await fetch(`${BASE_URL}/emergency-config`);
  if (!res.ok) throw new Error('Failed to fetch emergency configuration');
  return res.json();
}

export async function updateEmergencyConfig(regionCode: string): Promise<any> {
  const formData = new FormData();
  formData.append('region_code', regionCode);

  const res = await fetch(`${BASE_URL}/emergency-config`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error('Failed to update emergency configuration');
  return res.json();
}

