"""
SearchTome (official HF release, meghanadh/SearchTome) — validation and STAIR-method baselines.

IMPORTANT: the public release has one textbook per domain and differs from the paper's
Table 1 (18 books). Results here are therefore NOT a reproduction of the paper's numbers.

Steps
  1. validate every query's gold leaf against the released ToC (corpus titles); report
     unanswerable / duplicate / cross-split-overlap items  -> data/datasets/searchtome/processed/
  2. flat baselines over leaf content: BM25, BGE-M3 dense, hybrid RRF  (R@1, R@3, nDCG@3; test split)
  3. optional: out-of-the-box base LM with STAIR prompt + constrained scoring (sample)
  4. optional: zero-shot Ollama free generation -> invalid (hallucinated) leaf rate (sample)

    python -m evaluation.experiments.stair.run_searchtome [--zero-shot-n 100] [--ollama-n 50]
"""

import argparse
import datetime as dt
import hashlib
import json
import math
import random
import re
import time
from collections import Counter
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from backend.config import DATA_DIR, PROJECT_ROOT
from backend.rag.embeddings import get_embedder
from backend.rag.fusion import rrf, tokenize
from backend.stair_retriever.sft import BOOKS, SEARCHTOME_DIR, searchtome_examples, searchtome_toc_lines
from evaluation.metrics import capped_recall, ndcg

DOMAINS = list(BOOKS)
OUT = PROJECT_ROOT / "evaluation" / "experiments" / "stair" / "results"
PROC = DATA_DIR / "datasets" / "searchtome" / "processed"


def load(domain, name):
    return [json.loads(l) for l in open(SEARCHTOME_DIR / domain / f"{name}.jsonl", encoding="utf-8")]


def validate():
    report = {"release": "huggingface.co/datasets/meghanadh/SearchTome (official link in arXiv:2609.03874v2)",
              "label": "OFFICIAL RELEASE — reduced (one book per domain), differs from paper Table 1", "domains": {}}
    files = {}
    for d in DOMAINS:
        corpus = load(d, "corpus")
        titles = [c["title"] for c in corpus]
        tset = set(titles)
        dom = {"book": BOOKS[d], "leaves": len(titles), "duplicate_titles": len(titles) - len(tset),
               "empty_content_leaves": sum(1 for c in corpus if not c["content"].strip()), "splits": {}}
        texts = {}
        for s in ("train", "dev", "test"):
            rows = load(d, s)
            bad = [r["query_id"] for r in rows if r["gold_doc_title"] not in tset]
            texts[s] = {r["query"].strip().lower() for r in rows}
            dom["splits"][s] = {"queries": len(rows), "gold_valid": len(rows) - len(bad), "unanswerable": len(bad),
                                "unanswerable_ids": bad[:20],
                                "leaves_covered": len({r["gold_doc_title"] for r in rows if r["gold_doc_title"] in tset})}
        dom["query_text_overlap"] = {"train∩test": len(texts["train"] & texts["test"]),
                                     "train∩dev": len(texts["train"] & texts["dev"]), "dev∩test": len(texts["dev"] & texts["test"])}
        report["domains"][d] = dom
    for p in sorted(SEARCHTOME_DIR.rglob("*.jsonl")):
        files[p.relative_to(SEARCHTOME_DIR).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    report["raw_file_sha256"] = files
    PROC.mkdir(parents=True, exist_ok=True)
    (PROC / "validation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def flat_baselines(emb):
    res = {}
    for d in DOMAINS:
        corpus = load(d, "corpus")
        titles = [c["title"] for c in corpus]
        docs = [f"{c['title']}\n{c['content']}" for c in corpus]
        bm = BM25Okapi([tokenize(x) for x in docs])
        dv = emb.encode([x[:2000] for x in docs])
        test = [r for r in load(d, "test") if r["gold_doc_title"] in set(titles)]
        scores = {m: {"r@1": [], "r@3": [], "ndcg@3": []} for m in ("bm25", "dense_bge_m3", "hybrid_rrf")}
        qv = emb.encode([r["query"] for r in test], persist=False)
        for r, q in zip(test, qv):
            gold = {r["gold_doc_title"]}
            b = bm.get_scores(tokenize(r["query"]))
            rb = [titles[i] for i in np.argsort(-b)]
            rd = [titles[i] for i in np.argsort(-(dv @ q))]
            rh = [t for t, _ in rrf([rb[:50], rd[:50]])]
            for m, ranked in (("bm25", rb), ("dense_bge_m3", rd), ("hybrid_rrf", rh)):
                scores[m]["r@1"].append(capped_recall(ranked, gold, 1))
                scores[m]["r@3"].append(capped_recall(ranked, gold, 3))
                scores[m]["ndcg@3"].append(ndcg(ranked, gold, 3))
        res[d] = {"n_test": len(test), **{m: {k: sum(v) / len(v) for k, v in s.items()} for m, s in scores.items()}}
        print(d, json.dumps(res[d]))
    return res


def zero_shot_base(n, base_model, seed=3):
    from backend.stair_retriever.constrained import load_scorer
    sc = load_scorer(base_model)
    exs = searchtome_examples("medicine", "test", n, seed)
    hits1 = hits3 = 0
    t0 = time.time()
    for ex in exs:
        s = sc.score_candidates(ex["prompt"], ex["candidates"])
        ranked = [c for _, c in sorted(zip(s, ex["candidates"]), key=lambda x: -x[0])]
        hits1 += ranked[0] == ex["target"]
        hits3 += ex["target"] in ranked[:3]
    return {"domain": "medicine", "n": len(exs), "base_model": base_model, "constrained": True,
            "recall@1": hits1 / len(exs), "recall@3": hits3 / len(exs), "hits@1": hits1, "hits@3": hits3,
            "seconds_per_query": (time.time() - t0) / len(exs), "invalid_path_rate": 0.0,
            "note": "Out-of-the-box (no fine-tuning) baseline, analogous to the paper's 'Mistral out of the box'."}


def ollama_free(n, seed=4):
    from backend.llm.ollama_client import OllamaClient
    cli = OllamaClient()
    exs = searchtome_examples("medicine", "test", n, seed)
    invalid = exact = 0
    outs = []
    t0 = time.time()
    for ex in exs:
        out = cli.generate(ex["prompt"], max_tokens=40, temperature=0.0).strip().split("\n")[0]
        out = re.sub(r"^(leaf\s+)", "", out).strip()
        valid = out in set(ex["candidates"])
        invalid += not valid
        exact += out == ex["target"]
        outs.append({"query": ex["meta"]["query"], "output": out, "valid": valid, "gold": ex["target"]})
    return {"domain": "medicine", "n": len(exs), "model": cli.model, "constrained": False,
            "invalid_path_rate": invalid / len(exs), "exact_match": exact / len(exs), "invalid": invalid,
            "seconds_per_query": (time.time() - t0) / len(exs), "examples": outs[:10]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zero-shot-n", type=int, default=0)
    ap.add_argument("--ollama-n", type=int, default=0)
    ap.add_argument("--base-model", default="Qwen/Qwen2.5-0.5B-Instruct")
    ap.add_argument("--skip-flat", action="store_true")
    a = ap.parse_args()
    prev = OUT / "searchtome_results.json"
    out = json.loads(prev.read_text(encoding="utf-8")) if prev.exists() else {}   # merge with earlier runs
    out.update({"generated_at": dt.datetime.now().isoformat(timespec="seconds"), "validation": validate()})
    emb = get_embedder()
    if not a.skip_flat:
        out["flat_baselines_test"] = flat_baselines(emb)
    if a.zero_shot_n:
        out["stair_zero_shot_base_lm"] = zero_shot_base(a.zero_shot_n, a.base_model)
        print(out["stair_zero_shot_base_lm"])
    if a.ollama_n:
        out["ollama_free_generation"] = ollama_free(a.ollama_n)
        print({k: v for k, v in out["ollama_free_generation"].items() if k != "examples"})
    out["paper_reference_numbers_not_comparable"] = {
        "STAIR R@1": 0.826, "DSI R@1": 0.769, "BM25 R@1": 0.595, "DPR R@1": 0.687, "Mistral OOB R@1": 0.138,
        "note": "Paper averages over 18 books; this release has 6 books (3 differ from the paper). Do not compare directly."}
    out["fine_tuned_stair_searchtome"] = ("NOT RUN LOCALLY: CPU-only hardware. Use "
                                          "models/stair_clinical/configs/stair_cloud_gpu_training.ipynb.")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "searchtome_results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("wrote", OUT / "searchtome_results.json")


if __name__ == "__main__":
    main()
