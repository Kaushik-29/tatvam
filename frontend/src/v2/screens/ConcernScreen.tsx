import { useState } from 'react';
import { Send } from 'lucide-react';
import type { ConsultInput, PatientProfile } from '../types';
import { Button, Card, Field, Input, PageHeader, Select, TextArea } from '../ui';

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

  return (
    <>
      <PageHeader title="New health concern"
        description={`Describe what is happening now. MedResolve will check for emergency warning signs first, then look through ${profile.record_count ? `your ${profile.record_count.toLocaleString()} records` : 'your (currently empty) record'} and general medical references.`} />
      <div className="grid lg:grid-cols-[1.4fr_1fr] gap-4">
        <Card title="Your question">
          <div className="space-y-3">
            <Field label="What would you like to know?">
              <TextArea rows={4} value={query} onChange={(e) => setQuery(e.target.value)} placeholder="e.g. I've had headaches every morning this week — is this connected to anything in my history?" />
            </Field>
            <div className="grid sm:grid-cols-2 gap-3">
              <Field label="Current symptoms (comma separated)"><Input value={symptoms} onChange={(e) => setSymptoms(e.target.value)} placeholder="headache, nausea" /></Field>
              <Field label="When did it start?"><Input type="date" value={onset} onChange={(e) => setOnset(e.target.value)} /></Field>
              <Field label="How long has it lasted?"><Input value={duration} onChange={(e) => setDuration(e.target.value)} placeholder="3 days" /></Field>
              <Field label="Severity">
                <Select value={severity} onChange={(e) => setSeverity(e.target.value)}>
                  <option value="">Not specified</option><option>mild</option><option>moderate</option><option>severe</option>
                </Select>
              </Field>
              <Field label="Temperature (°C), if measured"><Input inputMode="decimal" value={temp} onChange={(e) => setTemp(e.target.value)} /></Field>
            </div>
            <Field label="Anything else?"><TextArea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
            <div className="flex items-center justify-between gap-3">
              <p className="text-[11px] text-[#8A99AB]">If you have chest pain, trouble breathing, signs of stroke or thoughts of self-harm, call emergency services now.</p>
              <Button onClick={submit} disabled={!query.trim()}><Send className="w-3.5 h-3.5" /> Ask MedResolve</Button>
            </div>
          </div>
        </Card>
        <Card title="Example questions">
          <ul className="space-y-2">
            {EXAMPLES.map((e) => (
              <li key={e}><button onClick={() => setQuery(e)} className="text-left text-[12px] text-[#3675CA] hover:underline">{e}</button></li>
            ))}
          </ul>
        </Card>
      </div>
    </>
  );
}
