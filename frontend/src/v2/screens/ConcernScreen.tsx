import { useState } from 'react';
import { ArrowUpRight, ChevronDown, OctagonAlert, Send } from 'lucide-react';
import type { ConsultInput, PatientProfile } from '../types';
import { Button, Card, Field, Input, PageHeader, Select, cx } from '../ui';
import { MicButton } from '../components';

const EXAMPLES = [
  "I've been feeling dizzy when I stand up for the last 3 days. Could it be related to my history or medications?",
  'Find my previous kidney-related laboratory results and explain how they changed.',
  'Have I had a cough like this before, and what medicines was I taking then?',
  'Do I have any allergies I should mention before my dentist prescribes an antibiotic?',
];

export function ConcernScreen({ profile, onSubmit }: { profile: PatientProfile; onSubmit: (q: ConsultInput) => void }) {
  const [query, setQuery] = useState('');
  const [symptoms, setSymptoms] = useState('');
  const [onset, setOnset] = useState('');
  const [duration, setDuration] = useState('');
  const [severity, setSeverity] = useState('');
  const [temp, setTemp] = useState('');
  const [notes, setNotes] = useState('');
  const [showDetails, setShowDetails] = useState(false);
  const detailCount = [symptoms, onset, duration, severity, temp, notes].filter((v) => v.trim()).length;

  const submit = () => {
    if (!query.trim()) return;
    const t = temp.trim() === '' ? undefined : Number(temp);
    onSubmit({
      query: query.trim(),
      symptoms: symptoms.split(',').map((s) => s.trim()).filter(Boolean),
      onset: onset || undefined, duration: duration || undefined, severity: severity || undefined,
      temperature_c: t !== undefined && !Number.isNaN(t) ? t : undefined, notes: notes || undefined,
    });
  };

  const first = profile.given_name?.split(' ')[0];
  return (
    <>
      <PageHeader eyebrow={first ? `Hello, ${first}` : undefined} title="What's on your mind today?"
        description={<>Describe what is happening now. MedResolve checks for emergency warning signs first, then looks through{' '}
          {profile.record_count ? <span className="text-ink">your {profile.record_count.toLocaleString()} records</span> : 'your record (currently empty)'} and general medical references.</>} />
      <div className="grid lg:grid-cols-[1.55fr_1fr] gap-6 items-start">
        <section className="bg-white rounded-[24px] border border-line/70 shadow-card animate-rise">
          <label htmlFor="concern-q" className="sr-only">Your question</label>
          <textarea id="concern-q" rows={5} value={query} onChange={(e) => setQuery(e.target.value)} autoFocus
            onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) submit(); }}
            placeholder="For example: I've had headaches every morning this week. Is this connected to anything in my history?"
            className="block w-full resize-none bg-transparent px-6 pt-6 pb-2 text-[19px] leading-[1.5] text-ink outline-none placeholder:text-[#a1a1a6]" />

          <div className="px-6">
            <button type="button" onClick={() => setShowDetails((v) => !v)} aria-expanded={showDetails}
              className="inline-flex h-8 items-center gap-1.5 rounded-full px-3 -ml-3 text-[14px] font-medium text-accent hover:bg-accent-soft transition-colors cursor-pointer">
              <ChevronDown className={cx('w-4 h-4 transition-transform duration-300', showDetails && 'rotate-180')} />
              {showDetails ? 'Hide details' : 'Add symptoms, timing and severity'}
              {!showDetails && detailCount > 0 && <span className="ml-0.5 text-muted font-normal">· {detailCount} added</span>}
            </button>
          </div>
          <div className={cx('grid transition-[grid-template-rows,opacity] duration-300 ease-[cubic-bezier(0.2,0.8,0.2,1)]',
            showDetails ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0')}>
            <div className="overflow-hidden">
              <div className="px-6 pt-4 pb-2 grid sm:grid-cols-2 gap-4">
                <Field label="Current symptoms"><Input value={symptoms} onChange={(e) => setSymptoms(e.target.value)} placeholder="headache, nausea (comma separated)" /></Field>
                <Field label="When did it start?"><Input type="date" value={onset} onChange={(e) => setOnset(e.target.value)} /></Field>
                <Field label="How long has it lasted?"><Input value={duration} onChange={(e) => setDuration(e.target.value)} placeholder="3 days" /></Field>
                <Field label="Severity">
                  <Select value={severity} onChange={(e) => setSeverity(e.target.value)}>
                    <option value="">Not specified</option><option>mild</option><option>moderate</option><option>severe</option>
                  </Select>
                </Field>
                <Field label="Temperature (°C), if measured"><Input inputMode="decimal" value={temp} onChange={(e) => setTemp(e.target.value)} placeholder="37.8" /></Field>
                <Field label="Anything else?"><Input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Optional" /></Field>
              </div>
            </div>
          </div>

          <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-line-soft px-6 py-4">
            <MicButton onText={(t) => setQuery((q) => (q.trim() ? `${q.trim()} ${t}` : t))} />
            <p className="hidden sm:block text-[13px] text-faint">Speak or type · Ctrl + Enter to send</p>
            <Button size="lg" onClick={submit} disabled={!query.trim()} className="ml-auto">
              Ask MedResolve <Send className="w-4 h-4" />
            </Button>
          </div>
        </section>

        <div className="space-y-6 animate-rise [animation-delay:80ms]">
          <Card title="Try asking" flush>
            <ul className="px-3 pt-1">
              {EXAMPLES.map((e) => (
                <li key={e}>
                  <button onClick={() => setQuery(e)}
                    className="group w-full flex items-start gap-3 rounded-[14px] px-3 py-3 text-left text-[14px] leading-snug text-ink-2 hover:bg-panel hover:text-ink transition-colors cursor-pointer">
                    <span className="flex-1">{e}</span>
                    <ArrowUpRight className="w-4 h-4 mt-0.5 shrink-0 text-ghost transition-all duration-200 group-hover:text-accent group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
                  </button>
                </li>
              ))}
            </ul>
          </Card>
          <div className="flex gap-3 rounded-[18px] bg-danger-tint border border-danger-line/60 px-4 py-3.5">
            <OctagonAlert className="w-[18px] h-[18px] mt-0.5 shrink-0 text-danger" />
            <p className="text-[14px] leading-snug text-ink-2">
              <span className="font-semibold text-ink">Chest pain, trouble breathing, signs of stroke or thoughts of self-harm?</span>{' '}
              Call your local emergency number now. Don't wait for an online answer.
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
