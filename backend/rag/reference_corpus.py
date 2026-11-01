"""
Hierarchical medical-reference corpus.

Builds one structure-preserving corpus from:
  * MedlinePlus Health Topics XML (public-domain summaries, NLM), and
  * the existing MedResolve curated guideline KB (data/knowledge_base_v2).

Hierarchy: Source > Chapter > Section > Subsection > Paragraph passages.
  MedlinePlus: Source=MedlinePlus, Chapter=topic group, Section=health topic,
               Subsection=<h3> heading of the full summary, passages=<p>/<li>/table rows.
  KB v2:       Source=issuing organization, Chapter=document, Section=section heading.

Usage:
    python -m backend.rag.reference_corpus     # writes data/datasets/medical_knowledge/processed/
"""

import datetime as dt
import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any, Dict, List

from lxml import etree
from lxml import html as lhtml

from backend.config import DATA_DIR, PROJECT_ROOT

RAW = DATA_DIR / "datasets" / "medical_knowledge" / "raw" / "medlineplus"
OUT = DATA_DIR / "datasets" / "medical_knowledge" / "processed"
KB_V2 = DATA_DIR / "knowledge_base_v2"
POPULATION_GROUPS = {"Children", "Teenagers", "Women", "Men", "Older Adults", "Seniors", "Infants",
                     "Population Groups", "Pregnancy and Reproduction"}
MEDLINE_LICENSE = ("U.S. National Library of Medicine — MedlinePlus health-topic summary; public domain "
                   "(https://medlineplus.gov/about/using/usingcontent/)")


def _clean(t: str) -> str:
    return " ".join(html.unescape(t or "").split())


def parse_medlineplus(xml_path: Path) -> List[Dict[str, Any]]:
    root = etree.parse(str(xml_path)).getroot()
    generated = root.get("date-generated")
    passages = []
    for topic in root.findall("health-topic"):
        if topic.get("language") != "English":
            continue
        groups = [g.text for g in topic.findall("group")]
        chapter = next((g for g in groups if g not in POPULATION_GROUPS), groups[0] if groups else "General")
        title = topic.get("title")
        tid = topic.get("id")
        summary = topic.findtext("full-summary") or ""
        meta = {
            "source": "MedlinePlus", "chapter": chapter, "section": title, "section_id": f"MPLUS_{tid}",
            "url": topic.get("url"), "date_created": topic.get("date-created"),
            "xml_date_generated": generated, "access_date": "2026-11-01", "license": MEDLINE_LICENSE,
            "organization": "U.S. National Library of Medicine (MedlinePlus)",
            "also_called": [a.text for a in topic.findall("also-called")],
            "see_references": [a.text for a in topic.findall("see-reference")],
            "related_topics": [r.text for r in topic.findall("related-topic")],
            "groups": groups, "meta_desc": topic.get("meta-desc"),
            "primary_institute": topic.findtext("primary-institute"),
            "links": [{"title": s.get("title"), "url": s.get("url")} for s in topic.findall("site")][:15],
        }
        doc = lhtml.fragment_fromstring(summary, create_parent="div")
        subsection, n = "Overview", 0
        for el in doc.iter():
            tag = el.tag if isinstance(el.tag, str) else ""
            if tag in ("h2", "h3", "h4"):
                subsection = _clean(el.text_content()) or subsection
                continue
            text = ""
            if tag == "p" or (tag == "li" and el.getparent() is not None):
                text = _clean(el.text_content())
            elif tag == "tr":
                cells = [_clean(c.text_content()) for c in el if isinstance(c.tag, str)]
                text = " | ".join(c for c in cells if c)
            if len(text) < 25:
                continue
            n += 1
            passages.append({
                "passage_id": f"MPLUS_{tid}_P{n:03d}", "text": text, "subsection": subsection,
                "path": f"MedlinePlus/{chapter}/{title}/{subsection}", **meta,
            })
    return passages


def parse_kb_v2() -> List[Dict[str, Any]]:
    out = []
    for f in sorted((KB_V2 / "documents").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        org = d["author_or_organization"]
        for p in d["passages"]:
            out.append({
                "passage_id": p["passage_id"], "text": p["text"], "subsection": p["section_heading"],
                "source": "MedResolve curated KB v2", "chapter": d["title"], "section": p["section_heading"],
                "section_id": f"{d['document_id']}::{p['section_heading']}",
                "path": f"KBv2/{d['title']}/{p['section_heading']}", "url": d["source_url"],
                "date_created": d.get("publication_or_revision_date"), "access_date": d.get("access_date"),
                "license": d["license_or_reuse_conditions"], "organization": org,
                "also_called": [], "see_references": [], "related_topics": [], "groups": [],
                "meta_desc": d["title"], "links": [],
                "provenance_note": "Passage text curated in MedResolve Phase 5 (pre-existing corpus); "
                                   "see docs/knowledge_corpus.md for its curation record.",
            })
    return out


def build() -> Dict[str, Any]:
    xmls = sorted((RAW / "extracted").glob("mplus_topics_*.xml"))
    if not xmls:
        raise FileNotFoundError("Run scripts/download_datasets.py --only medlineplus and unzip first")
    passages = parse_medlineplus(xmls[-1]) + parse_kb_v2()
    OUT.mkdir(parents=True, exist_ok=True)
    pfile = OUT / "reference_passages.jsonl"
    with open(pfile, "w", encoding="utf-8") as f:
        for p in passages:
            f.write(json.dumps(p) + "\n")
    toc: Dict[str, Dict[str, Any]] = {}
    for p in passages:
        sec = toc.setdefault(p["section_id"], {
            "section_id": p["section_id"], "source": p["source"], "chapter": p["chapter"], "section": p["section"],
            "meta_desc": p.get("meta_desc"), "url": p["url"], "subsections": [], "n_passages": 0,
            "also_called": p.get("also_called", []), "see_references": p.get("see_references", [])})
        if p["subsection"] not in sec["subsections"]:
            sec["subsections"].append(p["subsection"])
        sec["n_passages"] += 1
    tfile = OUT / "reference_toc.json"
    tfile.write_text(json.dumps(list(toc.values()), indent=1), encoding="utf-8")
    manifest = {
        "built_at": dt.datetime.now().isoformat(timespec="seconds"), "source_xml": xmls[-1].name,
        "source_xml_sha256": hashlib.sha256(xmls[-1].read_bytes()).hexdigest(),
        "n_passages": len(passages), "n_sections": len(toc),
        "n_chapters": len({t["chapter"] for t in toc.values()}),
        "by_source": {s: sum(1 for p in passages if p["source"] == s) for s in {p["source"] for p in passages}},
        "passages_sha256": hashlib.sha256(pfile.read_bytes()).hexdigest(),
        "indexed_fields": "full-summary paragraphs only (public domain). Third-party 'site' links kept as metadata, not indexed.",
    }
    (OUT / "reference_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return manifest


if __name__ == "__main__":
    build()
