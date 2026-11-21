"""
eICU Collaborative Research Database Demo (v2.0.1, PhysioNet, OPEN ACCESS) -> patient memory.

    python -m backend.fhir_ingestion.eicu_demo [--input data/datasets/eicu/raw/<folder>] [--limit N]

Cite: Johnson A, Pollard T, Badawi O, Raffa J. eICU Collaborative Research Database Demo (v2.0.1).
PhysioNet, 2021. https://doi.org/10.13026/4mxk-na84  (data: Pollard TJ et al., Sci Data 5:180178, 2018)

eICU ships CSV tables, not FHIR. Each table row is turned into a minimal FHIR-shaped resource and
passed through the same BundleMapper as Synthea/MIMIC, so ToC, derived records and retrieval are shared.

One memory "patient" = one HOSPITAL STAY (patienthealthsystemstayid), which may contain several
ICU stays. eICU gives no calendar dates: every time is a minute offset from ICU admission and only
the discharge year is known, and it gives no order between different hospital stays of the same
person. So times are reconstructed as  <discharge year>-01-01 + offsets : intervals and order WITHIN
a hospital stay are exact, absolute dates are not real. Linking several hospital stays of one
person would need an order eICU does not provide, so they are kept as separate memories.

Mapped: diagnosis + pastHistory (conditions), admissionDx reason, medication (ICU orders),
admissiondrug (home medications, patient-reported), allergy, lab, microLab, treatment (procedures),
vitalAperiodic (non-invasive BP) and vitalPeriodic down-sampled to one reading per 4 h.
Not loaded: nurse charting, care plans, notes/physical exam, infusions, APACHE, intake/output.
"""

import argparse
import collections
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy import delete, insert

from backend.config import DATA_DIR
from backend.fhir_ingestion.synthea_ingest import BundleMapper, _coding, _ref_id
from backend.patient_memory.db import get_engine
from backend.patient_memory.models import ClinicalRecord, Document, Patient

SOURCE = "eicu_crd_demo"
RAW = DATA_DIR / "datasets" / "eicu" / "raw" / "eicu-collaborative-research-database-demo-2.0.1"
MANIFEST_DIR = DATA_DIR / "datasets" / "eicu" / "manifests"
VITAL_EVERY_MIN = 240
PERIODIC = {"heartrate": ("Heart rate", "/min"), "respiration": ("Respiratory rate", "/min"),
            "sao2": ("Oxygen saturation", "%"), "temperature": ("Body temperature", "Cel")}
PAST_SKIP = ("No Health Problems", "Not Obtainable", "Not Performed", "Performed")


def _csv(raw: Path, name: str, **kw) -> pd.DataFrame:
    return pd.read_csv(raw / f"{name}.csv.gz", low_memory=False, **kw)


def _leaf_name(path: str) -> str:
    parts = [p.strip() for p in str(path).split("|") if p.strip()]
    return parts[-1] if parts else str(path)


class EicuMapper(BundleMapper):
    def _rec(self, *args, **kw):
        rec = super()._rec(*args, **kw)
        rec["source_system"] = SOURCE
        return rec

    def _patient(self, r):
        p = super()._patient(r)
        p.update(source=SOURCE, given_name="eICU", family_name=r["_label"])
        return p

    def _map_MedicationStatement(self, pid, r, enc):
        system, code, display = _coding(r.get("medicationCodeableConcept"))
        rec = self._rec(pid, "medication_history/previous_medications", "MedicationStatement", r["id"], display,
                        system=system, code=code, encounter=_ref_id(r.get("context")), start=r.get("dateAsserted"),
                        status=r.get("status"), verification="patient_reported",
                        extra_text="home medication recorded at ICU admission")
        return [rec], []


class Builder:
    """Builds one FHIR-shaped bundle per hospital stay from the eICU tables."""

    def __init__(self, raw: Path):
        self.p = _csv(raw, "patient")
        self.t = {n: _csv(raw, n) for n in ("diagnosis", "pastHistory", "admissionDx", "medication",
                                            "admissiondrug", "allergy", "lab", "microLab", "treatment",
                                            "vitalAperiodic")}
        vp = _csv(raw, "vitalPeriodic", usecols=["vitalperiodicid", "patientunitstayid", "observationoffset",
                                                 *PERIODIC])
        vp["bucket"] = vp.observationoffset // VITAL_EVERY_MIN
        vp = vp.sort_values("observationoffset")
        self.t["vitalPeriodic"] = vp.groupby(["patientunitstayid", "bucket"], as_index=False).first()
        va = self.t["vitalAperiodic"]
        va["bucket"] = va.observationoffset // VITAL_EVERY_MIN
        self.t["vitalAperiodic"] = (va.dropna(subset=["noninvasivesystolic"]).sort_values("observationoffset")
                                    .groupby(["patientunitstayid", "bucket"], as_index=False).first())
        self.by_stay = {n: dict(tuple(df.groupby("patientunitstayid"))) for n, df in self.t.items()}

    def stays(self):
        return self.p.groupby("patienthealthsystemstayid")

    def bundle(self, hsid: int, units: pd.DataFrame) -> Dict[str, Any]:
        units = units.sort_values(["hospitaladmitoffset", "unitvisitnumber"], ascending=[False, True])
        u0 = units.iloc[0]
        pid = f"eicu-{hsid}"
        year = int(u0.hospitaldischargeyear)
        t0 = dt.datetime(year, 1, 1)
        age = str(u0.age)
        age_n = 90 if age.startswith(">") else (int(age) if age.isdigit() else None)
        res: List[Dict[str, Any]] = [{
            "resourceType": "Patient", "id": pid, "_label": f"Stay_{hsid}",
            "gender": {"Male": "male", "Female": "female"}.get(u0.gender, "unknown"),
            "birthDate": f"{year - age_n}-01-01" if age_n is not None else None,
            "extension": [{"url": "us-core-ethnicity", "extension": [{"url": "text", "valueString": u0.ethnicity}]}]
            if isinstance(u0.ethnicity, str) else []}]
        subj = {"reference": f"Patient/{pid}"}

        def iso(base: dt.datetime, minutes) -> Optional[str]:
            return None if pd.isna(minutes) else (base + dt.timedelta(minutes=float(minutes))).isoformat()

        for _, u in units.iterrows():
            sid = int(u.patientunitstayid)
            base = t0 - dt.timedelta(minutes=float(u.hospitaladmitoffset))   # this ICU stay's admission time
            enc = {"reference": f"Encounter/icu-{sid}"}
            reason = u.apacheadmissiondx if isinstance(u.apacheadmissiondx, str) else None
            res.append({"resourceType": "Encounter", "id": f"icu-{sid}", "subject": subj, "status": "finished",
                        "class": {"code": "IMP", "display": "inpatient"},
                        "type": [{"text": f"{u.unittype} ICU stay" if "ICU" not in str(u.unittype) else f"{u.unittype} stay"}],
                        "period": {"start": iso(base, 0), "end": iso(base, u.unitdischargeoffset)},
                        "reasonCode": [{"text": reason}] if reason else [],
                        "location": [{"location": {"display": f"admitted from {u.unitadmitsource}"}}]
                        if isinstance(u.unitadmitsource, str) else []})
            g = lambda n: self.by_stay[n].get(sid, pd.DataFrame())
            for _, r in g("diagnosis").iterrows():
                code = str(r.icd9code).split(",")[0].strip() if isinstance(r.icd9code, str) else None
                res.append({"resourceType": "Condition", "id": f"dx-{r.diagnosisid}", "subject": subj, "encounter": enc,
                            "code": {"text": _leaf_name(r.diagnosisstring),
                                     "coding": [{"system": "icd9cm", "code": code}] if code else []},
                            "clinicalStatus": {"coding": [{"code": "active" if r.activeupondischarge else "resolved"}]},
                            "verificationStatus": {"coding": [{"code": "confirmed"}]},
                            "onsetDateTime": iso(base, r.diagnosisoffset)})
            for _, r in g("pastHistory").iterrows():
                if "/Past History/Organ Systems/" not in str(r.pasthistorypath) or str(r.pasthistoryvalue) in PAST_SKIP:
                    continue
                res.append({"resourceType": "Condition", "id": f"ph-{r.pasthistoryid}", "subject": subj, "encounter": enc,
                            "code": {"text": f"{r.pasthistoryvalue} (past history)"},
                            "clinicalStatus": {"coding": [{"code": "active"}]},
                            "verificationStatus": {"coding": [{"code": "confirmed"}]},
                            # onset is unknown; dated by when the history was documented
                            "onsetDateTime": iso(base, r.pasthistoryoffset),
                            "recordedDate": iso(base, r.pasthistoryoffset)})
            for _, r in g("medication").iterrows():
                if r.drugordercancelled == "Yes" or not isinstance(r.drugname, str):
                    continue
                res.append({"resourceType": "MedicationRequest", "id": f"med-{r.medicationid}", "subject": subj,
                            "encounter": enc, "status": "completed",
                            "medicationCodeableConcept": {"text": r.drugname.strip()},
                            "authoredOn": iso(base, r.drugstartoffset)})
            for _, r in g("admissiondrug").iterrows():
                if not isinstance(r.drugname, str):
                    continue
                res.append({"resourceType": "MedicationStatement", "id": f"hm-{r.admissiondrugid}", "subject": subj,
                            "context": enc, "status": "active",
                            "medicationCodeableConcept": {"text": r.drugname.strip()},
                            "dateAsserted": iso(base, r.drugoffset)})
            for _, r in g("allergy").iterrows():
                name = r.allergyname if isinstance(r.allergyname, str) else r.drugname
                if not isinstance(name, str):
                    continue
                res.append({"resourceType": "AllergyIntolerance", "id": f"al-{r.allergyid}", "patient": subj,
                            "code": {"text": name.strip()},
                            "category": ["medication" if r.allergytype == "Drug" else "environment"],
                            "verificationStatus": {"coding": [{"code": "confirmed"}]},
                            "recordedDate": iso(base, r.allergyoffset)})
            for _, r in g("lab").iterrows():
                if pd.isna(r.labresult):
                    continue
                res.append({"resourceType": "Observation", "id": f"lab-{r.labid}", "subject": subj, "encounter": enc,
                            "category": [{"coding": [{"code": "laboratory"}]}], "status": "final",
                            "code": {"text": str(r.labname).strip()},
                            "valueQuantity": {"value": float(r.labresult),
                                              "unit": r.labmeasurenamesystem if isinstance(r.labmeasurenamesystem, str) else None},
                            "effectiveDateTime": iso(base, r.labresultoffset)})
            for _, r in g("microLab").iterrows():
                res.append({"resourceType": "Observation", "id": f"micro-{r.microlabid}", "subject": subj,
                            "encounter": enc, "category": [{"coding": [{"code": "laboratory"}]}], "status": "final",
                            "code": {"text": f"Culture, {r.culturesite}"},
                            "valueString": str(r.organism) + (f"; {r.antibiotic} {r.sensitivitylevel}"
                                                              if isinstance(r.antibiotic, str) else ""),
                            "effectiveDateTime": iso(base, r.culturetakenoffset)})
            for _, r in g("treatment").iterrows():
                res.append({"resourceType": "Procedure", "id": f"tx-{r.treatmentid}", "subject": subj, "encounter": enc,
                            "status": "completed", "code": {"text": _leaf_name(r.treatmentstring)},
                            "performedDateTime": iso(base, r.treatmentoffset)})
            for _, r in g("vitalAperiodic").iterrows():
                res.append({"resourceType": "Observation", "id": f"bp-{r.vitalaperiodicid}", "subject": subj,
                            "encounter": enc, "category": [{"coding": [{"code": "vital-signs"}]}], "status": "final",
                            "code": {"text": "Blood pressure (non-invasive)"},
                            "component": [{"code": {"text": "Systolic blood pressure"},
                                           "valueQuantity": {"value": float(r.noninvasivesystolic), "unit": "mm[Hg]"}}] +
                                         ([{"code": {"text": "Diastolic blood pressure"},
                                            "valueQuantity": {"value": float(r.noninvasivediastolic), "unit": "mm[Hg]"}}]
                                          if not pd.isna(r.noninvasivediastolic) else []),
                            "effectiveDateTime": iso(base, r.observationoffset)})
            for _, r in g("vitalPeriodic").iterrows():
                for col, (name, unit) in PERIODIC.items():
                    if pd.isna(r[col]):
                        continue
                    res.append({"resourceType": "Observation", "id": f"vp-{r.vitalperiodicid}-{col}", "subject": subj,
                                "encounter": enc, "category": [{"coding": [{"code": "vital-signs"}]}], "status": "final",
                                "code": {"text": name}, "valueQuantity": {"value": float(r[col]), "unit": unit},
                                "effectiveDateTime": iso(base, r.observationoffset)})
        return {"resourceType": "Bundle", "entry": [{"resource": r} for r in res]}


def ingest(raw: Path = RAW, limit: Optional[int] = None) -> Dict[str, Any]:
    engine = get_engine()
    stats, issues, leaf_counts = collections.Counter(), collections.Counter(), collections.Counter()
    t0 = dt.datetime.now()
    b = Builder(raw)
    groups = list(b.stays())[:limit] if limit else list(b.stays())
    print(f"{len(groups)} hospital stays (tables loaded in {(dt.datetime.now() - t0).seconds}s)")
    for i, (hsid, units) in enumerate(groups, 1):
        bundle = b.bundle(int(hsid), units)
        patient, records, _ = EicuMapper(f"{SOURCE}/{hsid}", stats, issues).map_bundle(bundle)
        seen = set()
        unique = [r for r in records if not (r["record_id"] in seen or seen.add(r["record_id"]))]
        pid = patient["patient_id"]
        with engine.begin() as conn:
            conn.execute(delete(ClinicalRecord).where(ClinicalRecord.patient_id == pid))
            conn.execute(delete(Document).where(Document.patient_id == pid))
            conn.execute(delete(Patient).where(Patient.patient_id == pid))
            conn.execute(insert(Patient), [patient])
            for j in range(0, len(unique), 5000):
                conn.execute(insert(ClinicalRecord), unique[j:j + 5000])
        leaf_counts.update(r["leaf_path"] for r in unique)
        if i % 200 == 0:
            print(f"  {i}/{len(groups)} stays, {sum(leaf_counts.values())} records", flush=True)
    report = {"source": SOURCE, "input_dir": str(raw), "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
              "unit_of_patient": "hospital stay (patienthealthsystemstayid)",
              "dates": "reconstructed: <discharge year>-01-01 + eICU minute offsets; exact within a stay, not real dates",
              "patients": len(groups), "icu_stays": int(sum(len(u) for _, u in groups)),
              "records_total": sum(leaf_counts.values()),
              "elapsed_seconds": round((dt.datetime.now() - t0).total_seconds(), 1),
              "records_per_leaf": dict(sorted(leaf_counts.items())),
              "mapped_counts": {k[7:]: v for k, v in sorted(stats.items()) if k.startswith("mapped:")},
              "issues": {k: v for k, v in sorted(issues.items()) if not k.startswith("multiple_unit_strings")},
              "concepts_with_multiple_unit_strings": sum(1 for k in issues if k.startswith("multiple_unit_strings"))}
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    (MANIFEST_DIR / "ingest_report_eicu_crd_demo.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("patients", "icu_stays", "records_total", "elapsed_seconds",
                                             "records_per_leaf")}, indent=2))
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(RAW))
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    ingest(Path(a.input), a.limit)
