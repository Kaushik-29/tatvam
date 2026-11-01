"""
STAIR-Clinical training / evaluation data generator (Stage 2 of the training pipeline).

Builds natural-language questions over REAL Synthea patient records with gold
evidence that is computed programmatically from the database — an LLM never
chooses or edits a gold target. Every example stores:

  patient_id, query, query_category, template_id, expected_leaf_paths,
  expected_group_paths (evidence paths), gold_evidence_ids, temporal_constraint,
  source_resource_ids, split (assigned by PATIENT, never per query).

Usage:
    python -m backend.stair_retriever.training_data [--max-patients N] [--seed 13]
Outputs data/patient_retrieval/{train,validation,test}/queries.jsonl + manifest.
"""

import argparse
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from backend.config import DATA_DIR
from backend.patient_memory.db import session_scope
from backend.patient_memory.models import Patient
from backend.patient_memory.repository import PatientMemory
from backend.rag.query_understanding import (
    SYMPTOM_RELATED_CONDITIONS, SYSTEM_LABS, lay_name,
)

OUT_DIR = DATA_DIR / "patient_retrieval"
SPLIT_RATIOS = (0.70, 0.15, 0.15)
SYMPTOM_LEAVES = ("clinical_encounters/previous_symptoms", "clinical_encounters/complaints")
HISTORY_LEAVES = ("medical_history/diagnoses", "medical_history/conditions")
MED_LEAVES = ("medication_history/current_medications", "medication_history/previous_medications")
GOLD_PER_GROUP = 3     # most recent records per gold concept group that count as gold evidence


def patient_split(patient_id: str) -> str:
    """Deterministic split by patient ID (sha256 bucket) — prevents patient leakage."""
    u = int(hashlib.sha256(patient_id.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    if u < SPLIT_RATIOS[0]:
        return "train"
    if u < SPLIT_RATIOS[0] + SPLIT_RATIOS[1]:
        return "validation"
    return "test"


def _year(d: str) -> str:
    return d[:4]


def _month_year(d: str) -> str:
    import calendar
    return f"{calendar.month_name[int(d[5:7])]} {d[:4]}"


def _gold_from_records(recs: List[Dict[str, Any]], per_group: int = GOLD_PER_GROUP):
    by_group = defaultdict(list)
    for r in recs:
        by_group[r["group_path"]].append(r)
    gold = []
    for g, rs in by_group.items():
        rs.sort(key=lambda r: r.get("effective_start") or "", reverse=True)
        gold.extend(rs[:per_group])
    leaves = sorted({r["leaf_path"] for r in gold})
    groups = sorted(by_group)
    return leaves, groups, gold


class Generator:
    def __init__(self, mem: PatientMemory, rng: random.Random):
        self.mem = mem
        self.rng = rng
        self.examples: List[Dict[str, Any]] = []

    def emit(self, category: str, instance: str, templates: List[str], fills: Dict[str, str],
             gold_records: List[Dict[str, Any]], *, leaves: Optional[List[str]] = None,
             groups: Optional[List[str]] = None, temporal: Optional[Dict[str, Any]] = None, n_variants: int = 2):
        if not gold_records:
            return
        g_leaves, g_groups, gold = _gold_from_records(gold_records)
        leaves = sorted(set(leaves or g_leaves))
        groups = sorted(set(groups or g_groups))
        chosen = self.rng.sample(templates, k=min(n_variants, len(templates)))
        for t in chosen:
            q = t.format(**fills)
            q = q[0].upper() + q[1:]
            tid = f"{category}#{templates.index(t)}"
            self.examples.append({
                "example_id": hashlib.sha1(f"{self.mem.pid}|{instance}|{tid}".encode()).hexdigest()[:16],
                "patient_id": self.mem.pid, "instance_id": f"{self.mem.pid}|{instance}",
                "query": q, "query_category": category, "template_id": tid,
                "expected_leaf_paths": leaves, "expected_group_paths": groups,
                "gold_evidence_ids": [r["record_id"] for r in gold],
                "temporal_constraint": temporal,
                "source_resource_ids": sorted({r["fhir_resource_id"] for r in gold if r.get("fhir_resource_id")}),
            })

    # ---------------------------------------------------------------- categories
    def medication_during_episode(self):
        syms = [r for r in self.mem.records(leaves=list(SYMPTOM_LEAVES)) if r["effective_start"]]
        self.rng.shuffle(syms)
        for s in syms[:3]:
            d = s["effective_start"]
            meds = self.mem.medications_active_at(d)
            if not meds:
                continue
            name = lay_name(s["concept_display"])
            self.emit("medication_during_episode", f"meds@{s['record_id']}", [
                "What medications was the patient taking during their previous {sym} episode in {my}?",
                "Which medicines was I on when I had {sym} back in {my}?",
                "When I had {sym} in {my}, what drugs was I taking at the time?",
                "List the medications that were active when the patient reported {sym} in {my}.",
            ], {"sym": name, "my": _month_year(d)}, meds + [s],
                temporal={"type": "during_episode", "anchor_date": d[:10], "anchor_record": s["record_id"]})
            return

    def relevant_history(self):
        hist = self.mem.records(leaves=list(HISTORY_LEAVES))
        pairs = []
        for sym, rel in SYMPTOM_RELATED_CONDITIONS.items():
            hits = [h for h in hist if any(k in h["concept_display"].lower() for k in rel)]
            if hits:
                pairs.append((sym, hits))
        self.rng.shuffle(pairs)
        for sym, hits in pairs[:2]:
            self.emit("relevant_history", f"hist@{sym}", [
                "I've recently started having {sym}. Is there anything in my past medical history that could be relevant?",
                "Does the patient's previous medical history contain a condition relevant to the new complaint of {sym}?",
                "New problem: {sym}. Which of my previous conditions or diagnoses might be related?",
                "The patient now reports {sym}. Retrieve related prior diagnoses.",
            ], {"sym": sym}, hits)

    def lab_lookup(self):
        labs = self.mem.records(leaves=["laboratory_observations/laboratory_results"])
        systems = []
        for system, keys in SYSTEM_LABS.items():
            hits = [l for l in labs if any(k in l["concept_display"].lower() for k in keys)]
            if hits:
                systems.append((system, hits))
        self.rng.shuffle(systems)
        for system, hits in systems[:2]:
            self.emit("lab_lookup", f"labs@{system}", [
                "Find previous {sys}-related laboratory results.",
                "Show me my past {sys} blood tests.",
                "Have my {sys} labs been checked before, and what were the results?",
                "Retrieve the patient's historical {sys} lab values.",
            ], {"sys": system}, hits)

    def similar_symptoms(self):
        syms = self.mem.records(leaves=list(SYMPTOM_LEAVES))
        by = defaultdict(list)
        for s in syms:
            by[lay_name(s["concept_display"])].append(s)
        keys = list(by)
        self.rng.shuffle(keys)
        for k in keys[:2]:
            self.emit("similar_symptoms", f"sym@{k}", [
                "Has the patient experienced {sym} before?",
                "I have {sym} again. Have I had this in the past?",
                "When did I previously report {sym}?",
                "Is there any earlier record of {sym} in my history?",
            ], {"sym": k}, by[k])

    def current_medications(self):
        cur = self.mem.records(leaves=["medication_history/current_medications"])
        self.emit("current_medications", "current_meds", [
            "What medications am I currently taking?",
            "List the patient's active medications.",
            "Which prescriptions are still active for me right now?",
        ], {}, cur)

    def allergy_check(self):
        al = self.mem.records(leaves=["allergy_history"])
        drug = self.rng.choice(["penicillin", "an antibiotic", "ibuprofen", "a new painkiller", "aspirin"])
        self.emit("allergy_check", "allergies", [
            "Do I have any allergies I should mention before taking {drug}?",
            "What allergies does the patient have on record?",
            "Am I allergic to anything that matters if my doctor prescribes {drug}?",
        ], {"drug": drug}, al)

    def lab_trend(self):
        trends = self.mem.records(leaves=["laboratory_observations/historical_trends"])
        self.rng.shuffle(trends)
        for t in trends[:2]:
            raw = self.mem.records(groups=[t["group_path"].replace("historical_trends", "laboratory_results"),
                                           t["group_path"].replace("historical_trends", "vital_signs")], limit=3)
            name = lay_name(t["concept_display"])
            self.emit("lab_trend", f"trend@{t['record_id']}", [
                "How has my {c} changed over time?",
                "Is the patient's {c} getting better or worse over the years?",
                "Show the trend of my {c} measurements.",
            ], {"c": name}, [t] + raw, temporal={"type": "trend"})

    def latest_measurement(self):
        vit = self.mem.records(leaves=["laboratory_observations/vital_signs"], limit=400)
        by = {}
        for v in vit:                       # newest first
            by.setdefault(v["group_path"], v)
        keys = [k for k in by if any(w in k for w in ("blood_pressure", "body_weight", "heart_rate", "body_mass_index"))]
        self.rng.shuffle(keys)
        for k in keys[:2]:
            v = by[k]
            name = lay_name(v["concept_display"])
            gold = [v]
            if "blood_pressure" in k:       # both BP components of the same reading
                gold = [r for r in vit if r["fhir_resource_id"] == v["fhir_resource_id"]]
                name = "blood pressure"
            self.emit("latest_measurement", f"latest@{k}", [
                "What was my most recent {c} reading?",
                "What was the patient's {c} at the last visit?",
                "Tell me my latest {c} measurement.",
            ], {"c": name}, gold, temporal={"type": "most_recent", "anchor_date": v["effective_start"][:10]})

    def medication_changes(self):
        ch = [c for c in self.mem.records(leaves=["medication_history/medication_changes"])
              if c["clinical_status"] in ("dose_changed", "stopped")]
        self.rng.shuffle(ch)
        for c in ch[:1]:
            drug = c["concept_key"]
            related = [x for x in self.mem.records(groups=[c["group_path"]])]
            self.emit("medication_changes", f"medchg@{drug}", [
                "Was my {d} dose ever changed or stopped?",
                "Has the patient's {d} prescription changed over time?",
                "Did I stop taking {d}, and when?",
            ], {"d": drug}, related)

    def condition_status(self):
        dx = self.mem.records(leaves=["medical_history/diagnoses"])
        by = defaultdict(list)
        for d in dx:
            by[d["group_path"]].append(d)
        keys = list(by)
        self.rng.shuffle(keys)
        for k in keys[:1]:
            name = lay_name(by[k][0]["concept_display"])
            self.emit("condition_status", f"status@{k}", [
                "Do I still have {c}, or was it resolved?",
                "Is the patient's {c} currently active?",
                "What is the status of my {c} diagnosis?",
            ], {"c": name}, by[k])

    def last_visit(self):
        enc = self.mem.records(leaves=["clinical_encounters/consultations"], limit=1)
        if enc:
            self.emit("last_visit", "last_visit", [
                "When did I last see a doctor?",
                "When was the patient's most recent clinical encounter?",
                "What was my last appointment and when was it?",
            ], {}, enc, leaves=["clinical_encounters/encounter_dates", "clinical_encounters/consultations"],
                temporal={"type": "most_recent", "anchor_date": (enc[0]["effective_start"] or "")[:10]})

    def procedure_history(self):
        pr = [p for p in self.mem.records(leaves=["medical_history/procedures"])
              if not re.search(r"medication reconciliation|assessment|screening for|evaluation|review", p["concept_display"], re.I)]
        by = defaultdict(list)
        for p in pr:
            by[p["group_path"]].append(p)
        keys = list(by)
        self.rng.shuffle(keys)
        for k in keys[:1]:
            name = lay_name(by[k][0]["concept_display"])
            self.emit("procedure_history", f"proc@{k}", [
                "Have I ever had {p} done?",
                "When did the patient undergo {p}?",
                "Is there a record of {p} in my history?",
            ], {"p": name}, by[k])

    def immunization_history(self):
        im = self.mem.records(leaves=["medical_history/immunizations"])
        by = defaultdict(list)
        for i in im:
            by[i["group_path"]].append(i)
        keys = list(by)
        self.rng.shuffle(keys)
        for k in keys[:1]:
            name = by[k][0]["concept_display"]
            self.emit("immunization_history", f"imm@{k}", [
                "When did I last get the {v} vaccine?",
                "Has the patient received the {v} immunization?",
            ], {"v": name}, by[k])

    def diagnoses_in_year(self):
        dx = [d for d in self.mem.records(leaves=["medical_history/diagnoses"]) if d["effective_start"]]
        years = sorted({_year(d["effective_start"]) for d in dx})
        if not years:
            return
        y = self.rng.choice(years)
        hits = [d for d in dx if _year(d["effective_start"]) == y]
        self.emit("diagnoses_in_year", f"dxyear@{y}", [
            "What diagnoses were recorded for me in {y}?",
            "Which conditions was the patient diagnosed with during {y}?",
        ], {"y": y}, hits, temporal={"type": "range", "start": f"{y}-01-01", "end": f"{int(y) + 1}-01-01"})

    def run(self):
        for fn in (self.medication_during_episode, self.relevant_history, self.lab_lookup, self.similar_symptoms,
                   self.current_medications, self.allergy_check, self.lab_trend, self.latest_measurement,
                   self.medication_changes, self.condition_status, self.last_visit, self.procedure_history,
                   self.immunization_history, self.diagnoses_in_year):
            fn()
        return self.examples


def generate(max_patients: Optional[int] = None, seed: int = 13) -> Dict[str, Any]:
    rows = {"train": [], "validation": [], "test": []}
    with session_scope() as s:
        pids = list(s.scalars(select(Patient.patient_id).where(Patient.source == "synthea_fhir_r4")
                              .order_by(Patient.patient_id)))
        if max_patients:
            pids = pids[:max_patients]
        for i, pid in enumerate(pids):
            split = patient_split(pid)
            p = s.get(Patient, pid)
            p.split = split
            rng = random.Random(f"{seed}|{pid}")
            exs = Generator(PatientMemory(s, pid), rng).run()
            for e in exs:
                e["split"] = split
            rows[split].extend(exs)
            if (i + 1) % 100 == 0:
                print(f"  {i + 1}/{len(pids)} patients")
    manifest = {"seed": seed, "split_ratios": SPLIT_RATIOS, "split_unit": "patient_id (sha256 bucket)",
                "gold_per_group": GOLD_PER_GROUP, "splits": {}}
    patients_by_split = {}
    for split, exs in rows.items():
        d = OUT_DIR / split
        d.mkdir(parents=True, exist_ok=True)
        path = d / "queries.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for e in exs:
                f.write(json.dumps(e) + "\n")
        patients_by_split[split] = {e["patient_id"] for e in exs}
        manifest["splits"][split] = {
            "examples": len(exs), "patients": len(patients_by_split[split]),
            "categories": dict(Counter(e["query_category"] for e in exs)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    overlap = (patients_by_split["train"] & patients_by_split["test"]) | \
              (patients_by_split["train"] & patients_by_split["validation"]) | \
              (patients_by_split["validation"] & patients_by_split["test"])
    manifest["patient_overlap_between_splits"] = len(overlap)
    assert not overlap, "patient leakage between splits"
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return manifest


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-patients", type=int, default=None)
    ap.add_argument("--seed", type=int, default=13)
    a = ap.parse_args()
    generate(a.max_patients, a.seed)
