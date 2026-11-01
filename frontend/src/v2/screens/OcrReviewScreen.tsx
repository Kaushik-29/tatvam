import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';
import type { DocumentSummary, RecordItem } from '../types';
import { Button, Card, Empty, ErrorNote, Input, PageHeader, Pill, Select, Spinner, fmtDate } from '../ui';

type Review = Awaited<ReturnType<typeof api.documentReview>>;

export function OcrReviewScreen({ readOnly, initialDoc }: { readOnly: boolean; initialDoc: string | null }) {
  const [docs, setDocs] = useState<DocumentSummary[]>([]);
  const [docId, setDocId] = useState<string | null>(initialDoc);
  const [review, setReview] = useState<Review | null>(null);
  const [edits, setEdits] = useState<Record<string, { value: string; unit: string }>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.documents().then((d) => {
      const ocr = d.filter((x) => x.source_system === 'ocr_extracted');
      setDocs(ocr);
      if (!docId && ocr[0]) setDocId(ocr[0].document_id);
    }).catch((e) => setError(e.message));
  }, [docId]);

  const load = useCallback(() => { if (docId) api.documentReview(docId).then(setReview).catch((e) => setError(e.message)); }, [docId]);
  useEffect(() => { load(); }, [load]);

  const act = async (r: RecordItem, status: 'confirmed' | 'refuted') => {
    const e = edits[r.record_id];
    const patch: Record<string, unknown> = { verification_status: status };
    if (e && status === 'confirmed') {
      if (e.value !== '' && !Number.isNaN(Number(e.value))) patch.value_num = Number(e.value);
      if (e.unit) patch.unit = e.unit;
    }
    await api.patchRecord(r.record_id, patch);
    load();
  };

  return (
    <>
      <PageHeader title="Review extracted data" description="OCR can misread values and units. Confirm, correct or reject each extracted value. Unconfirmed values are labelled as such whenever MedResolve uses them." />
      <ErrorNote error={error} />
      {docs.length === 0 ? <Card><Empty title="No uploaded documents to review">Upload a document first.</Empty></Card> : (
        <div className="grid lg:grid-cols-[1fr_1.2fr] gap-4">
          <Card title="Document" actions={
            <Select value={docId ?? ''} onChange={(e) => setDocId(e.target.value)} className="max-w-[240px]">
              {docs.map((d) => <option key={d.document_id} value={d.document_id}>{d.title} ({d.ocr_status})</option>)}
            </Select>}>
            {!review ? <Spinner /> : (
              <pre className="text-[11px] whitespace-pre-wrap bg-[#FAF9F6] border border-[#EEF2F7] rounded p-3 max-h-[520px] overflow-y-auto font-mono text-[#172B4D]">{review.text || '(no text extracted)'}</pre>
            )}
          </Card>
          <Card title="Extracted values" subtitle={review ? `${review.extracted_records.length} item(s) · status ${review.ocr_status}` : undefined}
            actions={review && !readOnly && review.ocr_status !== 'reviewed' ? <Button variant="secondary" onClick={async () => { await api.completeReview(review.document_id); load(); }}>Mark review complete</Button> : undefined}>
            {!review ? <Spinner /> : review.extracted_records.length === 0 ? <Empty title="Nothing was extracted" /> : (
              <ul className="space-y-2">
                {review.extracted_records.map((r) => {
                  const prov = r.provenance as Record<string, string | number | null>;
                  return (
                    <li key={r.record_id} className="border border-[#EEF2F7] rounded p-2.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-[12px] font-medium text-[#172B4D]">{r.concept_display}</span>
                        <Pill value={r.verification_status} />
                        <span className="text-[10px] text-[#8A99AB] tabular-nums">confidence {(r.confidence ?? 0).toFixed(2)} · unit {String(prov.unit_status ?? 'n/a')} · page {String(prov.page ?? '?')}</span>
                      </div>
                      <p className="text-[11px] text-[#61738A] mt-1">Raw text: <span className="font-mono">{String(prov.raw_text ?? '')}</span></p>
                      <div className="flex flex-wrap gap-2 items-center mt-2">
                        <span className="text-[11px] tabular-nums">{r.value_num ?? r.value_text} {r.unit ?? <em className="text-[#C23E4A]">no unit</em>} · {fmtDate(r.effective_start)}</span>
                        {!readOnly && r.verification_status === 'unconfirmed' && (
                          <>
                            <Input className="max-w-[90px]" placeholder="value" value={edits[r.record_id]?.value ?? ''}
                              onChange={(e) => setEdits({ ...edits, [r.record_id]: { value: e.target.value, unit: edits[r.record_id]?.unit ?? '' } })} />
                            <Input className="max-w-[90px]" placeholder="unit" value={edits[r.record_id]?.unit ?? ''}
                              onChange={(e) => setEdits({ ...edits, [r.record_id]: { unit: e.target.value, value: edits[r.record_id]?.value ?? '' } })} />
                            <Button onClick={() => act(r, 'confirmed')}>Confirm</Button>
                            <Button variant="danger" onClick={() => act(r, 'refuted')}>Reject</Button>
                          </>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </Card>
        </div>
      )}
    </>
  );
}
