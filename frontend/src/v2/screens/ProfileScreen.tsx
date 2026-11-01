import { useEffect, useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { api } from '../api';
import { RecordTable } from '../components';
import type { PatientProfile, RecordItem, TocNode } from '../types';
import { Button, Card, ErrorNote, Field, Input, PageHeader, Select, Spinner, fmtDate } from '../ui';

function age(birth: string | null) {
  if (!birth) return null;
  const b = new Date(birth);
  const n = new Date();
  return n.getFullYear() - b.getFullYear() - (n < new Date(n.getFullYear(), b.getMonth(), b.getDate()) ? 1 : 0);
}

function TocTree({ nodes, onOpen, depth = 0 }: { nodes: TocNode[]; onOpen: (n: TocNode) => void; depth?: number }) {
  const [open, setOpen] = useState<Record<string, boolean>>({});
  return (
    <ul className={depth ? 'ml-4 border-l border-[#EEF2F7] pl-2' : ''}>
      {nodes.map((n) => {
        const hasKids = n.children.length > 0;
        const isOpen = open[n.path] ?? depth === 0;
        return (
          <li key={n.path} className="py-0.5">
            <div className="flex items-center gap-1.5 text-[12px]">
              {hasKids ? (
                <button onClick={() => setOpen({ ...open, [n.path]: !isOpen })} className="text-[#8A99AB]" aria-label={isOpen ? 'Collapse' : 'Expand'}>
                  {isOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                </button>
              ) : <span className="w-3.5" />}
              <button onClick={() => onOpen(n)} className="text-left hover:text-[#3675CA] disabled:text-[#8A99AB]" disabled={!n.count}>
                <span className="tabular-nums text-[#8A99AB] mr-1.5">{n.number}</span>
                <span className={depth ? 'text-[#172B4D]' : 'font-medium text-[#172B4D]'}>{n.title}</span>
              </button>
              <span className="text-[10px] text-[#8A99AB] tabular-nums">{n.count ? `${n.count}${n.date_range ? ` · ${n.date_range}` : ''}` : 'empty'}</span>
            </div>
            {hasKids && isOpen && <TocTree nodes={n.children.slice(0, 40)} onOpen={onOpen} depth={depth + 1} />}
            {hasKids && isOpen && n.children.length > 40 && <p className="ml-8 text-[10px] text-[#8A99AB]">+ {n.children.length - 40} more entries</p>}
          </li>
        );
      })}
    </ul>
  );
}

export function ProfileScreen({ profile, readOnly, onSaved }: { profile: PatientProfile; readOnly: boolean; onSaved: () => void }) {
  const [toc, setToc] = useState<TocNode[] | null>(null);
  const [sel, setSel] = useState<TocNode | null>(null);
  const [rows, setRows] = useState<RecordItem[]>([]);
  const [edit, setEdit] = useState(false);
  const [form, setForm] = useState({ given_name: profile.given_name ?? '', family_name: profile.family_name ?? '', birth_date: profile.birth_date ?? '', gender: profile.gender ?? '', city: profile.city ?? '' });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { api.toc().then(setToc).catch((e) => setError(e.message)); }, []);

  const open = async (n: TocNode) => {
    setSel(n);
    const isGroup = n.path.split('/').length >= 3 || (n.path.startsWith('allergy_history/') && n.path.split('/').length === 2);
    setRows(await api.records(isGroup ? { group: n.path, limit: 100 } : { leaf: n.path, limit: 100 }));
  };

  const save = async () => {
    try {
      await api.updateProfile(form);
      setEdit(false);
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <>
      <PageHeader title="Medical profile" description="Your longitudinal record, organised as the hierarchy MedResolve's structure-aware retriever (STAIR-Clinical) navigates." />
      <ErrorNote error={error} />
      <div className="grid lg:grid-cols-[320px_1fr] gap-4">
        <Card title="Personal details" actions={!readOnly && !edit ? <Button variant="ghost" onClick={() => setEdit(true)}>Edit</Button> : undefined}>
          {edit ? (
            <div className="space-y-2">
              <Field label="First name"><Input value={form.given_name} onChange={(e) => setForm({ ...form, given_name: e.target.value })} /></Field>
              <Field label="Last name"><Input value={form.family_name} onChange={(e) => setForm({ ...form, family_name: e.target.value })} /></Field>
              <Field label="Date of birth"><Input type="date" value={form.birth_date} onChange={(e) => setForm({ ...form, birth_date: e.target.value })} /></Field>
              <Field label="Sex"><Select value={form.gender} onChange={(e) => setForm({ ...form, gender: e.target.value })}>
                <option value="">Prefer not to say</option><option value="female">Female</option><option value="male">Male</option><option value="other">Other</option></Select></Field>
              <Field label="City"><Input value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} /></Field>
              <div className="flex gap-2"><Button onClick={save}>Save</Button><Button variant="secondary" onClick={() => setEdit(false)}>Cancel</Button></div>
            </div>
          ) : (
            <dl className="grid grid-cols-[110px_1fr] gap-y-1.5 text-[12px]">
              <dt className="text-[#61738A]">Name</dt><dd>{[profile.given_name, profile.family_name].filter(Boolean).join(' ') || '—'}</dd>
              <dt className="text-[#61738A]">Born</dt><dd className="tabular-nums">{fmtDate(profile.birth_date)}{age(profile.birth_date) !== null && ` (${age(profile.birth_date)} y)`}</dd>
              <dt className="text-[#61738A]">Sex</dt><dd>{profile.gender || '—'}</dd>
              <dt className="text-[#61738A]">Location</dt><dd>{[profile.city, profile.state].filter(Boolean).join(', ') || '—'}</dd>
              <dt className="text-[#61738A]">Records</dt><dd className="tabular-nums">{profile.record_count.toLocaleString()}</dd>
              <dt className="text-[#61738A]">Source</dt><dd>{profile.is_synthetic ? 'Synthea synthetic (FHIR R4)' : 'Registered user'}</dd>
            </dl>
          )}
        </Card>
        <Card title="Record hierarchy" subtitle="Branches → sections → your concept groups. Select an entry to see its records.">
          {!toc ? <Spinner label="Loading hierarchy…" /> : (
            <div className="grid xl:grid-cols-2 gap-4">
              <div className="max-h-[560px] overflow-y-auto pr-2"><TocTree nodes={toc} onOpen={open} /></div>
              <div className="min-w-0">
                {sel ? (
                  <>
                    <p className="text-[12px] font-medium mb-1"><span className="tabular-nums text-[#8A99AB] mr-1">{sel.number}</span>{sel.title}</p>
                    <p className="text-[10px] text-[#8A99AB] mb-2 font-mono break-all">{sel.path}</p>
                    <RecordTable records={rows} compact={false} />
                  </>
                ) : <p className="text-[12px] text-[#8A99AB]">Select a section on the left.</p>}
              </div>
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
