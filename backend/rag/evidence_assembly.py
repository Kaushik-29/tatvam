"""
Evidence assembly: dedupe, order chronologically, alias, and lay out the LLM
context in the clearly separated sections A–J.

Every patient fact is shown with an [E#] alias, its date, original value + unit,
and an explicit epistemic status:
  CONFIRMED            FHIR record with verificationStatus=confirmed (or clinician-confirmed)
  PATIENT-REPORTED     entered by the patient / chief complaint recorded from the patient
  EXTRACTED-UNCONFIRMED  OCR / automated extraction not yet confirmed by the patient
  DERIVED              computed by MedResolve from cited source records
Reference passages get [R#] aliases and are labelled GENERAL MEDICAL KNOWLEDGE.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from backend.patient_memory.classify import fmt_date

SECTION_OF_LEAF = {
    "demographics": "C",
    "medical_history/conditions": "C", "medical_history/diagnoses": "C", "medical_history/procedures": "C",
    "medical_history/immunizations": "C", "medical_history/care_plans": "C", "medical_history/social_history": "C",
    "medication_history/current_medications": "D", "medication_history/previous_medications": "D",
    "medication_history/medication_changes": "D", "allergy_history": "E",
    "clinical_encounters/previous_symptoms": "F", "clinical_encounters/complaints": "F",
    "clinical_encounters/consultations": "F", "clinical_encounters/encounter_dates": "F",
    "laboratory_observations/laboratory_results": "G", "laboratory_observations/vital_signs": "G",
    "laboratory_observations/historical_trends": "G", "laboratory_observations/assessments_and_surveys": "G",
    "medical_documents/prescriptions": "C", "medical_documents/discharge_summaries": "F",
    "medical_documents/diagnostic_reports": "G", "medical_documents/clinical_notes": "F",
}
SECTION_TITLES = {
    "A": "A. Current Patient Query", "B": "B. Current Symptoms (patient-reported now)",
    "C": "C. Relevant Previous Medical History", "D": "D. Medications (current and relevant previous)",
    "E": "E. Allergies", "F": "F. Relevant Previous Symptoms and Encounters",
    "G": "G. Relevant Laboratory Observations and Vital Signs", "H": "H. Temporal Context",
    "I": "I. Detected Conflicts and Uncertainty", "J": "J. Retrieved Medical Reference Passages (general knowledge, NOT patient facts)",
}


def epistemic_status(r: Dict[str, Any]) -> str:
    if r["source_system"] == "derived":
        return "DERIVED"
    if r["source_system"] == "ocr_extracted" and r["verification_status"] != "confirmed":
        return "EXTRACTED-UNCONFIRMED"
    if r["verification_status"] == "patient_reported" or r["source_system"] == "patient_entered":
        return "PATIENT-REPORTED"
    if r["verification_status"] in ("confirmed", "derived"):
        return "CONFIRMED"
    return "UNCONFIRMED"


@dataclass
class AssembledContext:
    evidence: Dict[str, Dict[str, Any]] = field(default_factory=dict)     # alias -> record (+status)
    references: Dict[str, Dict[str, Any]] = field(default_factory=dict)   # alias -> passage
    sections: Dict[str, List[str]] = field(default_factory=dict)
    record_alias: Dict[str, str] = field(default_factory=dict)

    def render(self) -> str:
        out = []
        for key in "ABCDEFGHIJ":
            lines = self.sections.get(key) or ["(none)"]
            out.append(f"### {SECTION_TITLES[key]}\n" + "\n".join(lines))
        return "\n\n".join(out)

    def to_dict(self):
        return {"evidence": self.evidence, "references": self.references, "sections": self.sections}


def assemble(query: str, symptoms: Sequence[str], intake: Optional[Dict[str, Any]],
             retrieved: Sequence[Dict[str, Any]], safety_context: Sequence[Dict[str, Any]],
             references: Sequence[Dict[str, Any]], findings: Sequence[Dict[str, Any]],
             med_intervals: Sequence[Dict[str, Any]] = (), max_records: int = 40) -> AssembledContext:
    ctx = AssembledContext()
    seen, ordered = set(), []
    for r in list(retrieved)[:max_records] + list(safety_context):
        if r["record_id"] not in seen:
            seen.add(r["record_id"]); ordered.append(r)
    ordered.sort(key=lambda r: (SECTION_OF_LEAF.get(r["leaf_path"], "C"), r.get("effective_start") or ""))
    for i, r in enumerate(ordered, 1):
        alias = f"E{i}"
        status = epistemic_status(r)
        ctx.evidence[alias] = {**r, "alias": alias, "epistemic_status": status}
        ctx.record_alias[r["record_id"]] = alias
        val = ""
        if r.get("value_num") is not None:
            val = f" = {r['value_num']:g} {r.get('unit') or '(no unit)'}"
            if r.get("normalized_unit") and r.get("normalized_unit") != r.get("unit") and r.get("normalized_value") is not None:
                val += f" (normalized {r['normalized_value']:g} {r['normalized_unit']})"
        elif r.get("value_text"):
            val = f" = {r['value_text']}"
        line = (f"[{alias}] ({status}; {fmt_date(r.get('effective_start'))}"
                + (f" to {fmt_date(r['effective_end'])}" if r.get("effective_end") else "")
                + (f"; status {r['clinical_status']}" if r.get("clinical_status") else "")
                + f") {r['concept_display']}{val} — {r['text'][:220]}")
        ctx.sections.setdefault(SECTION_OF_LEAF.get(r["leaf_path"], "C"), []).append(line)

    ctx.sections["A"] = [query.strip()]
    b = [f"Symptoms mentioned now: {', '.join(symptoms) if symptoms else 'none extracted'}"]
    for k, v in (intake or {}).items():
        if v not in (None, "", []):
            b.append(f"{k.replace('_', ' ')}: {v}")
    ctx.sections["B"] = b

    dated = [r for r in ordered if r.get("effective_start")]
    h = []
    if dated:
        h.append(f"Evidence spans {fmt_date(min(r['effective_start'] for r in dated))} to "
                 f"{fmt_date(max(r['effective_start'] for r in dated))}.")
    for iv in med_intervals:
        if iv["record_id"] in ctx.record_alias:
            h.append(f"[{ctx.record_alias[iv['record_id']]}] {iv['concept_key']} in effect "
                     f"{fmt_date(iv['interval_start'])} to {fmt_date(iv.get('interval_end')) if iv.get('interval_end') else 'present'}"
                     + (" (end date ESTIMATED, not recorded)" if iv.get("end_uncertain") else ""))
    ctx.sections["H"] = h

    ctx.sections["I"] = [f"- {f['finding_type']} ({f['severity']}): {f['description']}"
                         + (f" Evidence: {', '.join(ctx.record_alias.get(e, e) for e in f['evidence_ids'] if e in ctx.record_alias)}"
                            if f.get("evidence_ids") else "") for f in findings]

    for i, p in enumerate(references, 1):
        alias = f"R{i}"
        ctx.references[alias] = {**p, "alias": alias}
        ctx.sections.setdefault("J", []).append(
            f"[{alias}] {p['source']} › {p['chapter']} › {p['section']} › {p['subsection']}: {p['text']}")
    return ctx
