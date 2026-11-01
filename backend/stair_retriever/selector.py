"""
STAIR-Clinical selector: iterative, multi-path structural routing.

Stage 1  query + patient ToC (levels 1-2)            -> ranked leaves   (top-k)
Stage 2  query + sub-ToC of each selected leaf (L3)  -> ranked concept groups

Backends (all emit ONLY paths present in the patient's ToC; anything else is
recorded in `invalid` and dropped):
  * LoraSelector       — fine-tuned causal LM, constrained scoring over valid targets
  * OllamaSelector     — zero-shot local LLM, free generation parsed + validated
  * StructuralSelector — no LLM: BM25 + BGE-M3 over ToC titles/descriptions + intent prior
Stage 2 falls back to the structural scorer when a backend has no stage-2 model.
"""

import math
import re
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from rank_bm25 import BM25Okapi

from backend.patient_memory.hierarchy import LEAF_BY_PATH, LEAVES, TocNode
from backend.patient_memory.repository import PatientMemory
from backend.rag.fusion import rrf, tokenize
from backend.rag.query_understanding import QueryUnderstanding
from backend.stair_retriever.prompts import clinical_stage1_prompt, clinical_stage2_prompt

Scored = List[Tuple[str, float]]

INTENT_PRIOR: Dict[str, List[str]] = {
    "medication_during_episode": ["medication_history/previous_medications", "medication_history/current_medications",
                                  "clinical_encounters/previous_symptoms", "clinical_encounters/complaints"],
    "medication_changes": ["medication_history/medication_changes"],
    "allergy_check": ["allergy_history"],
    "current_medications": ["medication_history/current_medications"],
    "lab_trend": ["laboratory_observations/historical_trends", "laboratory_observations/laboratory_results",
                  "laboratory_observations/vital_signs"],
    "latest_measurement": ["laboratory_observations/vital_signs", "laboratory_observations/laboratory_results"],
    "lab_lookup": ["laboratory_observations/laboratory_results"],
    "similar_symptoms": ["clinical_encounters/previous_symptoms", "clinical_encounters/complaints"],
    "last_visit": ["clinical_encounters/encounter_dates", "clinical_encounters/consultations"],
    "procedure_history": ["medical_history/procedures"],
    "immunization_history": ["medical_history/immunizations"],
    "condition_status": ["medical_history/diagnoses", "medical_history/conditions"],
    "relevant_history": ["medical_history/diagnoses", "medical_history/conditions"],
}


def patient_header(mem: PatientMemory) -> str:
    p = mem.patient()
    if p is None:
        return "patient"
    age = ""
    if p.birth_date:
        try:
            age = f"{int((np.datetime64('2026-11-01') - np.datetime64(p.birth_date)).astype(int) / 365.25)}-year-old "
        except Exception:
            age = ""
    return f"{age}{p.gender or 'unknown sex'}".strip()


def leaf_nodes(toc: List[TocNode]) -> List[TocNode]:
    out = []
    for n in toc:
        if n.path in LEAF_BY_PATH:
            out.append(n)
        else:
            out.extend(c for c in n.children if c.path in LEAF_BY_PATH)
    return out


def _softmax(xs: Sequence[float]) -> List[float]:
    m = max(xs)
    e = [math.exp(x - m) for x in xs]
    s = sum(e)
    return [v / s for v in e]


def _cut(scored: Scored, max_k: int, mass: float) -> Scored:
    """Keep top items until cumulative normalized score reaches `mass` (multi-path top-k)."""
    if not scored:
        return []
    tot = sum(max(s, 0) for _, s in scored) or 1.0
    out, acc = [], 0.0
    for p, s in scored[:max_k]:
        out.append((p, s))
        acc += max(s, 0) / tot
        if acc >= mass:
            break
    return out


class BaseSelector:
    backend_name = "base"

    def __init__(self, embedder=None, max_leaves: int = 3, max_groups_per_leaf: int = 4,
                 leaf_mass: float = 0.85, group_mass: float = 0.8, leaf_rel: Optional[float] = None):
        self.embedder = embedder
        self.max_leaves = max_leaves
        self.max_groups_per_leaf = max_groups_per_leaf
        self.leaf_mass = leaf_mass
        self.group_mass = group_mass
        self.leaf_rel = leaf_rel          # keep leaves scoring >= leaf_rel * best (selected on validation)

    # -- to override
    def rank_leaves(self, mem, query, qu, toc) -> Tuple[Scored, List[str]]:
        raise NotImplementedError

    def rank_groups(self, leaf: TocNode, query: str, qu: QueryUnderstanding) -> Tuple[Scored, List[str]]:
        return structural_rank_groups(leaf, query, qu, self.embedder)

    # -- shared
    def select(self, mem: PatientMemory, query: str, qu: QueryUnderstanding):
        toc = mem.toc()
        leaves, invalid = self.rank_leaves(mem, query, qu, toc)
        nodes = {n.path: n for n in leaf_nodes(toc)}
        leaves = [(p, s) for p, s in leaves if p in nodes and nodes[p].count > 0]
        if self.leaf_rel is not None and leaves:
            top = leaves[0][1]
            leaves = [(p, s) for p, s in leaves if s >= self.leaf_rel * top]
        leaves = _cut(leaves, self.max_leaves, self.leaf_mass)
        groups: Scored = []
        for lp, ls in leaves:
            node = nodes[lp]
            if not node.children:
                continue
            g, inv = self.rank_groups(node, query, qu)
            invalid += inv
            valid = {c.path for c in node.children}
            g = [(p, s) for p, s in g if p in valid]
            groups += [(p, ls * s) for p, s in _cut(g, self.max_groups_per_leaf, self.group_mass)]
        groups.sort(key=lambda x: -x[1])
        return leaves, groups, invalid


# ----------------------------------------------------------------- structural
def _lex_dense_rank(query: str, texts: List[str], embedder, extra_terms: Sequence[str] = ()) -> List[float]:
    q = f"{query} {' '.join(extra_terms)}"
    bm = BM25Okapi([tokenize(t) or ["_"] for t in texts]).get_scores(tokenize(q) or ["_"])
    rankings = [[i for i in np.argsort(-bm) if bm[i] > 0]]
    if embedder is not None:
        sims = embedder.encode(texts) @ embedder.encode_query(q)
        rankings.append(list(np.argsort(-sims)))
    fused = dict(rrf(rankings))
    return [fused.get(i, 0.0) for i in range(len(texts))], bm


def structural_rank_groups(leaf: TocNode, query: str, qu: QueryUnderstanding, embedder) -> Tuple[Scored, List[str]]:
    kids = leaf.children
    texts = [f"{leaf.title}: {c.title}" for c in kids]
    fused, bm = _lex_dense_rank(query, texts, embedder, qu.expanded_terms)
    specific = any(t in " ".join(texts).lower() for t in qu.expanded_terms) or bm.max(initial=0) > 2.0
    if not specific:
        # generic question about the section (e.g. "current medications", "allergies"): recency order
        n = len(kids)
        return [(c.path, 1.0 / (i + 1)) for i, c in enumerate(kids)][: n], []
    ranked = sorted(zip([c.path for c in kids], fused), key=lambda x: -x[1])
    return [(p, s) for p, s in ranked if s > 0], []


class StructuralSelector(BaseSelector):
    backend_name = "structural"

    def __init__(self, embedder=None, max_leaves: int = 2, leaf_rel: Optional[float] = 0.6, **kw):
        # cut-offs selected on the VALIDATION split (evaluation/.../results/retrieval_eval_val_sweep_*.json)
        super().__init__(embedder=embedder, max_leaves=max_leaves, leaf_rel=leaf_rel, **kw)

    def rank_leaves(self, mem, query, qu, toc):
        nodes = leaf_nodes(toc)
        texts = [f"{n.title}: {LEAF_BY_PATH[n.path].description}" for n in nodes]
        fused, _ = _lex_dense_rank(query, texts, self.embedder, qu.expanded_terms)
        prior = INTENT_PRIOR.get(qu.intent, [])
        scored = []
        for n, f in zip(nodes, fused):
            bonus = (0.05 / (prior.index(n.path) + 1)) if n.path in prior else 0.0
            scored.append((n.path, f + bonus))
        scored.sort(key=lambda x: -x[1])
        return scored, []


# ---------------------------------------------------------------------- LoRA
class LoraSelector(BaseSelector):
    backend_name = "lora"

    def __init__(self, scorer, stage2: bool = False, **kw):
        super().__init__(**kw)
        self.scorer = scorer
        self.stage2 = stage2

    def rank_leaves(self, mem, query, qu, toc):
        prompt, targets = clinical_stage1_prompt(patient_header(mem), toc, query)
        lps = self.scorer.score_candidates(prompt, [t for t, _ in targets])
        probs = _softmax(lps)
        scored = sorted(((p, pr) for (_, p), pr in zip(targets, probs)), key=lambda x: -x[1])
        return scored, []

    def rank_groups(self, leaf, query, qu):
        if not self.stage2:
            return super().rank_groups(leaf, query, qu)
        prompt, targets = clinical_stage2_prompt(leaf, query)
        probs = _softmax(self.scorer.score_candidates(prompt, [t for t, _ in targets]))
        return sorted(((p, pr) for (_, p), pr in zip(targets, probs)), key=lambda x: -x[1]), []


# -------------------------------------------------------------------- Ollama
class OllamaSelector(BaseSelector):
    """Zero-shot STAIR-style routing with a local LLM. Output is free text, so every
    returned section is parsed and validated against the ToC; non-matching outputs are
    counted as invalid paths (the hallucination metric of the STAIR paper)."""
    backend_name = "ollama_zero_shot"

    def __init__(self, client, **kw):
        super().__init__(**kw)
        self.client = client

    def rank_leaves(self, mem, query, qu, toc):
        prompt, targets = clinical_stage1_prompt(patient_header(mem), toc, query)
        prompt = prompt.replace("Only generate the section name", "Generate up to 3 section names, one per line, best first. Only generate section names")
        text = self.client.generate(prompt, max_tokens=60, temperature=0.0)
        by_num = {t.split(" ", 1)[0]: p for t, p in targets}
        by_title = {t.split(" ", 1)[1].lower(): p for t, p in targets}
        scored, invalid = [], []
        for i, line in enumerate(l.strip() for l in text.splitlines() if l.strip()):
            line = re.sub(r"^(leaf\s+)", "", line, flags=re.I).strip(" -*.")
            m = re.match(r"(\d+(?:\.\d+)?)\b", line)
            path = by_num.get(m.group(1)) if m else None
            if path is None:
                path = next((p for t, p in by_title.items() if t in line.lower()), None)
            if path is None:
                invalid.append(line[:80])
            elif path not in [p for p, _ in scored]:
                scored.append((path, 1.0 / (len(scored) + 1)))
        return scored, invalid


def build_selector(backend: str = "auto", embedder=None, **kw) -> BaseSelector:
    from backend import config
    if backend in ("auto", "lora"):
        adapter = config.STAIR_ADAPTER_DIR
        meta = adapter / "stair_clinical_meta.json"
        if meta.exists():
            import json
            from backend.stair_retriever.constrained import load_scorer
            m = json.loads(meta.read_text(encoding="utf-8"))
            sel = LoraSelector(load_scorer(m["base_model"], str(adapter)), stage2=m.get("stage2", False),
                               embedder=embedder, **kw)
            return sel
        if backend == "lora":
            raise FileNotFoundError(f"No trained STAIR-Clinical adapter at {adapter}")
    if backend == "ollama":
        from backend.llm.ollama_client import OllamaClient
        return OllamaSelector(OllamaClient(), embedder=embedder, **kw)
    return StructuralSelector(embedder=embedder, **kw)
