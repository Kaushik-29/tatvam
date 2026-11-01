"""
Renders evaluation JSON files into markdown tables (so reported numbers are copied
mechanically from result files, never by hand).

    python scripts/render_results.py            # writes docs/results_tables.md
"""

import glob
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def f(x, nd=3):
    return "—" if x is None else f"{x:.{nd}f}"


def ci(m):
    if not isinstance(m, dict) or "mean" not in m:
        return "—"
    lo, hi = m.get("ci95", [None, None])
    s = f(m["mean"])
    if lo is not None and hi is not None:
        s += f" [{f(lo)}, {f(hi)}]"
    return s


def retrieval(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    out = [f"### Retrieval — `{Path(path).name}`", "",
           f"Split **{d['split']}**, {d['sample']} queries, seed {d['seed']}, selector params {d.get('selector_params', {})}, "
           f"query-set SHA-256 `{d['query_set_sha256'][:16]}…`", "",
           "| Method | n | R@1 | R@3 | R@5 | R@10 | MRR | nDCG@10 | Ctx-P@10 | Ctx-R@10 | Leaf EM | Invalid paths | s/query |",
           "|---|---:|---|---|---|---|---|---|---|---|---|---|---:|"]
    for name, s in d["summary"].items():
        inv = s.get("invalid_path_rate")
        out.append("| " + " | ".join([
            name, str(s["n_queries"]), ci(s.get("recall@1")), ci(s.get("recall@3")), ci(s.get("recall@5")),
            ci(s.get("recall@10")), ci(s.get("mrr")), ci(s.get("ndcg@10")), ci(s.get("context_precision@10")),
            ci(s.get("context_recall@10")), ci(s.get("leaf_exact_match")),
            f"{inv['numerator']}/{inv['denominator']}" if inv else "—", f(s.get("seconds_per_query"), 2)]) + " |")
    if d.get("paired_comparisons"):
        out += ["", "Paired differences (patient-clustered bootstrap):", "",
                "| Comparison | Δ mean | 95% CI | p (bootstrap) | n queries / patients |", "|---|---|---|---|---|"]
        for k, v in d["paired_comparisons"].items():
            out.append(f"| {k} | {f(v['diff'])} | [{f(v['ci'][0])}, {f(v['ci'][1])}] | {f(v.get('p_bootstrap'))} | "
                       f"{v.get('n_queries')} / {v.get('n_patients')} |")
    cats = None
    for name, s in d["summary"].items():
        cats = cats or sorted(s["recall@5_by_category"])
    if cats:
        names = list(d["summary"])
        out += ["", "Recall@5 by query category:", "", "| Category | " + " | ".join(names) + " |",
                "|---|" + "---|" * len(names)]
        for c in cats:
            row = [f"{d['summary'][n]['recall@5_by_category'].get(c, {}).get('mean', float('nan')):.3f}" for n in names]
            n = d["summary"][names[0]]["recall@5_by_category"].get(c, {}).get("n", "")
            out.append(f"| {c} (n={n}) | " + " | ".join(row) + " |")
    return "\n".join(out)


def response(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    out = [f"### Responses — `{Path(path).name}`", "",
           f"LLM `{d['llm']}`, STAIR backend `{d['stair_backend']}`, {d['n_clinical_queries']} clinical queries + "
           f"{d['n_probes']} safety probes, wall time {d['wall_time_s']} s.", "",
           "| Variant | Unsupported patient-claim rate (raw) | Evidence support (raw) | Historical coverage | "
           "History consistency | Action appropriateness (probes) | Latency s |", "|---|---|---|---|---|---|---|"]
    for v, s in d["summary"].items():
        out.append(f"| {v} | {ci(s.get('unsupported_patient_claim_rate_raw'))} | {ci(s.get('evidence_support_rate_raw'))} | "
                   f"{ci(s.get('historical_context_coverage'))} | {ci(s.get('patient_history_consistency'))} | "
                   f"{ci(s.get('action_appropriateness_probes'))} | {ci(s.get('latency_s'))} |")
    b5 = d["summary"].get("B5", {})
    if "unsupported_patient_claims_released_total" in b5:
        out += ["", f"B5 unsupported patient-specific claims **released to the user** (after verification): "
                    f"**{b5['unsupported_patient_claims_released_total']}**."]
    return "\n".join(out)


def searchtome(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    out = ["### SearchTome (official reduced HF release) — validation and baselines", "",
           "| Domain | Book | Leaves | Test queries | Unanswerable (all splits) | Train∩Test query overlap |", "|---|---|---:|---:|---:|---:|"]
    for dom, v in d["validation"]["domains"].items():
        un = sum(s["unanswerable"] for s in v["splits"].values())
        out.append(f"| {dom} | {v['book']} | {v['leaves']} | {v['splits']['test']['queries']} | {un} | "
                   f"{v['query_text_overlap']['train∩test']} |")
    if "flat_baselines_test" in d:
        out += ["", "| Domain | n | BM25 R@1 | BM25 R@3 | BM25 nDCG@3 | Dense R@1 | Dense R@3 | Dense nDCG@3 | Hybrid R@1 | Hybrid R@3 | Hybrid nDCG@3 |",
                "|---|---:|---|---|---|---|---|---|---|---|---|"]
        for dom, v in d["flat_baselines_test"].items():
            out.append(f"| {dom} | {v['n_test']} | " + " | ".join(
                f(v[m][k]) for m in ("bm25", "dense_bge_m3", "hybrid_rrf") for k in ("r@1", "r@3", "ndcg@3")) + " |")
    if "stair_zero_shot_base_lm" in d:
        z = d["stair_zero_shot_base_lm"]
        out += ["", f"Out-of-the-box STAIR prompt + constrained scoring, `{z['base_model']}` (no fine-tuning), medicine test sample "
                    f"n={z['n']}: R@1 {f(z['recall@1'])} ({z['hits@1']}/{z['n']}), R@3 {f(z['recall@3'])}, invalid paths 0 by construction, "
                    f"{f(z['seconds_per_query'], 1)} s/query."]
    if "ollama_free_generation" in d:
        o = d["ollama_free_generation"]
        out += [f"Zero-shot free generation with `{o['model']}` (unconstrained), n={o['n']}: invalid (non-leaf) output rate "
                f"**{f(o['invalid_path_rate'])}** ({o['invalid']}/{o['n']}), exact match {f(o['exact_match'])}."]
    out += ["", f"Fine-tuned STAIR on SearchTome: {d['fine_tuned_stair_searchtome']}"]
    return "\n".join(out)


def training():
    out = ["### STAIR-Clinical LoRA runs", "",
           "| Run | Status | Base model | Steps | Train ex. | Train time s | Val R@1 before → after | Val R@3 after | Val MRR after | Free-gen invalid rate | Hardware |",
           "|---|---|---|---:|---:|---:|---|---|---|---|---|"]
    for p in sorted(glob.glob(str(ROOT / "models/stair_clinical/checkpoints/*/train_metrics.json"))):
        m = json.loads(Path(p).read_text(encoding="utf-8"))
        b, a = m.get("validation_before_training") or {}, m.get("validation_final") or {}
        hw = m["hardware"]
        out.append(f"| {Path(p).parent.name} | {m['training_status']} | {m['base_model']} | {m['steps']} | {m['train_examples']} | "
                   f"{m['train_time_s']} | {f(b.get('recall@1'))} → {f(a.get('recall@1'))} (n={a.get('n_queries')}) | "
                   f"{f(a.get('recall@3'))} | {f(a.get('mrr'))} | {f(a.get('free_generation_invalid_path_rate'))} "
                   f"(n={a.get('free_generation_n')}) | {hw.get('cpu_count')} CPU threads, CUDA={hw.get('cuda')} |")
    return "\n".join(out)


def main():
    parts = ["# Results tables (auto-generated by scripts/render_results.py)", "", training(), ""]
    for p in sorted(glob.glob(str(ROOT / "evaluation/experiments/patient_context_retrieval/results/retrieval_eval_*.json"))):
        if p.endswith("_per_query.jsonl"):
            continue
        parts += [retrieval(p), ""]
    st = ROOT / "evaluation/experiments/stair/results/searchtome_results.json"
    if st.exists():
        parts += [searchtome(st), ""]
    for p in sorted(glob.glob(str(ROOT / "evaluation/experiments/response_evaluation/results/response_eval_*.json"))):
        parts += [response(p), ""]
    out = ROOT / "docs" / "results_tables.md"
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
