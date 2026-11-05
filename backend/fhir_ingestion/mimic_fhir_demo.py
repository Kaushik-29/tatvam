"""
MIMIC-IV Clinical Database Demo on FHIR (v2.1.0, PhysioNet, OPEN ACCESS) -> patient memory.

    python -m backend.fhir_ingestion.mimic_fhir_demo [--input data/datasets/mimic/raw] [--limit N]

This is the openly available ~100-patient demo, not the credentialed MIMIC-IV
(see mimic_pipeline.py, still pending authorization). Cite:
  Bennett A. et al. MIMIC-IV Clinical Database Demo on FHIR (v2.1.0). PhysioNet, 2025.
  Bennett AM et al. MIMIC-IV on FHIR. JAMIA 30(4):718-725, 2023.

The demo ships one NDJSON file per resource type. Resources are regrouped into one
bundle per patient and passed through the Synthea BundleMapper, after filling in what
MIMIC leaves elsewhere:
  * Condition has no onset date        -> start of its encounter; coded diagnoses marked confirmed
  * MedicationRequest -> Medication     -> drug name from the Medication identifier
  * Encounter type is generic           -> named by encounter class (emergency, ambulatory, ...)
  * MedicationStatement (ED home meds)  -> previous medications, marked patient-reported
ICU chart events (~1M rows) and microbiology are not loaded. MIMIC has no allergy resources,
and every hospital medication order is completed/stopped, so these patients have no
"current medications". Dates are MIMIC's privacy-shifted dates (years 2100+); order is kept.
Rows are stored with source / source_system "mimic_iv_fhir_demo", separate from Synthea.
"""

import argparse
import collections
import datetime as dt
import gzip
import json
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from sqlalchemy import delete, insert

from backend.config import DATA_DIR
from backend.fhir_ingestion.synthea_ingest import BundleMapper, _coding, _ref_id
from backend.patient_memory.db import get_engine
from backend.patient_memory.models import ClinicalRecord, Document, Patient

SOURCE = "mimic_iv_fhir_demo"
RAW = DATA_DIR / "datasets" / "mimic" / "raw"
MANIFEST_DIR = DATA_DIR / "datasets" / "mimic" / "manifests"
FILES = ["MimicPatient", "MimicEncounter", "MimicEncounterED", "MimicCondition", "MimicConditionED",
         "MimicMedicationRequest", "MimicMedicationStatementED", "MimicProcedure", "MimicProcedureICU",
         "MimicObservationLabevents", "MimicObservationVitalSignsED"]
NAME_SYSTEM = "mimic-medication-name"


def _ndjson(path: Path) -> Iterator[Dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


class MimicMapper(BundleMapper):
    def _rec(self, *args, **kw):
        rec = super()._rec(*args, **kw)
        rec["source_system"] = SOURCE
        return rec

    def _patient(self, r):
        p = super()._patient(r)
        p.update(source=SOURCE, given_name="MIMIC", family_name=p["family_name"] or r["id"][:8])
        return p

    def _map_MedicationStatement(self, pid, r, enc):
        system, code, display = _coding(r.get("medicationCodeableConcept"))
        rec = self._rec(pid, "medication_history/previous_medications", "MedicationStatement", r["id"], display,
                        system=system, code=code, encounter=_ref_id(r.get("context")), start=r.get("dateAsserted"),
                        status=r.get("status"), verification="patient_reported",
                        extra_text="home medication reported at an emergency visit")
        return [rec], []


def load_bundles(raw: Path, limit: Optional[int] = None) -> Dict[str, Dict[str, Any]]:
    """Group resources by patient into {patient_id: bundle}, enriching MIMIC-specific gaps."""
    meds = {}
    for m in _ndjson(raw / "MimicMedication.ndjson.gz"):
        name = next((i["value"] for i in m.get("identifier", []) if i.get("system", "").endswith(NAME_SYSTEM)), None)
        meds[m["id"]] = name or _coding(m.get("code"))[2]
    by_pid: Dict[str, list] = collections.defaultdict(list)
    encounters: Dict[str, Dict[str, Any]] = {}
    for name in FILES:
        for r in _ndjson(raw / f"{name}.ndjson.gz"):
            if r["resourceType"] == "Patient":
                by_pid[r["id"]].insert(0, r)
                continue
            if r["resourceType"] == "Encounter":
                encounters[r["id"]] = r
                cls = (r.get("class") or {}).get("display") or "hospital"
                r["type"] = [{"text": f"{cls.capitalize()} encounter", "coding": (r.get("type") or [{}])[0].get("coding", [])}]
            pid = _ref_id(r.get("subject") or r.get("patient"))
            if pid:
                by_pid[pid].append(r)
    for res in by_pid.values():
        for r in res:
            t = r["resourceType"]
            if t == "Condition":
                e = encounters.get(_ref_id(r.get("encounter")) or "")
                if not r.get("onsetDateTime") and e and e.get("period", {}).get("start"):
                    r["onsetDateTime"] = e["period"]["start"]
                # ICD-coded encounter diagnoses are recorded diagnoses; MIMIC omits verificationStatus.
                r.setdefault("verificationStatus", {"coding": [{"code": "confirmed"}]})
            elif t == "MedicationRequest" and "medicationCodeableConcept" not in r and r.get("medicationReference"):
                r["medicationCodeableConcept"] = {"text": meds.get(_ref_id(r["medicationReference"]), "Unspecified medication")}
    pids = sorted(p for p, res in by_pid.items() if res and res[0]["resourceType"] == "Patient")
    if limit:
        pids = pids[:limit]
    return {p: {"resourceType": "Bundle", "entry": [{"resource": r} for r in by_pid[p]]} for p in pids}


def ingest(raw: Path = RAW, limit: Optional[int] = None) -> Dict[str, Any]:
    engine = get_engine()
    stats, issues = collections.Counter(), collections.Counter()
    leaf_counts = collections.Counter()
    t0 = dt.datetime.now()
    bundles = load_bundles(raw, limit)
    seen = set()
    for i, (pid, bundle) in enumerate(bundles.items(), 1):
        patient, records, docs = MimicMapper(f"{SOURCE}/{pid}", stats, issues).map_bundle(bundle)
        if patient is None:
            continue
        unique = [r for r in records if not (r["record_id"] in seen or seen.add(r["record_id"]))]
        with engine.begin() as conn:
            conn.execute(delete(ClinicalRecord).where(ClinicalRecord.patient_id == pid))
            conn.execute(delete(Document).where(Document.patient_id == pid))
            conn.execute(delete(Patient).where(Patient.patient_id == pid))
            conn.execute(insert(Patient), [patient])
            for j in range(0, len(unique), 5000):
                conn.execute(insert(ClinicalRecord), unique[j:j + 5000])
        leaf_counts.update(r["leaf_path"] for r in unique)
        if i % 20 == 0:
            print(f"  {i}/{len(bundles)} patients, {sum(leaf_counts.values())} records")
    report = {"source": SOURCE, "input_dir": str(raw), "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
              "patients": len(bundles), "records_total": sum(leaf_counts.values()),
              "elapsed_seconds": round((dt.datetime.now() - t0).total_seconds(), 1),
              "records_per_leaf": dict(sorted(leaf_counts.items())),
              "mapped_counts": {k[7:]: v for k, v in sorted(stats.items()) if k.startswith("mapped:")},
              "unmapped_counts": {k[9:]: v for k, v in sorted(stats.items()) if k.startswith("unmapped:")},
              "issues": dict(sorted(issues.items()))}
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    (MANIFEST_DIR / "ingest_report_mimic_iv_fhir_demo.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("patients", "records_total", "elapsed_seconds", "records_per_leaf")}, indent=2))
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(RAW))
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    ingest(Path(a.input), a.limit)
