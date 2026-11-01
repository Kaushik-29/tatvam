import { useEffect, useRef, useState } from 'react';
import { Check, Loader2, Send } from 'lucide-react';
import { consultStream } from '../api';
import type { Consultation, ConsultInput, EvidenceItem, Finding, ReferenceItem } from '../types';
import type { V2Screen } from '../PatientApp';
import { ActionBanner, AnswerText, Button, Card, ErrorNote, Pill, TextArea, cx, fmtDate } from '../ui';

const STAGES: { key: string; label: string }[] = [
  { key: 'emergency_check', label: 'Emergency warning-sign check' },
  { key: 'retrieving_patient_context', label: 'STAIR-Clinical + hybrid retrieval of your records' },
  { key: 'retrieving_references', label: 'Medical reference retrieval' },
  { key: 'reconciling', label: 'Conflict & missing-information check' },
  { key: 'generating', label: 'Drafting answer (held back until verified)' },
  { key: 'verifying', label: 'Claim-by-claim verification' },
];

interface Turn {
  input: ConsultInput;
  stages: string[];
  evidence?: { evidence: EvidenceItem[]; references: ReferenceItem[]; findings: Finding[] };
  answer: string;
  result?: Consultation;
  error?: string;
}

export function ChatScreen({ pending, clearPending, current, onResult, onCite, onNavigate }: {
  pending: ConsultInput | null; clearPending: () => void; current: Consultation | null;
  onResult: (c: Consultation) => void; onCite: (alias: string) => void; onNavigate: (s: V2Screen) => void;
}) {
  const [turns, setTurns] = useState<Turn[]>(() => current ? [{ input: { query: current.query }, stages: [], answer: current.final_text, result: current }] : []);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);

  const ask = async (input: ConsultInput) => {
    setBusy(true);
    const idx = turns.length;
    setTurns((t) => [...t, { input, stages: [], answer: '' }]);
    const update = (fn: (t: Turn) => Turn) => setTurns((ts) => ts.map((t, i) => (i === idx ? fn(t) : t)));
    try {
      await consultStream(input, (e) => {
        if (e.event === 'stage') update((t) => ({ ...t, stages: [...t.stages, e.data.stage] }));
        else if (e.event === 'evidence') update((t) => ({ ...t, evidence: e.data }));
        else if (e.event === 'answer_chunk') update((t) => ({ ...t, answer: t.answer + e.data.text }));
        else if (e.event === 'done') { update((t) => ({ ...t, result: e.data, answer: e.data.final_text })); onResult(e.data); }
        else if (e.event === 'error') update((t) => ({ ...t, error: e.data.message }));
      });
    } catch (err) {
      update((t) => ({ ...t, error: (err as Error).message }));
    } finally {
      setBusy(false);
    }
  };

  // Each pending intake is sent exactly once (StrictMode runs mount effects twice in development).
  const sent = useRef<ConsultInput | null>(null);
  useEffect(() => {
    if (pending && sent.current !== pending) {
      sent.current = pending;
      ask(pending);
      clearPending();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pending]);
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [turns]);

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-[17px] font-semibold text-[#172B4D]">Personalised medical chat</h1>
        <p className="text-[12px] text-[#61738A]">Answers use your records and general references. Click a citation to see the exact record or passage.</p>
      </div>
      {turns.length === 0 && (
        <Card><p className="text-[12px] text-[#61738A]">Ask a question below, or use <button className="text-[#3675CA] underline" onClick={() => onNavigate('concern')}>New health concern</button> for a structured intake.</p></Card>
      )}
      {turns.map((t, i) => (
        <div key={i} className="space-y-2">
          <div className="flex justify-end">
            <p className="max-w-[80%] bg-[#EAF2FC] text-[#172B4D] text-[13px] rounded-lg px-3 py-2 whitespace-pre-wrap">{t.input.query}</p>
          </div>
          <div className="grid xl:grid-cols-[1fr_300px] gap-3">
            <Card>
              {!t.result && !t.error && (
                <ol className="space-y-1 mb-2" aria-live="polite">
                  {STAGES.map((s) => {
                    const seen = t.stages.includes(s.key);
                    const last = t.stages[t.stages.length - 1] === s.key;
                    return (
                      <li key={s.key} className={cx('flex items-center gap-2 text-[12px]', seen ? 'text-[#172B4D]' : 'text-[#B3BFCC]')}>
                        {seen && !last ? <Check className="w-3.5 h-3.5 text-[#26845A]" /> : last ? <Loader2 className="w-3.5 h-3.5 animate-spin text-[#3675CA]" /> : <span className="w-3.5 h-3.5 rounded-full border border-[#DFE7F1]" />}
                        {s.label}
                      </li>
                    );
                  })}
                </ol>
              )}
              <ErrorNote error={t.error ?? null} />
              {t.result && <div className="mb-3"><ActionBanner action={t.result.action} reason={t.result.action_reason} /></div>}
              {t.answer && <AnswerText text={t.answer} onCite={onCite} />}
              {t.result && (
                <p className="mt-3 pt-2 border-t border-[#EEF2F7] text-[10px] text-[#8A99AB] tabular-nums">
                  {t.result.engine} · STAIR backend: {t.result.retrieval_trace?.selector_backend ?? 'n/a'} · {t.result.timings.total_s}s
                  {t.result.verification && ` · ${t.result.verification.stats.withheld_claims} claim(s) withheld`}
                </p>
              )}
            </Card>
            {t.evidence && (
              <aside className="space-y-3">
                <Card title="Records used" subtitle={`${t.evidence.evidence.length} patient evidence items`} actions={<Button variant="ghost" onClick={() => onNavigate('context')}>All</Button>}>
                  <ul className="space-y-1.5 max-h-56 overflow-y-auto">
                    {t.evidence.evidence.slice(0, 8).map((e) => (
                      <li key={e.alias} className="text-[11px]">
                        <button onClick={() => onCite(e.alias)} className="font-semibold text-[#265EAA] mr-1 tabular-nums">{e.alias}</button>
                        <span className="text-[#172B4D]">{e.concept_display}</span>
                        <span className="text-[#8A99AB] tabular-nums"> · {fmtDate(e.effective_start)}</span>
                      </li>
                    ))}
                  </ul>
                </Card>
                <Card title="References" subtitle={`${t.evidence.references.length} passages`} actions={<Button variant="ghost" onClick={() => onNavigate('references')}>All</Button>}>
                  <ul className="space-y-1">
                    {t.evidence.references.map((r) => (
                      <li key={r.alias} className="text-[11px]"><span className="font-semibold text-[#61738A] mr-1">{r.alias}</span>{r.section} › {r.subsection}</li>
                    ))}
                  </ul>
                </Card>
                {t.evidence.findings.length > 0 && (
                  <Card title="Flags" actions={<Button variant="ghost" onClick={() => onNavigate('conflicts')}>Review</Button>}>
                    <ul className="space-y-1">
                      {t.evidence.findings.slice(0, 4).map((f, k) => (
                        <li key={k} className="text-[11px] flex gap-1.5 items-start"><Pill value={f.severity} /><span>{f.description}</span></li>
                      ))}
                    </ul>
                  </Card>
                )}
              </aside>
            )}
          </div>
        </div>
      ))}
      <div ref={bottom} />
      <Card>
        <div className="flex gap-2 items-end">
          <TextArea rows={2} value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Ask a follow-up question…"
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey && draft.trim() && !busy) { e.preventDefault(); ask({ query: draft.trim() }); setDraft(''); } }} />
          <Button disabled={!draft.trim() || busy} onClick={() => { ask({ query: draft.trim() }); setDraft(''); }}><Send className="w-3.5 h-3.5" /> Send</Button>
        </div>
      </Card>
    </div>
  );
}
