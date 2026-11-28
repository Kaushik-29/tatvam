import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Brain, Columns2, Loader2, MessageCircle, Mic, Plus, Square, Trash2 } from 'lucide-react';
import { api } from './api';
import type { AnswerMode, RecordItem } from './types';
import { Button, ErrorNote, Field, Input, Pill, Select, cx, fmtDate } from './ui';

export const LEAF_LABEL: Record<string, string> = {
  'medical_history/diagnoses': 'Diagnosis',
  'medical_history/conditions': 'Condition',
  'medical_history/procedures': 'Procedure',
  'medical_history/immunizations': 'Immunization',
  'medical_history/social_history': 'Social history',
  'medication_history/current_medications': 'Current medication',
  'medication_history/previous_medications': 'Previous medication',
  'allergy_history': 'Allergy',
  'clinical_encounters/previous_symptoms': 'Previous symptom',
  'clinical_encounters/complaints': 'Complaint',
  'laboratory_observations/laboratory_results': 'Lab result',
  'laboratory_observations/vital_signs': 'Vital sign',
};

const STATUS_OPTIONS: Record<string, string[]> = {
  'medical_history/diagnoses': ['active', 'resolved'],
  'medical_history/conditions': ['active', 'resolved'],
  'medication_history/current_medications': ['active'],
  'medication_history/previous_medications': ['stopped', 'completed'],
  'allergy_history': ['active', 'inactive'],
  'clinical_encounters/previous_symptoms': ['resolved', 'ongoing'],
};

export function QuickAdd({ leaves, onAdded, placeholder }: { leaves: string[]; onAdded: (r: RecordItem) => void; placeholder?: string }) {
  const [leaf, setLeaf] = useState(leaves[0]);
  const [display, setDisplay] = useState('');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [value, setValue] = useState('');
  const [unit, setUnit] = useState('');
  const [status, setStatus] = useState('');
  const [error, setError] = useState<string | null>(null);
  const numeric = leaf.startsWith('laboratory_observations');
  const statuses = STATUS_OPTIONS[leaf];

  const add = async () => {
    if (!display.trim()) return;
    setError(null);
    try {
      const num = numeric && value.trim() !== '' ? Number(value) : undefined;
      if (num !== undefined && Number.isNaN(num)) throw new Error('Value must be a number');
      const r = await api.addRecord({
        leaf_path: leaf, display: display.trim(), start: start || undefined, end: end || undefined,
        value_num: num, value_text: !numeric && value ? value : undefined, unit: unit || undefined,
        status: status || statuses?.[0],
      });
      onAdded(r);
      setDisplay(''); setStart(''); setEnd(''); setValue(''); setUnit('');
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3 items-end rounded-[16px] bg-panel border border-line-soft p-4">
        {leaves.length > 1 && (
          <Field label="Type">
            <Select value={leaf} onChange={(e) => { setLeaf(e.target.value); setStatus(''); }}>
              {leaves.map((l) => <option key={l} value={l}>{LEAF_LABEL[l] ?? l}</option>)}
            </Select>
          </Field>
        )}
        <div className={leaves.length > 1 ? 'col-span-2 md:col-span-2' : 'col-span-2 md:col-span-3'}>
          <Field label="Name"><Input value={display} placeholder={placeholder} onChange={(e) => setDisplay(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && add()} /></Field>
        </div>
        {numeric ? (
          <>
            <Field label="Value"><Input inputMode="decimal" value={value} onChange={(e) => setValue(e.target.value)} /></Field>
            <Field label="Unit"><Input value={unit} placeholder="e.g. mg/dL" onChange={(e) => setUnit(e.target.value)} /></Field>
          </>
        ) : (
          <Field label={leaf.includes('medication') ? 'Dose / details' : 'Details'}><Input value={value} onChange={(e) => setValue(e.target.value)} /></Field>
        )}
        <Field label="Start / date"><Input type="date" value={start} onChange={(e) => setStart(e.target.value)} /></Field>
        {statuses && (
          <Field label="Status">
            <Select value={status || statuses[0]} onChange={(e) => setStatus(e.target.value)}>
              {statuses.map((s) => <option key={s}>{s}</option>)}
            </Select>
          </Field>
        )}
        {(status === 'resolved' || status === 'stopped' || leaf.endsWith('previous_medications')) && (
          <Field label="End date"><Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} /></Field>
        )}
        <Button onClick={add} disabled={!display.trim()} className="h-11"><Plus className="w-4 h-4" /> Add</Button>
      </div>
      <ErrorNote error={error} />
    </div>
  );
}

export function RecordTable({ records, onDelete, onConfirm, emptyText, compact }: {
  records: RecordItem[]; onDelete?: (r: RecordItem) => void; onConfirm?: (r: RecordItem) => void; emptyText?: string; compact?: boolean;
}) {
  if (!records.length) return <p className="text-[14px] text-faint py-3">{emptyText ?? 'Nothing recorded.'}</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[14px]">
        <thead>
          <tr className="text-left text-[14px] font-medium text-faint">
            <th className="py-2 px-1 pr-4 font-medium">Item</th>
            <th className="py-2 pr-4 font-medium">Date</th>
            {!compact && <th className="py-2 pr-4 font-medium">Value / status</th>}
            <th className="py-2 pr-4 font-medium">Source</th>
            {(onDelete || onConfirm) && <th className="py-2" />}
          </tr>
        </thead>
        <tbody className="divide-y divide-line-soft border-t border-line-soft">
          {records.map((r) => (
            <tr key={r.record_id} className="align-top group transition-colors hover:bg-panel">
              <td className="py-3 px-1 pr-4 text-ink font-medium">{r.concept_display}</td>
              <td className="py-3 pr-4 tabular-nums text-muted whitespace-nowrap">
                {fmtDate(r.effective_start)}{r.effective_end ? ` → ${fmtDate(r.effective_end)}` : ''}
              </td>
              {!compact && (
                <td className="py-3 pr-4 tabular-nums text-muted">
                  {r.value_num !== null ? `${r.value_num} ${r.unit ?? '(no unit)'}` : r.value_text ?? ''} {r.clinical_status && <span className="text-faint">· {r.clinical_status}</span>}
                </td>
              )}
              <td className="py-3 pr-4">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <Pill value={r.verification_status} />
                  <span className="text-[14px] text-faint">{r.source_system.replace(/_/g, ' ')}</span>
                </div>
              </td>
              {(onDelete || onConfirm) && (
                <td className="py-2.5 pr-1 text-right whitespace-nowrap">
                  {onConfirm && r.verification_status === 'unconfirmed' && (
                    <button onClick={() => onConfirm(r)} className="h-8 px-3 rounded-full text-[15px] font-medium text-success-ink hover:bg-success-soft transition-colors cursor-pointer mr-1">Confirm</button>
                  )}
                  {onDelete && r.source_system !== 'synthea_fhir_r4' && r.source_system !== 'derived' && (
                    <button onClick={() => onDelete(r)} aria-label={`Delete ${r.concept_display}`}
                      className="inline-flex h-8 w-8 items-center justify-center rounded-full text-faint opacity-60 group-hover:opacity-100 hover:text-danger hover:bg-danger-soft transition-all cursor-pointer">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Record a spoken question and turn it into text with local Whisper (nothing leaves this machine).
 *  Click to start, click again to stop (stops by itself after 60 s). The text is handed back for editing. */
export function MicButton({ onText, className }: { onText: (text: string) => void; className?: string }) {
  const [state, setState] = useState<'idle' | 'recording' | 'working'>('idle');
  const [error, setError] = useState<string | null>(null);
  const rec = useRef<MediaRecorder | null>(null);
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => () => { window.clearTimeout(timer.current); rec.current?.stream.getTracks().forEach((t) => t.stop()); }, []);

  const start = async () => {
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setError('Voice input is not supported in this browser.'); return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      const chunks: Blob[] = [];
      mr.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
      mr.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setState('working');
        try {
          const r = await api.transcribe(new Blob(chunks, { type: mr.mimeType || 'audio/webm' }));
          if (r.text) onText(r.text); else setError("Didn't catch that. Please try again.");
        } catch (e) { setError((e as Error).message); }
        finally { setState('idle'); }
      };
      rec.current = mr;
      mr.start();
      setState('recording');
      timer.current = window.setTimeout(() => { if (mr.state === 'recording') mr.stop(); }, 60_000);
    } catch {
      setError('Microphone access was blocked. Allow it in the browser to speak your question.');
    }
  };
  const stop = () => { window.clearTimeout(timer.current); rec.current?.state === 'recording' && rec.current.stop(); };

  const label = state === 'recording' ? 'Stop recording' : state === 'working' ? 'Turning speech into text' : 'Speak your question';
  return (
    <span className={cx('inline-flex items-center gap-2', className)}>
      <button type="button" onClick={state === 'recording' ? stop : start} disabled={state === 'working'}
        aria-label={label} title={label}
        className={cx('flex h-10 w-10 shrink-0 items-center justify-center rounded-full transition-colors cursor-pointer disabled:cursor-wait',
          state === 'recording' ? 'bg-danger text-white animate-pulse' : 'bg-accent-soft text-accent hover:bg-accent hover:text-white')}>
        {state === 'recording' ? <Square className="w-4 h-4" fill="currentColor" />
          : state === 'working' ? <Loader2 className="w-5 h-5 animate-spin" /> : <Mic className="w-5 h-5" />}
      </button>
      {state === 'recording' && <span className="text-[13px] text-danger-ink" role="status">Listening… click to stop</span>}
      {state === 'working' && <span className="text-[13px] text-muted" role="status">Turning speech into text…</span>}
      {error && <span className="text-[13px] text-danger-ink" role="alert">{error}</span>}
    </span>
  );
}

/* ---------------------------------------------------------------- answer mode */

const MODE_KEY = 'medresolve.answerMode';
const MODES: { id: AnswerMode; label: string; hint: string; icon: ReactNode }[] = [
  { id: 'memory', label: 'Use my memory', hint: 'Answers use your health record', icon: <Brain className="w-4 h-4" /> },
  { id: 'normal', label: 'Normal', hint: 'General answer, your record is not used', icon: <MessageCircle className="w-4 h-4" /> },
  { id: 'both', label: 'Compare both', hint: 'Both answers side by side', icon: <Columns2 className="w-4 h-4" /> },
];

/** The chosen answer mode, remembered in this browser (shared by the Ask and Chat screens). */
export function useAnswerMode(): [AnswerMode, (m: AnswerMode) => void] {
  const read = (): AnswerMode => {
    const v = typeof localStorage !== 'undefined' ? localStorage.getItem(MODE_KEY) : null;
    return v === 'normal' || v === 'both' ? v : 'memory';
  };
  const [mode, setMode] = useState<AnswerMode>(read);
  const set = (m: AnswerMode) => { setMode(m); try { localStorage.setItem(MODE_KEY, m); } catch { /* private mode */ } };
  return [mode, set];
}

export function AnswerModeSwitch({ mode, onChange, disabled = false }: {
  mode: AnswerMode; onChange: (m: AnswerMode) => void; disabled?: boolean;
}) {
  const current = MODES.find((m) => m.id === mode) ?? MODES[0];
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
      <div role="radiogroup" aria-label="Answer mode" className="inline-flex rounded-full bg-canvas p-1 border border-line/70">
        {MODES.map((m) => (
          <button key={m.id} type="button" role="radio" aria-checked={mode === m.id} disabled={disabled}
            onClick={() => onChange(m.id)} title={m.hint}
            className={cx('inline-flex h-8 items-center gap-1.5 rounded-full px-3 text-[13px] font-medium transition-all duration-200 cursor-pointer disabled:cursor-not-allowed disabled:opacity-60',
              mode === m.id ? 'bg-white text-ink shadow-[0_1px_3px_rgba(0,0,0,0.12)]' : 'text-muted hover:text-ink')}>
            {m.icon}{m.label}
          </button>
        ))}
      </div>
      <span className="text-[13px] text-faint">{current.hint}</span>
    </div>
  );
}
