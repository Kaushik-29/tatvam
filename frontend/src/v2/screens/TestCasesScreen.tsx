import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Bot, CheckCircle2, ChevronDown, Info } from 'lucide-react';
import { api } from '../api';
import type { TestCase, TestCaseSet } from '../types';
import { Card, ErrorNote, PageHeader, Spinner, cx } from '../ui';

/** The 40 doctor-assessment cases: what the AI chose as the diagnosis, and what the patient app would do. */
export function TestCasesScreen() {
  const [data, setData] = useState<TestCaseSet | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [phase, setPhase] = useState<number | 'all'>('all');
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState<number | null>(null);

  useEffect(() => { api.testCases().then(setData).catch((e) => setError((e as Error).message)); }, []);

  const shown = useMemo(() => (data?.cases ?? []).filter((c) =>
    (phase === 'all' || c.phase === phase) &&
    (!query.trim() || `${c.title} ${c.specialty} ${c.ai_answer} ${c.options.join(' ')}`.toLowerCase().includes(query.trim().toLowerCase()))),
  [data, phase, query]);

  if (error) return <ErrorNote error={error} />;
  if (!data) return <Spinner label="Loading test cases…" />;
  const nEmergency = data.cases.filter((c) => c.patient_app.emergency).length;
  const scored = data.cases.filter((c) => c.answer_index != null);
  const nCorrect = scored.filter((c) => c.answer_index === c.ai_index).length;

  return (
    <>
      <PageHeader eyebrow="Research" title="Test cases"
        description="The 40 cases from the Doctor Diagnostic Assessment, with the diagnosis the AI model chose for each and what MedResolve's patient app would do if a patient described the same situation." />

      <div className="grid sm:grid-cols-3 gap-3 mb-5">
        <Stat label="Cases" value={String(data.cases.length)} note={`${data.phases.length} phases`} />
        <Stat label="Patient app: emergency warning" value={String(nEmergency)} note="cases where the story itself triggers it" />
        <Stat label="AI diagnosis correct" value={scored.length ? `${nCorrect} / ${scored.length}` : 'Not scored yet'}
          note={scored.length ? 'against the clinician answer key' : 'needs a clinician answer key'} />
      </div>

      <p className="mb-5 flex gap-2 rounded-[14px] bg-accent-soft text-accent-strong px-4 py-3 text-[14px] leading-snug">
        <Info className="w-4 h-4 mt-0.5 shrink-0" />
        <span>
          Diagnoses were picked by the AI model alone ({data.ai_run.model}, {data.ai_run.method}). MedResolve's patient app never names a
          diagnosis: it gives information, refers to a clinician, or raises an emergency warning. These are sample cases that a clinician
          has not yet reviewed, so no answer is marked right or wrong.
        </span>
      </p>

      <div className="flex flex-wrap items-center gap-2 mb-4">
        {(['all', ...data.phases.map((p) => p.number)] as (number | 'all')[]).map((p) => (
          <button key={p} onClick={() => setPhase(p)}
            className={cx('h-9 px-3.5 rounded-full text-[14px] transition-colors cursor-pointer',
              phase === p ? 'bg-accent text-white' : 'bg-white border border-line text-ink-2 hover:bg-panel')}>
            {p === 'all' ? 'All phases' : `Phase ${p}: ${data.phases.find((x) => x.number === p)?.title}`}
          </button>
        ))}
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search a disease or specialty"
          aria-label="Search test cases"
          className="ml-auto h-9 w-full sm:w-64 rounded-full border border-line bg-white px-4 text-[14px] outline-none focus:border-accent" />
      </div>

      <Card flush>
        <ul className="divide-y divide-line-soft">
          {shown.map((c) => <CaseRow key={c.id} c={c} open={open === c.id} onToggle={() => setOpen(open === c.id ? null : c.id)} />)}
          {!shown.length && <li className="p-6 text-[14px] text-muted">No case matches.</li>}
        </ul>
      </Card>
      <p className="mt-4 text-[12px] text-faint">Source: {data.source}. AI run {data.ai_run.generated_at.slice(0, 10)}; snapshot {data.generated_at.slice(0, 10)}.</p>
    </>
  );
}

function Stat({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="bg-white rounded-[18px] border border-line/70 shadow-card px-4 py-3">
      <p className="text-[13px] text-muted">{label}</p>
      <p className="text-[24px] font-semibold tabular-nums leading-tight mt-0.5">{value}</p>
      <p className="text-[12px] text-faint">{note}</p>
    </div>
  );
}

function CaseRow({ c, open, onToggle }: { c: TestCase; open: boolean; onToggle: () => void }) {
  const em = c.patient_app.emergency;
  return (
    <li>
      <button onClick={onToggle} aria-expanded={open}
        className="w-full flex items-center gap-3 px-5 py-3.5 text-left hover:bg-panel/60 transition-colors cursor-pointer">
        <span className="w-8 shrink-0 text-[13px] font-semibold text-faint tabular-nums">#{c.id}</span>
        <span className="flex-1 min-w-0">
          <span className="block text-[15px] font-medium truncate">{c.title}</span>
          <span className="block text-[13px] text-muted truncate">{c.specialty} · AI: {c.ai_answer}</span>
        </span>
        {em && <span className="hidden sm:inline-flex items-center gap-1 h-[22px] px-2.5 rounded-full bg-danger-soft text-danger-ink text-[12px] font-medium">
          <AlertTriangle className="w-3 h-3" />Emergency</span>}
        <ChevronDown className={cx('w-4 h-4 text-faint transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <div className="px-5 pb-5 pl-16 space-y-4 animate-fade">
          <p className="text-[15px] leading-relaxed text-ink-2">{c.vignette}</p>
          <div>
            <p className="text-[14px] font-semibold mb-2">{c.question}</p>
            <ol className="space-y-1.5">
              {c.options.map((o, i) => (
                <li key={o} className={cx('flex items-start gap-2 rounded-[10px] px-3 py-2 text-[14px]',
                  i === c.ai_index ? 'bg-accent-soft text-accent-strong font-medium' : 'bg-panel/60 text-ink-2')}>
                  <span className="w-5 shrink-0 font-semibold">{String.fromCharCode(65 + i)}.</span>
                  <span className="flex-1">{o}</span>
                  {i === c.ai_index && <span className="inline-flex items-center gap-1 text-[12px]"><Bot className="w-3.5 h-3.5" />AI's choice</span>}
                  {c.answer_index === i && <span className="inline-flex items-center gap-1 text-[12px] text-success-ink"><CheckCircle2 className="w-3.5 h-3.5" />Answer key</span>}
                </li>
              ))}
            </ol>
          </div>
          {c.ai_reasoning && (
            <div className="rounded-[14px] border border-line px-4 py-3 text-[14px]">
              <p className="font-semibold mb-0.5 flex items-center gap-1.5"><Bot className="w-4 h-4 text-accent" />Why the AI chose this</p>
              <p className="text-ink-2 leading-relaxed">{c.ai_reasoning}</p>
              <p className="mt-1.5 text-[12px] text-faint">Explanation written afterwards by the same model for the answer it had already chosen; not reviewed by a clinician.</p>
            </div>
          )}
          <div className={cx('rounded-[14px] px-4 py-3 text-[14px]', em ? 'bg-danger-soft text-danger-ink' : 'bg-panel text-ink-2')}>
            <p className="font-semibold mb-0.5">If a patient described this in MedResolve</p>
            {em
              ? <p>Emergency warning, before anything else: {c.patient_app.red_flags.join('; ')}. The app tells them to call 112 / 108 or go to the nearest emergency department.</p>
              : <p>No emergency warning is triggered by this wording. The app would give general information and suggest seeing a doctor; it would not name a diagnosis.</p>}
          </div>
        </div>
      )}
    </li>
  );
}
