import React, { useEffect, useRef, useState } from 'react';
import { ArrowUp, BookOpen, Check, ChevronRight, ClipboardPlus, Flag, Plus, Waypoints } from 'lucide-react';
import { api, consultStream } from '../api';
import type { Consultation, ConsultInput, EvidenceItem, Finding, RecordOffer, ReferenceItem } from '../types';
import type { V2Screen } from '../PatientApp';
import { ActionBanner, AnswerText, Button, Empty, ErrorNote, Input, PageHeader, Pill, cx, fmtDate } from '../ui';

const STAGES: { key: string; label: string }[] = [
  { key: 'emergency_check', label: 'Checking for emergency warning signs' },
  { key: 'retrieving_patient_context', label: 'Finding relevant records in your history' },
  { key: 'retrieving_references', label: 'Looking up medical references' },
  { key: 'reconciling', label: 'Checking for conflicts and missing information' },
  { key: 'generating', label: 'Drafting an answer, held back until verified' },
  { key: 'verifying', label: 'Verifying each statement against the evidence' },
];

interface Turn {
  input: ConsultInput;
  stages: string[];
  evidence?: { evidence: EvidenceItem[]; references: ReferenceItem[]; findings: Finding[] };
  answer: string;
  result?: Consultation;
  error?: string;
}

export function ChatScreen({ pending, clearPending, current, onResult, onCite, onNavigate, readOnly = false }: {
  pending: ConsultInput | null; clearPending: () => void; current: Consultation | null;
  onResult: (c: Consultation) => void; onCite: (alias: string) => void; onNavigate: (s: V2Screen) => void;
  readOnly?: boolean;
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

  const send = () => {
    if (!draft.trim() || busy) return;
    ask({ query: draft.trim() });
    setDraft('');
  };

  return (
    <div className="flex flex-col min-h-[calc(100vh-11rem)]">
      <PageHeader title="Conversation" description="Answers draw on your records and general references. Select a citation to see the exact record or passage." />
      <div className="flex-1 space-y-10">
        {turns.length === 0 && (
          <div className="bg-white rounded-[22px] border border-line/70 shadow-card">
            <Empty title="Start a conversation">
              Ask a question below, or use{' '}
              <button className="text-accent font-medium hover:underline cursor-pointer" onClick={() => onNavigate('concern')}>New health concern</button>{' '}
              to add symptoms, timing and severity.
            </Empty>
          </div>
        )}
        {turns.map((t, i) => (
          <div key={i} className="space-y-4">
            <div className="flex justify-end animate-rise">
              <p className="max-w-[min(80%,640px)] bg-accent text-white text-[16px] leading-relaxed rounded-[22px] rounded-br-[8px] px-[18px] py-3 whitespace-pre-wrap shadow-[0_1px_2px_rgba(10,102,228,0.25)]">
                {t.input.query}
              </p>
            </div>
            <div className="grid xl:grid-cols-[1fr_320px] gap-5 items-start">
              <article className="bg-white rounded-[22px] border border-line/70 shadow-card p-6 animate-rise [animation-delay:60ms]">
                <div className="flex items-center gap-2.5 mb-5">
                  <span className="flex h-7 w-7 items-center justify-center rounded-[8px] bg-accent text-white"><Plus className="w-4 h-4" strokeWidth={3} /></span>
                  <span className="text-[14px] font-semibold">MedResolve</span>
                  {!t.result && !t.error && <span className="text-[13px] text-faint">· working</span>}
                </div>
                {!t.result && !t.error && (
                  <div aria-live="polite">
                    <div className="h-1 rounded-full bg-canvas overflow-hidden mb-5">
                      <div className="h-full rounded-full bg-accent transition-[width] duration-500 ease-out"
                        style={{ width: `${Math.max(6, (t.stages.length / STAGES.length) * 100)}%` }} />
                    </div>
                    <ol className="space-y-2.5">
                      {STAGES.map((st) => {
                        const seen = t.stages.includes(st.key);
                        const last = t.stages[t.stages.length - 1] === st.key;
                        return (
                          <li key={st.key} className={cx('flex items-center gap-3 text-[15px] transition-colors duration-300', seen ? 'text-ink' : 'text-ghost')}>
                            <span className={cx('flex h-5 w-5 shrink-0 items-center justify-center rounded-full transition-all duration-300',
                              seen && !last ? 'bg-success text-white' : last ? 'border-2 border-accent border-t-transparent animate-spin' : 'border-[1.5px] border-line')}>
                              {seen && !last && <Check className="w-3 h-3 animate-pop" strokeWidth={3} />}
                            </span>
                            {st.label}
                          </li>
                        );
                      })}
                    </ol>
                  </div>
                )}
                <ErrorNote error={t.error ?? null} />
                {t.result && <div className="mb-5"><ActionBanner action={t.result.action} reason={t.result.action_reason} /></div>}
                {t.answer && <div className="animate-fade"><AnswerText text={t.answer} onCite={onCite} /></div>}
                {t.result?.record_offer && !readOnly && (
                  <RecordOfferCard consultationId={t.result.consultation_id} offer={t.result.record_offer} />
                )}
                {t.result && (
                  <p className="mt-6 pt-4 border-t border-line-soft text-[12px] text-faint tabular-nums">
                    {t.result.engine} · STAIR: {t.result.retrieval_trace?.selector_backend ?? 'n/a'} · {t.result.timings.total_s}s
                    {t.result.verification && ` · ${t.result.verification.stats.withheld_claims} statement(s) withheld`}
                  </p>
                )}
              </article>
              {t.evidence && (
                <aside className="space-y-4 animate-rise [animation-delay:120ms]">
                  <EvidencePanel icon={<Waypoints className="w-4 h-4" />} title="Records used" count={t.evidence.evidence.length} onAll={() => onNavigate('context')}>
                    <ul className="max-h-60 overflow-y-auto -mx-1">
                      {t.evidence.evidence.slice(0, 8).map((e) => (
                        <li key={e.alias}>
                          <button onClick={() => onCite(e.alias)}
                            className="w-full flex items-baseline gap-2 rounded-[10px] px-1 py-1.5 text-left text-[13px] hover:bg-panel transition-colors cursor-pointer">
                            <span className="font-semibold text-accent tabular-nums shrink-0">{e.alias}</span>
                            <span className="text-ink truncate flex-1">{e.concept_display}</span>
                            <span className="text-faint tabular-nums shrink-0">{fmtDate(e.effective_start).slice(0, 4)}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </EvidencePanel>
                  <EvidencePanel icon={<BookOpen className="w-4 h-4" />} title="References" count={t.evidence.references.length} onAll={() => onNavigate('references')}>
                    <ul className="space-y-1.5">
                      {t.evidence.references.map((r) => (
                        <li key={r.alias} className="text-[13px] leading-snug flex gap-2">
                          <span className="font-semibold text-muted shrink-0">{r.alias}</span>
                          <span className="text-ink-2">{r.section} <span className="text-faint">› {r.subsection}</span></span>
                        </li>
                      ))}
                    </ul>
                  </EvidencePanel>
                  {t.evidence.findings.length > 0 && (
                    <EvidencePanel icon={<Flag className="w-4 h-4" />} title="Flags" count={t.evidence.findings.length} onAll={() => onNavigate('conflicts')} allLabel="Review">
                      <ul className="space-y-2.5">
                        {t.evidence.findings.slice(0, 4).map((f, k) => (
                          <li key={k} className="text-[13px] leading-snug space-y-1"><Pill value={f.severity} /><p className="text-ink-2">{f.description}</p></li>
                        ))}
                      </ul>
                    </EvidencePanel>
                  )}
                </aside>
              )}
            </div>
          </div>
        ))}
        <div ref={bottom} />
      </div>
      <div className="sticky bottom-0 -mx-2 px-2 pt-6 pb-2 mt-8 bg-gradient-to-t from-canvas from-70% to-transparent">
        <div className="flex items-end gap-2 rounded-[26px] bg-white border border-line shadow-float pl-5 pr-2 py-2 transition-[border-color,box-shadow] focus-within:border-accent focus-within:ring-4 focus-within:ring-accent/15">
          <label htmlFor="chat-draft" className="sr-only">Message</label>
          <textarea id="chat-draft" rows={1} value={draft} onChange={(e) => setDraft(e.target.value)}
            placeholder={turns.length ? 'Ask a follow-up question…' : 'Ask about your health record…'}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
            className="flex-1 max-h-40 resize-none bg-transparent py-2 text-[16px] leading-relaxed outline-none placeholder:text-[#a1a1a6] [field-sizing:content]" />
          <button onClick={send} disabled={!draft.trim() || busy} aria-label="Send"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-accent text-white transition-all duration-200 hover:bg-accent-strong active:scale-95 disabled:bg-line disabled:text-faint cursor-pointer disabled:cursor-not-allowed">
            <ArrowUp className="w-5 h-5" strokeWidth={2.4} />
          </button>
        </div>
      </div>
    </div>
  );
}

function EvidencePanel({ icon, title, count, onAll, allLabel = 'All', children }: {
  icon: React.ReactNode; title: string; count: number; onAll: () => void; allLabel?: string; children: React.ReactNode;
}) {
  return (
    <section className="bg-white rounded-[20px] border border-line/70 shadow-card p-4">
      <header className="flex items-center gap-2 mb-3">
        <span className="text-faint">{icon}</span>
        <h3 className="text-[14px] font-semibold flex-1">{title} <span className="text-faint font-normal tabular-nums">{count}</span></h3>
        <button onClick={onAll} className="inline-flex items-center gap-0.5 h-7 rounded-full pl-2.5 pr-1.5 text-[13px] font-medium text-accent hover:bg-accent-soft transition-colors cursor-pointer">
          {allLabel}<ChevronRight className="w-3.5 h-3.5" />
        </button>
      </header>
      {children}
    </section>
  );
}

/** Shown under an answer about a new problem: the patient decides whether it goes into their record. */
function RecordOfferCard({ consultationId, offer }: { consultationId: string; offer: RecordOffer }) {
  const [state, setState] = useState<RecordOffer>(offer);
  const [name, setName] = useState(offer.suggested);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const decide = async (save: boolean) => {
    setBusy(true); setError(null);
    try { setState(await api.recordDecision(consultationId, { save, display: save ? name.trim() : undefined })); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };
  if (state.status === 'saved') {
    return (
      <p className="mt-6 flex items-center gap-2 rounded-[14px] bg-success-soft text-success-ink px-4 py-3 text-[14px]">
        <Check className="w-4 h-4" strokeWidth={3} />
        Added "{state.display}" to your health record as a symptom, dated today. Future answers will use it.
      </p>
    );
  }
  if (state.status === 'declined') {
    return <p className="mt-6 rounded-[14px] bg-panel px-4 py-3 text-[14px] text-muted">Not added to your health record.</p>;
  }
  return (
    <section className="mt-6 rounded-[18px] border border-line bg-panel/60 p-4" aria-label="Add this problem to your health record">
      <p className="flex items-center gap-2 text-[15px] font-semibold"><ClipboardPlus className="w-4 h-4 text-accent" />Is this a new health problem for you?</p>
      <p className="mt-1 text-[14px] text-muted">Add it to your health record so future answers can take it into account. Nothing is saved unless you choose to.</p>
      <label className="mt-3 block text-[13px] text-muted" htmlFor={`offer-${consultationId}`}>Problem to add</label>
      <Input id={`offer-${consultationId}`} value={name} maxLength={200} onChange={(e) => setName(e.target.value)} />
      <div className="mt-3 flex flex-wrap gap-2">
        <Button onClick={() => decide(true)} disabled={busy || !name.trim()}>Add to my health record</Button>
        <Button variant="secondary" onClick={() => decide(false)} disabled={busy}>Don't add</Button>
      </div>
      <ErrorNote error={error} />
    </section>
  );
}
