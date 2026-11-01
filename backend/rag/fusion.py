"""Shared ranking utilities: tokenizer, Reciprocal Rank Fusion."""

import re
from typing import Dict, Hashable, List, Sequence, Tuple

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "are", "was", "were", "be", "been",
    "my", "me", "i", "i'm", "i've", "you", "your", "it", "its", "this", "that", "with", "by", "at", "as",
    "do", "does", "did", "have", "has", "had", "what", "which", "when", "how", "any", "there", "from",
    "patient", "patient's", "their", "they", "them", "about", "can", "could", "should", "would", "will",
}


def tokenize(text: str) -> List[str]:
    toks = re.findall(r"[a-z0-9][a-z0-9\-/]*", (text or "").lower())
    return [t for t in toks if t not in STOPWORDS and len(t) > 1]


def rrf(rankings: Sequence[Sequence[Hashable]], k: int = 60,
        weights: Sequence[float] = ()) -> List[Tuple[Hashable, float]]:
    """Reciprocal Rank Fusion (Cormack et al., 2009): score(d) = sum_i w_i / (k + rank_i(d))."""
    scores: Dict[Hashable, float] = {}
    for j, ranking in enumerate(rankings):
        w = weights[j] if j < len(weights) else 1.0
        for r, item in enumerate(ranking, 1):
            scores[item] = scores.get(item, 0.0) + w / (k + r)
    return sorted(scores.items(), key=lambda x: (-x[1], str(x[0])))
