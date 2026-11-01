"""
Synthea FHIR R4 -> normalized longitudinal patient memory.

Usage:
    python -m backend.fhir_ingestion.synthea_ingest --input data/datasets/synthea/raw/generated_p600_seed20261101/fhir
        [--input data/datasets/synthea/raw/official_sample/extracted --tag official_sample]
        [--limit N] [--reset]

Each bundle is parsed resource by resource. Resources are mapped to STAIR-Clinical
leaves (backend/patient_memory/hierarchy.py) while preserving resource type,
resource ID, patient ID, encounter ID, source document, effective / recorded
dates, concept code, value, unit, provenance and confirmation status.
Derived records (medication changes, historical trends) are computed afterwards
and cite their source record IDs. A data-quality report is written to
data/datasets/synthea/manifests/.
"""

import argparse
import base64
import collections
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import delete, insert

from backend.config import DATA_DIR
from backend.patient_memory import classify as C
from backend.patient_memory.db import get_engine
from backend.patient_memory.derived import derive_medication_changes, derive_trends
from backend.patient_memory.hierarchy import LEAF_BY_PATH, concept_group_path
from backend.patient_memory.models import ClinicalRecord, Document, Patient

MANIFEST_DIR = DATA_DIR / "datasets" / "synthea" / "manifests"
PROCESSED_DIR = DATA_DIR / "datasets" / "synthea" / "processed"

UNMAPPED_TYPES = {
    "Claim": "billing, not clinical evidence",
    "ExplanationOfBenefit": "billing, not clinical evidence",
    "Provenance": "bundle-level provenance (kept as source_document reference)",
    "SupplyDelivery": "supply logistics",
    "CareTeam": "care-team roster",
    "Medication": "referenced medication definition (display copied onto MedicationRequest)",
    "MedicationAdministration": "in-clinic administrations (MedicationRequest is the prescribing record)",
    "Device": "device inventory (not in the requested hierarchy)",
    "Goal": "care-plan goals (CarePlan record retained)",
    "Organization": "directory resource",
    "Location": "directory resource",
    "Practitioner": "directory resource",
    "PractitionerRole": "directory resource",
}
NOTE_REPORT_CODES = {"34117-2", "51847-2", "11488-4", "18842-5"}


def _ref_id(ref: Optional[Dict[str, Any]]) -> Optional[str]:
    if not ref or "reference" not in ref:
        return None
    r = ref["reference"]
    return r.split(":")[-1].split("/")[-1] if r.startswith("urn:uuid:") or "/" in r else r


def _coding(cc: Optional[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str], str]:
    if not cc:
        return None, None, "Unspecified"
    codings = cc.get("coding") or [{}]
    c = codings[0]
    display = cc.get("text") or c.get("display") or c.get("code") or "Unspecified"
    system = (c.get("system") or "").rsplit("/", 1)[-1] or None
    return system, c.get("code"), display


def _status(cc: Optional[Dict[str, Any]]) -> Optional[str]:
    if not cc:
        return None
    return (cc.get("coding") or [{}])[0].get("code")


def _fmt_qty(v: Optional[float], unit: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    vs = f"{v:.2f}".rstrip("0").rstrip(".")
    return f"{vs} {unit}" if unit else vs


class BundleMapper:
    """Maps one Synthea patient bundle to Patient / ClinicalRecord / Document rows."""

    def __init__(self, source_name: str, stats: collections.Counter, issues: collections.Counter):
        self.source = source_name
        self.stats = stats
        self.issues = issues

    def map_bundle(self, bundle: Dict[str, Any]):
        resources = [e["resource"] for e in bundle.get("entry", [])]
        patient_res = next((r for r in resources if r["resourceType"] == "Patient"), None)
        if patient_res is None:
            self.issues["bundle_without_patient"] += 1
            return None, [], []
        pid = patient_res["id"]
        patient = self._patient(patient_res)
        encounters = {r["id"]: r for r in resources if r["resourceType"] == "Encounter"}
        records: List[Dict[str, Any]] = []
        documents: List[Dict[str, Any]] = []
        records.append(self._demographics(pid, patient))
        for r in resources:
            t = r["resourceType"]
            self.stats[f"resource:{t}"] += 1
            subject = _ref_id(r.get("subject") or r.get("patient"))
            if t != "Patient" and subject and subject != pid:
                self.issues["subject_mismatch"] += 1
                continue
            handler = getattr(self, f"_map_{t}", None)
            if handler is None:
                if t != "Patient":
                    self.stats[f"unmapped:{t}"] += 1
                continue
            out = handler(pid, r, encounters)
            if out is None:
                continue
            recs, docs = out
            for rec in recs:
                if rec.get("encounter_id") and rec["encounter_id"] not in encounters:
                    self.issues["unresolved_encounter_reference"] += 1
            records.extend(recs)
            documents.extend(docs)
            self.stats[f"mapped:{t}"] += 1
        units = collections.defaultdict(set)
        for rec in records:
            if rec.get("unit"):
                units[rec["concept_key"]].add(rec["unit"])
        for key, us in units.items():
            if len(us) > 1:
                self.issues[f"multiple_unit_strings_same_concept:{key}:{'|'.join(sorted(us))}"] += 1
        records.extend(derive_medication_changes(pid, records, self.source))
        records.extend(derive_trends(pid, records, self.source))
        return patient, records, documents

    # ------------------------------------------------------------------ helpers
    def _rec(self, pid: str, leaf: str, rtype: str, rid: str, display: str, *, concept_key: Optional[str] = None,
             system=None, code=None, encounter=None, start=None, end=None, recorded=None,
             value_num=None, value_text=None, unit=None, status=None, verification="confirmed",
             extra_text=None, provenance: Optional[Dict[str, Any]] = None, record_suffix: str = "") -> Dict[str, Any]:
        key = concept_key or C.strip_semantic_tag(display).lower()
        nv, nu = C.normalize_quantity(value_num, unit)
        val_str = _fmt_qty(value_num, unit) or value_text
        if start is None:
            self.issues[f"missing_effective_date:{rtype}"] += 1
        if value_num is not None and not unit:
            self.issues["numeric_value_without_unit"] += 1
        prov = {"fhir_resource_type": rtype, "fhir_resource_id": rid, "bundle": self.source}
        prov.update(provenance or {})
        return dict(
            record_id=f"{rtype}/{rid}{record_suffix}",
            patient_id=pid, leaf_path=leaf, group_path=concept_group_path(leaf, key),
            resource_type=rtype, fhir_resource_id=rid, encounter_id=encounter,
            source_document=self.source, source_system="synthea_fhir_r4",
            concept_system=system, concept_code=code, concept_display=display, concept_key=key,
            effective_start=start, effective_end=end, recorded_date=recorded or start,
            value_num=value_num, value_text=value_text, unit=unit,
            normalized_value=nv, normalized_unit=nu, clinical_status=status,
            verification_status=verification, confidence=1.0, provenance=json.dumps(prov),
            text=C.render_text(LEAF_BY_PATH[leaf].title, display, start=start, end=end, value=val_str,
                               status=status, verification=verification, extra=extra_text),
        )

    def _patient(self, r: Dict[str, Any]) -> Dict[str, Any]:
        name = (r.get("name") or [{}])[0]
        addr = (r.get("address") or [{}])[0]
        race = eth = None
        for ext in r.get("extension", []):
            if ext["url"].endswith("us-core-race"):
                race = next((e.get("valueString") for e in ext.get("extension", []) if e["url"] == "text"), None)
            if ext["url"].endswith("us-core-ethnicity"):
                eth = next((e.get("valueString") for e in ext.get("extension", []) if e["url"] == "text"), None)
        return dict(patient_id=r["id"], source="synthea_fhir_r4", fhir_resource_id=r["id"],
                    given_name=" ".join(name.get("given", [])), family_name=name.get("family"),
                    birth_date=r.get("birthDate"), gender=r.get("gender"),
                    deceased_date=r.get("deceasedDateTime"), city=addr.get("city"), state=addr.get("state"),
                    race=race, ethnicity=eth, source_document=self.source, onboarding_complete=True)

    def _demographics(self, pid: str, p: Dict[str, Any]) -> Dict[str, Any]:
        desc = f"{p['gender']}, born {p['birth_date']}"
        if p.get("deceased_date"):
            desc += f", deceased {p['deceased_date'][:10]}"
        return self._rec(pid, "demographics", "Patient", pid, "Demographics", concept_key="demographics",
                         start=p["birth_date"], value_text=desc, record_suffix="#demographics")

    # ---------------------------------------------------------------- mappers
    def _map_Condition(self, pid, r, enc):
        system, code, display = _coding(r.get("code"))
        leaf = C.classify_condition(display)
        status = _status(r.get("clinicalStatus"))
        ver = _status(r.get("verificationStatus")) or "unconfirmed"
        ver = {"confirmed": "confirmed", "refuted": "refuted", "entered-in-error": "refuted"}.get(ver, "unconfirmed")
        return [self._rec(pid, leaf, "Condition", r["id"], display, system=system, code=code,
                          encounter=_ref_id(r.get("encounter")), start=r.get("onsetDateTime"),
                          end=r.get("abatementDateTime"), recorded=r.get("recordedDate"),
                          status=status, verification=ver)], []

    def _map_MedicationRequest(self, pid, r, enc):
        system, code, display = _coding(r.get("medicationCodeableConcept"))
        if display == "Unspecified" and r.get("medicationReference"):
            display = r["medicationReference"].get("display") or "Unspecified medication"
        status = r.get("status")
        leaf = ("medication_history/current_medications" if status in ("active", "on-hold")
                else "medication_history/previous_medications")
        reasons = [x.get("display") for x in r.get("reasonReference", []) if x.get("display")]
        reasons += [_coding(x)[2] for x in r.get("reasonCode", [])]
        dose = None
        di = (r.get("dosageInstruction") or [{}])[0]
        if di.get("timing", {}).get("repeat"):
            rep = di["timing"]["repeat"]
            dose = f"{rep.get('frequency', '?')}x per {rep.get('period', '?')} {rep.get('periodUnit', '')}".strip()
        extra = []
        if reasons:
            extra.append("for " + "; ".join(C.strip_semantic_tag(x) for x in reasons))
        if dose:
            extra.append(f"dosing {dose}")
        return [self._rec(pid, leaf, "MedicationRequest", r["id"], display, system=system, code=code,
                          concept_key=C.medication_ingredient(display), encounter=_ref_id(r.get("encounter")),
                          start=r.get("authoredOn"), status=status, value_text=C.medication_strength(display),
                          extra_text=" ".join(extra) or None,
                          provenance={"reasons": reasons, "requester": (r.get("requester") or {}).get("display")})], []

    def _map_AllergyIntolerance(self, pid, r, enc):
        system, code, display = _coding(r.get("code"))
        reactions = []
        for rx in r.get("reaction", []):
            for m in rx.get("manifestation", []):
                reactions.append(f"{_coding(m)[2]} ({rx.get('severity', 'severity unknown')})")
        ver = _status(r.get("verificationStatus")) or "unconfirmed"
        cat = ",".join(r.get("category", [])) or None
        extra = f"category {cat}, criticality {r.get('criticality', 'unknown')}"
        if reactions:
            extra += "; reactions: " + "; ".join(reactions)
        return [self._rec(pid, "allergy_history", "AllergyIntolerance", r["id"], display, system=system, code=code,
                          start=r.get("onsetDateTime") or r.get("recordedDate"), recorded=r.get("recordedDate"),
                          status=_status(r.get("clinicalStatus")),
                          verification="confirmed" if ver == "confirmed" else "unconfirmed",
                          value_text=cat, extra_text=extra,
                          provenance={"reactions": reactions, "criticality": r.get("criticality")})], []

    def _map_Encounter(self, pid, r, enc):
        system, code, display = _coding((r.get("type") or [None])[0])
        period = r.get("period", {})
        cls = (r.get("class") or {}).get("code")
        provider = ((r.get("participant") or [{}])[0].get("individual") or {}).get("display")
        location = ((r.get("location") or [{}])[0].get("location") or {}).get("display")
        reasons = [_coding(x)[2] for x in r.get("reasonCode", [])]
        extra = f"class {cls}"
        if provider:
            extra += f", provider {provider}"
        if location:
            extra += f", at {location}"
        if reasons:
            extra += "; reason: " + "; ".join(C.strip_semantic_tag(x) for x in reasons)
        recs = [self._rec(pid, "clinical_encounters/consultations", "Encounter", r["id"], display, system=system,
                          code=code, encounter=r["id"], start=period.get("start"), end=period.get("end"),
                          status=r.get("status"), value_text=cls, extra_text=extra,
                          provenance={"class": cls, "provider": provider, "location": location})]
        for i, rc in enumerate(r.get("reasonCode", [])):
            rs, rcode, rdisp = _coding(rc)
            recs.append(self._rec(pid, "clinical_encounters/complaints", "Encounter", r["id"], rdisp, system=rs,
                                  code=rcode, encounter=r["id"], start=period.get("start"),
                                  extra_text=f"(reason for {C.strip_semantic_tag(display)} visit)",
                                  record_suffix=f"#reason{i}", provenance={"element": "Encounter.reasonCode"}))
        return recs, []

    def _map_Observation(self, pid, r, enc):
        cat = ((r.get("category") or [{}])[0].get("coding") or [{}])[0].get("code", "")
        leaf = C.OBS_CATEGORY_TO_LEAF.get(cat, "laboratory_observations/assessments_and_surveys")
        system, code, display = _coding(r.get("code"))
        common = dict(encounter=_ref_id(r.get("encounter")), start=r.get("effectiveDateTime"),
                      recorded=r.get("issued"), status=r.get("status"))
        recs = []
        if "valueQuantity" in r:
            q = r["valueQuantity"]
            recs.append(self._rec(pid, leaf, "Observation", r["id"], display, system=system, code=code,
                                  value_num=q.get("value"), unit=q.get("code") or q.get("unit"), **common))
        elif "valueCodeableConcept" in r:
            recs.append(self._rec(pid, leaf, "Observation", r["id"], display, system=system, code=code,
                                  value_text=_coding(r["valueCodeableConcept"])[2], **common))
        elif "valueString" in r:
            recs.append(self._rec(pid, leaf, "Observation", r["id"], display, system=system, code=code,
                                  value_text=r["valueString"], **common))
        for comp in r.get("component", []):
            cs, ccode, cdisp = _coding(comp.get("code"))
            if "valueQuantity" in comp:
                q = comp["valueQuantity"]
                recs.append(self._rec(pid, leaf, "Observation", r["id"], cdisp, system=cs, code=ccode,
                                      value_num=q.get("value"), unit=q.get("code") or q.get("unit"),
                                      record_suffix=f"#{ccode}", provenance={"component_of": display}, **common))
            elif "valueCodeableConcept" in comp:
                recs.append(self._rec(pid, leaf, "Observation", r["id"], cdisp, system=cs, code=ccode,
                                      value_text=_coding(comp["valueCodeableConcept"])[2],
                                      record_suffix=f"#{ccode}", provenance={"component_of": display}, **common))
        if not recs:
            self.issues["observation_without_value"] += 1
        return recs, []

    def _map_Procedure(self, pid, r, enc):
        system, code, display = _coding(r.get("code"))
        per = r.get("performedPeriod", {})
        start = per.get("start") or r.get("performedDateTime")
        reasons = [x.get("display") for x in r.get("reasonReference", []) if x.get("display")]
        return [self._rec(pid, "medical_history/procedures", "Procedure", r["id"], display, system=system,
                          code=code, encounter=_ref_id(r.get("encounter")), start=start, end=per.get("end"),
                          status=r.get("status"),
                          extra_text=("for " + "; ".join(C.strip_semantic_tag(x) for x in reasons)) if reasons else None)], []

    def _map_Immunization(self, pid, r, enc):
        system, code, display = _coding(r.get("vaccineCode"))
        return [self._rec(pid, "medical_history/immunizations", "Immunization", r["id"], display, system=system,
                          code=code, encounter=_ref_id(r.get("encounter")), start=r.get("occurrenceDateTime"),
                          status=r.get("status"))], []

    def _map_CarePlan(self, pid, r, enc):
        cats = [c for c in r.get("category", []) if c.get("text")]
        system, code, display = _coding(cats[0] if cats else None)
        per = r.get("period", {})
        addresses = [x.get("display") for x in r.get("addresses", []) if x.get("display")]
        acts = sorted({_coding(a.get("detail", {}).get("code"))[2] for a in r.get("activity", [])})
        extra = []
        if addresses:
            extra.append("addresses " + "; ".join(C.strip_semantic_tag(a) for a in addresses))
        if acts:
            extra.append("activities: " + "; ".join(C.strip_semantic_tag(a) for a in acts[:6]))
        return [self._rec(pid, "medical_history/care_plans", "CarePlan", r["id"], display, system=system, code=code,
                          encounter=_ref_id(r.get("encounter")), start=per.get("start"), end=per.get("end"),
                          status=r.get("status"), extra_text=" ".join(extra) or None)], []

    def _map_DiagnosticReport(self, pid, r, enc):
        system, code, display = _coding(r.get("code"))
        if code in NOTE_REPORT_CODES and r.get("presentedForm"):
            self.stats["dedup:DiagnosticReport_note_duplicate_of_DocumentReference"] += 1
            return None
        results = [x.get("display") for x in r.get("result", []) if x.get("display")]
        return [self._rec(pid, "medical_documents/diagnostic_reports", "DiagnosticReport", r["id"], display,
                          system=system, code=code, encounter=_ref_id(r.get("encounter")),
                          start=r.get("effectiveDateTime"), recorded=r.get("issued"), status=r.get("status"),
                          extra_text=(f"includes {len(results)} results: " + "; ".join(results[:8])) if results else None,
                          provenance={"result_refs": [_ref_id(x) for x in r.get("result", [])]})], []

    def _map_ImagingStudy(self, pid, r, enc):
        series = r.get("series") or [{}]
        modality = (series[0].get("modality") or {}).get("display", "Imaging")
        body = (series[0].get("bodySite") or {}).get("display", "")
        display = f"Imaging study: {modality} {body}".strip()
        return [self._rec(pid, "medical_documents/diagnostic_reports", "ImagingStudy", r["id"], display,
                          concept_key=f"imaging {modality} {body}".lower(), encounter=_ref_id(r.get("encounter")),
                          start=r.get("started"), status=r.get("status"))], []

    def _map_DocumentReference(self, pid, r, enc):
        system, code, display = _coding(r.get("type"))
        att = (r.get("content") or [{}])[0].get("attachment", {})
        try:
            text = base64.b64decode(att.get("data", "")).decode("utf-8", errors="replace")
        except Exception:
            text = ""
            self.issues["document_decode_error"] += 1
        enc_id = _ref_id((r.get("context") or {}).get("encounter", [None])[0]) if r.get("context") else None
        enc_class = ((enc.get(enc_id) or {}).get("class") or {}).get("code") if enc_id else None
        leaf = "medical_documents/discharge_summaries" if enc_class == "IMP" else "medical_documents/clinical_notes"
        title = "Discharge summary" if leaf.endswith("discharge_summaries") else "Clinical note"
        date = r.get("date")
        cc = _chief_complaints(text)
        assessment = _section(text, "Assessment and Plan")
        recs = [self._rec(pid, leaf, "DocumentReference", r["id"], f"{title} ({display})",
                          concept_key=title.lower(), system=system, code=code, encounter=enc_id, start=date,
                          status=r.get("status"),
                          extra_text=("chief complaint: " + ", ".join(cc) + "; " if cc else "") +
                                     (("assessment: " + assessment[:240]) if assessment else ""))]
        for i, complaint in enumerate(cc):
            recs.append(self._rec(pid, "clinical_encounters/complaints", "DocumentReference", r["id"], complaint,
                                  encounter=enc_id, start=date, verification="patient_reported",
                                  extra_text="(chief complaint recorded in clinical note)",
                                  record_suffix=f"#cc{i}",
                                  provenance={"element": "note section '# Chief Complaint'",
                                              "extraction_method": "RULE_BASED_PARSER"}))
        doc = dict(document_id=f"DocumentReference/{r['id']}", patient_id=pid, leaf_path=leaf,
                   title=f"{title} — {display}", doc_date=date, encounter_id=enc_id,
                   fhir_resource_id=r["id"], source_system="synthea_fhir_r4", text=text, ocr_status="n/a")
        return recs, [doc]


def _section(text: str, header: str) -> str:
    m = re.search(rf"# {re.escape(header)}\n(.*?)(?=\n# |\Z)", text, re.S)
    return " ".join(m.group(1).split()) if m else ""


def _chief_complaints(text: str) -> List[str]:
    sec = re.search(r"# Chief Complaint\n(.*?)(?=\n\n|\n# |\Z)", text, re.S)
    if not sec:
        return []
    items = [ln.strip()[2:].strip() for ln in sec.group(1).splitlines() if ln.strip().startswith("- ")]
    return [i for i in items if i]


def iter_bundles(input_dir: Path, limit: Optional[int]):
    files = sorted(p for p in input_dir.glob("*.json")
                   if not p.name.startswith(("hospitalInformation", "practitionerInformation")))
    if limit:
        files = files[:limit]
    for f in files:
        yield f, json.loads(f.read_text(encoding="utf-8"))


def ingest(input_dir: Path, tag: str, limit: Optional[int] = None, reset: bool = False) -> Dict[str, Any]:
    engine = get_engine()
    stats, issues = collections.Counter(), collections.Counter()
    leaf_counts, per_patient_leaves = collections.Counter(), []
    seen_ids, dup_ids = set(), 0
    t0 = dt.datetime.now()
    n_pat = 0
    with engine.begin() as conn:
        if reset:
            conn.execute(delete(ClinicalRecord).where(ClinicalRecord.source_system.in_(["synthea_fhir_r4", "derived"])))
            conn.execute(delete(Document).where(Document.source_system == "synthea_fhir_r4"))
            conn.execute(delete(Patient).where(Patient.source == "synthea_fhir_r4"))
    for path, bundle in iter_bundles(input_dir, limit):
        mapper = BundleMapper(f"{tag}/{path.name}", stats, issues)
        patient, records, docs = mapper.map_bundle(bundle)
        if patient is None:
            continue
        unique = []
        for rec in records:
            if rec["record_id"] in seen_ids:
                dup_ids += 1
                continue
            seen_ids.add(rec["record_id"])
            unique.append(rec)
        with engine.begin() as conn:
            conn.execute(delete(ClinicalRecord).where(ClinicalRecord.patient_id == patient["patient_id"]))
            conn.execute(delete(Document).where(Document.patient_id == patient["patient_id"]))
            conn.execute(delete(Patient).where(Patient.patient_id == patient["patient_id"]))
            conn.execute(insert(Patient), [patient])
            for i in range(0, len(unique), 5000):
                conn.execute(insert(ClinicalRecord), unique[i:i + 5000])
            if docs:
                conn.execute(insert(Document), docs)
        lc = collections.Counter(r["leaf_path"] for r in unique)
        leaf_counts.update(lc)
        per_patient_leaves.append(lc)
        n_pat += 1
        if n_pat % 50 == 0:
            print(f"  ingested {n_pat} patients, {sum(leaf_counts.values())} records")
    elapsed = (dt.datetime.now() - t0).total_seconds()
    from backend.patient_memory.hierarchy import STORED_LEAF_PATHS
    coverage = {lp: sum(1 for c in per_patient_leaves if c.get(lp)) for lp in STORED_LEAF_PATHS}
    report = {
        "source_dir": str(input_dir), "tag": tag, "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "patients_ingested": n_pat, "records_total": sum(leaf_counts.values()),
        "duplicate_record_ids_skipped": dup_ids, "elapsed_seconds": round(elapsed, 1),
        "records_per_leaf": dict(sorted(leaf_counts.items())),
        "patients_with_any_record_per_leaf": coverage,
        "resource_counts": {k[9:]: v for k, v in sorted(stats.items()) if k.startswith("resource:")},
        "mapped_counts": {k[7:]: v for k, v in sorted(stats.items()) if k.startswith("mapped:")},
        "unmapped_counts": {k[9:]: {"count": v, "reason": UNMAPPED_TYPES.get(k[9:], "not mapped")}
                            for k, v in sorted(stats.items()) if k.startswith("unmapped:")},
        "deduplication": {k[6:]: v for k, v in stats.items() if k.startswith("dedup:")},
        "issues": dict(sorted(issues.items())),
    }
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    out = MANIFEST_DIR / f"data_quality_report_{tag}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_markdown(report, MANIFEST_DIR / f"data_quality_report_{tag}.md")
    print(f"Wrote {out}")
    return report


def _write_markdown(rep: Dict[str, Any], path: Path) -> None:
    lines = [f"# Synthea ingestion data-quality report — `{rep['tag']}`", "",
             f"- Source: `{rep['source_dir']}`", f"- Generated: {rep['generated_at']}",
             f"- Patients: **{rep['patients_ingested']}**, records: **{rep['records_total']}**, "
             f"duplicate IDs skipped: {rep['duplicate_record_ids_skipped']}", "",
             "## Records per STAIR-Clinical leaf", "", "| Leaf | Records | Patients with ≥1 |", "|---|---:|---:|"]
    for leaf, n in rep["records_per_leaf"].items():
        lines.append(f"| `{leaf}` | {n} | {rep['patients_with_any_record_per_leaf'].get(leaf, '—')} |")
    empty = [l for l, n in rep["patients_with_any_record_per_leaf"].items() if n == 0]
    if empty:
        lines += ["", "Leaves with no Synthea records (expected — populated by uploads / patient entry): "
                  + ", ".join(f"`{e}`" for e in empty)]
    lines += ["", "## FHIR resources", "", "| Resource | Seen | Mapped |", "|---|---:|---:|"]
    for k, v in rep["resource_counts"].items():
        lines.append(f"| {k} | {v} | {rep['mapped_counts'].get(k, 0)} |")
    lines += ["", "## Not mapped (by design)", ""]
    for k, v in rep["unmapped_counts"].items():
        lines.append(f"- **{k}** ({v['count']}): {v['reason']}")
    lines += ["", "## Data-quality issues", ""]
    lines += [f"- `{k}`: {v}" for k, v in rep["issues"].items()] or ["- none"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--tag", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--reset", action="store_true")
    a = ap.parse_args()
    inp = Path(a.input)
    ingest(inp, a.tag or inp.parent.name, a.limit, a.reset)


if __name__ == "__main__":
    main()
