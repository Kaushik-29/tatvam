"""
Longitudinal patient-context retrieval evaluation (separate protocol; does NOT touch the
frozen Phase 5.5.2.1 OCR or Phase 6 benchmarks).

Test split = patients never seen in training (patient-separated). Gold evidence is
programmatic (backend/stair_retriever/training_data.py).

Methods
  R1_bm25                 flat BM25 over the patient's record texts
  R2_dense_bge_m3         flat BGE-M3 over record concept texts
  R3_hybrid_rrf           RRF(BM25, dense) + query-understanding expansions
  R4_hybrid_structured    R3 + structured temporal operations            (B3 retrieval)
  R5_stair_structural     STAIR-Clinical routing, structural selector    (no LLM)
  R6_stair_base_zeroshot  STAIR-Clinical, untrained base LM, constrained (out-of-the-box)
  R7_stair_lora           STAIR-Clinical, LoRA stage-1 selector, constrained
  R8_stair_hybrid         RRF(R5, R4) — the retrieval used by B4/B5 in the app
  R9_stair_lora_hybrid    RRF(R7, R4)

Usage
  python -m evaluation.experiments.patient_context_retrieval.run_retrieval_eval \
      --split test --sample 600 [--methods R1_bm25,...] [--lora-adapter models/.../adapter]
"""

import argparse
import datetime as dt
import hashlib
import json
import math
import random
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

from backend.config import PROJECT_ROOT
from backend.patient_memory.db import session_scope
from backend.patient_memory.hierarchy import leaf_of
from backend.patient_memory.repository import PatientMemory
from backend.rag.embeddings import get_embedder
from backend.rag.fusion import rrf
from backend.rag.query_understanding import understand
from backend.stair_retriever.sft import load_queries
from backend.stair_retriever.selector import LoraSelector, StructuralSelector
from backend.structured_retrieval.patient_retriever import PatientRetriever
from evaluation.metrics import capped_recall, cluster_bootstrap_ci, mrr, ndcg, paired_cluster_bootstrap

OUT = PROJECT_ROOT / "evaluation" / "experiments" / "patient_context_retrieval" / "results"
KS = (1, 3, 5, 10)
ALL_METHODS = ["R1_bm25", "R2_dense_bge_m3", "R3_hybrid_rrf", "R4_hybrid_structured", "R5_stair_structural",
               "R6_stair_base_zeroshot", "R7_stair_lora", "R8_stair_hybrid", "R9_stair_lora_hybrid"]


def stratified_sample(rows: List[Dict[str, Any]], n: int, seed: int) -> List[Dict[str, Any]]:
    if not n or n >= len(rows):
        return rows
    by = defaultdict(list)
    for r in rows:
        by[r["query_category"]].append(r)
    rng = random.Random(seed)
    out = []
    for cat, rs in sorted(by.items()):
        k = max(1, round(n * len(rs) / len(rows)))
        out += rng.sample(rs, min(k, len(rs)))
    return out


def fuse(a: List[Dict], b: List[Dict], k: int = 20) -> List[Dict]:
    by = {r["record_id"]: r for r in a + b}
    return [by[i] for i, _ in rrf([[r["record_id"] for r in a], [r["record_id"] for r in b]], weights=[1.0, 0.5])[:k]]


def score_query(ex: Dict[str, Any], recs: List[Dict], trace=None) -> Dict[str, Any]:
    ranked = [r["record_id"] for r in recs]
    gold = set(ex["gold_evidence_ids"])
    gold_groups = set(ex["expected_group_paths"])
    gold_leaves = set(ex["expected_leaf_paths"])
    m = {f"recall@{k}": capped_recall(ranked, gold, k) for k in KS}
    m.update({"mrr": mrr(ranked, gold), "ndcg@10": ndcg(ranked, gold, 10)})
    top10 = recs[:10]
    m["context_precision@10"] = (sum(1 for r in top10 if r["group_path"] in gold_groups) / len(top10)) if top10 else 0.0
    m["context_recall@10"] = len({r["group_path"] for r in top10} & gold_groups) / len(gold_groups) if gold_groups else float("nan")
    if trace is not None:
        sel_leaves = {p for p, _ in trace.selected_leaves}
        sel_groups = {p for p, _ in trace.selected_groups}
        # a virtual leaf (encounter_dates) and its source are equivalent routes
        norm = lambda s: {x.replace("encounter_dates", "consultations") for x in s}
        m["leaf_exact_match"] = float(norm(sel_leaves) == norm(gold_leaves))
        m["leaf_recall"] = len(norm(sel_leaves) & norm(gold_leaves)) / len(norm(gold_leaves))
        m["leaf_hit@1"] = float(bool(trace.selected_leaves) and norm({trace.selected_leaves[0][0]}) <= norm(gold_leaves))
        m["group_path_recall"] = (len(sel_groups & gold_groups) / len(gold_groups)) if gold_groups else float("nan")
        emitted = len(trace.selected_leaves) + len(trace.selected_groups) + len(trace.invalid_paths)
        m["invalid_paths"] = len(trace.invalid_paths)
        m["emitted_paths"] = emitted
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test")
    ap.add_argument("--sample", type=int, default=600)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--methods", default=",".join(ALL_METHODS))
    ap.add_argument("--base-model", default="Qwen/Qwen2.5-0.5B-Instruct")
    ap.add_argument("--lora-adapter", default=None)
    ap.add_argument("--tag", default=None)
    ap.add_argument("--max-leaves", type=int, default=None)
    ap.add_argument("--leaf-rel", type=float, default=None)
    a = ap.parse_args()
    methods = [m for m in a.methods.split(",") if m]
    rows = stratified_sample(load_queries(a.split), a.sample, a.seed)
    print(f"{len(rows)} queries, {len({r['patient_id'] for r in rows})} patients, methods={methods}")
    emb = get_embedder()
    sel_kw = {k: v for k, v in {"max_leaves": a.max_leaves, "leaf_rel": a.leaf_rel}.items() if v is not None}
    structural = StructuralSelector(embedder=emb, **sel_kw)
    base_sel = lora_sel = None
    if "R6_stair_base_zeroshot" in methods:
        from backend.stair_retriever.constrained import load_scorer
        base_sel = LoraSelector(load_scorer(a.base_model), embedder=emb, **sel_kw)
        base_sel.backend_name = "base_lm_zero_shot_constrained"
    if any(m in methods for m in ("R7_stair_lora", "R9_stair_lora_hybrid")):
        if not a.lora_adapter:
            raise SystemExit("--lora-adapter required for R7/R9")
        from backend.stair_retriever.constrained import load_scorer
        lora_sel = LoraSelector(load_scorer(a.base_model, a.lora_adapter), embedder=emb, **sel_kw)

    per_query: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    timing = Counter()
    by_patient = defaultdict(list)
    for r in rows:
        by_patient[r["patient_id"]].append(r)
    t_all = time.time()
    with session_scope() as s:
        for n_p, (pid, exs) in enumerate(sorted(by_patient.items()), 1):
            mem = PatientMemory(s, pid)
            ret = PatientRetriever(mem, emb)
            for ex in exs:
                q = ex["query"]
                qu = understand(q, known_medications=[])
                cache = {}

                def run(name, fn):
                    t0 = time.time()
                    out = fn()
                    timing[name] += time.time() - t0
                    return out

                results = {}
                if "R1_bm25" in methods:
                    results["R1_bm25"] = (run("R1_bm25", lambda: ret.bm25(q, 20)), None)
                if "R2_dense_bge_m3" in methods:
                    results["R2_dense_bge_m3"] = (run("R2_dense_bge_m3", lambda: ret.dense(q, 20)), None)
                if "R3_hybrid_rrf" in methods:
                    results["R3_hybrid_rrf"] = (run("R3_hybrid_rrf", lambda: ret.hybrid(q, 20, qu.expanded_terms)), None)
                if any(m in methods for m in ("R4_hybrid_structured", "R8_stair_hybrid", "R9_stair_lora_hybrid")):
                    cache["R4"] = run("R4_hybrid_structured", lambda: ret.hybrid_structured(q, qu, 20))
                    if "R4_hybrid_structured" in methods:
                        results["R4_hybrid_structured"] = cache["R4"]
                if any(m in methods for m in ("R5_stair_structural", "R8_stair_hybrid")):
                    cache["R5"] = run("R5_stair_structural", lambda: ret.stair(q, qu, structural, 20))
                    if "R5_stair_structural" in methods:
                        results["R5_stair_structural"] = cache["R5"]
                if base_sel and "R6_stair_base_zeroshot" in methods:
                    results["R6_stair_base_zeroshot"] = run("R6_stair_base_zeroshot", lambda: ret.stair(q, qu, base_sel, 20))
                if lora_sel and any(m in methods for m in ("R7_stair_lora", "R9_stair_lora_hybrid")):
                    cache["R7"] = run("R7_stair_lora", lambda: ret.stair(q, qu, lora_sel, 20))
                    if "R7_stair_lora" in methods:
                        results["R7_stair_lora"] = cache["R7"]
                if "R8_stair_hybrid" in methods:
                    results["R8_stair_hybrid"] = (fuse(cache["R5"][0], cache["R4"][0]), cache["R5"][1])
                if "R9_stair_lora_hybrid" in methods and "R7" in cache:
                    results["R9_stair_lora_hybrid"] = (fuse(cache["R7"][0], cache["R4"][0]), cache["R7"][1])
                for name, (recs, trace) in results.items():
                    assert all(r["patient_id"] == pid for r in recs), "patient isolation violated"
                    m = score_query(ex, recs, trace if name.startswith(("R5", "R6", "R7", "R8", "R9")) else None)
                    m.update({"example_id": ex["example_id"], "patient_id": pid, "category": ex["query_category"],
                              "n_gold": len(ex["gold_evidence_ids"]), "top5": [r["record_id"] for r in recs[:5]]})
                    per_query[name].append(m)
            if n_p % 10 == 0:
                print(f"  {n_p}/{len(by_patient)} patients ({time.time() - t_all:.0f}s)", flush=True)

    summary = {}
    metric_names = [f"recall@{k}" for k in KS] + ["mrr", "ndcg@10", "context_precision@10", "context_recall@10",
                                                  "leaf_exact_match", "leaf_recall", "leaf_hit@1", "group_path_recall"]
    for name, qs in per_query.items():
        res = {"n_queries": len(qs), "n_patients": len({q["patient_id"] for q in qs}),
               "seconds_per_query": timing[name] / max(1, len(qs))}
        for mn in metric_names:
            vals = [q[mn] for q in qs if mn in q]
            if not vals:
                continue
            mean, lo, hi = cluster_bootstrap_ci(vals, [q["patient_id"] for q in qs if mn in q])
            valid = [v for v in vals if not math.isnan(v)]
            res[mn] = {"mean": mean, "ci95": [lo, hi], "n": len(valid),
                       "numerator": round(sum(valid), 3), "denominator": len(valid)}
        if any("invalid_paths" in q for q in qs):
            inv = sum(q.get("invalid_paths", 0) for q in qs)
            emitted = sum(q.get("emitted_paths", 0) for q in qs)
            res["invalid_path_rate"] = {"numerator": inv, "denominator": emitted, "mean": inv / emitted if emitted else 0.0}
        by_cat = defaultdict(list)
        for q in qs:
            by_cat[q["category"]].append(q["recall@5"])
        res["recall@5_by_category"] = {c: {"mean": sum(v) / len(v), "n": len(v)} for c, v in sorted(by_cat.items())}
        summary[name] = res

    comparisons = {}
    def paired(a_name, b_name, metric="recall@5"):
        if a_name in per_query and b_name in per_query:
            A = {q["example_id"]: q for q in per_query[a_name]}
            B = {q["example_id"]: q for q in per_query[b_name]}
            ids = [i for i in A if i in B]
            comparisons[f"{a_name} - {b_name} ({metric})"] = paired_cluster_bootstrap(
                [A[i][metric] for i in ids], [B[i][metric] for i in ids], [A[i]["patient_id"] for i in ids])
    for metric in ("recall@5", "mrr"):
        paired("R5_stair_structural", "R4_hybrid_structured", metric)
        paired("R8_stair_hybrid", "R4_hybrid_structured", metric)
        paired("R7_stair_lora", "R6_stair_base_zeroshot", metric)
        paired("R7_stair_lora", "R5_stair_structural", metric)
        paired("R9_stair_lora_hybrid", "R4_hybrid_structured", metric)
        paired("R3_hybrid_rrf", "R1_bm25", metric)

    failures = {}
    for name, qs in per_query.items():
        worst = sorted((q for q in qs if q["recall@5"] == 0), key=lambda q: q["category"])
        failures[name] = {"zero_recall@5_count": len(worst),
                          "by_category": dict(Counter(q["category"] for q in worst)),
                          "examples": [{k: q[k] for k in ("example_id", "category", "top5")} for q in worst[:8]]}
    q_index = {r["example_id"]: r["query"] for r in rows}
    for name in failures:
        for e in failures[name]["examples"]:
            e["query"] = q_index[e["example_id"]]

    tag = a.tag or dt.datetime.now().strftime("%Y%m%d_%H%M")
    OUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "protocol": "STAIR-Clinical longitudinal patient-context retrieval v1 (patient-separated split)",
        "split": a.split, "sample": len(rows), "seed": a.seed, "methods": methods, "selector_params": sel_kw,
        "query_set_sha256": hashlib.sha256(json.dumps(sorted(q["example_id"] for q in rows)).encode()).hexdigest(),
        "embedding_model": emb.model_name, "base_model": a.base_model, "lora_adapter": a.lora_adapter,
        "metric_definitions": {
            "recall@k": "capped: |gold ∩ top-k| / min(|gold|, k); gold = up to 3 most recent records per gold evidence path",
            "context_precision@10": "share of top-10 records that belong to a gold evidence path (concept group)",
            "context_recall@10": "share of gold evidence paths with >=1 record in top-10",
            "leaf_exact_match": "selected level-2 sections == gold sections (STAIR methods only)",
            "invalid_path_rate": "emitted paths not present in the patient's hierarchy / all emitted paths",
            "ci95": "patient-clustered percentile bootstrap, 1000 resamples",
        },
        "summary": summary, "paired_comparisons": comparisons, "failure_analysis": failures,
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
    }
    (OUT / f"retrieval_eval_{tag}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    with open(OUT / f"retrieval_eval_{tag}_per_query.jsonl", "w", encoding="utf-8") as f:
        for name, qs in per_query.items():
            for q in qs:
                f.write(json.dumps({"method": name, **q}) + "\n")
    print(json.dumps({n: {k: (v["mean"] if isinstance(v, dict) and "mean" in v else v)
                          for k, v in s.items() if k in ("recall@1", "recall@5", "mrr", "ndcg@10", "leaf_exact_match",
                                                         "invalid_path_rate", "seconds_per_query", "n_queries")}
                      for n, s in summary.items()}, indent=1, default=str))


if __name__ == "__main__":
    main()
