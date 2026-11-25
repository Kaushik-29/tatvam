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

_FORMS = r"medicines?|medications?|tablets?|pills?|drugs?|syrups?|creams?|ointments?|shampoos?|sprays?|drops|gels?|lotions?"
MED_REQUEST_RE = re.compile(
    rf"\b(which|what|any|suggest|recommend|name of|tell me|give me|need)\b.{{0,40}}\b({_FORMS})\b|\bmedicines? names?\b|"
    rf"\bwhat (can|should) i (take|use|apply)\b|\bsomething (for|to take)\b|\b({_FORMS})\s+(for|to (take|use|apply))\b", re.I)
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


PREGNANCY_KWS = ("pregnan", "breastfeed", "breast feeding", "breast-feeding", "lactating")


def history_keywords(group: str) -> List[str]:
    g = KB["groups"][group]
    kws = [k for a in g["avoid"] for k in a.get("history_match", [])]
    kws += [k for o in g["options"] for c in o.get("cautions", []) for k in c["match"]]
    return sorted(set(kws) | set(PREGNANCY_KWS))


def matching_history(records: Sequence[Dict[str, Any]], group: str) -> List[Dict[str, Any]]:
    """History records (conditions / diagnoses) that a caution in this group depends on."""
    kws = history_keywords(group)
    return [r for r in records if any(k in _txt(r) for k in kws)]


def age_years(birth_date: Optional[str], today: Optional[date] = None) -> Optional[int]:
    if not birth_date:
        return None
    try:
        b = date.fromisoformat(birth_date[:10])
    except ValueError:            # malformed stored date: treat the age as unknown, never crash the answer
        return None
    t = today or date.today()
    return t.year - b.year - ((t.month, t.day) < (b.month, b.day))


# ---- who the medicine is for, pregnancy, and how long the symptom has lasted --------------------------
CHILD_RE = re.compile(r"\b(son|daughter|child|children|kid|kids|baby|babies|infant|toddler|newborn|grandson|"
                      r"granddaughter|nephew|niece)\b|\b(\d{1,2})[- ]?(?:years?|yrs?)[- ]?old\b|\b\d+[- ]?months?[- ]?old\b",
                      re.I)
OTHER_PERSON_RE = re.compile(r"\b(my|our)\s+(mother|mom|mum|amma|father|dad|appa|wife|husband|brother|sister|friend|"
                             r"grand(mother|father|ma|pa)|aunt|uncle|neighbou?r|colleague|roommate|parents?|partner|"
                             r"boyfriend|girlfriend|patient)\b|\bfor (him|her|them)\b|\b(he|she) (has|is|have)\b", re.I)
PREGNANCY_RE = re.compile(r"\bpregnan\w*|\bbreast[- ]?feed\w*|\blactating\b|\bexpecting a baby\b", re.I)
NUM_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
             "eight": 8, "nine": 9, "ten": 10, "few": 3, "several": 4}
DURATION_RE = re.compile(r"\b(?:for|since|from|past|last)\s+(?:the\s+)?(?:past\s+|last\s+)?(\d+|a|an|one|two|three|four|"
                         r"five|six|seven|eight|nine|ten|few|several)\s+(day|week|month|year)s?\b", re.I)
UNIT_DAYS = {"day": 1, "week": 7, "month": 30, "year": 365}


def symptom_days(query: str) -> Optional[int]:
    """Longest duration the question states ("for 5 days", "since two weeks"), in days."""
    best = None
    for n, unit in DURATION_RE.findall(query):
        k = int(n) if n.isdigit() else NUM_WORDS.get(n.lower(), 1)
        d = k * UNIT_DAYS[unit.lower()]
        best = d if best is None else max(best, d)
    return best


def blocked_reason(query: str, group: str, history: Sequence[Dict[str, Any]] = ()) -> Optional[str]:
    """Why general options must NOT be given for this question, or None. Options are for the adult account
    holder only, checked against their own record; they are not given in pregnancy / breastfeeding, nor once
    the symptom has lasted past the point where the sources say to see a doctor."""
    q = query.lower()
    if any(not m.group(2) or int(m.group(2)) < 18 for m in CHILD_RE.finditer(q)):
        return ("Medicine doses for children depend on their age and weight, and MedResolve's options are for adults "
                "only. Please ask a doctor or pharmacist for the right medicine and dose for the child.")
    if OTHER_PERSON_RE.search(q):
        return ("MedResolve checks medicines against your own records only, so it cannot suggest one for another "
                "person. Please ask a doctor or pharmacist, or use that person's own profile.")
    preg = [h for h in history if any(k in _txt(h) for k in PREGNANCY_KWS)]
    if PREGNANCY_RE.search(q) or preg:
        return ("Some common medicines are not safe during pregnancy or breastfeeding, so please ask your doctor or "
                "pharmacist before taking any medicine.")
    days, max_days = symptom_days(q), KB["groups"][group].get("max_days")
    if days is not None and max_days is not None and days > max_days:
        extra = " and ask about a dengue test" if group == "fever" else ""
        return (f"Your {KB['groups'][group]['label']} has lasted about {days} days, which is longer than the sources "
                f"advise treating on your own. Please see a doctor{extra}.")
    return None


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
