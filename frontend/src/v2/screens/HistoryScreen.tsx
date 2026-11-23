import { useEffect, useState } from 'react';
import { api } from '../api';
import type { Consultation, ConsultationSummary } from '../types';
import { Card, Empty, ErrorNote, PageHeader, Pill, Spinner } from '../ui';

const ACTION_PILL: Record<string, string> = { EXPLAIN: 'CONFIRMED', GENERAL_OPTIONS: 'INFO', ASK: 'INFO', ABSTAIN_AND_NAVIGATE: 'MEDIUM', EMERGENCY_OVERRIDE: 'HIGH' };

export function HistoryScreen({ onOpen }: { onOpen: (c: Consultation) => void }) {
  const [rows, setRows] = useState<ConsultationSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api.consultations().then(setRows).catch((e) => setError(e.message)); }, []);
  return (
    <>
      <PageHeader title="Previous consultations" description="Every question, the action taken, and the full evidence trail are kept so you can revisit them." />
      <ErrorNote error={error} />
      <Card>
        {!rows ? <Spinner /> : rows.length === 0 ? <Empty title="No consultations yet" /> : (
          <ul className="divide-y divide-line-soft">
            {rows.map((r) => (
              <li key={r.consultation_id}>
                <button className="w-full text-left py-2.5 hover:bg-panel px-1 rounded" onClick={async () => onOpen(await api.consultation(r.consultation_id))}>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[13px] tabular-nums text-faint">{new Date(r.created_at + 'Z').toLocaleString()}</span>
                    <Pill value={ACTION_PILL[r.action] ?? 'INFO'} label={r.action} />
                    {r.latency_s !== null && <span className="text-[12px] text-faint tabular-nums">{r.latency_s.toFixed(1)}s</span>}
                  </div>
                  <p className="text-[14px] text-ink mt-0.5">{r.query}</p>
                  <p className="text-[13px] text-muted truncate">{r.preview.replace(/[#*_]/g, '')}</p>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}
