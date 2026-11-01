import { useEffect, useState } from 'react';
import { api, setToken } from '../api';
import type { DemoPatient } from '../types';
import { Button, ErrorNote, Field, Input, Select, cx } from '../ui';

export function AuthScreen({ onAuthed }: { onAuthed: (isDemo: boolean) => void }) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [form, setForm] = useState({ email: '', password: '', given_name: '', family_name: '', birth_date: '', gender: '' });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [demo, setDemo] = useState<DemoPatient[]>([]);
  const [demoPid, setDemoPid] = useState('');

  useEffect(() => {
    api.demoPatients().then((d) => { setDemo(d); if (d[0]) setDemoPid(d[0].patient_id); }).catch(() => setDemo([]));
  }, []);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const r = mode === 'login'
        ? await api.login(form.email, form.password)
        : await api.register({ ...form, birth_date: form.birth_date || undefined, gender: form.gender || undefined, family_name: form.family_name || undefined });
      setToken(r.access_token);
      onAuthed(false);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const openDemo = async () => {
    setBusy(true);
    try {
      const r = await api.demoLogin(demoPid);
      setToken(r.access_token);
      onAuthed(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex-1 flex items-center justify-center p-4">
      <div className="w-full max-w-4xl grid md:grid-cols-[1.1fr_1fr] gap-6 items-start">
        <div className="pt-2">
          <h1 className="text-[22px] font-semibold text-[#172B4D] leading-tight">MedResolve</h1>
          <p className="text-[13px] text-[#61738A] mt-2 max-w-md">
            A research prototype that answers new health questions in the context of <strong className="text-[#172B4D]">your own medical history</strong> —
            previous conditions, medications, allergies, symptoms and lab results — and shows exactly which records and references it used.
          </p>
          <ul className="mt-4 space-y-2 text-[12px] text-[#61738A]">
            <li>• Your history stays in a structured record and is never mixed with anyone else's.</li>
            <li>• Every statement about you must cite a record, or it is withheld.</li>
            <li>• Emergency warning signs are checked before anything else.</li>
          </ul>
          <p className="mt-6 text-[11px] text-[#8A99AB] max-w-md border-l-2 border-[#DFE7F1] pl-3">
            Academic medical information assistant. It does not diagnose, prescribe or replace a clinician, and it has not been clinically validated.
          </p>
        </div>

        <div className="space-y-4">
          <form onSubmit={submit} className="bg-white border border-[#DFE7F1] rounded-lg p-5 space-y-3">
            <div className="flex gap-1 p-0.5 bg-[#F1F5FA] rounded-md" role="tablist">
              {(['login', 'register'] as const).map((m) => (
                <button key={m} type="button" role="tab" aria-selected={mode === m} onClick={() => setMode(m)}
                  className={cx('flex-1 py-1.5 text-[12px] rounded', mode === m ? 'bg-white text-[#172B4D] font-medium shadow-sm' : 'text-[#61738A]')}>
                  {m === 'login' ? 'Sign in' : 'Create account'}
                </button>
              ))}
            </div>
            {mode === 'register' && (
              <div className="grid grid-cols-2 gap-3">
                <Field label="First name"><Input required value={form.given_name} onChange={set('given_name')} /></Field>
                <Field label="Last name"><Input value={form.family_name} onChange={set('family_name')} /></Field>
                <Field label="Date of birth"><Input type="date" value={form.birth_date} onChange={set('birth_date')} /></Field>
                <Field label="Sex">
                  <Select value={form.gender} onChange={set('gender')}>
                    <option value="">Prefer not to say</option><option value="female">Female</option><option value="male">Male</option><option value="other">Other</option>
                  </Select>
                </Field>
              </div>
            )}
            <Field label="Email"><Input type="email" autoComplete="email" required value={form.email} onChange={set('email')} /></Field>
            <Field label="Password" hint={mode === 'register' ? 'At least 8 characters.' : undefined}>
              <Input type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} minLength={8} required value={form.password} onChange={set('password')} />
            </Field>
            <ErrorNote error={error} />
            <Button type="submit" disabled={busy} className="w-full">{mode === 'login' ? 'Sign in' : 'Create account'}</Button>
          </form>

          <div className="bg-[#FAF9F6] border border-[#DFE7F1] rounded-lg p-4 space-y-2">
            <p className="text-[12px] font-semibold text-[#172B4D]">Explore with a synthetic patient</p>
            <p className="text-[11px] text-[#61738A]">Open a read-only Synthea patient (test split) with years of generated history. No real person's data.</p>
            {demo.length > 0 ? (
              <div className="flex gap-2">
                <Select value={demoPid} onChange={(e) => setDemoPid(e.target.value)} aria-label="Synthetic patient">
                  {demo.map((d) => <option key={d.patient_id} value={d.patient_id}>{d.label} · {d.gender} · b. {d.birth_date}</option>)}
                </Select>
                <Button variant="secondary" disabled={busy} onClick={openDemo}>Open</Button>
              </div>
            ) : <p className="text-[11px] text-[#8A99AB]">No synthetic patients are loaded.</p>}
          </div>
        </div>
      </div>
    </div>
  );
}
