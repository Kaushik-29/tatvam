// MedResolve v2 API client (longitudinal patient memory + STAIR-Clinical pipeline).
import type {
  Consultation, ConsultationSummary, DocumentSummary, LeafDef, PatientProfile, RecordItem,
  SystemStatus, TimelineEvent, TocNode, DemoPatient, StreamEvent, ConsultInput, RecordOffer,
} from './types';

const BASE = '/api/v2';
const TOKEN_KEY = 'medresolve.v2.token';

let token: string | null = null;
try {
  token = sessionStorage.getItem(TOKEN_KEY);
} catch {
  token = null;
}

export function setToken(t: string | null) {
  token = t;
  try {
    if (t) sessionStorage.setItem(TOKEN_KEY, t);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable: keep in memory only */
  }
}

export function hasToken() {
  return !!token;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (init.body && !(init.body instanceof FormData)) headers['Content-Type'] = 'application/json';
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const j = await res.json();
      msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* non-JSON error */
    }
    if (res.status === 401) setToken(null);
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

export interface AuthResult {
  access_token: string;
  patient_id: string;
  onboarding_complete: boolean;
  is_demo: boolean;
}

export const api = {
  register: (b: { email: string; password: string; given_name: string; family_name?: string; birth_date?: string; gender?: string }) =>
    req<AuthResult>('/auth/register', { method: 'POST', body: JSON.stringify(b) }),
  login: (email: string, password: string) =>
    req<AuthResult>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  demoPatients: () => req<DemoPatient[]>('/auth/demo-patients'),
  demoLogin: (pid: string) => req<AuthResult>(`/auth/demo-login/${encodeURIComponent(pid)}`, { method: 'POST' }),

  profile: () => req<PatientProfile>('/profile'),
  updateProfile: (b: Partial<PatientProfile>) => req<PatientProfile>('/profile', { method: 'PUT', body: JSON.stringify(b) }),
  hierarchy: () => req<LeafDef[]>('/hierarchy'),
  toc: () => req<TocNode[]>('/toc'),

  records: (params: { leaf?: string; group?: string; start?: string; end?: string; limit?: number } = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => v !== undefined && v !== '' && q.set(k, String(v)));
    return req<RecordItem[]>(`/records?${q.toString()}`);
  },
  addRecord: (b: { leaf_path: string; display: string; start?: string; end?: string; value_num?: number; value_text?: string; unit?: string; status?: string }) =>
    req<RecordItem>('/records', { method: 'POST', body: JSON.stringify(b) }),
  patchRecord: (id: string, b: Record<string, unknown>) =>
    req<RecordItem>(`/records/${id}`, { method: 'PATCH', body: JSON.stringify(b) }),
  deleteRecord: (id: string) => req<{ deleted: string }>(`/records/${id}`, { method: 'DELETE' }),
  timeline: (params: { start?: string; end?: string; leaves?: string } = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => v && q.set(k, v));
    return req<TimelineEvent[]>(`/timeline?${q.toString()}`);
  },

  uploadDocument: (file: File, documentType: string, documentDate?: string) => {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('document_type', documentType);
    if (documentDate) fd.append('document_date', documentDate);
    return req<{ document_id: string; extracted_records: RecordItem[]; pages: number }>('/documents', { method: 'POST', body: fd });
  },
  documents: (leaf?: string) => req<DocumentSummary[]>(`/documents${leaf ? `?leaf=${encodeURIComponent(leaf)}` : ''}`),
  documentReview: (id: string) =>
    req<{ document_id: string; title: string; text: string; ocr_status: string; doc_date: string | null; extracted_records: RecordItem[] }>(
      `/documents/${id}/review`),
  completeReview: (id: string) => req<{ ocr_status: string }>(`/documents/${id}/complete-review`, { method: 'POST' }),

  consult: (b: ConsultInput) => req<Consultation>('/consult', { method: 'POST', body: JSON.stringify(b) }),
  consultations: () => req<ConsultationSummary[]>('/consultations'),
  recordDecision: (id: string, b: { save: boolean; display?: string }) =>
    req<RecordOffer>(`/consultations/${encodeURIComponent(id)}/record-decision`, { method: 'POST', body: JSON.stringify(b) }),
  consultation: (id: string) => req<Consultation>(`/consultations/${id}`),
  deleteConsultations: () => req<{ deleted: number }>('/data/consultations', { method: 'DELETE' }),
  exportData: () => req<Record<string, unknown>>('/data/export'),
  deleteAccount: () => req<{ deleted: boolean }>('/data/account', { method: 'DELETE' }),
  audit: () => req<{ event: string; actor: string; detail: string; at: string }[]>('/audit'),
  systemStatus: () => req<SystemStatus>('/system/status'),
};

/** Streams a consultation. Stage/evidence events arrive live; answer text arrives only after verification. */
export async function consultStream(body: ConsultInput, onEvent: (e: StreamEvent) => void): Promise<void> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${BASE}/consult/stream`, { method: 'POST', headers, body: JSON.stringify(body) });
  if (!res.ok || !res.body) {
    if (res.status === 401) setToken(null);
    throw new ApiError(res.status, 'Consultation request failed');
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf('\n\n')) >= 0) {
      const raw = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const ev = /^event: (.*)$/m.exec(raw)?.[1] ?? 'message';
      const data = /^data: (.*)$/m.exec(raw)?.[1];
      if (data) onEvent({ event: ev, data: JSON.parse(data) } as StreamEvent);
    }
  }
}
