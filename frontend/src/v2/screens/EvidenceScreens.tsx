import { useEffect, useMemo, useRef } from 'react';
import type { Consultation, EvidenceItem } from '../types';
import type { V2Screen } from '../PatientApp';
import { ActionBanner, Button, Card, Empty, PageHeader, Pill, cx, fmtDate } from '../ui';

const SECTION_NAME: Record<string, string> = {
  C: 'Relevant previous medical history', D: 'Medications', E: 'Allergies', F: 'Previous symptoms & encounters', G: 'Laboratory observations & vital signs',
};
const LEAF_SECTION = (leaf: string) =>
  leaf === 'allergy_history' ? 'E' : leaf.startsWith('medication') ? 'D' : leaf.startsWith('laboratory') || leaf.endsWith('diagnostic_reports') ? 'G'
    : leaf.startsWith('clinical_encounters') || leaf.endsWith('clinical_notes') || leaf.endsWith('discharge_summaries') ? 'F' : 'C';

function NoConsultation({ onNavigate }: { onNavigate: (s: V2Screen) => void }) {
  return (
    <Card><Empty title="No consultation selected">Ask a question first, or open one from <button className="text-[#3675CA] underline" onClick={() => onNavigate('history')}>previous consultations</button>.</Empty></Card>
  );
}

function useFocus(focus: string | null) {
  const ref = useRef<HTMLElement | null>(null);
  useEffect(() => { ref.current?.scrollIntoView({ block: 'center' }); }, [focus]);
  return ref;
}

export function ContextScreen({ consultation: c, focus, onNavigate }: { consultation: Consultation | null; focus: string | null; onNavigate: (s: V2Screen) => void }) {
  const ref = useFocus(focus);
  const grouped = useMemo(() => {
    const g: Record<string, EvidenceItem[]> = {};
    (c?.evidence ?? []).forEach((e) => { const k = LEAF_SECTION(e.leaf_path); (g[k] ??= []).push(e); });
    return g;
  }, [c]);
  if (!c) return <><PageHeader title="Retrieved patient context" /><NoConsultation onNavigate={onNavigate} /></>;
  const cited = new Set((c.verification?.claims ?? []).flatMap((x) => x.cited_evidence));
  const t = c.retrieval_trace;
  return (
    <>
      <PageHeader title="Retrieved patient context" description={`Question: “${c.query}”`} />
      <div className="grid lg:grid-cols-[1fr_320px] gap-4">
        <div className="space-y-4">
          {Object.keys(SECTION_NAME).filter((k) => grouped[k]).map((k) => (
            <Card key={k} title={SECTION_NAME[k]} subtitle={`${grouped[k].length} item(s)`}>
              <ul className="divide-y divide-[#EEF2F7]">
                {grouped[k].map((e) => (
                  <li key={e.alias} ref={e.alias === focus ? (el) => { ref.current = el; } : undefined}
                    className={cx('py-2 px-1 rounded', e.alias === focus && 'bg-[#EAF2FC]')}>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[11px] font-semibold text-[#265EAA] tabular-nums w-8">{e.alias}</span>
                      <span className="text-[12px] text-[#172B4D]">{e.concept_display}</span>
                      <Pill value={e.epistemic_status} />
                      {cited.has(e.alias) && <span className="text-[10px] text-[#26845A] font-medium">cited in answer</span>}
                    </div>
                    <p className="text-[11px] text-[#61738A] ml-10 tabular-nums">
                      {fmtDate(e.effective_start)}{e.effective_end ? ` → ${fmtDate(e.effective_end)}` : ''}
                      {e.value_num !== null && ` · ${e.value_num} ${e.unit ?? '(no unit)'}`}
                      {e.normalized_unit && e.normalized_unit !== e.unit && e.normalized_value !== null && ` (normalised ${e.normalized_value} ${e.normalized_unit})`}
                      {e.clinical_status && ` · ${e.clinical_status}`}
                    </p>
                    <details className="ml-10 mt-0.5">
                      <summary className="text-[10px] text-[#8A99AB] cursor-pointer">Provenance</summary>
                      <dl className="text-[10px] text-[#61738A] grid grid-cols-[110px_1fr] gap-x-2 mt-1 font-mono break-all">
                        <dt>record_id</dt><dd>{e.record_id}</dd>
                        <dt>hierarchy path</dt><dd>{e.group_path}</dd>
                        <dt>resource</dt><dd>{e.resource_type} {e.fhir_resource_id ?? ''}</dd>
                        <dt>encounter</dt><dd>{e.encounter_id ?? '—'}</dd>
                        <dt>source</dt><dd>{e.source_system} · {e.source_document ?? '—'}</dd>
                        <dt>details</dt><dd>{JSON.stringify(e.provenance)}</dd>
                      </dl>
                    </details>
                  </li>
                ))}
              </ul>
            </Card>
          ))}
          {!c.evidence.length && <Card><Empty title="No patient records were used">{c.action === 'EMERGENCY_OVERRIDE' ? 'Retrieval was skipped because emergency warning signs were detected.' : 'Your record had nothing relevant, or it is empty.'}</Empty></Card>}
        </div>
        <aside className="space-y-4">
          <Card title="How the records were found">
            {t ? (
              <div className="space-y-3 text-[11px]">
                <p className="text-[#61738A]">Method: <span className="text-[#172B4D]">{t.method}</span> · selector: <span className="text-[#172B4D]">{t.selector_backend ?? '—'}</span></p>
                <div>
                  <p className="font-medium text-[#172B4D] mb-1">STAIR stage 1 — sections</p>
                  <ul className="space-y-0.5">{t.selected_leaves.map(([p, s]) => <li key={p} className="font-mono break-all text-[#61738A]">{p} <span className="text-[#8A99AB]">({s.toFixed(3)})</span></li>)}</ul>
                </div>
                <div>
                  <p className="font-medium text-[#172B4D] mb-1">Stage 2 — concept groups</p>
                  <ul className="space-y-0.5 max-h-48 overflow-y-auto">{t.selected_groups.map(([p, s]) => <li key={p} className="font-mono break-all text-[#61738A]">{p.split('/').slice(-1)[0]} <span className="text-[#8A99AB]">({s.toFixed(3)})</span></li>)}</ul>
                </div>
                {t.structured_ops.length > 0 && <div><p className="font-medium text-[#172B4D] mb-1">Structured operations</p><ul>{t.structured_ops.map((o) => <li key={o} className="font-mono text-[#61738A] break-all">{o}</li>)}</ul></div>}
                <p className={t.invalid_paths.length ? 'text-[#C23E4A]' : 'text-[#26845A]'}>Invalid paths rejected: {t.invalid_paths.length}</p>
              </div>
            ) : <p className="text-[11px] text-[#8A99AB]">No retrieval trace.</p>}
          </Card>
          <Card title="Status legend">
            <ul className="space-y-1 text-[11px] text-[#61738A]">
              <li><Pill value="CONFIRMED" /> verified clinical record</li>
              <li><Pill value="PATIENT-REPORTED" /> entered or reported by you</li>
              <li><Pill value="EXTRACTED-UNCONFIRMED" /> read from a document, not yet confirmed</li>
              <li><Pill value="DERIVED" /> computed by MedResolve from cited records</li>
            </ul>
          </Card>
        </aside>
      </div>
    </>
  );
}

export function ReferencesScreen({ consultation: c, focus, onNavigate }: { consultation: Consultation | null; focus: string | null; onNavigate: (s: V2Screen) => void }) {
  const ref = useFocus(focus);
  if (!c) return <><PageHeader title="Medical reference evidence" /><NoConsultation onNavigate={onNavigate} /></>;
  return (
    <>
      <PageHeader title="Medical reference evidence" description="General medical knowledge retrieved for this question. These passages are not facts about you." />
      {!c.references.length ? <Card><Empty title="No reference passages were used" /></Card> : (
        <div className="space-y-3">
          {c.references.map((r) => (
            <section key={r.alias} ref={r.alias === focus ? (el) => { ref.current = el; } : undefined}
              className={cx('bg-white border rounded-lg p-4', r.alias === focus ? 'border-[#3675CA]' : 'border-[#DFE7F1]')}>
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <span className="text-[11px] font-semibold text-[#61738A]">{r.alias}</span>
                <span className="text-[11px] text-[#61738A]">{r.source} › {r.chapter} › <strong className="text-[#172B4D]">{r.section}</strong> › {r.subsection}</span>
              </div>
              <p className="text-[13px] text-[#172B4D] leading-relaxed">{r.text}</p>
              <p className="text-[10px] text-[#8A99AB] mt-2">
                {r.organization} · <a className="underline" href={r.url} target="_blank" rel="noreferrer">{r.url}</a> · accessed {r.access_date ?? '—'} · {r.license} · retrieval {r.method} (score {r.score.toFixed(4)})
              </p>
            </section>
          ))}
        </div>
      )}
    </>
  );
}

export function ConflictsScreen({ consultation: c, onNavigate }: { consultation: Consultation | null; onNavigate: (s: V2Screen) => void }) {
  if (!c) return <><PageHeader title="Conflicts & uncertainty" /><NoConsultation onNavigate={onNavigate} /></>;
  const v = c.verification;
  return (
    <>
      <PageHeader title="Conflicts, uncertainty & verification" description={`Question: “${c.query}”`} />
      <div className="space-y-4">
        <ActionBanner action={c.action} reason={c.action_reason} />
        <Card title="Record conflicts and missing information" subtitle={`${c.findings.length} finding(s)`}>
          {!c.findings.length ? <p className="text-[12px] text-[#61738A]">No conflicts or gaps were detected in the evidence used.</p> : (
            <ul className="divide-y divide-[#EEF2F7]">
              {c.findings.map((f, i) => (
                <li key={i} className="py-2">
                  <div className="flex flex-wrap items-center gap-2"><Pill value={f.severity} /><span className="text-[11px] font-semibold text-[#172B4D]">{f.finding_type.replace(/_/g, ' ')}</span>
                    <span className="text-[10px] text-[#8A99AB]">→ {f.recommended_action.replace(/_/g, ' ').toLowerCase()}</span></div>
                  <p className="text-[12px] text-[#61738A] mt-0.5">{f.description}</p>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Claim verification" subtitle={v ? `${v.stats.total_claims} claims · ${v.stats.withheld_claims} withheld · unsupported patient-claim rate ${(v.stats.unsupported_patient_claim_rate * 100).toFixed(0)}%` : 'Not run for this response'}>
          {!v ? <p className="text-[12px] text-[#61738A]">No generated narrative to verify (emergency, clarification or abstention response).</p> : (
            <div className="overflow-x-auto">
              <table className="w-full text-[12px]">
                <thead><tr className="text-left text-[10px] uppercase tracking-wide text-[#8A99AB] border-b border-[#DFE7F1]">
                  <th className="py-1.5 pr-2 font-medium">Claim</th><th className="py-1.5 pr-2 font-medium">Type</th><th className="py-1.5 pr-2 font-medium">Status</th><th className="py-1.5 font-medium">Why</th></tr></thead>
                <tbody>
                  {v.claims.filter((x) => x.claim_type !== 'STRUCTURAL').map((x) => (
                    <tr key={x.claim_id} className={cx('border-b border-[#EEF2F7] align-top', !x.permitted && 'bg-[#FFF8F6]')}>
                      <td className="py-1.5 pr-2 max-w-[420px]">{x.text}</td>
                      <td className="py-1.5 pr-2 text-[11px] text-[#61738A]">{x.claim_type.replace(/_/g, ' ').toLowerCase()}</td>
                      <td className="py-1.5 pr-2"><Pill value={x.status} />{!x.permitted && <span className="block text-[10px] text-[#C23E4A] mt-0.5">withheld</span>}</td>
                      <td className="py-1.5 text-[11px] text-[#61738A]">{x.rationale}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
        <div className="flex gap-2"><Button variant="secondary" onClick={() => onNavigate('context')}>View patient context</Button><Button variant="secondary" onClick={() => onNavigate('chat')}>Back to answer</Button></div>
      </div>
    </>
  );
}
