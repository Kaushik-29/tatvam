"""
Deterministically derived longitudinal records.

* Medication changes: start / dose change / no-longer-active events per ingredient.
* Historical trends: first / latest / min / max / direction per numeric lab or vital.

Derived rows carry `source_system="derived"`, `verification_status="derived"` and
cite every source record ID in their provenance, so they can be audited and never
masquerade as primary clinical facts.
"""

import json
from collections import defaultdict
from typing import Any, Dict, List

from backend.patient_memory import classify as C
from backend.patient_memory.hierarchy import LEAF_BY_PATH, concept_group_path, slugify

MED_LEAVES = ("medication_history/current_medications", "medication_history/previous_medications")
TREND_SOURCE_LEAVES = ("laboratory_observations/laboratory_results", "laboratory_observations/vital_signs")
CHANGE_LEAF = "medication_history/medication_changes"
TREND_LEAF = "laboratory_observations/historical_trends"


def _derived(pid: str, leaf: str, rid: str, key: str, display: str, start, text_extra: str, sources: List[str],
             rule: str, source_doc: str, **kw) -> Dict[str, Any]:
    return dict(
        record_id=rid, patient_id=pid, leaf_path=leaf, group_path=concept_group_path(leaf, key),
        resource_type="Derived", fhir_resource_id=None, encounter_id=kw.get("encounter_id"),
        source_document=source_doc, source_system="derived", concept_system=None, concept_code=kw.get("code"),
        concept_display=display, concept_key=key, effective_start=start, effective_end=kw.get("end"),
        recorded_date=start, value_num=kw.get("value_num"), value_text=kw.get("value_text"), unit=kw.get("unit"),
        normalized_value=kw.get("normalized_value"), normalized_unit=kw.get("normalized_unit"),
        clinical_status=kw.get("status"), verification_status="derived", confidence=1.0,
        provenance=json.dumps({"derived_from": sources[:60], "n_sources": len(sources), "rule": rule}),
        text=f"{LEAF_BY_PATH[leaf].title}: {display} — {text_extra}",
    )


def derive_medication_changes(pid: str, records: List[Dict[str, Any]], source_doc: str) -> List[Dict[str, Any]]:
    by_drug = defaultdict(list)
    for r in records:
        if r["leaf_path"] in MED_LEAVES and r.get("effective_start"):
            by_drug[r["concept_key"]].append(r)
    out = []
    for drug, reqs in by_drug.items():
        reqs.sort(key=lambda r: r["effective_start"])
        base = f"Derived/medchange/{pid}/{slugify(drug, 40)}"
        first = reqs[0]
        out.append(_derived(pid, CHANGE_LEAF, f"{base}/0", drug, f"{drug} started",
                            first["effective_start"], f"first prescribed {C.fmt_date(first['effective_start'])} "
                            f"as {first['concept_display']}", [first["record_id"]], "first_request", source_doc,
                            value_text="started", status="started"))
        prev = first
        n = 1
        for cur in reqs[1:]:
            s_prev, s_cur = C.medication_strength(prev["concept_display"]), C.medication_strength(cur["concept_display"])
            if s_prev and s_cur and s_prev != s_cur:
                out.append(_derived(pid, CHANGE_LEAF, f"{base}/{n}", drug, f"{drug} dose changed",
                                    cur["effective_start"], f"changed from {s_prev} to {s_cur} on "
                                    f"{C.fmt_date(cur['effective_start'])}", [prev["record_id"], cur["record_id"]],
                                    "strength_differs_from_previous_request", source_doc,
                                    value_text=f"{s_prev} -> {s_cur}", status="dose_changed"))
                n += 1
            prev = cur
        if not any(r["leaf_path"] == MED_LEAVES[0] for r in reqs):
            last = reqs[-1]
            out.append(_derived(pid, CHANGE_LEAF, f"{base}/{n}", drug, f"{drug} no longer active",
                                last["effective_start"], f"no active prescription; last prescribed "
                                f"{C.fmt_date(last['effective_start'])} (status {last.get('clinical_status')})",
                                [r["record_id"] for r in reqs], "no_active_request", source_doc,
                                value_text="inactive", status="stopped"))
    return out


def derive_trends(pid: str, records: List[Dict[str, Any]], source_doc: str) -> List[Dict[str, Any]]:
    series = defaultdict(list)
    for r in records:
        if (r["leaf_path"] in TREND_SOURCE_LEAVES and r.get("normalized_value") is not None
                and r.get("effective_start")):
            series[(r["concept_key"], r.get("normalized_unit"))].append(r)
    out = []
    for (key, unit), pts in series.items():
        if len(pts) < 3:
            continue
        pts.sort(key=lambda r: r["effective_start"])
        vals = [p["normalized_value"] for p in pts]
        w = max(1, min(3, len(vals) // 2))          # non-overlapping head / tail windows
        head = sum(vals[:w]) / w
        tail = sum(vals[-w:]) / w
        rel = (tail - head) / abs(head) if head else 0.0
        direction = "increasing" if rel > 0.05 else "decreasing" if rel < -0.05 else "stable"
        u = f" {unit}" if unit else ""
        fmt = lambda v: f"{v:.2f}".rstrip("0").rstrip(".")
        desc = (f"{len(vals)} measurements {C.fmt_date(pts[0]['effective_start'])} to "
                f"{C.fmt_date(pts[-1]['effective_start'])}; first {fmt(vals[0])}{u}, latest {fmt(vals[-1])}{u}, "
                f"min {fmt(min(vals))}{u}, max {fmt(max(vals))}{u}; overall {direction}")
        out.append(_derived(pid, TREND_LEAF, f"Derived/trend/{pid}/{slugify(key, 60)}/{slugify(unit or 'nounit', 12)}",
                            key, pts[0]["concept_display"], pts[0]["effective_start"], desc,
                            [p["record_id"] for p in pts], "mean(first w) vs mean(last w), w=min(3,n//2), 5% threshold", source_doc,
                            value_num=vals[-1], unit=unit,
                            normalized_value=vals[-1], normalized_unit=unit, value_text=direction,
                            status=direction, code=pts[0].get("concept_code"),
                            end=pts[-1]["effective_start"]))
    return out


WINDOWS_DAYS = (30, 90, 365)


def _days(a: str, b: str) -> float:
    from datetime import datetime
    pa = datetime.fromisoformat(a[:19].replace("Z", ""))
    pb = datetime.fromisoformat(b[:19].replace("Z", ""))
    return (pa - pb).total_seconds() / 86400.0


def window_summaries(pid: str, series: List[Dict[str, Any]], windows=WINDOWS_DAYS,
                     threshold: float = 0.05) -> List[Dict[str, Any]]:
    """Time-slice summaries of ONE measurement series (after Li & Liu, TA-RAG, HBD 2026).

    For each window W (days) ending at the series' LATEST measurement (not today: records may be
    old or date-shifted), report n / mean / min / max and compare the mean with the preceding window
    of the same length (up / down / stable at a 5% relative threshold). A window is emitted only when
    it holds >= 2 points and more points than the next smaller one, so short histories are not repeated.
    Computed on demand for trend/comparison questions; never stored and never part of the benchmarks.
    """
    pts = sorted([r for r in series if r.get("normalized_value") is not None and r.get("effective_start")],
                 key=lambda r: r["effective_start"])
    if len(pts) < 2:
        return []
    last = pts[-1]["effective_start"]
    key, unit = pts[-1]["concept_key"], pts[-1].get("normalized_unit")
    u = f" {unit}" if unit else ""
    fmt = lambda v: f"{v:.2f}".rstrip("0").rstrip(".")
    age = [(p, _days(last, p["effective_start"])) for p in pts]
    out, prev_n = [], None
    for w in sorted(windows):
        cur = [p for p, d in age if d <= w]
        same_as_smaller = prev_n == len(cur)
        prev_n = len(cur)
        if len(cur) < 2 or same_as_smaller:
            continue
        before = [p for p, d in age if w < d <= 2 * w]
        vals = [p["normalized_value"] for p in cur]
        mean = sum(vals) / len(vals)
        desc = (f"last {w} days up to {fmt_date_safe(last)}: {len(vals)} measurements, mean {fmt(mean)}{u}, "
                f"min {fmt(min(vals))}{u}, max {fmt(max(vals))}{u}")
        direction = None
        if before:
            bv = [p["normalized_value"] for p in before]
            bmean = sum(bv) / len(bv)
            rel = (mean - bmean) / abs(bmean) if bmean else 0.0
            direction = "up" if rel > threshold else "down" if rel < -threshold else "stable"
            desc += (f"; previous {w} days: {len(bv)} measurements, mean {fmt(bmean)}{u} -> {direction} "
                     f"({'+' if mean - bmean >= 0 else ''}{fmt(mean - bmean)}{u})")
        else:
            desc += f"; no measurements in the previous {w} days to compare"
        out.append(_derived(pid, TREND_LEAF, f"Derived/window/{pid}/{slugify(key, 60)}/{w}d", key,
                            f"{pts[-1]['concept_display']} ({w}-day window)", cur[0]["effective_start"], desc,
                            [p["record_id"] for p in cur + before], f"window {w}d ending at latest; mean vs previous "
                            f"{w}d, {int(threshold * 100)}% threshold", "computed_on_demand",
                            value_num=mean, unit=unit, normalized_value=mean, normalized_unit=unit,
                            value_text=direction or "no_comparison", status=direction, end=last))
    return out


def fmt_date_safe(d: str) -> str:
    return C.fmt_date(d)
