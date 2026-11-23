import { useEffect, useState } from 'react';
import { Download } from 'lucide-react';
import { api } from '../api';
import type { PatientProfile, SystemStatus } from '../types';
import { Button, Card, ErrorNote, PageHeader, Pill, Spinner } from '../ui';

export function SettingsScreen({ profile, isDemo, onLoggedOut }: { profile: PatientProfile; isDemo: boolean; onLoggedOut: () => void }) {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [audit, setAudit] = useState<{ event: string; actor: string; detail: string; at: string }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    api.systemStatus().then(setStatus).catch(() => setStatus(null));
    api.audit().then(setAudit).catch(() => setAudit([]));
  }, []);

  const exportData = async () => {
    const data = await api.exportData();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `medresolve-export-${profile.patient_id}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const clearHistory = async () => {
    if (!window.confirm('Delete all saved consultations? This cannot be undone.')) return;
    const r = await api.deleteConsultations();
    setMsg(`Deleted ${r.deleted} consultation(s).`);
  };

  const deleteAccount = async () => {
    if (!window.confirm('Permanently delete your account, medical records, documents and consultations? This cannot be undone.')) return;
    try {
      await api.deleteAccount();
      onLoggedOut();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const adapter = status?.stair.adapter as Record<string, unknown> | null | undefined;
  return (
    <>
      <PageHeader title="Settings & data management" />
      <div className="grid lg:grid-cols-2 gap-6">
        <Card title="Your data">
          <div className="space-y-3 text-[14px]">
            <p className="text-muted">Your records are stored in MedResolve's local database and are only accessible with your sign-in. The local language model runs on this machine; no records are sent to external AI services.</p>
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" onClick={exportData}><Download className="w-3.5 h-3.5" /> Export all my data (JSON)</Button>
              <Button variant="secondary" onClick={clearHistory}>Delete consultation history</Button>
              {!isDemo && <Button variant="danger" onClick={deleteAccount}>Delete account and all data</Button>}
            </div>
            {isDemo && <p className="text-[13px] text-faint">Synthetic demo patients are read-only and cannot be deleted from the app.</p>}
            <ErrorNote error={error} />
            {msg && <p className="text-[14px] text-success-ink">{msg}</p>}
          </div>
        </Card>
        <Card title="System status">
          {!status ? <Spinner /> : (
            <dl className="grid grid-cols-[140px_1fr] gap-y-1.5 text-[14px]">
              <dt className="text-muted">Local LLM</dt><dd>{status.llm.model} <Pill value={status.llm.available ? 'CONFIRMED' : 'UNSUPPORTED'} label={status.llm.available ? 'available' : 'unavailable (template fallback)'} /></dd>
              <dt className="text-muted">Embeddings</dt><dd>{status.embedding_model}</dd>
              <dt className="text-muted">STAIR selector</dt>
              <dd>{adapter ? `${String(adapter.base_model)} LoRA · ${String(adapter.training_status)}` : `structural (no trained adapter loaded) · configured: ${status.stair.configured_backend}`}</dd>
              <dt className="text-muted">MIMIC-IV</dt><dd className="text-muted">{String(status.datasets.mimic_iv)}</dd>
              <dt className="text-muted">Notice</dt><dd className="text-warn">{status.disclaimer}</dd>
            </dl>
          )}
        </Card>
        <Card title="Recent account activity" className="lg:col-span-2">
          {audit.length === 0 ? <p className="text-[14px] text-faint">No activity recorded.</p> : (
            <ul className="text-[13px] divide-y divide-line-soft max-h-64 overflow-y-auto">
              {audit.map((a, i) => <li key={i} className="py-1 flex gap-3"><span className="tabular-nums text-faint w-40">{a.at.replace('T', ' ').slice(0, 19)}</span><span className="text-ink w-48">{a.event}</span><span className="text-faint truncate">{a.detail}</span></li>)}
            </ul>
          )}
        </Card>
      </div>
    </>
  );
}
