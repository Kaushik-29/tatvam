"""
Patient-scoped record retrieval: BM25, BGE-M3 dense, hybrid RRF, structured
filters, and STAIR-Clinical structure-aware retrieval.

All methods operate on ONE PatientMemory (one patient_id). The ranking unit is a
clinical record; every result keeps its record_id, leaf path and group path.

Dense representation: BGE-M3 embeds the record's *concept text*
("<leaf title>: <concept display>") — deduplicated across the cohort and cached —
because CPU encoding of every dated value (~750k rows) is infeasible. Records of
the same concept therefore tie on dense score; ties are broken by recency.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from rank_bm25 import BM25Okapi

from backend.patient_memory.hierarchy import LEAF_BY_PATH, leaf_of, resolve_virtual
from backend.patient_memory.repository import PatientMemory
from backend.rag.embeddings import CachedEmbedder
from backend.rag.fusion import rrf, tokenize
from backend.rag.query_understanding import QueryUnderstanding

SYMPTOM_LEAVES = ("clinical_encounters/previous_symptoms", "clinical_encounters/complaints")
MED_LEAVES = ("medication_history/current_medications", "medication_history/previous_medications")
TREND_LEAF = "laboratory_observations/historical_trends"
MED_WORDS = re.compile(r"\b(prescription|medication|medicine|dose|drug|pill|tablet)s?\b")
SERIES_LEAVES = (TREND_LEAF, "laboratory_observations/laboratory_results", "laboratory_observations/vital_signs")


def concept_text(r: Dict[str, Any]) -> str:
    return f"{LEAF_BY_PATH[r['leaf_path']].title}: {r['concept_display']}"


@dataclass
class RetrievalTrace:
    method: str
    selected_leaves: List[Tuple[str, float]] = field(default_factory=list)
    selected_groups: List[Tuple[str, float]] = field(default_factory=list)
    invalid_paths: List[str] = field(default_factory=list)
    structured_ops: List[str] = field(default_factory=list)
    selector_backend: Optional[str] = None


class PatientRetriever:
    def __init__(self, mem: PatientMemory, embedder: Optional[CachedEmbedder] = None):
        self.mem = mem
        self.embedder = embedder
        self._records: Optional[List[Dict[str, Any]]] = None
        self._bm25 = None

    @property
    def records(self) -> List[Dict[str, Any]]:
        if self._records is None:
            self._records = self.mem.records()        # newest first
        return self._records

    # --------------------------------------------------------------- flat
    def bm25(self, query: str, k: int = 20, expansions: Sequence[str] = ()) -> List[Dict[str, Any]]:
        if not self.records:
            return []
        if self._bm25 is None:
            self._bm25 = BM25Okapi([tokenize(r["text"]) for r in self.records])
        q = tokenize(query + " " + " ".join(expansions))
        if not q:
            return []
        scores = self._bm25.get_scores(q)
        order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))   # i ascending == newer first
        return [self.records[i] for i in order[:k] if scores[i] > 0]

    def dense(self, query: str, k: int = 20, expansions: Sequence[str] = ()) -> List[Dict[str, Any]]:
        if not self.records or self.embedder is None:
            return []
        texts = [concept_text(r) for r in self.records]
        uniq = list(dict.fromkeys(texts))
        vecs = self.embedder.encode(uniq)
        qv = self.embedder.encode_query(query if not expansions else f"{query} ({', '.join(expansions)})")
        sim = dict(zip(uniq, vecs @ qv))
        order = sorted(range(len(texts)), key=lambda i: (-sim[texts[i]], i))
        return [self.records[i] for i in order[:k]]

    def hybrid(self, query: str, k: int = 20, expansions: Sequence[str] = ()) -> List[Dict[str, Any]]:
        a = [r["record_id"] for r in self.bm25(query, 100, expansions)]
        b = [r["record_id"] for r in self.dense(query, 100, expansions)]
        by_id = {r["record_id"]: r for r in self.records}
        return [by_id[i] for i, _ in rrf([a, b])[:k]]

    # --------------------------------------------------------- structured
    def structured_filter(self, recs: List[Dict[str, Any]], qu: QueryUnderstanding,
                          trace: RetrievalTrace) -> List[Dict[str, Any]]:
        """Exact database-style operations driven by query understanding (applied in B3/B4/B5 alike)."""
        out = recs
        if qu.time_start or qu.time_end:
            lo, hi = qu.time_start or "0000", qu.time_end or "9999"
            kept = [r for r in out if r["leaf_path"] == "demographics" or
                    (r.get("effective_start") and lo <= r["effective_start"][:10] < hi)]
            if kept:
                out = kept
                trace.structured_ops.append(f"date_range[{lo},{hi})")
        return out

    def episode_medications(self, qu: QueryUnderstanding, trace: RetrievalTrace) -> List[Dict[str, Any]]:
        """For 'during my previous <symptom> episode' questions: anchor on the matching symptom
        record (respecting any date range) and return medications in effect at that date."""
        if qu.temporal_relation != "during_episode" or not qu.symptoms:
            return []
        lo, hi = qu.time_start or "0000", qu.time_end or "9999"
        anchors = [r for r in self.records if r["leaf_path"] in SYMPTOM_LEAVES and r.get("effective_start")
                   and lo <= r["effective_start"][:10] < hi
                   and any(s in r["concept_display"].lower() for s in qu.symptoms)]
        if not anchors:
            return []
        a = anchors[0]                       # most recent matching episode
        meds = self.mem.medications_active_at(a["effective_start"])
        trace.structured_ops.append(f"medications_active_at({a['effective_start'][:10]}) anchored on {a['record_id']}")
        return [a] + [{k: v for k, v in m.items() if not k.startswith("interval")} for m in meds]

    def trend_series(self, groups: Sequence[Tuple[str, float]], by_group: Dict[str, List[Dict[str, Any]]],
                     qu: QueryUnderstanding, trace: RetrievalTrace, n_series: int = 2,
                     n_recent: int = 3) -> List[Dict[str, Any]]:
        """Trend / comparison questions: keep one measurement series together. For the top routed
        measurement concepts, emit the series' trend summary followed by its newest readings, instead of
        interleaving the newest reading of many different tests (temporal proximity, as in TA-RAG)."""
        # only when the router's top choice is a measurement section: "changed" also appears in
        # medication-change questions, which must not be crowded out by lab series
        if (qu.temporal_relation != "trend" or MED_WORDS.search(qu.raw_query.lower())
                or not groups or leaf_of(groups[0][0]) not in SERIES_LEAVES):
            return []
        out, families = [], []
        for gp, _ in groups:
            leaf = leaf_of(gp)
            if leaf not in SERIES_LEAVES:
                continue
            slug = gp[len(leaf) + 1:]
            if slug not in families:
                families.append(slug)
            if len(families) == n_series:
                break
        for slug in families:
            trend = by_group.get(f"{TREND_LEAF}/{slug}", [])[:1]
            raw = sorted(by_group.get(f"laboratory_observations/laboratory_results/{slug}", []) +
                         by_group.get(f"laboratory_observations/vital_signs/{slug}", []),
                         key=lambda r: r.get("effective_start") or "", reverse=True)[:n_recent]
            if trend or raw:
                out += trend + raw
                trace.structured_ops.append(f"trend_series({slug}: summary + {len(raw)} newest)")
        return out

    # -------------------------------------------------------------- STAIR
    def stair(self, query: str, qu: QueryUnderstanding, selector, k: int = 20,
              per_group: int = 3) -> Tuple[List[Dict[str, Any]], RetrievalTrace]:
        """STAIR-Clinical: (1) route to leaves over the patient ToC, (2) route to concept groups
        within those leaves, (3) validate every path against THIS patient's hierarchy,
        (4) resolve paths to real records via the database, (5) apply structured ops."""
        trace = RetrievalTrace(method="stair_clinical", selector_backend=selector.backend_name)
        leaves, groups, invalid = selector.select(self.mem, query, qu)
        trace.selected_leaves, trace.selected_groups, trace.invalid_paths = leaves, groups, invalid
        valid_groups = self.mem.valid_group_paths()
        by_group = defaultdict(list)
        for r in self.records:
            by_group[r["group_path"]].append(r)
        ordered: List[List[Dict[str, Any]]] = []
        for gp, _ in groups:
            if gp in valid_groups:
                ordered.append(self.structured_filter(by_group[gp], qu, trace))
        # leaves selected without a group choice (e.g. virtual "encounter_dates", demographics)
        chosen_leaves_with_groups = {leaf_of(g) for g, _ in groups}
        for lp, _ in leaves:
            if lp not in chosen_leaves_with_groups:
                src = resolve_virtual(lp)
                ordered.append(self.structured_filter([r for r in self.records if r["leaf_path"] == src], qu, trace))
        result: List[Dict[str, Any]] = []
        seen = set()
        episode = self.episode_medications(qu, trace)
        for r in episode + self.trend_series(groups, by_group, qu, trace):
            if r["record_id"] not in seen:
                seen.add(r["record_id"]); result.append(r)
        for depth in range(per_group):                  # round-robin: newest of each group first
            for grp in ordered:
                if depth < len(grp) and grp[depth]["record_id"] not in seen:
                    seen.add(grp[depth]["record_id"]); result.append(grp[depth])
        return result[:k], trace

    def hybrid_structured(self, query: str, qu: QueryUnderstanding, k: int = 20) -> Tuple[List[Dict[str, Any]], RetrievalTrace]:
        """B3 retrieval: hybrid RRF + the same structured ops, but no STAIR routing."""
        trace = RetrievalTrace(method="hybrid_structured")
        res = self.structured_filter(self.hybrid(query, 200, qu.expanded_terms), qu, trace)
        episode = self.episode_medications(qu, trace)
        seen = {r["record_id"] for r in episode}
        return (episode + [r for r in res if r["record_id"] not in seen])[:k], trace
