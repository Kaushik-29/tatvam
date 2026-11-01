"""
Offline STAIR-Clinical stage-1 prediction (GPU-friendly, database-free).

1. Locally:  python -m backend.stair_retriever.predict_stage1 export
   -> data/patient_retrieval/sft/stair_clinical_stage1_test_eval.jsonl
   The SAME stratified test sample as evaluation/.../run_retrieval_eval.py
   (split=test, sample=600, seed=2026), each with its rendered patient ToC prompt,
   valid candidate targets + their hierarchy paths, and gold paths.
2. On a GPU:  python -m backend.stair_retriever.predict_stage1 predict --adapter ... --base-model ...
   -> scores every valid candidate (constrained) and appends one JSON line per question.
   Safe to re-run after a disconnect: questions already in the output are skipped.
3. Locally:  run_retrieval_eval ... --stage1-predictions <file>  (PrecomputedSelector)
"""

import argparse
import json
import math
import time
from pathlib import Path

from backend.config import DATA_DIR

EXPORT = DATA_DIR / "patient_retrieval" / "sft" / "stair_clinical_stage1_test_eval.jsonl"


def export(split: str = "test", sample: int = 600, seed: int = 2026, out: Path = EXPORT):
    from collections import defaultdict
    from backend.patient_memory.db import session_scope
    from backend.patient_memory.repository import PatientMemory
    from backend.stair_retriever.prompts import clinical_stage1_prompt
    from backend.stair_retriever.selector import patient_header
    from backend.stair_retriever.sft import load_queries
    from evaluation.experiments.patient_context_retrieval.run_retrieval_eval import stratified_sample
    rows = stratified_sample(load_queries(split), sample, seed)
    by_pid = defaultdict(list)
    for r in rows:
        by_pid[r["patient_id"]].append(r)
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with session_scope() as s, open(out, "w", encoding="utf-8") as f:
        for pid, qs in sorted(by_pid.items()):
            mem = PatientMemory(s, pid)
            toc, header = mem.toc(), patient_header(mem)
            for q in qs:
                prompt, targets = clinical_stage1_prompt(header, toc, q["query"])
                f.write(json.dumps({
                    "example_id": q["example_id"], "patient_id": pid, "query": q["query"],
                    "category": q["query_category"], "prompt": prompt,
                    "candidates": [t for t, _ in targets], "candidate_paths": [p for _, p in targets],
                    "gold_paths": q["expected_leaf_paths"],
                }) + "\n")
                n += 1
    print(f"exported {n} questions ({len(by_pid)} patients) -> {out}")


def predict(inp: Path, out: Path, base_model: str, adapter: str, load_in_4bit: bool):
    import torch
    from backend.stair_retriever.constrained import CausalLMScorer
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel
    rows = [json.loads(l) for l in open(inp, encoding="utf-8")]
    done = set()
    if out.exists():
        done = {json.loads(l)["example_id"] for l in open(out, encoding="utf-8") if l.strip()}
    todo = [r for r in rows if r["example_id"] not in done]
    print(f"{len(rows)} questions, {len(done)} already done, {len(todo)} to go")
    if not todo:
        return summarize(out)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    half = torch.bfloat16 if device == "cuda" and torch.cuda.is_bf16_supported() else torch.float16
    tok = AutoTokenizer.from_pretrained(base_model)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    kw = {}
    if load_in_4bit:
        from transformers import BitsAndBytesConfig
        kw = {"quantization_config": BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=half,
                                                        bnb_4bit_quant_type="nf4"), "device_map": "auto"}
    else:
        kw = {"dtype": half if device == "cuda" else torch.float32}
    model = AutoModelForCausalLM.from_pretrained(base_model, **kw)
    if not load_in_4bit and device == "cuda":
        model.to(device)
    if adapter:
        model = PeftModel.from_pretrained(model, adapter)
    scorer = CausalLMScorer(model, tok, device=device)
    t0 = time.time()
    with open(out, "a", encoding="utf-8") as f:
        for i, r in enumerate(todo, 1):
            lps = scorer.score_candidates(r["prompt"], r["candidates"])
            m = max(lps)
            z = sum(math.exp(x - m) for x in lps)
            ranked = sorted(zip(r["candidate_paths"], r["candidates"], lps), key=lambda x: -x[2])
            f.write(json.dumps({"example_id": r["example_id"], "patient_id": r["patient_id"], "query": r["query"],
                                "category": r["category"], "gold_paths": r["gold_paths"],
                                "ranked": [{"path": p, "target": t, "logprob": lp, "prob": math.exp(lp - m) / z}
                                           for p, t, lp in ranked],
                                "base_model": base_model, "adapter": adapter}) + "\n")
            f.flush()
            if i % 25 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)} ({(time.time() - t0) / i:.1f}s/question)", flush=True)
    return summarize(out)


def summarize(out: Path):
    rows = [json.loads(l) for l in open(out, encoding="utf-8") if l.strip()]
    norm = lambda p: p.replace("encounter_dates", "consultations")
    h1 = h3 = 0
    for r in rows:
        gold = {norm(g) for g in r["gold_paths"]}
        top = [norm(x["path"]) for x in r["ranked"]]
        h1 += top[0] in gold
        h3 += bool(gold & set(top[:3]))
    res = {"n": len(rows), "section_hit@1": h1 / len(rows), "section_hit@3": h3 / len(rows), "hits@1": h1, "hits@3": h3}
    print(json.dumps(res))
    return res


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("export")
    p = sub.add_parser("predict")
    p.add_argument("--input", default=str(EXPORT))
    p.add_argument("--output", required=True)
    p.add_argument("--base-model", required=True)
    p.add_argument("--adapter", default=None)
    p.add_argument("--load-in-4bit", action="store_true")
    a = ap.parse_args()
    if a.cmd == "export":
        export()
    else:
        predict(Path(a.input), Path(a.output), a.base_model, a.adapter, a.load_in_4bit)


if __name__ == "__main__":
    main()
