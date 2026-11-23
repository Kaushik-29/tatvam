import { useEffect, useState } from 'react';
import { Check } from 'lucide-react';
import { api } from '../api';
import { QuickAdd, RecordTable } from '../components';
import type { PatientProfile, RecordItem } from '../types';
import { Button, Card, Field, Input, PageHeader, Select, cx } from '../ui';

const STEPS = [
  { key: 'profile', title: 'About you' },
  { key: 'history', title: 'Conditions & diagnoses', leaves: ['medical_history/diagnoses', 'medical_history/conditions', 'medical_history/procedures'], placeholder: 'e.g. Type 2 diabetes' },
  { key: 'meds', title: 'Medications', leaves: ['medication_history/current_medications', 'medication_history/previous_medications'], placeholder: 'e.g. metformin 500 mg' },
  { key: 'allergies', title: 'Allergies', leaves: ['allergy_history'], placeholder: 'e.g. Penicillin — hives' },
  { key: 'symptoms', title: 'Previous symptoms', leaves: ['clinical_encounters/previous_symptoms'], placeholder: 'e.g. Dizziness' },
  { key: 'docs', title: 'Old records' },
] as const;

export function OnboardingScreen({ profile, onDone }: { profile: PatientProfile; onDone: () => void }) {
  const [step, setStep] = useState(0);
  const [records, setRecords] = useState<RecordItem[]>([]);
  const [p, setP] = useState({ given_name: profile.given_name ?? '', family_name: profile.family_name ?? '', birth_date: profile.birth_date ?? '', gender: profile.gender ?? '', city: profile.city ?? '' });

  useEffect(() => { api.records({ limit: 500 }).then(setRecords).catch(() => undefined); }, []);
  const s = STEPS[step];

  const next = async () => {
    if (s.key === 'profile') await api.updateProfile(p);
    if (step === STEPS.length - 1) {
      await api.updateProfile({ onboarding_complete: true });
      onDone();
      return;
    }
    setStep(step + 1);
  };

  const remove = async (r: RecordItem) => {
    await api.deleteRecord(r.record_id);
    setRecords((rs) => rs.filter((x) => x.record_id !== r.record_id));
  };

  return (
    <>
      <PageHeader title="Set up your health record"
        description="Add what you know. Everything you enter is stored as patient-reported and you can change it later. If your profile is empty, MedResolve will not invent history — it will ask." />
      <div className="mb-3 h-1 rounded-full bg-line/70 overflow-hidden" aria-hidden>
        <div className="h-full rounded-full bg-accent transition-[width] duration-500 ease-out" style={{ width: `${((step + 1) / STEPS.length) * 100}%` }} />
      </div>
      <ol className="flex flex-wrap gap-1.5 mb-6" aria-label="Onboarding steps">
        {STEPS.map((st, i) => (
          <li key={st.key}>
            <button onClick={() => setStep(i)} aria-current={i === step ? 'step' : undefined}
              className={cx('inline-flex items-center gap-2 h-9 pl-1.5 pr-3.5 rounded-full text-[14px] transition-all duration-200 cursor-pointer',
                i === step ? 'bg-white text-ink font-medium shadow-[0_1px_2px_rgba(0,0,0,0.06),0_0_0_1px_rgba(0,0,0,0.04)]' : 'text-muted hover:text-ink hover:bg-black/[0.04]')}>
              <span className={cx('flex h-6 w-6 items-center justify-center rounded-full text-[12px] font-semibold tabular-nums transition-colors',
                i === step ? 'bg-accent text-white' : i < step ? 'bg-success-soft text-success-ink' : 'bg-line/70 text-muted')}>
                {i < step ? <Check className="w-3.5 h-3.5" strokeWidth={3} /> : i + 1}
              </span>
              {st.title}
            </button>
          </li>
        ))}
      </ol>
      <Card title={s.title}>
        {s.key === 'profile' && (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            <Field label="First name"><Input value={p.given_name} onChange={(e) => setP({ ...p, given_name: e.target.value })} /></Field>
            <Field label="Last name"><Input value={p.family_name} onChange={(e) => setP({ ...p, family_name: e.target.value })} /></Field>
            <Field label="Date of birth"><Input type="date" value={p.birth_date} onChange={(e) => setP({ ...p, birth_date: e.target.value })} /></Field>
            <Field label="Sex">
              <Select value={p.gender} onChange={(e) => setP({ ...p, gender: e.target.value })}>
                <option value="">Prefer not to say</option><option value="female">Female</option><option value="male">Male</option><option value="other">Other</option>
              </Select>
            </Field>
            <Field label="City"><Input value={p.city} onChange={(e) => setP({ ...p, city: e.target.value })} /></Field>
          </div>
        )}
        {'leaves' in s && (
          <div className="space-y-6">
            {/* key: remount per step so the record type never carries over (e.g. an allergy saved as a medication) */}
            <QuickAdd key={s.key} leaves={[...s.leaves]} placeholder={s.placeholder} onAdded={(r) => setRecords((rs) => [r, ...rs])} />
            <RecordTable records={records.filter((r) => (s.leaves as readonly string[]).includes(r.leaf_path))} onDelete={remove}
              emptyText="Nothing added yet — that's fine if none apply." />
          </div>
        )}
        {s.key === 'docs' && (
          <p className="text-[14px] text-muted">
            You can upload old prescriptions, lab reports and discharge summaries from <strong>Upload documents</strong> at any time.
            Extracted values are kept as <em>unconfirmed</em> until you review them.
          </p>
        )}
        <div className="flex justify-between mt-8 pt-5 border-t border-line-soft">
          <Button variant="secondary" disabled={step === 0} onClick={() => setStep(step - 1)}>Back</Button>
          <Button onClick={next}>{step === STEPS.length - 1 ? 'Finish setup' : 'Continue'}</Button>
        </div>
      </Card>
    </>
  );
}
