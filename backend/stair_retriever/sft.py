"""
Supervised fine-tuning examples for original STAIR (SearchTome) and STAIR-Clinical.

Each example: {"prompt", "target", "candidates", "gold_targets", "meta"}.
`candidates` = every valid ToC target for that prompt (used for constrained
scoring at evaluation time); `target` is ONE gold target (multi-gold queries are
expanded into one example per gold path — the top-k extension of STAIR).
"""

import json
import random
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.config import DATA_DIR
from backend.patient_memory.db import session_scope
from backend.patient_memory.hierarchy import LEAF_BY_PATH
from backend.patient_memory.repository import PatientMemory
from backend.stair_retriever.prompts import (
    clinical_stage1_prompt, clinical_stage2_prompt, original_stair_prompt,
)

SEARCHTOME_DIR = DATA_DIR / "datasets" / "searchtome" / "raw" / "official_hf_meghanadh"
BOOKS = {
    "education": "Action Research", "finance": "Principles of Financial Accounting",
    "law": "Introduction to Intellectual Property", "medicine": "Nursing Assistant",
    "natural_sciences": "Introduction to Soil Science", "social_sciences": "Foundations of Aural Skills",
}
SPLIT_FILES = {"train": "train", "validation": "dev", "dev": "dev", "test": "test"}


# --------------------------------------------------------------- SearchTome
def searchtome_toc(domain: str) -> List[str]:
    rows = [json.loads(l) for l in open(SEARCHTOME_DIR / domain / "corpus.jsonl", encoding="utf-8")]
    return [r["title"] for r in rows]


def searchtome_toc_lines(titles: List[str]) -> List[str]:
    """Rebuild a hierarchical ToC from the numbered leaf titles (chapters inferred from numbering)."""
    lines, seen = [], set()
    for t in titles:
        m = re.match(r"(\d+)\.", t)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            lines.append(f"{m.group(1)} Chapter {m.group(1)}")
        lines.append(f"leaf {t}")
    return lines


def searchtome_examples(domain: str, split: str, limit: Optional[int] = None, seed: int = 0) -> List[Dict[str, Any]]:
    titles = searchtome_toc(domain)
    valid = set(titles)
    lines = searchtome_toc_lines(titles)
    rows = [json.loads(l) for l in open(SEARCHTOME_DIR / domain / f"{SPLIT_FILES[split]}.jsonl", encoding="utf-8")]
    out = []
    for r in rows:
        if r["gold_doc_title"] not in valid:      # unanswerable: excluded and reported by the validator
            continue
        out.append({"prompt": original_stair_prompt(BOOKS[domain], lines, r["query"]),
                    "target": r["gold_doc_title"], "candidates": titles, "gold_targets": [r["gold_doc_title"]],
                    "meta": {"domain": domain, "query_id": r["query_id"], "query": r["query"]}})
    if limit and len(out) > limit:
        out = random.Random(seed).sample(out, limit)
    return out


# ----------------------------------------------------------- STAIR-Clinical
def load_queries(split: str) -> List[Dict[str, Any]]:
    path = DATA_DIR / "patient_retrieval" / split / "queries.jsonl"
    return [json.loads(l) for l in open(path, encoding="utf-8")]


def clinical_examples(split: str, stage: int = 1, limit: Optional[int] = None, seed: int = 0,
                      expand_multi_gold: bool = True, max_groups_per_leaf: int = 60) -> List[Dict[str, Any]]:
    from backend.stair_retriever.selector import leaf_nodes, patient_header
    queries = load_queries(split)
    rng = random.Random(seed)
    if limit:
        # sample whole queries first (stable), then expand
        queries = rng.sample(queries, min(limit, len(queries)))
    by_patient = defaultdict(list)
    for q in queries:
        by_patient[q["patient_id"]].append(q)
    out = []
    with session_scope() as s:
        for pid, qs in by_patient.items():
            mem = PatientMemory(s, pid)
            toc = mem.toc()
            header = patient_header(mem)
            nodes = {n.path: n for n in leaf_nodes(toc)}
            for q in qs:
                if stage == 1:
                    prompt, targets = clinical_stage1_prompt(header, toc, q["query"])
                    t2p = dict(targets)
                    p2t = {p: t for t, p in targets}
                    gold = [p2t[p] for p in q["expected_leaf_paths"] if p in p2t]
                    if not gold:
                        continue
                    for g in (gold if expand_multi_gold else gold[:1]):
                        out.append({"prompt": prompt, "target": g, "candidates": list(t2p), "gold_targets": gold,
                                    "meta": {"patient_id": pid, "query": q["query"], "example_id": q["example_id"],
                                             "category": q["query_category"], "stage": 1}})
                else:
                    for lp in q["expected_leaf_paths"]:
                        node = nodes.get(lp)
                        if node is None or not node.children:
                            continue
                        prompt, targets = clinical_stage2_prompt(node, q["query"], max_groups_per_leaf)
                        p2t = {p: t for t, p in targets}
                        gold = [p2t[g] for g in q["expected_group_paths"] if g in p2t]
                        if not gold:
                            continue
                        for g in (gold[:2] if expand_multi_gold else gold[:1]):
                            out.append({"prompt": prompt, "target": g, "candidates": [t for t, _ in targets],
                                        "gold_targets": gold,
                                        "meta": {"patient_id": pid, "query": q["query"], "example_id": q["example_id"],
                                                 "category": q["query_category"], "stage": 2, "leaf": lp}})
    rng.shuffle(out)
    return out


def export_jsonl(out_dir: Path, stage: int, limits: Dict[str, Optional[int]], seed: int = 0) -> Dict[str, Any]:
    """Pre-renders STAIR-Clinical SFT examples (prompt with the patient's ToC, valid candidates, gold)
    so GPU training can run without the patient database. Patient data in prompts is synthetic (Synthea)."""
    import hashlib
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"stage": stage, "seed": seed, "files": {}}
    for split, lim in limits.items():
        exs = clinical_examples(split, stage, lim, seed, expand_multi_gold=(split == "train"))
        path = out_dir / f"stair_clinical_stage{stage}_{split}.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for e in exs:
                f.write(json.dumps(e) + "\n")
        manifest["files"][path.name] = {"examples": len(exs), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    (out_dir / f"stair_clinical_stage{stage}_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def load_jsonl(path: Path, limit: Optional[int] = None, seed: int = 0) -> List[Dict[str, Any]]:
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    if limit and len(rows) > limit:
        rows = random.Random(seed).sample(rows, limit)
    return rows


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Export STAIR-Clinical SFT JSONL for cloud GPU training")
    ap.add_argument("--stage", type=int, default=1)
    ap.add_argument("--out", default=str(DATA_DIR / "patient_retrieval" / "sft"))
    ap.add_argument("--validation-limit", type=int, default=400)
    a = ap.parse_args()
    print(json.dumps(export_jsonl(Path(a.out), a.stage, {"train": None, "validation": a.validation_limit}), indent=2))
