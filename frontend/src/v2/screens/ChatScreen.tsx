import React, { useEffect, useRef, useState } from 'react';
import { ArrowUp, BookOpen, Brain, Check, ChevronRight, ClipboardPlus, Flag, MessageCircle, Plus, Sparkles, Waypoints } from 'lucide-react';
import { api, consultStream } from '../api';
import type { AnswerMode, Consultation, ConsultInput, EvidenceItem, Finding, MemoryMode, RecordOffer, ReferenceItem } from '../types';
import type { V2Screen } from '../PatientApp';
import { ActionBanner, AnswerText, Button, Empty, ErrorNote, Input, PageHeader, Pill, cx, fmtDate } from '../ui';
import { AnswerModeSwitch, MicButton, useAnswerMode } from '../components';

const STAGES: { key: string; label: string; memoryOnly?: boolean }[] = [
  { key: 'emergency_check', label: 'Checking for emergency warning signs' },
  { key: 'retrieving_patient_context', label: 'Finding relevant records in your history', memoryOnly: true },
  { key: 'retrieving_references', label: 'Looking up medical references' },
  { key: 'reconciling', label: 'Checking for conflicts and missing information', memoryOnly: true },
  { key: 'generating', label: 'Drafting an answer, held back until verified' },
  { key: 'verifying', label: 'Verifying each statement against the evidence' },
];

const PANEL_INFO: Record<MemoryMode, { title: string; sub: string; icon: React.ReactNode; chip: string }> = {
  memory: { title: 'With your memory', sub: 'Uses your health record', icon: <Brain className="w-4 h-4" strokeWidth={2.4} />, chip: 'bg-accent text-white' },
  normal: { title: 'Normal answer', sub: 'Your health record is not used', icon: <MessageCircle className="w-4 h-4" strokeWidth={2.4} />, chip: 'bg-ink-2 text-white' },
};

interface Panel {
  started: boolean;
  stages: string[];
  evidence?: { evidence: EvidenceItem[]; references: ReferenceItem[]; findings: Finding[] };
  answer: string;
  result?: Consultation;
  error?: string;
}

interface Turn {
  input: ConsultInput;
  mode: AnswerMode;
  panels: Partial<Record<MemoryMode, Panel>>;
}

const panelsFor = (mode: AnswerMode): MemoryMode[] => (mode === 'both' ? ['normal', 'memory'] : [mode]);
const blankPanel = (started: boolean): Panel => ({ started, stages: [], answer: '' });

export function ChatScreen({ pending, clearPending, current, onResult, onCite, onNavigate, readOnly = false }: {
  pending: ConsultInput | null; clearPending: () => void; current: Consultation | null;
  onResult: (c: Consultation) => void; onCite: (alias: string) => void; onNavigate: (s: V2Screen) => void;
  readOnly?: boolean;
}) {
  const [mode, setMode] = useAnswerMode();
  const [turns, setTurns] = useState<Turn[]>(() => {
    if (!current) return [];
    const m: MemoryMode = current.memory_mode ?? 'memory';
    return [{ input: { query: current.query }, mode: m, panels: { [m]: { started: true, stages: [], answer: current.final_text, result: current } } }];
  });
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);

  const ask = async (input: ConsultInput) => {
    const m: AnswerMode = input.mode ?? mode;
    const body = { ...input, mode: m };
    setBusy(true);
    const idx = turns.length;
    const order = panelsFor(m);
    const panels: Turn['panels'] = {};
    order.forEach((p, i) => { panels[p] = blankPanel(i === 0); });
    setTurns((t) => [...t, { input: body, mode: m, panels }]);
    const update = (p: MemoryMode, fn: (x: Panel) => Panel) =>
      setTurns((ts) => ts.map((t, i) => (i === idx && t.panels[p] ? { ...t, panels: { ...t.panels, [p]: fn(t.panels[p]!) } } : t)));
    const finished: Partial<Record<MemoryMode, Consultation>> = {};
    try {
      await consultStream(body, (e) => {
        const p: MemoryMode = ('panel' in e.data && e.data.panel) || order[order.length - 1];
        if (e.event === 'panel_start') update(p, (x) => ({ ...x, started: true }));
        else if (e.event === 'stage') update(p, (x) => ({ ...x, started: true, stages: [...x.stages, e.data.stage] }));
        else if (e.event === 'evidence') update(p, (x) => ({ ...x, evidence: e.data }));
        else if (e.event === 'answer_chunk') update(p, (x) => ({ ...x, answer: x.answer + e.data.text }));
        else if (e.event === 'done') { finished[p] = e.data; update(p, (x) => ({ ...x, result: e.data, answer: e.data.final_text })); }
        else if (e.event === 'error') update(p, (x) => ({ ...x, started: true, error: e.data.message }));
      });
      // "Why this answer" screens follow the record-based answer when there is one
      const main = finished.memory ?? finished.normal;
      if (main) onResult(main);
    } catch (err) {
      order.forEach((p) => update(p, (x) => (x.result ? x : { ...x, started: true, error: (err as Error).message })));
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
              to add symptoms, timing and severity. Choose <span className="text-ink font-medium">Compare both</span> to see how your record changes the answer.
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
            {t.mode === 'both' ? (
              <>
                {t.panels.normal?.result && t.panels.memory?.result && (
                  <CompareSummary normal={t.panels.normal.result} memory={t.panels.memory.result} onCite={onCite} />
                )}
                <div className="grid lg:grid-cols-2 gap-5 items-start">
                  {panelsFor('both').map((p) => t.panels[p] && (
                    <div key={p} className="space-y-4 min-w-0">
                      <AnswerCard panel={t.panels[p]!} which={p} labelled waitingFor={p === 'memory' ? 'the normal answer' : undefined}
                        onCite={onCite} readOnly={readOnly} />
                      {t.panels[p]!.evidence && p === 'memory' && <EvidenceAside ev={t.panels[p]!.evidence!} onCite={onCite} onNavigate={onNavigate} compact />}
                      {t.panels[p]!.evidence && p === 'normal' && <ReferencesOnly ev={t.panels[p]!.evidence!} onNavigate={onNavigate} />}
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="grid xl:grid-cols-[1fr_320px] gap-5 items-start">
                {panelsFor(t.mode).map((p) => t.panels[p] && (
                  <AnswerCard key={p} panel={t.panels[p]!} which={p} labelled={p === 'normal'} onCite={onCite} readOnly={readOnly} />
                ))}
                {panelsFor(t.mode).map((p) => t.panels[p]?.evidence && (
                  <EvidenceAside key={`ev-${p}`} ev={t.panels[p]!.evidence!} onCite={onCite} onNavigate={onNavigate} />
                ))}
              </div>
            )}
          </div>
        ))}
        <div ref={bottom} />
      </div>
      <div className="sticky bottom-0 -mx-2 px-2 pt-6 pb-2 mt-8 bg-gradient-to-t from-canvas from-70% to-transparent">
        <div className="mb-2.5 pl-1"><AnswerModeSwitch mode={mode} onChange={setMode} disabled={busy} /></div>
        <div className="flex items-end gap-2 rounded-[26px] bg-white border border-line shadow-float pl-5 pr-2 py-2 transition-[border-color,box-shadow] focus-within:border-accent focus-within:ring-4 focus-within:ring-accent/15">
          <label htmlFor="chat-draft" className="sr-only">Message</label>
          <textarea id="chat-draft" rows={1} value={draft} onChange={(e) => setDraft(e.target.value)}
            placeholder={turns.length ? 'Ask a follow-up question…' : 'Ask about your health record…'}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
            className="flex-1 max-h-40 resize-none bg-transparent py-2 text-[16px] leading-relaxed outline-none placeholder:text-[#a1a1a6] [field-sizing:content]" />
          <MicButton onText={(t) => setDraft((d) => (d.trim() ? `${d.trim()} ${t}` : t))} />
          <button onClick={send} disabled={!draft.trim() || busy} aria-label="Send"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-accent text-white transition-all duration-200 hover:bg-accent-strong active:scale-95 disabled:bg-line disabled:text-faint cursor-pointer disabled:cursor-not-allowed">
            <ArrowUp className="w-5 h-5" strokeWidth={2.4} />
          </button>
        </div>
      </div>
    </div>
  );
}

/** One answer: progress while working, then the action banner, verified text and footer. */
function AnswerCard({ panel, which, labelled, waitingFor, onCite, readOnly }: {
  panel: Panel; which: MemoryMode; labelled: boolean; waitingFor?: string; onCite: (a: string) => void; readOnly: boolean;
}) {
  const info = PANEL_INFO[which];
  const stages = STAGES.filter((s) => which === 'memory' || !s.memoryOnly);
  const working = !panel.result && !panel.error;
  const bannerLabel = which === 'normal' && panel.result?.action === 'GENERAL_OPTIONS'
    ? 'General medicine options, not checked against your records' : undefined;
  return (
    <article className="bg-white rounded-[22px] border border-line/70 shadow-card p-6 animate-rise [animation-delay:60ms] min-w-0">
      <div className="flex items-center gap-2.5 mb-5">
        {labelled ? (
          <>
            <span className={cx('flex h-7 w-7 items-center justify-center rounded-[8px]', info.chip)}>{info.icon}</span>
            <span className="min-w-0">
              <span className="block text-[14px] font-semibold leading-tight">{info.title}</span>
              <span className="block text-[12px] text-faint leading-tight">{info.sub}</span>
            </span>
          </>
        ) : (
          <>
            <span className="flex h-7 w-7 items-center justify-center rounded-[8px] bg-accent text-white"><Plus className="w-4 h-4" strokeWidth={3} /></span>
            <span className="text-[14px] font-semibold">MedResolve</span>
          </>
        )}
        {working && <span className="text-[13px] text-faint">· {panel.started ? 'working' : 'waiting'}</span>}
      </div>
      {working && !panel.started && (
        <p className="text-[14px] text-muted" aria-live="polite">Starts as soon as {waitingFor ?? 'the other answer'} is ready.</p>
      )}
      {working && panel.started && (
        <div aria-live="polite">
          <div className="h-1 rounded-full bg-canvas overflow-hidden mb-5">
            <div className="h-full rounded-full bg-accent transition-[width] duration-500 ease-out"
              style={{ width: `${Math.max(6, (panel.stages.length / stages.length) * 100)}%` }} />
          </div>
          <ol className="space-y-2.5">
            {stages.map((st) => {
              const seen = panel.stages.includes(st.key);
              const last = panel.stages[panel.stages.length - 1] === st.key;
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
      <ErrorNote error={panel.error ?? null} />
      {panel.result && <div className="mb-5"><ActionBanner action={panel.result.action} reason={panel.result.action_reason} label={bannerLabel} /></div>}
      {panel.answer && <div className="animate-fade min-w-0 [overflow-wrap:anywhere]"><AnswerText text={panel.answer} onCite={onCite} /></div>}
      {panel.result?.record_offer && !readOnly && (
        <RecordOfferCard consultationId={panel.result.consultation_id} offer={panel.result.record_offer} />
      )}
      {panel.result && (
        <p className="mt-6 pt-4 border-t border-line-soft text-[12px] text-faint tabular-nums">
          {panel.result.engine} · {which === 'normal' ? 'record not used' : `STAIR: ${panel.result.retrieval_trace?.selector_backend ?? 'n/a'}`} · {panel.result.timings.total_s}s
          {panel.result.verification && ` · ${panel.result.verification.stats.withheld_claims} statement(s) withheld`}
        </p>
      )}
    </article>
  );
}

const cited = (text: string) => new Set(Array.from(text.matchAll(/\[(E\d+(?:\s*,\s*E\d+)*)\]/g)).flatMap((m) => m[1].split(/\s*,\s*/)));

/** "Compare both": what the health record changed, so the patient can see where the difference comes from. */
function CompareSummary({ normal, memory, onCite }: { normal: Consultation; memory: Consultation; onCite: (a: string) => void }) {
  const aliases = cited(memory.final_text);
  for (const a of memory.medicine_options?.record_aliases ?? []) aliases.add(a);
  const used = memory.evidence.filter((e) => aliases.has(e.alias));
  const points: React.ReactNode[] = [];
  if (normal.action !== memory.action) {
    points.push(<>The normal answer gave <b className="font-semibold">{label(normal.action)}</b>. With your memory, MedResolve chose{' '}
      <b className="font-semibold">{label(memory.action)}</b>: {memory.action_reason}</>);
  }
  const nOpts = normal.medicine_options?.options ?? [];
  const mOpts = memory.medicine_options?.options ?? [];
  const dropped = nOpts.filter((o) => !mOpts.includes(o));
  if (dropped.length) {
    points.push(<>Your record removed <b className="font-semibold">{dropped.join(', ')}</b> from the medicine options (see the "Checked against your records" part of the memory answer).</>);
  }
  if (memory.findings.length) {
    points.push(<>Your record raised {memory.findings.length} flag{memory.findings.length > 1 ? 's' : ''}: {memory.findings.slice(0, 2).map((f) => f.description).join(' ')}</>);
  }
  if (used.length) {
    points.push(<>The memory answer cites {used.length} record{used.length > 1 ? 's' : ''} from your history. The normal answer cites none.</>);
  }
  return (
    <section className="rounded-[22px] border border-accent/25 bg-accent-soft/50 p-5 animate-rise" aria-label="What your memory changed">
      <h3 className="flex items-center gap-2 text-[15px] font-semibold text-ink"><Sparkles className="w-4 h-4 text-accent" />What your memory changed</h3>
      {points.length ? (
        <ul className="mt-2.5 space-y-1.5 text-[14px] leading-snug text-ink-2 list-disc pl-5">
          {points.map((p, k) => <li key={k}>{p}</li>)}
        </ul>
      ) : (
        <p className="mt-2 text-[14px] text-ink-2">Nothing in your record changed this answer: no record was relevant to the question, so both answers give the same general information.</p>
      )}
      {used.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {used.slice(0, 10).map((e) => (
            <button key={e.alias} onClick={() => onCite(e.alias)}
              className="inline-flex items-baseline gap-1.5 rounded-full bg-white border border-line px-2.5 py-1 text-[13px] hover:border-accent transition-colors cursor-pointer">
              <span className="font-semibold text-accent tabular-nums">{e.alias}</span>
              <span className="text-ink">{e.concept_display}</span>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

const ACTION_WORDS: Record<string, string> = {
  EXPLAIN: 'an explanation', GENERAL_OPTIONS: 'general medicine options', ASK: 'follow-up questions',
  ABSTAIN_AND_NAVIGATE: 'advice to see a clinician', EMERGENCY_OVERRIDE: 'an emergency warning',
};
const label = (a: string) => ACTION_WORDS[a] ?? a;

function EvidenceAside({ ev, onCite, onNavigate, compact = false }: {
  ev: NonNullable<Panel['evidence']>; onCite: (a: string) => void; onNavigate: (s: V2Screen) => void; compact?: boolean;
}) {
  return (
    <aside className={cx('animate-rise [animation-delay:120ms]', compact ? 'grid sm:grid-cols-2 gap-4' : 'space-y-4')}>
      <EvidencePanel icon={<Waypoints className="w-4 h-4" />} title="Records used" count={ev.evidence.length} onAll={() => onNavigate('context')}>
        <ul className="max-h-60 overflow-y-auto -mx-1">
          {ev.evidence.slice(0, 8).map((e) => (
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
      <ReferencesOnly ev={ev} onNavigate={onNavigate} />
      {ev.findings.length > 0 && (
        <EvidencePanel icon={<Flag className="w-4 h-4" />} title="Flags" count={ev.findings.length} onAll={() => onNavigate('conflicts')} allLabel="Review">
          <ul className="space-y-2.5">
            {ev.findings.slice(0, 4).map((f, k) => (
              <li key={k} className="text-[13px] leading-snug space-y-1"><Pill value={f.severity} /><p className="text-ink-2">{f.description}</p></li>
            ))}
          </ul>
        </EvidencePanel>
      )}
    </aside>
  );
}

function ReferencesOnly({ ev, onNavigate }: { ev: NonNullable<Panel['evidence']>; onNavigate: (s: V2Screen) => void }) {
  return (
    <EvidencePanel icon={<BookOpen className="w-4 h-4" />} title="References" count={ev.references.length} onAll={() => onNavigate('references')}>
      {ev.references.length === 0 ? <p className="text-[13px] text-faint">Medicine options cite their sources in the answer.</p> : (
        <ul className="space-y-1.5">
          {ev.references.map((r) => (
            <li key={r.alias} className="text-[13px] leading-snug flex gap-2">
              <span className="font-semibold text-muted shrink-0">{r.alias}</span>
              <span className="text-ink-2">{r.section} <span className="text-faint">› {r.subsection}</span></span>
            </li>
          ))}
        </ul>
      )}
    </EvidencePanel>
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
