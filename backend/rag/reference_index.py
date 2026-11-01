"""
Medical-reference retrieval over the hierarchical corpus.

Modes
  * bm25    — flat lexical retrieval over passages
  * dense   — flat BGE-M3 retrieval over passages (FAISS, inner product)
  * hybrid  — RRF(bm25, dense)
  * stair   — structure-aware: route the query to ToC sections first (STAIR-style,
              scored over section titles / descriptions / subsection headings), then
              retrieve supporting passages ONLY inside the selected sections (hybrid).
Every result carries its full Source > Chapter > Section > Subsection path.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import faiss
import numpy as np
from rank_bm25 import BM25Okapi

from backend import config
from backend.rag.embeddings import CachedEmbedder, get_embedder
from backend.rag.fusion import rrf, tokenize

PASSAGES = config.REFERENCE_INDEX_DIR / "reference_passages.jsonl"
TOC = config.REFERENCE_INDEX_DIR / "reference_toc.json"


def section_text(s: Dict[str, Any]) -> str:
    return f"{s['chapter']} > {s['section']}: {s.get('meta_desc') or ''} Subsections: {'; '.join(s['subsections'][:12])}"


def passage_text(p: Dict[str, Any]) -> str:
    return f"{p['section']} — {p['subsection']}: {p['text']}"


@dataclass
class RefHit:
    passage: Dict[str, Any]
    score: float
    rank: int
    method: str
    section_score: Optional[float] = None
    components: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        p = self.passage
        return {
            "evidence_id": p["passage_id"], "text": p["text"], "path": p["path"], "source": p["source"],
            "chapter": p["chapter"], "section": p["section"], "subsection": p["subsection"], "url": p["url"],
            "organization": p.get("organization"), "license": p["license"], "access_date": p.get("access_date"),
            "date_created": p.get("date_created"), "score": round(float(self.score), 5), "rank": self.rank,
            "method": self.method, "section_score": self.section_score,
        }


class ReferenceIndex:
    def __init__(self, embedder: Optional[CachedEmbedder] = None, use_dense: bool = True):
        self.passages: List[Dict[str, Any]] = [json.loads(l) for l in open(PASSAGES, encoding="utf-8")]
        self.sections: List[Dict[str, Any]] = json.loads(TOC.read_text(encoding="utf-8"))
        self.sec_index = {s["section_id"]: i for i, s in enumerate(self.sections)}
        self.by_section: Dict[str, List[int]] = {}
        for i, p in enumerate(self.passages):
            self.by_section.setdefault(p["section_id"], []).append(i)
        self.bm25 = BM25Okapi([tokenize(passage_text(p)) for p in self.passages])
        self.sec_bm25 = BM25Okapi([tokenize(section_text(s)) for s in self.sections])
        self.use_dense = use_dense
        self.embedder = embedder or (get_embedder() if use_dense else None)
        if use_dense:
            pv = self.embedder.encode([passage_text(p) for p in self.passages])
            sv = self.embedder.encode([section_text(s) for s in self.sections])
            self.p_index = faiss.IndexFlatIP(pv.shape[1]); self.p_index.add(pv)
            self.s_index = faiss.IndexFlatIP(sv.shape[1]); self.s_index.add(sv)
            self.p_vecs = pv

    # ------------------------------------------------------------- primitives
    def _bm25_rank(self, q: str, subset: Optional[Sequence[int]] = None, k: int = 50) -> List[int]:
        scores = self.bm25.get_scores(tokenize(q))
        idx = np.array(subset) if subset is not None else np.arange(len(self.passages))
        order = idx[np.argsort(-scores[idx])]
        return [int(i) for i in order[:k] if scores[i] > 0]

    def _dense_rank(self, qv: np.ndarray, subset: Optional[Sequence[int]] = None, k: int = 50):
        if subset is None:
            D, I = self.p_index.search(qv[None, :], k)
            return [int(i) for i in I[0] if i >= 0], {int(i): float(d) for i, d in zip(I[0], D[0])}
        sub = np.array(subset)
        sims = self.p_vecs[sub] @ qv
        order = np.argsort(-sims)[:k]
        return [int(sub[o]) for o in order], {int(sub[o]): float(sims[o]) for o in order}

    def route_sections(self, query: str, top_s: int = 5, qv: Optional[np.ndarray] = None) -> List[tuple]:
        """STAIR-style structural routing: score ToC sections, return [(section_id, score)]."""
        lex = self.sec_bm25.get_scores(tokenize(query))
        lex_rank = [int(i) for i in np.argsort(-lex)[:50] if lex[i] > 0]
        rankings = [lex_rank]
        if self.use_dense:
            qv = qv if qv is not None else self.embedder.encode_query(query)
            D, I = self.s_index.search(qv[None, :], 50)
            rankings.append([int(i) for i in I[0]])
        fused = rrf(rankings)[:top_s]
        return [(self.sections[i]["section_id"], s) for i, s in fused]

    # ----------------------------------------------------------------- public
    def search(self, query: str, k: int = 5, mode: str = "hybrid", top_sections: int = 4,
               expansions: Sequence[str] = ()) -> List[RefHit]:
        q = query if not expansions else f"{query} {' '.join(expansions)}"
        qv = self.embedder.encode_query(q) if self.use_dense and mode in ("dense", "hybrid", "stair") else None
        subset, sec_scores = None, {}
        if mode == "stair":
            routed = self.route_sections(q, top_sections, qv)
            sec_scores = dict(routed)
            subset = [i for sid, _ in routed for i in self.by_section.get(sid, [])]
            if not subset:
                return []
        if mode == "bm25" or (mode in ("hybrid", "stair") and not self.use_dense):
            ranked = [(i, 1.0 / (r + 1)) for r, i in enumerate(self._bm25_rank(q, subset, k=max(50, k)))]
            method = "bm25" if mode == "bm25" else f"{mode}_lexical_only"
        elif mode == "dense":
            order, sims = self._dense_rank(qv, subset, k)
            ranked = [(i, sims[i]) for i in order]
            method = "dense_bge_m3"
        else:
            lex = self._bm25_rank(q, subset, k=50)
            dense, _ = self._dense_rank(qv, subset, k=50)
            ranked = rrf([lex, dense])
            method = "stair_routed_hybrid_rrf" if mode == "stair" else "hybrid_rrf"
        hits = []
        for r, (i, s) in enumerate(ranked[:k], 1):
            p = self.passages[i]
            hits.append(RefHit(p, s, r, method, section_score=sec_scores.get(p["section_id"])))
        return hits


_ref: Optional[ReferenceIndex] = None


def get_reference_index() -> ReferenceIndex:
    global _ref
    if _ref is None:
        _ref = ReferenceIndex()
    return _ref
