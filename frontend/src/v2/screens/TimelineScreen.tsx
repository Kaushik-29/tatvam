import { useEffect, useMemo, useState } from 'react';
import { api } from '../api';
import type { TimelineEvent } from '../types';
import { Card, Empty, ErrorNote, Field, Input, PageHeader, Pill, Spinner, cx } from '../ui';

const FILTERS: { label: string; leaves: string }[] = [
  { label: 'Everything', leaves: '' },
  { label: 'Diagnoses & conditions', leaves: 'medical_history/diagnoses,medical_history/conditions' },
  { label: 'Medication changes', leaves: 'medication_history/medication_changes' },
  { label: 'Symptoms', leaves: 'clinical_encounters/previous_symptoms,clinical_encounters/complaints' },
  { label: 'Visits', leaves: 'clinical_encounters/consultations' },
  { label: 'Labs', leaves: 'laboratory_observations/laboratory_results' },
  { label: 'Procedures', leaves: 'medical_history/procedures' },
];

const DOT: Record<string, string> = {
  'medical_history/diagnoses': 'bg-danger', 'medical_history/conditions': 'bg-warn',
  'medication_history/medication_changes': 'bg-accent', 'clinical_encounters/previous_symptoms': 'bg-accent',
  'clinical_encounters/consultations': 'bg-faint', 'laboratory_observations/laboratory_results': 'bg-success-ink',
};

export function TimelineScreen() {
  const [filter, setFilter] = useState(0);
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [events, setEvents] = useState<TimelineEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setEvents(null);
    api.timeline({ leaves: FILTERS[filter].leaves || undefined, start: start || undefined, end: end || undefined })
      .then(setEvents).catch((e) => setError(e.message));
  }, [filter, start, end]);

  const byYear = useMemo(() => {
    const m = new Map<string, TimelineEvent[]>();
    (events ?? []).forEach((e) => { const y = e.date.slice(0, 4); m.set(y, [...(m.get(y) ?? []), e]); });
    return [...m.entries()];
  }, [events]);

  return (
    <>
      <PageHeader title="Medical history & timeline" description="Chronological view of your longitudinal record. Lab results are grouped per day; routine vitals are omitted here." />
      <ErrorNote error={error} />
      <Card>
        <div className="flex flex-wrap gap-2 items-end mb-4">
          <div className="flex flex-wrap gap-1">
            {FILTERS.map((f, i) => (
              <button key={f.label} onClick={() => setFilter(i)}
                className={cx('h-8 px-3.5 text-[13px] rounded-full border transition-all duration-200 cursor-pointer', i === filter ? 'border-transparent bg-ink text-white font-medium shadow-sm' : 'border-line text-ink-2 hover:bg-panel hover:border-[#d2d2d7]')}>
                {f.label}
              </button>
            ))}
          </div>
          <div className="flex gap-2 ml-auto">
            <Field label="From"><Input type="date" value={start} onChange={(e) => setStart(e.target.value)} /></Field>
            <Field label="To"><Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} /></Field>
          </div>
        </div>
        {!events ? <Spinner label="Loading timeline…" /> : events.length === 0 ? (
          <Empty title="No events in this view">Add history in Medications & allergies or Onboarding, or upload documents.</Empty>
        ) : (
          <div className="space-y-5">
            {byYear.map(([year, evs]) => (
              <div key={year}>
                <p className="font-display text-[20px] font-semibold tracking-[-0.01em] text-ink tabular-nums sticky top-14 z-10 bg-white/90 backdrop-blur py-2">{year} <span className="text-[14px] text-faint font-normal tracking-normal">· {evs.length} events</span></p>
                <ol className="mt-1 border-l border-line ml-1.5">
                  {evs.map((e, i) => (
                    <li key={`${e.record_ids[0]}-${i}`} className="relative pl-4 py-1.5">
                      <span className={cx('absolute -left-[4.5px] top-3 w-2 h-2 rounded-full', DOT[e.leaf_path] ?? 'bg-accent-line')} />
                      <div className="flex flex-wrap items-baseline gap-x-2">
                        <span className="text-[13px] tabular-nums text-muted w-[78px]">{e.date}</span>
                        <span className="text-[14px] text-ink">{e.title}</span>
                        {e.status && <span className="text-[12px] text-faint">{e.status}</span>}
                        {e.verification_status !== 'confirmed' && <Pill value={e.verification_status} />}
                      </div>
                      <p className="text-[13px] text-faint ml-[86px] truncate">{e.text}</p>
                    </li>
                  ))}
                </ol>
              </div>
            ))}
          </div>
        )}
      </Card>
    </>
  );
}
