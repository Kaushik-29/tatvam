import { useCallback, useEffect, useState } from 'react';
import { Upload } from 'lucide-react';
import { api } from '../api';
import type { DocumentSummary } from '../types';
import { Button, Card, Empty, ErrorNote, Field, Input, PageHeader, Pill, Select, Spinner, fmtDate } from '../ui';

export function DocumentsScreen({ readOnly, onReview }: { readOnly: boolean; onReview: (id: string) => void }) {
  const [docs, setDocs] = useState<DocumentSummary[] | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [type, setType] = useState('LAB_REPORT');
  const [date, setDate] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(() => api.documents().then(setDocs).catch((e) => setError(e.message)), []);
  useEffect(() => { load(); }, [load]);

  const upload = async () => {
    if (!file) return;
    setBusy(true); setError(null); setMsg(null);
    try {
      const r = await api.uploadDocument(file, type, date || undefined);
      setMsg(`Processed ${r.pages} page(s); ${r.extracted_records.length} value(s) extracted and held as unconfirmed.`);
      setFile(null);
      await load();
      if (r.extracted_records.length) onReview(r.document_id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader title="Medical documents" description="Upload prescriptions, lab reports and discharge summaries (PDF, PNG, JPG or TXT, max 15 MB). Text is extracted locally with OCR; nothing is sent to external services." />
      {!readOnly && (
        <Card title="Upload a document" className="mb-4">
          <div className="grid sm:grid-cols-4 gap-3 items-end">
            <div className="sm:col-span-2">
              <Field label="File"><Input type="file" accept=".pdf,.png,.jpg,.jpeg,.txt" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></Field>
            </div>
            <Field label="Document type">
              <Select value={type} onChange={(e) => setType(e.target.value)}>
                <option value="LAB_REPORT">Lab / diagnostic report</option>
                <option value="PRESCRIPTION">Prescription</option>
                <option value="DISCHARGE_SUMMARY">Discharge summary</option>
              </Select>
            </Field>
            <Field label="Document date (if known)"><Input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></Field>
          </div>
          <div className="mt-3 flex items-center gap-3">
            <Button onClick={upload} disabled={!file || busy}><Upload className="w-3.5 h-3.5" /> Upload & extract</Button>
            {busy && <Spinner label="Extracting text…" />}
          </div>
          <div className="mt-2 space-y-2"><ErrorNote error={error} />{msg && <p className="text-[12px] text-[#26845A]">{msg}</p>}</div>
        </Card>
      )}
      <Card title="Your documents" subtitle={docs ? `${docs.length} document(s)` : undefined}>
        {!docs ? <Spinner /> : docs.length === 0 ? <Empty title="No documents yet" /> : (
          <ul className="divide-y divide-[#EEF2F7]">
            {docs.map((d) => (
              <li key={d.document_id} className="py-2 flex items-start gap-3">
                <div className="min-w-0 flex-1">
                  <p className="text-[12px] text-[#172B4D] truncate">{d.title}</p>
                  <p className="text-[11px] text-[#8A99AB] tabular-nums">{fmtDate(d.doc_date)} · {d.leaf_path.split('/').pop()?.replace(/_/g, ' ')} · {d.source_system.replace(/_/g, ' ')}</p>
                  <p className="text-[11px] text-[#61738A] line-clamp-2 mt-0.5">{d.preview}</p>
                </div>
                {d.ocr_status === 'pending_review' && <Pill value="UNCONFIRMED" label="needs review" />}
                {d.ocr_status === 'reviewed' && <Pill value="CONFIRMED" label="reviewed" />}
                {d.source_system === 'ocr_extracted' && <Button variant="secondary" onClick={() => onReview(d.document_id)}>Review</Button>}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}
