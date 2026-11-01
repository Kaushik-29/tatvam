import { useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { api } from './api';
import type { RecordItem } from './types';
import { Button, ErrorNote, Field, Input, Pill, Select, fmtDate } from './ui';

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
    <div className="space-y-2">
      <div className="grid grid-cols-2 md:grid-cols-6 gap-2 items-end">
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
        <Button onClick={add} disabled={!display.trim()}><Plus className="w-3.5 h-3.5" /> Add</Button>
      </div>
      <ErrorNote error={error} />
    </div>
  );
}

export function RecordTable({ records, onDelete, onConfirm, emptyText, compact }: {
  records: RecordItem[]; onDelete?: (r: RecordItem) => void; onConfirm?: (r: RecordItem) => void; emptyText?: string; compact?: boolean;
}) {
  if (!records.length) return <p className="text-[12px] text-[#8A99AB] py-2">{emptyText ?? 'Nothing recorded.'}</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[12px]">
        <thead>
          <tr className="text-left text-[10px] uppercase tracking-wide text-[#8A99AB] border-b border-[#DFE7F1]">
            <th className="py-1.5 pr-3 font-medium">Item</th>
            <th className="py-1.5 pr-3 font-medium">Date</th>
            {!compact && <th className="py-1.5 pr-3 font-medium">Value / status</th>}
            <th className="py-1.5 pr-3 font-medium">Source</th>
            {(onDelete || onConfirm) && <th className="py-1.5" />}
          </tr>
        </thead>
        <tbody>
          {records.map((r) => (
            <tr key={r.record_id} className="border-b border-[#EEF2F7] align-top">
              <td className="py-1.5 pr-3 text-[#172B4D]">{r.concept_display}</td>
              <td className="py-1.5 pr-3 tabular-nums text-[#61738A] whitespace-nowrap">
                {fmtDate(r.effective_start)}{r.effective_end ? ` → ${fmtDate(r.effective_end)}` : ''}
              </td>
              {!compact && (
                <td className="py-1.5 pr-3 tabular-nums text-[#61738A]">
                  {r.value_num !== null ? `${r.value_num} ${r.unit ?? '(no unit)'}` : r.value_text ?? ''} {r.clinical_status && <span className="text-[#8A99AB]">· {r.clinical_status}</span>}
                </td>
              )}
              <td className="py-1.5 pr-3"><Pill value={r.verification_status} /> <span className="text-[10px] text-[#8A99AB]">{r.source_system.replace(/_/g, ' ')}</span></td>
              {(onDelete || onConfirm) && (
                <td className="py-1.5 text-right whitespace-nowrap">
                  {onConfirm && r.verification_status === 'unconfirmed' && (
                    <button onClick={() => onConfirm(r)} className="text-[11px] text-[#26845A] hover:underline mr-2">Confirm</button>
                  )}
                  {onDelete && r.source_system !== 'synthea_fhir_r4' && r.source_system !== 'derived' && (
                    <button onClick={() => onDelete(r)} className="text-[#8A99AB] hover:text-[#C23E4A]" aria-label={`Delete ${r.concept_display}`}>
                      <Trash2 className="w-3.5 h-3.5" />
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
