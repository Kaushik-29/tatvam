"""
Patient-scoped access to the longitudinal memory.

`PatientMemory` is the ONLY way retrieval code reads clinical data. It is bound to
a single patient_id at construction; every query adds `patient_id == :pid`, so
records of different patients can never be mixed.
"""

import json
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.patient_memory import classify as C
from backend.patient_memory.hierarchy import (
    BRANCHES, LEAF_BY_PATH, LEAVES, TocNode, concept_group_path, leaf_of, resolve_virtual,
)
from backend.patient_memory.models import ClinicalRecord, Document, Patient

MED_LEAVES = ("medication_history/current_medications", "medication_history/previous_medications")


def record_to_dict(r: ClinicalRecord) -> Dict[str, Any]:
    return {
        "record_id": r.record_id, "patient_id": r.patient_id, "leaf_path": r.leaf_path,
        "group_path": r.group_path, "resource_type": r.resource_type, "fhir_resource_id": r.fhir_resource_id,
        "encounter_id": r.encounter_id, "source_document": r.source_document, "source_system": r.source_system,
        "concept_system": r.concept_system, "concept_code": r.concept_code, "concept_display": r.concept_display,
        "concept_key": r.concept_key, "effective_start": r.effective_start, "effective_end": r.effective_end,
        "recorded_date": r.recorded_date, "value_num": r.value_num, "value_text": r.value_text, "unit": r.unit,
        "normalized_value": r.normalized_value, "normalized_unit": r.normalized_unit,
        "clinical_status": r.clinical_status, "verification_status": r.verification_status,
        "confidence": r.confidence, "provenance": json.loads(r.provenance) if r.provenance else {},
        "text": r.text,
    }


class PatientMemory:
    def __init__(self, session: Session, patient_id: str):
        if not patient_id:
            raise ValueError("PatientMemory requires a patient_id")
        self.s = session
        self.pid = patient_id

    # ------------------------------------------------------------------ basics
    def patient(self) -> Optional[Patient]:
        return self.s.get(Patient, self.pid)

    def _base(self):
        return select(ClinicalRecord).where(ClinicalRecord.patient_id == self.pid)

    def count(self) -> int:
        return self.s.scalar(select(func.count()).select_from(ClinicalRecord)
                             .where(ClinicalRecord.patient_id == self.pid)) or 0

    def records(self, *, leaves: Optional[Sequence[str]] = None, groups: Optional[Sequence[str]] = None,
                start: Optional[str] = None, end: Optional[str] = None, encounter_id: Optional[str] = None,
                record_ids: Optional[Sequence[str]] = None, limit: Optional[int] = None,
                newest_first: bool = True) -> List[Dict[str, Any]]:
        q = self._base()
        if leaves:
            q = q.where(ClinicalRecord.leaf_path.in_([resolve_virtual(l) for l in leaves]))
        if groups:
            q = q.where(ClinicalRecord.group_path.in_(list(groups)))
        if start:
            q = q.where(ClinicalRecord.effective_start >= start)
        if end:
            q = q.where(ClinicalRecord.effective_start <= end)
        if encounter_id:
            q = q.where(ClinicalRecord.encounter_id == encounter_id)
        if record_ids is not None:
            q = q.where(ClinicalRecord.record_id.in_(list(record_ids)))
        order = ClinicalRecord.effective_start.desc() if newest_first else ClinicalRecord.effective_start.asc()
        q = q.order_by(order)
        if limit:
            q = q.limit(limit)
        return [record_to_dict(r) for r in self.s.scalars(q)]

    def get(self, record_id: str) -> Optional[Dict[str, Any]]:
        r = self.s.get(ClinicalRecord, record_id)
        if r is None or r.patient_id != self.pid:   # isolation: never return another patient's row
            return None
        return record_to_dict(r)

    # ----------------------------------------------------------------- the ToC
    def group_stats(self) -> List[Tuple[str, str, str, int, Optional[str], Optional[str]]]:
        q = (select(ClinicalRecord.leaf_path, ClinicalRecord.group_path, func.max(ClinicalRecord.concept_display),
                    func.count(), func.min(ClinicalRecord.effective_start), func.max(ClinicalRecord.effective_start))
             .where(ClinicalRecord.patient_id == self.pid)
             .group_by(ClinicalRecord.leaf_path, ClinicalRecord.group_path))
        return list(self.s.execute(q).all())

    def toc(self, max_groups_per_leaf: Optional[int] = None) -> List[TocNode]:
        """Builds the patient's numbered ToC: branches -> leaves -> concept groups."""
        stats = self.group_stats()
        by_leaf: Dict[str, List[Tuple]] = defaultdict(list)
        for leaf, group, disp, n, d0, d1 in stats:
            by_leaf[leaf].append((group, disp, n, d0, d1))
        roots: Dict[str, TocNode] = {}
        out: List[TocNode] = []
        for leaf in LEAVES:
            branch = leaf.path.split("/")[0]
            src = resolve_virtual(leaf.path)
            groups = by_leaf.get(src, [])
            n_total = sum(g[2] for g in groups)
            d0 = min((g[3] for g in groups if g[3]), default=None)
            d1 = max((g[4] for g in groups if g[4]), default=None)
            node = TocNode(path=leaf.path, number=leaf.number, title=leaf.title, is_leaf=True, count=n_total,
                           date_range=_range(d0, d1))
            if not leaf.virtual and leaf.path != "demographics":
                groups = sorted(groups, key=lambda g: g[4] or "", reverse=True)  # most recent first
                if max_groups_per_leaf:
                    groups = groups[:max_groups_per_leaf]
                for i, (gp, disp, n, a, b) in enumerate(groups, 1):
                    node.children.append(TocNode(path=gp, number=f"{leaf.number}.{i}",
                                                 title=_group_title(leaf.path, disp, gp), is_leaf=True, count=n,
                                                 date_range=_range(a, b)))
                node.is_leaf = not node.children
            if "/" in leaf.path:
                if branch not in roots:
                    num, title = BRANCHES[branch].split(" ", 1)
                    roots[branch] = TocNode(path=branch, number=num, title=title, is_leaf=False)
                    out.append(roots[branch])
                roots[branch].children.append(node)
                roots[branch].count += n_total
            else:
                out.append(node)
        return out

    def valid_group_paths(self) -> Dict[str, str]:
        """All selectable level-3 paths (plus leaves without children) -> leaf path."""
        out = {}
        for leaf, group, *_ in self.group_stats():
            out[group] = leaf
        return out

    # ------------------------------------------------------- path resolution
    def resolve_paths(self, paths: Iterable[str], per_group_limit: int = 8,
                      start: Optional[str] = None, end: Optional[str] = None
                      ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Validates evidence paths against THIS patient's hierarchy and fetches their records.
        Returns (records, invalid_paths). Unknown paths are rejected, never guessed."""
        valid_groups = self.valid_group_paths()
        records, invalid, seen = [], [], set()
        for p in paths:
            if p in LEAF_BY_PATH:
                leaf_recs = self.records(leaves=[p], start=start, end=end)
                # newest per group first, then cap per group to keep context small
                per = defaultdict(int)
                for r in leaf_recs:
                    if per[r["group_path"]] < per_group_limit and r["record_id"] not in seen:
                        per[r["group_path"]] += 1
                        seen.add(r["record_id"])
                        records.append(r)
            elif p in valid_groups:
                for r in self.records(groups=[p], start=start, end=end, limit=per_group_limit):
                    if r["record_id"] not in seen:
                        seen.add(r["record_id"])
                        records.append(r)
            else:
                invalid.append(p)
        return records, invalid

    # -------------------------------------------------------- medication logic
    def medication_intervals(self, as_of: Optional[str] = None) -> List[Dict[str, Any]]:
        """Deterministic medication exposure intervals. Synthea MedicationRequests carry no
        supply duration, so the end of exposure is an ASSUMPTION (documented rule):
          * chronic pattern (>=3 requests for the ingredient, or any active request):
            in effect until the next request, capped at 400 days; latest active request is open-ended;
            latest completed request lasts 365 days.
          * otherwise (acute pattern): in effect for 30 days.
        Every assumed end is flagged end_uncertain=True."""
        meds = self.records(leaves=list(MED_LEAVES), newest_first=False)
        by = defaultdict(list)
        for m in meds:
            if m["effective_start"]:
                by[m["concept_key"]].append(m)
        out = []
        for key, reqs in by.items():
            chronic = len(reqs) >= 3 or any(r["leaf_path"] == MED_LEAVES[0] for r in reqs)
            for i, r in enumerate(reqs):
                start = datetime.fromisoformat(r["effective_start"][:19])
                if r.get("effective_end"):                     # a recorded end date is used as-is, never estimated
                    end, unc = r["effective_end"], False
                elif r["leaf_path"] == MED_LEAVES[0]:
                    end, unc = as_of, False
                elif chronic and i + 1 < len(reqs):
                    nxt = reqs[i + 1]["effective_start"]
                    cap = (start + timedelta(days=400)).isoformat()
                    end, unc = (nxt, False) if nxt <= cap else (cap, True)
                else:
                    end, unc = (start + timedelta(days=365 if chronic else 30)).isoformat(), True
                out.append({**r, "interval_start": r["effective_start"], "interval_end": end,
                            "end_uncertain": unc, "exposure_pattern": "chronic" if chronic else "acute"})
        return out

    def medications_active_at(self, when: str) -> List[Dict[str, Any]]:
        res = []
        for iv in self.medication_intervals():
            if iv["interval_start"] <= when and (iv["interval_end"] is None or when < iv["interval_end"]):
                res.append(iv)
        return res

    # --------------------------------------------------------- writes (user)
    def add_patient_entry(self, leaf_path: str, display: str, *, start: Optional[str] = None,
                          end: Optional[str] = None, value_num: Optional[float] = None,
                          value_text: Optional[str] = None, unit: Optional[str] = None,
                          status: Optional[str] = None, source_system: str = "patient_entered",
                          verification: str = "patient_reported", confidence: float = 1.0,
                          provenance: Optional[Dict[str, Any]] = None, source_document: Optional[str] = None,
                          concept_key: Optional[str] = None) -> Dict[str, Any]:
        if leaf_path not in LEAF_BY_PATH or LEAF_BY_PATH[leaf_path].virtual:
            raise ValueError(f"Invalid leaf path: {leaf_path}")
        if leaf_path in MED_LEAVES:
            concept_key = concept_key or C.medication_ingredient(display)
        key = concept_key or C.strip_semantic_tag(display).lower()
        nv, nu = C.normalize_quantity(value_num, unit)
        rtype = {"patient_entered": "UserEntry", "ocr_extracted": "OCRExtraction"}.get(source_system, "UserEntry")
        val = (f"{value_num:g} {unit}".strip() if value_num is not None else value_text)
        rec = ClinicalRecord(
            record_id=f"{rtype}/{uuid.uuid4().hex[:16]}", patient_id=self.pid, leaf_path=leaf_path,
            group_path=concept_group_path(leaf_path, key), resource_type=rtype, source_system=source_system,
            source_document=source_document, concept_display=display, concept_key=key,
            effective_start=start, effective_end=end, recorded_date=datetime.utcnow().isoformat(timespec="seconds"),
            value_num=value_num, value_text=value_text, unit=unit, normalized_value=nv, normalized_unit=nu,
            clinical_status=status, verification_status=verification, confidence=confidence,
            provenance=json.dumps(provenance or {"entered_via": "MedResolve UI"}),
            text=C.render_text(LEAF_BY_PATH[leaf_path].title, display, start=start, end=end, value=val,
                               status=status, verification=verification),
        )
        self.s.add(rec)
        self.s.flush()
        return record_to_dict(rec)

    def update_record(self, record_id: str, **fields) -> Optional[Dict[str, Any]]:
        r = self.s.get(ClinicalRecord, record_id)
        if r is None or r.patient_id != self.pid:
            return None
        allowed = {"concept_display", "effective_start", "effective_end", "value_num", "value_text", "unit",
                   "clinical_status", "verification_status"}
        for k, v in fields.items():
            if k in allowed and v is not None:
                setattr(r, k, v)
        r.normalized_value, r.normalized_unit = C.normalize_quantity(r.value_num, r.unit)
        val = f"{r.value_num:g} {r.unit or ''}".strip() if r.value_num is not None else r.value_text
        r.text = C.render_text(LEAF_BY_PATH[r.leaf_path].title, r.concept_display, start=r.effective_start,
                               end=r.effective_end, value=val, status=r.clinical_status,
                               verification=r.verification_status)
        self.s.flush()
        return record_to_dict(r)

    def delete_record(self, record_id: str) -> bool:
        r = self.s.get(ClinicalRecord, record_id)
        if r is None or r.patient_id != self.pid:
            return False
        self.s.delete(r)
        return True

    def documents(self, leaf: Optional[str] = None) -> List[Document]:
        q = select(Document).where(Document.patient_id == self.pid)
        if leaf:
            q = q.where(Document.leaf_path == leaf)
        return list(self.s.scalars(q.order_by(Document.doc_date.desc())))


def _range(a: Optional[str], b: Optional[str]) -> Optional[str]:
    if not a:
        return None
    a, b = a[:10], (b or a)[:10]
    return a if a == b else f"{a} to {b}"


def _group_title(leaf: str, display: str, group_path: str) -> str:
    title = C.strip_semantic_tag(display or group_path.rsplit("/", 1)[-1])
    if leaf in MED_LEAVES or leaf.endswith("medication_changes"):
        return group_path.rsplit("/", 1)[-1].replace("_", " ")
    if leaf.endswith("historical_trends"):
        return f"Trend: {title}"
    return title
