"""
General over-the-counter medicine options for a few common, non-emergency adult symptoms.

When a patient asks which medicine to use for a symptom listed in medicine_options.json (fever,
sneezing / allergy symptoms), MedResolve answers with the curated general option(s) and checks each
one against the patient's own record: recorded allergies, current medicines and relevant history
(e.g. past dengue -> avoid ibuprofen and aspirin). The answer is built deterministically from the
curated file and the records (no LLM text); every statement cites a source [S#] or a record [E#].

Requests to start / stop / change a medicine the patient already takes, dose changes, diagnoses,
children and any symptom not in the file still go to "please speak with a clinician".
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

KB = json.loads((Path(__file__).with_name("medicine_options.json")).read_text(encoding="utf-8"))

MED_REQUEST_RE = re.compile(
    r"\b(which|what|any|suggest|recommend|name of|tell me|give me|need)\b.{0,40}\b(medicines?|medications?|tablets?|"
    r"pills?|drugs?)\b|\bmedicines? names?\b|\bwhat (can|should) i (take|use)\b|\bsomething (for|to take)\b|"
    r"\b(medicines?|medications?|tablets?|pills?)\s+(for|to (take|use))\b", re.I)
CHANGE_RE = re.compile(r"\b(stop|stopping|increase|decrease|double|skip|quit|change|switch|reduce)\b|\bprescribe\b|"
                       r"\bdiagnos\w*\b|\binstead of\b", re.I)
HISTORY_LEAVES = ("medical_history/diagnoses", "medical_history/conditions", "medical_history/procedures")


def detect(query: str) -> Optional[str]:
    """Group key if the question asks for a general medicine for a covered symptom, else None."""
    q = query.lower()
    if not MED_REQUEST_RE.search(q) or CHANGE_RE.search(q):
        return None
    for key, g in KB["groups"].items():
        if any(re.search(rf"\b{re.escape(s)}", q) for s in g["symptoms"]):
            return key
    return None


def history_keywords(group: str) -> List[str]:
    g = KB["groups"][group]
    kws = [k for a in g["avoid"] for k in a.get("history_match", [])]
    kws += [k for o in g["options"] for c in o.get("cautions", []) for k in c["match"]]
    return sorted(set(kws))


def matching_history(records: Sequence[Dict[str, Any]], group: str) -> List[Dict[str, Any]]:
    """History records (conditions / diagnoses) that a caution in this group depends on."""
    kws = history_keywords(group)
    return [r for r in records if any(k in _txt(r) for k in kws)]


def age_years(birth_date: Optional[str], today: Optional[date] = None) -> Optional[int]:
    if not birth_date:
        return None
    b = date.fromisoformat(birth_date[:10])
    t = today or date.today()
    return t.year - b.year - ((t.month, t.day) < (b.month, b.day))


def _txt(r: Dict[str, Any]) -> str:
    return f"{r.get('concept_display') or ''} {r.get('value_text') or ''}".lower()


def _cite(srcs: Sequence[str]) -> str:
    return "".join(f" [{s}]" for s in srcs)


def _hits(names: Sequence[str], recs: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [r for r in recs if any(re.search(rf"\b{re.escape(n)}", _txt(r)) for n in names)]


def build_answer(group: str, evidence: Dict[str, Dict[str, Any]], query: str = "") -> Dict[str, Any]:
    """Deterministic answer from the curated file + the patient's assembled evidence (alias -> record)."""
    g = KB["groups"][group]
    by_leaf = lambda pred: [e for e in evidence.values() if pred(e.get("leaf_path", ""))]
    allergies = by_leaf(lambda l: l == "allergy_history")
    current = by_leaf(lambda l: l == "medication_history/current_medications")
    history = by_leaf(lambda l: l in HISTORY_LEAVES)
    lines = [f"## General medicine options for {g['label']} (not a prescription)"]
    checks, offered, used_sources = [], [], set()
    q = query.lower()

    for o in g["options"]:
        allergic = _hits(o["names"] + [o["generic"]] + o.get("allergy_names", []), allergies)
        if allergic:
            checks.append(f"{o['generic'].capitalize()} is not suggested because your records list an allergy to it "
                          "or a related medicine " + "".join(f"[{a['alias']}]" for a in allergic) + ".")
            continue
        if any(w in q for w in o.get("skip_if_query", [])):     # e.g. loperamide with fever or blood in the stool
            used_sources |= set(o["sources"])
            checks.append(o["skip_text"] + _cite(o["sources"]))
            continue
        blocked = [(c, h) for c in o.get("cautions", []) if c.get("block")
                   for h in history if any(k in _txt(h) for k in c["match"])]
        if blocked:                                              # a record makes this option unsuitable
            c = blocked[0][0]
            used_sources |= set(c["sources"])
            refs = "".join("[" + h["alias"] + "]" for _, h in blocked)
            checks.append(f"{o['generic'].capitalize()} is not suggested because of your records {refs}: {c['text']}."
                          + _cite(c["sources"]))
            continue
        lead = (f"A commonly used over-the-counter option for {g['label']} is" if not offered
                else "Another option is")
        offered.append(o)
        used_sources |= set(o["sources"])
        brands = f" (for example {o['brands']})" if o.get("brands") else ""
        lines.append(f"{lead} **{o['generic']}**{brands}: {o['use']}{_cite(o['sources'])}. {o['limit']}")
        for c in o.get("cautions", []):
            hit = [h for h in history if any(k in _txt(h) for k in c["match"])]
            if hit and not c.get("block"):
                used_sources |= set(c["sources"])
                refs = ", ".join("[" + h["alias"] + "]" for h in hit)
                lines.append(f"Because of your records ({refs}), {c['text']}." + _cite(c["sources"]))
        taking = _hits(o["names"] + [o["generic"]], current)
        if taking:
            checks.append(f"You already take {o['generic']} " + "".join(f"[{t['alias']}]" for t in taking)
                          + ": do not take an extra dose on top of it.")

    for a in g["avoid"]:
        hit = [h for h in history if any(k in _txt(h) for k in a.get("history_match", []))]
        if a.get("always", True):                        # general caution, shown to everyone
            lines.append(f"**{a['text']}**{_cite(a['sources'])}")
        elif not hit:                                    # record-dependent caution: only when the record triggers it
            continue
        used_sources |= set(a["sources"])
        if hit:
            lines.append(f"{a['history_text'].replace('you have had', 'your records show you have had', 1)} "
                         + "".join(f"[{h['alias']}]" for h in hit) + _cite(a["sources"]))
        taking = _hits(a["names"], current)
        if taking:
            checks.append("Your current medicines include " + ", ".join(f"{t['concept_display']} [{t['alias']}]" for t in taking)
                          + f", which is one of the medicines to avoid here: ask your doctor before your next dose.")

    if not offered:
        lines.append("No general option can be suggested from your records; please ask a pharmacist or doctor.")

    # checked against the record
    if allergies:
        checks.append("Recorded allergies: " + ", ".join(f"{a['concept_display']} [{a['alias']}]" for a in allergies)
                      + (" (none of them affects the options above)." if offered else "."))
    else:
        checks.append("No allergies are recorded in your profile; tell the pharmacist about any you know of.")
    others = [c for c in current if not any(c in _hits(o["names"] + [o["generic"]], [c]) for o in offered)]
    if others and offered:
        names = ", ".join(o["generic"] for o in offered)
        checks.append("Current medicines: " + ", ".join(f"{c['concept_display']} [{c['alias']}]" for c in others)
                      + f". None is on the caution list MedResolve checks for {names}.")
    lines += ["", "## Checked against your records"] + [f"- {c}" for c in checks]

    lines += ["", "## See a doctor if"]
    for sd in g["see_doctor"]:
        used_sources |= set(sd["sources"])
        lines.append(f"- {sd['text']}{_cite(sd['sources'])}")
    used_sources |= set(g["warning_signs"]["sources"])
    lines.append(f"- **Warning signs:** {g['warning_signs']['text']}{_cite(g['warning_signs']['sources'])}")
    lines += ["", "Confirm with a pharmacist before taking any medicine, especially if you are pregnant or breastfeeding "
              "or take other medicines."]
    lines += ["", "## Sources"] + [f"- [{s}] {KB['sources'][s]['title']}: {KB['sources'][s]['url']}"
                                   for s in sorted(used_sources)]
    return {"text": "\n".join(lines), "options": [o["generic"] for o in offered], "sources": sorted(used_sources),
            "record_aliases": sorted({e["alias"] for e in allergies + current + history})}
