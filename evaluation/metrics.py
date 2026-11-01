"""Retrieval metrics and patient-clustered bootstrap confidence intervals."""

import math
import random
from collections import defaultdict
from typing import Dict, List, Sequence, Set


def capped_recall(ranked: Sequence[str], gold: Set[str], k: int) -> float:
    """BEIR-style capped recall: |gold ∩ top-k| / min(|gold|, k)."""
    if not gold:
        return float("nan")
    return len(gold & set(ranked[:k])) / min(len(gold), k)


def mrr(ranked: Sequence[str], gold: Set[str]) -> float:
    for i, r in enumerate(ranked, 1):
        if r in gold:
            return 1.0 / i
    return 0.0


def ndcg(ranked: Sequence[str], gold: Set[str], k: int) -> float:
    dcg = sum(1.0 / math.log2(i + 1) for i, r in enumerate(ranked[:k], 1) if r in gold)
    ideal = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(gold), k) + 1))
    return dcg / ideal if ideal else float("nan")


def cluster_bootstrap_ci(values: Sequence[float], clusters: Sequence[str], n_boot: int = 1000,
                         seed: int = 7, alpha: float = 0.05):
    """Mean with a percentile CI from resampling PATIENTS (queries of a patient are correlated)."""
    by = defaultdict(list)
    for v, c in zip(values, clusters):
        if not math.isnan(v):
            by[c].append(v)
    keys = list(by)
    if not keys:
        return float("nan"), float("nan"), float("nan")
    flat = [v for k in keys for v in by[k]]
    mean = sum(flat) / len(flat)
    rng = random.Random(seed)
    stats = []
    for _ in range(n_boot):
        sample = [v for k in (rng.choice(keys) for _ in keys) for v in by[k]]
        stats.append(sum(sample) / len(sample))
    stats.sort()
    lo = stats[int(alpha / 2 * n_boot)]
    hi = stats[int((1 - alpha / 2) * n_boot) - 1]
    return mean, lo, hi


def paired_cluster_bootstrap(a: Sequence[float], b: Sequence[float], clusters: Sequence[str],
                             n_boot: int = 1000, seed: int = 11):
    """Mean difference (a - b) with patient-clustered percentile CI and two-sided bootstrap p-value."""
    by = defaultdict(list)
    for x, y, c in zip(a, b, clusters):
        if not (math.isnan(x) or math.isnan(y)):
            by[c].append(x - y)
    keys = list(by)
    diffs = [d for k in keys for d in by[k]]
    if not diffs:
        return {"diff": float("nan"), "ci": [float("nan")] * 2, "p": float("nan"), "n": 0}
    mean = sum(diffs) / len(diffs)
    rng = random.Random(seed)
    stats = []
    for _ in range(n_boot):
        s = [d for k in (rng.choice(keys) for _ in keys) for d in by[k]]
        stats.append(sum(s) / len(s))
    stats.sort()
    p = 2 * min(sum(1 for s in stats if s <= 0), sum(1 for s in stats if s >= 0)) / n_boot
    return {"diff": mean, "ci": [stats[int(0.025 * n_boot)], stats[int(0.975 * n_boot) - 1]],
            "p_bootstrap": min(1.0, p), "n_queries": len(diffs), "n_patients": len(keys)}
