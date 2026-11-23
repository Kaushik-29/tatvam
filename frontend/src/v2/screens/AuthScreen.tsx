import { useEffect, useState } from 'react';
import { ArrowRight, Fingerprint, Plus, ShieldCheck, Siren } from 'lucide-react';
import { api, setToken } from '../api';
import type { DemoPatient } from '../types';
import { Button, ErrorNote, Field, Input, Select, Spinner, cx } from '../ui';

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

  const brand = (
    <div className="flex items-center gap-2.5">
      <span className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-accent text-white shadow-[0_1px_2px_rgba(10,102,228,0.35)]">
        <Plus className="w-5 h-5" strokeWidth={3} />
      </span>
      <span className="font-display text-[19px] font-semibold tracking-[-0.015em]">MedResolve</span>
    </div>
  );

  return (
    <div className="flex-1 min-h-screen lg:grid lg:grid-cols-[1.05fr_1fr]">
      {/* Story panel */}
      <aside className="relative hidden lg:flex flex-col justify-between overflow-hidden p-14 bg-[linear-gradient(165deg,#fbfcff_0%,#eef4fe_52%,#e1ecfd_100%)]">
        {brand}
        <div className="max-w-[460px] animate-rise">
          <p className="mb-4 text-[14px] font-semibold text-accent">Your history, in context</p>
          <h1 className="font-display text-[46px] font-semibold leading-[1.06] tracking-[-0.03em] text-ink">
            Answers that know<br />where you've been.
          </h1>
          <p className="mt-5 text-[17px] leading-relaxed text-ink-2">
            MedResolve reads a new health question alongside your own record: earlier conditions, medications, allergies,
            symptoms and lab results. It shows exactly which records and references it used.
          </p>
          <ul className="mt-10 grid gap-4 text-[15px] text-ink-2">
            {([
              [Fingerprint, 'Your history stays in your own structured record.'],
              [ShieldCheck, 'Every statement about you must cite a record, or it is withheld.'],
              [Siren, 'Emergency warning signs are checked before anything else.'],
            ] as const).map(([Icon, text]) => (
              <li key={text} className="flex items-center gap-3.5">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white/85 text-accent shadow-[0_1px_2px_rgba(0,0,0,0.05)]">
                  <Icon className="w-[18px] h-[18px]" />
                </span>
                {text}
              </li>
            ))}
          </ul>
        </div>
        <p className="max-w-[460px] text-[13px] leading-relaxed text-muted">
          Academic research prototype. It does not diagnose, prescribe or replace a clinician, and it has not been clinically validated.
        </p>
        <div className="pointer-events-none absolute -right-32 -top-32 h-[420px] w-[420px] rounded-full bg-white/60 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-40 -left-24 h-[360px] w-[360px] rounded-full bg-[#d7e6fd]/60 blur-3xl" />
      </aside>

      {/* Forms */}
      <main className="flex min-h-screen items-center justify-center px-5 py-12 sm:px-10">
        <div className="w-full max-w-[420px] animate-rise">
          <div className="mb-10 lg:hidden">{brand}</div>
          <h2 className="font-display text-[32px] font-semibold tracking-[-0.025em] leading-tight">
            {mode === 'login' ? 'Welcome back' : 'Create your account'}
          </h2>
          <p className="mt-2 text-[16px] text-muted">
            {mode === 'login' ? 'Sign in to continue with your health record.' : 'Set up a private record in under a minute.'}
          </p>

          <div role="tablist" aria-label="Sign in or create account" className="mt-8 grid grid-cols-2 rounded-full bg-[#e9e9ee] p-1 text-[14px] font-medium">
            {(['login', 'register'] as const).map((m) => (
              <button key={m} type="button" role="tab" aria-selected={mode === m} onClick={() => { setMode(m); setError(null); }}
                className={cx('h-9 rounded-full transition-all duration-200 cursor-pointer', mode === m ? 'bg-white text-ink shadow-sm' : 'text-muted hover:text-ink')}>
                {m === 'login' ? 'Sign in' : 'Create account'}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="mt-6 grid gap-4">
            {mode === 'register' && (
              <div className="grid grid-cols-2 gap-3 animate-fade">
                <Field label="First name"><Input required autoComplete="given-name" value={form.given_name} onChange={set('given_name')} /></Field>
                <Field label="Last name"><Input autoComplete="family-name" value={form.family_name} onChange={set('family_name')} /></Field>
                <Field label="Date of birth"><Input type="date" value={form.birth_date} onChange={set('birth_date')} /></Field>
                <Field label="Sex">
                  <Select value={form.gender} onChange={set('gender')}>
                    <option value="">Prefer not to say</option><option value="female">Female</option><option value="male">Male</option><option value="other">Other</option>
                  </Select>
                </Field>
              </div>
            )}
            <Field label="Email"><Input type="email" autoComplete="email" required value={form.email} onChange={set('email')} placeholder="you@example.com" /></Field>
            <Field label="Password" hint={mode === 'register' ? 'At least 8 characters.' : undefined}>
              <Input type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} minLength={8} required value={form.password} onChange={set('password')} />
            </Field>
            <ErrorNote error={error} />
            <Button type="submit" size="lg" disabled={busy} className="w-full mt-1">
              {busy ? <Spinner /> : <>{mode === 'login' ? 'Sign in' : 'Create account'} <ArrowRight className="w-[18px] h-[18px]" /></>}
            </Button>
          </form>

          <div className="mt-10 rounded-[20px] bg-white border border-line/70 shadow-card p-5">
            <p className="text-[15px] font-semibold">Explore with a synthetic patient</p>
            <p className="mt-1 text-[14px] text-muted leading-relaxed">Open a read-only Synthea patient with years of generated history. No real person's data.</p>
            {demo.length > 0 ? (
              <div className="mt-4 flex gap-2">
                <Select value={demoPid} onChange={(e) => setDemoPid(e.target.value)} aria-label="Synthetic patient" className="min-w-0">
                  {demo.map((d) => <option key={d.patient_id} value={d.patient_id}>{d.label} · {d.gender} · b. {d.birth_date}</option>)}
                </Select>
                <Button variant="secondary" disabled={busy} onClick={openDemo} className="h-11">Open</Button>
              </div>
            ) : <p className="mt-3 text-[13px] text-faint">No synthetic patients are loaded.</p>}
          </div>
        </div>
      </main>
    </div>
  );
}
