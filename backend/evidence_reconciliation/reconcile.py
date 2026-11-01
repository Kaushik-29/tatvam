"""
Longitudinal evidence reconciliation.

Inspects the assembled patient evidence (and the new query) for:
  ALLERGY_MEDICATION_CONFLICT   active allergy vs current / mentioned medication of the same class
  DUPLICATE_ACTIVE_MEDICATION   >1 active request for an ingredient with different strengths
  SOURCE_STATUS_DISAGREEMENT    same concept with conflicting status across sources
  UNIT_DISCREPANCY              same concept recorded with different units (no silent conversion)
  TEMPORAL_INCONSISTENCY        end before start, events before birth, future-dated records
  UNCONFIRMED_EXTRACTION        OCR / extracted values not yet confirmed by the patient
  ASSUMED_MEDICATION_EXPOSURE   medication exposure window inferred, not recorded
  MISSING_INFORMATION           mentioned medication not in record, empty section, value without unit
  STALE_EVIDENCE                most recent relevant measurement older than 2 years
"""

import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Sequence

DRUG_CLASSES = {
    "penicillin": ["penicillin", "amoxicillin", "ampicillin", "piperacillin", "dicloxacillin", "nafcillin"],
    "cephalosporin": ["cefuroxime", "cephalexin", "ceftriaxone", "cefazolin", "cefdinir"],
    "sulfonamide": ["sulfamethoxazole", "sulfasalazine", "sulfa"],
    "nsaid": ["ibuprofen", "naproxen", "aspirin", "diclofenac", "celecoxib", "ketorolac", "meloxicam"],
    "opioid": ["codeine", "morphine", "oxycodone", "hydrocodone", "tramadol", "fentanyl"],
    "ace inhibitor": ["lisinopril", "enalapril", "ramipril", "captopril"],
    "statin": ["simvastatin", "atorvastatin", "rosuvastatin", "pravastatin"],
}
ALLERGY_TO_CLASS = {
    "penicillin": "penicillin", "amoxicillin": "penicillin", "cephalosporin": "cephalosporin",
    "sulfa": "sulfonamide", "sulfonamide": "sulfonamide", "aspirin": "nsaid", "ibuprofen": "nsaid",
    "nsaid": "nsaid", "non-steroidal": "nsaid", "codeine": "opioid", "morphine": "opioid", "opioid": "opioid",
    "lisinopril": "ace inhibitor", "ace inhibitor": "ace inhibitor", "statin": "statin",
}


@dataclass
class Finding:
    finding_type: str
    severity: str                    # HIGH | MEDIUM | LOW | INFO
    description: str
    evidence_ids: List[str] = field(default_factory=list)
    recommended_action: str = "INFO"   # USER_CONFIRMATION | QUALIFIED_CLINICAL_REVIEW | INFO

    def to_dict(self):
        return asdict(self)


def _drug_class(name: str) -> Optional[str]:
    n = name.lower()
    for cls, members in DRUG_CLASSES.items():
        if any(m in n for m in members):
            return cls
    return None


def reconcile(evidence: Sequence[Dict[str, Any]], *, allergies: Sequence[Dict[str, Any]] = (),
              current_meds: Sequence[Dict[str, Any]] = (), mentioned_medications: Sequence[str] = (),
              query_drug_terms: Sequence[str] = (), birth_date: Optional[str] = None,
              needed_leaves: Sequence[str] = (), leaf_counts: Optional[Dict[str, int]] = None,
              med_intervals: Sequence[Dict[str, Any]] = (), today: Optional[str] = None) -> List[Finding]:
    today = today or date.today().isoformat()
    out: List[Finding] = []
    ev = list(evidence)

    # ---- allergy vs medication (current meds + drugs named in the question)
    active_allergies = [a for a in allergies if (a.get("clinical_status") or "active") == "active"]
    for a in active_allergies:
        acls = next((c for k, c in ALLERGY_TO_CLASS.items() if k in a["concept_display"].lower()), None)
        if not acls:
            continue
        for m in current_meds:
            if _drug_class(m["concept_display"]) == acls:
                out.append(Finding("ALLERGY_MEDICATION_CONFLICT", "HIGH",
                                   f"Recorded allergy '{a['concept_display']}' and active medication "
                                   f"'{m['concept_display']}' belong to the same drug class ({acls}).",
                                   [a["record_id"], m["record_id"]], "QUALIFIED_CLINICAL_REVIEW"))
        for term in query_drug_terms:
            if _drug_class(term) == acls or acls in term.lower():
                out.append(Finding("ALLERGY_MEDICATION_CONFLICT", "HIGH",
                                   f"The question mentions '{term}', and the record lists an allergy to "
                                   f"'{a['concept_display']}' ({acls} class).", [a["record_id"]],
                                   "QUALIFIED_CLINICAL_REVIEW"))

    # ---- duplicate active medications with different strengths
    by_drug = defaultdict(list)
    for m in current_meds:
        by_drug[m["concept_key"]].append(m)
    for drug, ms in by_drug.items():
        strengths = {m.get("value_text") for m in ms if m.get("value_text")}
        if len(ms) > 1 and len(strengths) > 1:
            out.append(Finding("DUPLICATE_ACTIVE_MEDICATION", "MEDIUM",
                               f"{len(ms)} active prescriptions for {drug} with different strengths "
                               f"({', '.join(sorted(strengths))}).", [m["record_id"] for m in ms],
                               "QUALIFIED_CLINICAL_REVIEW"))

    # ---- status disagreement across sources / unit discrepancy
    by_concept = defaultdict(list)
    for r in ev:
        by_concept[(r["leaf_path"], r["concept_key"])].append(r)
    for (leaf, key), rs in by_concept.items():
        srcs = {r["source_system"] for r in rs}
        statuses = {(r["source_system"], r.get("clinical_status")) for r in rs if r.get("clinical_status")}
        if len(srcs) > 1 and len({s for _, s in statuses}) > 1 and "derived" not in srcs:
            out.append(Finding("SOURCE_STATUS_DISAGREEMENT", "MEDIUM",
                               f"'{rs[0]['concept_display']}' has conflicting status across sources: "
                               + "; ".join(f"{s}={st}" for s, st in sorted(statuses)),
                               [r["record_id"] for r in rs], "USER_CONFIRMATION"))
        units = {r["unit"] for r in rs if r.get("unit")}
        if len(units) > 1 and leaf.startswith("laboratory_observations"):
            out.append(Finding("UNIT_DISCREPANCY", "MEDIUM",
                               f"'{rs[0]['concept_display']}' is recorded in different units ({', '.join(sorted(units))}); "
                               "values were not converted or compared across units.",
                               [r["record_id"] for r in rs][:6], "INFO"))

    # ---- temporal consistency
    for r in ev:
        s, e = r.get("effective_start"), r.get("effective_end")
        if s and e and e[:19] < s[:19]:
            out.append(Finding("TEMPORAL_INCONSISTENCY", "LOW", f"Record ends before it starts: {r['text'][:120]}",
                               [r["record_id"]], "USER_CONFIRMATION"))
        if s and s[:10] > today:
            out.append(Finding("TEMPORAL_INCONSISTENCY", "LOW", f"Future-dated record: {r['text'][:120]}",
                               [r["record_id"]], "USER_CONFIRMATION"))
        if s and birth_date and s[:10] < birth_date and r["leaf_path"] != "demographics":
            out.append(Finding("TEMPORAL_INCONSISTENCY", "LOW", f"Record dated before birth: {r['text'][:120]}",
                               [r["record_id"]], "USER_CONFIRMATION"))

    # ---- extraction confidence / confirmation
    for r in ev:
        if r["source_system"] == "ocr_extracted" and r["verification_status"] != "confirmed":
            out.append(Finding("UNCONFIRMED_EXTRACTION", "MEDIUM" if (r.get("confidence") or 1) < 0.8 else "LOW",
                               f"Value extracted from an uploaded document and not yet confirmed: {r['text'][:120]} "
                               f"(confidence {r.get('confidence', 0):.2f})", [r["record_id"]], "USER_CONFIRMATION"))
        if r.get("value_num") is not None and not r.get("unit") and r["leaf_path"].startswith("laboratory"):
            out.append(Finding("MISSING_INFORMATION", "LOW", f"Numeric value without a unit: {r['text'][:120]}",
                               [r["record_id"]], "USER_CONFIRMATION"))

    # ---- assumed exposure windows used in the answer
    ev_ids = {r["record_id"] for r in ev}
    unc = [iv for iv in med_intervals if iv.get("end_uncertain") and iv["record_id"] in ev_ids]
    if unc:
        out.append(Finding("ASSUMED_MEDICATION_EXPOSURE", "INFO",
                           "Medication end dates are not recorded; exposure windows for "
                           + ", ".join(sorted({iv["concept_key"] for iv in unc})[:6])
                           + " were estimated (acute 30 days / chronic until next prescription).",
                           [iv["record_id"] for iv in unc][:8], "USER_CONFIRMATION"))

    # ---- missing information
    known = {m["concept_key"] for m in current_meds} | {r["concept_key"] for r in ev if "medication" in r["leaf_path"]}
    for m in mentioned_medications:
        if not any(m.lower() in k for k in known):
            out.append(Finding("MISSING_INFORMATION", "MEDIUM",
                               f"You mentioned '{m}', but it is not in your medication records.", [],
                               "USER_CONFIRMATION"))
    leaf_counts = leaf_counts or {}
    for lp in needed_leaves:
        if leaf_counts.get(lp, 0) == 0:
            pretty = lp.split("/")[-1].replace("_", " ")
            out.append(Finding("MISSING_INFORMATION", "MEDIUM" if lp in ("allergy_history",) else "LOW",
                               f"No {pretty} are recorded. Absence of a record does not mean absence of the condition.",
                               [], "USER_CONFIRMATION"))

    # ---- stale evidence
    labs = [r for r in ev if r["leaf_path"] in ("laboratory_observations/laboratory_results",
                                                "laboratory_observations/vital_signs") and r.get("effective_start")]
    if labs:
        latest = max(r["effective_start"][:10] for r in labs)
        if latest < f"{int(today[:4]) - 2}{today[4:]}":
            out.append(Finding("STALE_EVIDENCE", "LOW", f"The most recent relevant measurement is from {latest}; "
                               "current values may differ.", [], "INFO"))
    # de-duplicate identical findings
    uniq, seen = [], set()
    for f in out:
        key = (f.finding_type, f.description)
        if key not in seen:
            seen.add(key); uniq.append(f)
    return uniq
