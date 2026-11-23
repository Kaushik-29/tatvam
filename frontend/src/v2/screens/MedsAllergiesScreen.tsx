import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';
import { QuickAdd, RecordTable } from '../components';
import type { RecordItem } from '../types';
import { Card, ErrorNote, PageHeader, Spinner } from '../ui';

const SECTIONS = [
  { leaf: 'medication_history/current_medications', title: 'Current medications', add: true },
  { leaf: 'allergy_history', title: 'Allergies & intolerances', add: true },
  { leaf: 'medication_history/medication_changes', title: 'Medication changes (derived from prescriptions)', add: false },
  { leaf: 'medication_history/previous_medications', title: 'Previous medications', add: true },
];

export function MedsAllergiesScreen({ readOnly }: { readOnly: boolean }) {
  const [data, setData] = useState<Record<string, RecordItem[]> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const out: Record<string, RecordItem[]> = {};
      for (const s of SECTIONS) out[s.leaf] = await api.records({ leaf: s.leaf, limit: 300 });
      setData(out);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const del = async (r: RecordItem) => { await api.deleteRecord(r.record_id); load(); };
  const confirm = async (r: RecordItem) => { await api.patchRecord(r.record_id, { verification_status: 'confirmed' }); load(); };

  return (
    <>
      <PageHeader title="Medications & allergies"
        description="Current medications and allergies are always included as safety context when you ask a question, even if they were not retrieved as relevant." />
      <ErrorNote error={error} />
      {!data ? <Spinner label="Loading…" /> : (
        <div className="space-y-6">
          {SECTIONS.map((s) => (
            <Card key={s.leaf} title={s.title} subtitle={`${data[s.leaf].length} record(s)`}>
              {!readOnly && s.add && (
                <div className="mb-3"><QuickAdd leaves={[s.leaf]} placeholder={s.leaf === 'allergy_history' ? 'e.g. Penicillin' : 'e.g. lisinopril 10 mg'}
                  onAdded={() => load()} /></div>
              )}
              <div className="max-h-80 overflow-y-auto">
                <RecordTable records={data[s.leaf]} onDelete={readOnly ? undefined : del} onConfirm={readOnly ? undefined : confirm}
                  emptyText={s.leaf === 'allergy_history' ? 'No allergies recorded. (No record is not the same as no allergy.)' : 'None recorded.'} />
              </div>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
