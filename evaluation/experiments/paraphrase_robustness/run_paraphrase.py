"""
Paraphrase robustness of patient-context retrieval.

The retrieval test questions are template-generated, and query understanding uses regular
expressions that match those templates (e.g. the episode anchor "when I had <X> in <month>").
This experiment re-asks the SAME sampled test questions (same patients, same gold evidence) in
different wording and measures how much each retrieval method drops.

Paraphrases are written by the app's own local model (Ollama llama3.2:3b; run on a Kaggle GPU with
scripts/kaggle_answer_generation.py — no external API, no restricted data leaves the user's control).
Scope: the rewrite must keep every medical name, test, medicine, month and year, so this measures
robustness to sentence structure and wording around the clinical terms, not to synonyms of the terms.

  1. python -m evaluation.experiments.paraphrase_robustness.run_paraphrase export
       -> results/kaggle/paraphrase_prompts_<dataset>.jsonl            (upload to Kaggle, run Cell 2)
  2. python -m ... import --answers-dir <folder with answers_paraphrase_prompts_*.jsonl>
       -> data/paraphrase_robustness/<dataset>/queries.jsonl  (validated paraphrases only)
       -> data/paraphrase_robustness/<dataset>/stage1_<dataset>_para_eval.jsonl  (Mistral router input)
  3. run_retrieval_eval --queries data/paraphrase_robustness/<dataset>/queries.jsonl --sample 0 ...
  4. python -m ... compare    -> results/paraphrase_robustness_summary.json
"""

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from backend.config import DATA_DIR, PROJECT_ROOT

HERE = PROJECT_ROOT / "evaluation" / "experiments" / "paraphrase_robustness"
RES = HERE / "results"
OUT_DATA = DATA_DIR / "paraphrase_robustness"
RET_RES = PROJECT_ROOT / "evaluation" / "experiments" / "patient_context_retrieval" / "results"
SAMPLE, SEED = 600, 2026          # identical to the frozen retrieval evaluation

DATASETS = {
    "synthea": {"queries": DATA_DIR / "patient_retrieval" / "test" / "queries.jsonl",
                "original_results": "retrieval_eval_test_mistral_trained_episodefix"},
    "mimic": {"queries": DATA_DIR / "patient_retrieval_mimic_iv_fhir_demo" / "test" / "queries.jsonl",
              "original_results": "retrieval_eval_mimic_demo_mistral_episodefix"},
    "eicu": {"queries": DATA_DIR / "patient_retrieval_eicu_crd_demo" / "test" / "queries.jsonl",
             "original_results": "retrieval_eval_eicu_demo_mistral_episodefix"},
}
MODEL = "llama3.2:3b"
SYSTEM = ("You rewrite questions. You never answer them. You output only the rewritten question, "
          "on one line, with no quotes and no explanation.")
PROMPT = ("Rewrite this question about a patient's health record so it is worded differently, the way a "
          "real patient or doctor might ask it. Change the sentence structure and the ordinary words. "
          "Keep the meaning exactly the same. Keep every condition, symptom, test, medicine and procedure "
          "name, and every month and year, exactly as written. Keep whether it is about 'I/my' or "
          "'the patient'. Do not add anything that is not in the question, such as a time period, a reason "
          "or an extra test.\n\nQuestion: {q}\nRewritten question:")
OPTIONS = {"temperature": 0.7, "num_predict": 80, "seed": 2026, "num_ctx": 2048}

YEAR_RE = re.compile(r"\b(?:19|20|21)\d\d\b")
MONTH_RE = re.compile(r"\b(january|february|march|april|may|june|july|august|september|october|november|"
                      r"december)\b")
WORD_RE = re.compile(r"[a-z0-9]+")
# a paraphrase must not add a time window ("over the past 12 months"): that changes the question
TIME_RE = re.compile(r"\b(?:past|last|previous|recent)\s+(?:\d+|one|two|three|six|twelve|few|several)?\s*"
                     r"(?:days?|weeks?|months?|years?)\b|\bthis (?:year|month)\b")


def sampled(ds):
    from evaluation.experiments.patient_context_retrieval.run_retrieval_eval import stratified_sample
    rows = [json.loads(l) for l in open(DATASETS[ds]["queries"], encoding="utf-8")]
    return rows, stratified_sample(rows, SAMPLE, SEED)


def template_words(rows, share=0.02):
    """Words used by many questions of the dataset come from the templates ('medications', 'trend', 'my');
    the rest are the clinical names a paraphrase must keep. Data-driven, per dataset."""
    df = Counter()
    for r in rows:
        df.update(set(WORD_RE.findall(r["query"].lower())))
    return {w for w, c in df.items() if c / len(rows) >= share}


def clean(text):
    t = text.strip().splitlines()[0] if text.strip() else ""
    t = re.sub(r"^(rewritten question|question)\s*:\s*", "", t, flags=re.I).strip().strip('"“”\'')
    return t


def validate(orig, para, tmpl):
    """Accept only paraphrases that keep the facts the gold evidence depends on."""
    o, p = orig.lower(), para.lower()
    if not para or len(para) < 8 or len(para) > 3 * len(orig) + 40:
        return "empty_or_length"
    if WORD_RE.findall(o) == WORD_RE.findall(p):
        return "unchanged"
    if Counter(YEAR_RE.findall(o)) != Counter(YEAR_RE.findall(p)) or set(MONTH_RE.findall(o)) != set(MONTH_RE.findall(p)):
        return "date_changed"
    if TIME_RE.search(p) and not TIME_RE.search(o):
        return "time_period_added"
    names = [w for w in WORD_RE.findall(o) if w not in tmpl and not w.isdigit() and len(w) > 2]
    pw = set(WORD_RE.findall(p))
    if names and sum(w in pw for w in names) / len(names) < 0.8:
        return "clinical_name_changed"
    return None


def attempts_for(ds, eid, answers):
    """Answers for one question in attempt order: first try, then the retries (#2, #3, ...)."""
    out, k = [], 1
    while True:
        g = answers.get(f"{ds}:{eid}" + ("" if k == 1 else f"#{k}"))
        if g is None and k > 1:
            return out
        out.append(g)
        k += 1


def load_answers(ds, answers_dir):
    ans = {}
    for fp in sorted(Path(answers_dir).glob(f"answers_paraphrase_prompts_{ds}*.jsonl")):
        for l in open(fp, encoding="utf-8"):
            if l.strip():
                r = json.loads(l)
                ans[r["id"]] = r
    return ans


def export(a):
    """First export: every sampled question. --retry N: only questions with no accepted paraphrase in
    attempts 1..N-1, with a different sampling seed. The same validator decides; attempts are reported."""
    RES.joinpath("kaggle").mkdir(parents=True, exist_ok=True)
    for ds in a.datasets:
        all_rows, rows = sampled(ds)
        suffix, opts = "", OPTIONS
        if a.retry:
            tmpl, ans = template_words(all_rows), load_answers(ds, a.answers_dir)
            rows = [r for r in rows
                    if not any(g and not validate(r["query"], clean(g["response"]), tmpl)
                               for g in attempts_for(ds, r["example_id"], ans))]
            suffix, opts = f"_try{a.retry}", {**OPTIONS, "seed": OPTIONS["seed"] + a.retry - 1}
        out = RES / "kaggle" / f"paraphrase_prompts_{ds}{suffix}.jsonl"
        if out.exists():
            raise SystemExit(f"{out} exists; frozen exports are not overwritten")
        with open(out, "w", encoding="utf-8") as f:
            for r in rows:
                rid = f"{ds}:{r['example_id']}" + (f"#{a.retry}" if a.retry else "")
                f.write(json.dumps({"id": rid, "model": MODEL, "today": None, "system": SYSTEM,
                                    "prompt": PROMPT.format(q=r["query"]), "options": opts}) + "\n")
        print(f"{ds}: {len(rows)} prompts -> {out}")


def do_import(a):
    from backend.stair_retriever.predict_stage1 import export as stage1_export
    rep_file = RES / "paraphrase_import_report.json"
    report = json.loads(rep_file.read_text(encoding="utf-8")) if rep_file.exists() else {}
    for ds in a.datasets:
        all_rows, rows = sampled(ds)
        tmpl = template_words(all_rows)
        ans = load_answers(ds, a.answers_dir)
        kept, reasons, meta, by_attempt = [], Counter(), None, Counter()
        for r in rows:
            tries = [g for g in attempts_for(ds, r["example_id"], ans) if g is not None]
            if not tries:
                reasons["missing"] += 1
                continue
            why = None
            for k, g in enumerate(tries, 1):
                meta = meta or {x: g.get(x) for x in ("model", "model_digest", "ollama_version", "hardware")}
                para = clean(g["response"])
                why = validate(r["query"], para, tmpl)
                if not why:
                    by_attempt[k] += 1
                    kept.append({**r, "query": para, "original_query": r["query"], "paraphrase_attempt": k})
                    break
            if why:
                reasons[why] += 1          # reason of the last attempt
        d = OUT_DATA / ds
        d.mkdir(parents=True, exist_ok=True)
        qf = d / "queries.jsonl"
        with open(qf, "w", encoding="utf-8") as f:
            for r in kept:
                f.write(json.dumps(r) + "\n")
        stage1_export(sample=0, seed=SEED, out=d / f"stage1_{ds}_para_eval.jsonl", queries=str(qf))
        report[ds] = {"sampled": len(rows), "accepted": len(kept), "accepted_by_attempt": dict(by_attempt),
                      "rejected_after_last_attempt": dict(reasons),
                      "acceptance_rate": round(len(kept) / len(rows), 3), "generator": meta,
                      "paraphrase_sha256": hashlib.sha256(qf.read_bytes()).hexdigest()}
        print(ds, report[ds])
    RES.mkdir(parents=True, exist_ok=True)
    rep_file.write_text(json.dumps(report, indent=1), encoding="utf-8")


def compare(a):
    from evaluation.metrics import cluster_bootstrap_ci, paired_cluster_bootstrap
    summary = {}
    for ds in a.datasets:
        para_file = RET_RES / f"retrieval_eval_{ds}_paraphrase_per_query.jsonl"
        if not para_file.exists():
            print(f"{ds}: no paraphrase results yet ({para_file.name})")
            continue
        orig = {(r["method"], r["example_id"]): r for r in map(json.loads, open(
            RET_RES / f"{DATASETS[ds]['original_results']}_per_query.jsonl", encoding="utf-8"))}
        para = [json.loads(l) for l in open(para_file, encoding="utf-8")]
        out = {}
        for m in sorted({r["method"] for r in para}):
            pr = [r for r in para if r["method"] == m and (m, r["example_id"]) in orig]
            if not pr:
                continue
            o = [orig[(m, r["example_id"])]["recall@5"] for r in pr]
            p = [r["recall@5"] for r in pr]
            cl = [r["patient_id"] for r in pr]
            ci = lambda v: dict(zip(("mean", "lo", "hi"), cluster_bootstrap_ci(v, cl)))
            out[m] = {"n": len(pr), "original_recall@5": ci(o),
                      "paraphrase_recall@5": ci(p),
                      "paraphrase_minus_original": paired_cluster_bootstrap(p, o, cl)}
            cats = {}
            for c in sorted({r["category"] for r in pr}):
                idx = [i for i, r in enumerate(pr) if r["category"] == c]
                cats[c] = {"n": len(idx), "original": round(sum(o[i] for i in idx) / len(idx), 3),
                           "paraphrase": round(sum(p[i] for i in idx) / len(idx), 3)}
            out[m]["by_category"] = cats
        # does each method's advantage over the R4 baseline survive rewording? (paired, same questions)
        base = "R4_hybrid_structured"
        p_by = {(r["method"], r["example_id"]): r for r in para}
        gaps = {}
        for m in out:
            if m == base:
                continue
            ids = [r["example_id"] for r in para if r["method"] == m and (base, r["example_id"]) in p_by
                   and (m, r["example_id"]) in orig and (base, r["example_id"]) in orig]
            cl = [p_by[(m, i)]["patient_id"] for i in ids]
            gaps[m] = {f"{w}_minus_R4": paired_cluster_bootstrap([src[(m, i)]["recall@5"] for i in ids],
                                                                [src[(base, i)]["recall@5"] for i in ids], cl)
                       for w, src in (("original", orig), ("paraphrase", p_by))}
        out["_vs_R4"] = gaps
        summary[ds] = out
        for m, v in out.items():
            if m.startswith("_"):
                continue
            d = v["paraphrase_minus_original"]
            print(f"{ds:8} {m:30} n={v['n']} orig {v['original_recall@5']['mean']:.3f} -> para "
                  f"{v['paraphrase_recall@5']['mean']:.3f}  diff {d['diff']:+.3f} [{d['ci'][0]:+.3f}, {d['ci'][1]:+.3f}]")
        for m, g in gaps.items():
            o, p = g["original_minus_R4"], g["paraphrase_minus_R4"]
            print(f"{ds:8} {m:30} vs R4: original {o['diff']:+.3f} [{o['ci'][0]:+.3f}, {o['ci'][1]:+.3f}]"
                  f"  paraphrase {p['diff']:+.3f} [{p['ci'][0]:+.3f}, {p['ci'][1]:+.3f}]")
    RES.mkdir(parents=True, exist_ok=True)
    (RES / "paraphrase_robustness_summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["export", "import", "compare"])
    ap.add_argument("--datasets", nargs="+", default=list(DATASETS))
    ap.add_argument("--answers-dir", default=str(RES / "kaggle"))
    ap.add_argument("--retry", type=int, default=0, help="export: attempt number (2, 3, ...) for unaccepted questions")
    a = ap.parse_args()
    {"export": export, "import": do_import, "compare": compare}[a.cmd](a)


if __name__ == "__main__":
    main()
