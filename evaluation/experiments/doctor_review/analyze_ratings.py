"""
Analyse the returned doctor-review workbooks.

  python -m evaluation.experiments.doctor_review.analyze_ratings \
      --raters path/to/RaterA_filled.xlsx path/to/RaterB_filled.xlsx

Reports (results/doctor_review_summary.json + printed table):
  * completeness per rater
  * inter-rater agreement per item: exact agreement, quadratic-weighted Cohen's kappa (1-5 scales),
    Cohen's kappa (Y/N, acceptability), Krippendorff's alpha (ordinal for 1-5 scales, nominal otherwise)
  * per-variant mean of the two raters with patient-clustered bootstrap 95% CI
  * paired differences B4-B0, B5-B4, B5-B0 (patient-clustered bootstrap)
  * doctor "unsupported claim" vs. the automatic verifier (B4/B5 rows): agreement and kappa
"""
import argparse
import json
from collections import Counter, defaultdict
from itertools import combinations

from openpyxl import load_workbook

from backend.config import PROJECT_ROOT
from evaluation.metrics import cluster_bootstrap_ci, paired_cluster_bootstrap

HERE = PROJECT_ROOT / "evaluation/experiments/doctor_review"
SCORES = ["Correctness (1-5)", "History use (1-5)", "Safety (1-5)"]
YN = "Unsupported patient claim? (Y/N)"
ACC = "Acceptable to show a patient? (Yes / With edits / No)"
ACC_NUM = {"yes": 2, "with edits": 1, "no": 0}


def read_rater(path):
    ws = load_workbook(path, data_only=True)["Ratings"]
    head = [c.value for c in ws[1]]
    out = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        d = dict(zip(head, row))
        if d.get("Row") is None:
            continue
        rec = {}
        for s in SCORES:
            v = d.get(s)
            rec[s] = int(v) if v not in (None, "") and str(v).strip() in "12345" else None
        yn = str(d.get(YN) or "").strip().upper()[:1]
        rec[YN] = {"Y": 1, "N": 0}.get(yn)
        rec[ACC] = ACC_NUM.get(str(d.get(ACC) or "").strip().lower())
        rec["notes"] = d.get("Notes")
        out[int(d["Row"])] = rec
    return out


def cohen_kappa(a, b, cats, weights=None):
    """weights: None (nominal) or 'quadratic' (ordinal categories in order)."""
    n = len(a)
    if n == 0:
        return float("nan")
    idx = {c: i for i, c in enumerate(cats)}
    k = len(cats)
    w = [[(0 if i == j else 1) if weights is None else ((i - j) ** 2) / ((k - 1) ** 2) for j in range(k)]
         for i in range(k)]
    obs = [[0] * k for _ in range(k)]
    for x, y in zip(a, b):
        obs[idx[x]][idx[y]] += 1
    ra = [sum(obs[i]) for i in range(k)]
    cb = [sum(obs[i][j] for i in range(k)) for j in range(k)]
    po = sum(w[i][j] * obs[i][j] for i in range(k) for j in range(k)) / n
    pe = sum(w[i][j] * ra[i] * cb[j] for i in range(k) for j in range(k)) / (n * n)
    return float("nan") if pe == 0 else 1 - po / pe


def kripp_alpha(units, cats, ordinal=False):
    """units: list of lists of values (one list per rated item, missing removed)."""
    units = [u for u in units if len(u) >= 2]
    n_c = Counter(v for u in units for v in u)
    n = sum(n_c.values())
    if n <= 1:
        return float("nan")
    cats = [c for c in cats if n_c[c]] or cats

    def delta(c, k):
        if c == k:
            return 0.0
        if not ordinal:
            return 1.0
        i, j = sorted((cats.index(c), cats.index(k)))
        s = sum(n_c[cats[g]] for g in range(i, j + 1)) - (n_c[cats[i]] + n_c[cats[j]]) / 2
        return s * s

    do = sum(sum(delta(x, y) for x, y in combinations(u, 2)) * 2 / (len(u) - 1) for u in units) / n
    de = sum(n_c[c] * n_c[k] * delta(c, k) for c in cats for k in cats) / (n * (n - 1))
    return float("nan") if de == 0 else 1 - do / de


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raters", nargs="+", required=True)
    ap.add_argument("--key", default=str(HERE / "key/review_key.json"))
    ap.add_argument("--out", default=str(HERE / "results/doctor_review_summary.json"))
    a = ap.parse_args()
    key = {r["row"]: r for r in json.load(open(a.key, encoding="utf-8"))["rows"]}
    raters = [read_rater(p) for p in a.raters]
    items = SCORES + [YN, ACC]
    summary = {"n_answers": len(key), "raters": a.raters,
               "completeness": [{it: sum(r[row][it] is not None for row in r) for it in items} for r in raters]}

    # ---- agreement (first two raters)
    if len(raters) >= 2:
        A, B = raters[0], raters[1]
        agree = {}
        for it in items:
            pairs = [(A[r][it], B[r][it]) for r in key if r in A and r in B
                     and A[r][it] is not None and B[r][it] is not None]
            if not pairs:
                continue
            x, y = zip(*pairs)
            cats = [1, 2, 3, 4, 5] if it in SCORES else ([0, 1] if it == YN else [0, 1, 2])
            agree[it] = {"n": len(pairs), "exact_agreement": sum(p == q for p, q in pairs) / len(pairs),
                         "cohen_kappa": cohen_kappa(x, y, cats),
                         "kripp_alpha": kripp_alpha([[p, q] for p, q in pairs], cats, ordinal=it != YN)}
            if it in SCORES:
                agree[it]["weighted_kappa_quadratic"] = cohen_kappa(x, y, cats, "quadratic")
                agree[it]["within_1_point"] = sum(abs(p - q) <= 1 for p, q in pairs) / len(pairs)
        summary["agreement"] = agree

    # ---- per-variant means (average of available raters per answer)
    def mean_score(row, it):
        v = [r[row][it] for r in raters if row in r and r[row][it] is not None]
        return sum(v) / len(v) if v else None

    per_variant, paired = {}, {}
    for it in items:
        per_variant[it] = {}
        by_q = defaultdict(dict)
        for row, k in key.items():
            m = mean_score(row, it)
            if m is not None:
                by_q[k["question"]][k["variant"]] = (m, k["patient_id"])
        for v in ("B0", "B4", "B5"):
            vals = [(d[v][0], d[v][1]) for d in by_q.values() if v in d]
            if vals:
                mean, lo, hi = cluster_bootstrap_ci([x for x, _ in vals], [c for _, c in vals])
                per_variant[it][v] = {"n": len(vals), "mean": mean, "ci": [lo, hi]}
        paired[it] = {}
        for x, y in (("B4", "B0"), ("B5", "B4"), ("B5", "B0")):
            qs = [d for d in by_q.values() if x in d and y in d]
            if qs:
                paired[it][f"{x}-{y}"] = paired_cluster_bootstrap([d[x][0] for d in qs], [d[y][0] for d in qs],
                                                                  [d[x][1] for d in qs])
    summary["per_variant"], summary["paired"] = per_variant, paired

    # ---- doctors vs. automatic verifier on unsupported patient claims (B4/B5)
    auto_rows = []
    for row, k in key.items():
        if k["variant"] not in ("B4", "B5"):
            continue
        m = mean_score(row, YN)
        if m is None:
            continue
        if k["variant"] == "B5" and k.get("auto_unsupported_claims_released") not in (None, ""):
            auto = int(float(k["auto_unsupported_claims_released"]) > 0)
        else:
            rate = k.get("auto_unsupported_patient_claim_rate")
            if rate in (None, "", "nan"):
                continue
            auto = int(float(rate) > 0)
        auto_rows.append((auto, int(m >= 0.5)))
    if auto_rows:
        x, y = zip(*auto_rows)
        summary["auto_vs_doctor_unsupported"] = {
            "n": len(auto_rows), "agreement": sum(p == q for p, q in auto_rows) / len(auto_rows),
            "cohen_kappa": cohen_kappa(x, y, [0, 1]),
            "auto_yes_doctor_yes": sum(p and q for p, q in auto_rows),
            "auto_yes_doctor_no": sum(p and not q for p, q in auto_rows),
            "auto_no_doctor_yes": sum(q and not p for p, q in auto_rows),
            "auto_no_doctor_no": sum(not p and not q for p, q in auto_rows),
            "note": "doctor = majority/mean of raters >= 0.5; B5 auto = unsupported claims in the RELEASED text"}

    from pathlib import Path
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")

    print("completeness:", summary["completeness"])
    for it, g in summary.get("agreement", {}).items():
        extra = f"  wkappa {g['weighted_kappa_quadratic']:.2f}" if "weighted_kappa_quadratic" in g else ""
        print(f"agreement {it:55} n={g['n']} exact {g['exact_agreement']:.2f}  kappa {g['cohen_kappa']:.2f}"
              f"  alpha {g['kripp_alpha']:.2f}{extra}")
    for it in items:
        pv = "  ".join(f"{v} {d['mean']:.2f} [{d['ci'][0]:.2f},{d['ci'][1]:.2f}]" for v, d in per_variant[it].items())
        pd = "  ".join(f"{k} {d['diff']:+.2f} [{d['ci'][0]:+.2f},{d['ci'][1]:+.2f}]" for k, d in paired[it].items())
        print(f"{it:55} {pv}\n{'':55} {pd}")
    if "auto_vs_doctor_unsupported" in summary:
        print("auto verifier vs doctors:", summary["auto_vs_doctor_unsupported"])


if __name__ == "__main__":
    main()
