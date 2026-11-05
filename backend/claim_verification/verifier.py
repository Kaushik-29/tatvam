"""
Claim-level verification for patient-context-aware answers.

The LLM must cite patient evidence as [E#] and reference passages as [R#].
Each sentence (atomic claim) is checked:

PATIENT-SPECIFIC claims ("you/your/the patient ..." or citing [E#]):
  * must cite >= 1 [E#] that exists in the assembled evidence (no invented IDs);
  * every number / date in the claim must appear in the cited evidence;
  * every clinical entity (medication, diagnosis, lab name from the cohort vocabulary)
    named in the claim must appear in the cited evidence — this blocks invented
    diagnoses and medication changes;
  * citing ONLY reference passages for a patient fact is rejected (a guideline
    must never silently become a patient-specific fact).
GENERAL claims:
  * cited [R#] must exist; support = content-token overlap with the cited passage(s);
  * safety / navigation statements are always permitted.
Only permitted claims are released; everything else is withheld and reported.
"""

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set

from backend.rag.fusion import tokenize

CITE_RE = re.compile(r"\[((?:E|R)\d+(?:\s*,\s*(?:E|R)\d+)*)\]")
PATIENT_RE = re.compile(r"\b(you|your|you're|you've|the patient|patient's|their record|this patient)\b", re.I)
NUM_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d+(?:\.\d+)?\b")
SAFETY_RE = re.compile(r"(seek (urgent|emergency|immediate)|call (emergency|911|112|108)|contact (your|a) (doctor|clinician|"
                       r"health ?care|provider|pharmacist)|speak (with|to) (your|a)|consult (your|a)|see (your|a) (doctor|clinician|"
                       r"provider)|not a (diagnosis|substitute)|medical advice|professional assessment|if (your )?symptoms (worsen|get worse))",
                       re.I)
# Navigation advice addressed to the user ("discuss this with your dentist", "seek medical care if ...").
# It tells the user where to go, not what their record says, so it needs no [E#] citation.
NAV_RE = re.compile(r"\b((seek|get)( \w+){0,2} (care|attention|help|advice|assessment)|make an appointment|"
                    r"(contact|call|see|visit|consult|ask|tell|inform|talk (with|to)|speak (with|to)|check with)"
                    r"( \w+){0,2} (doctor|dentist|clinician|physician|provider|pharmacist|nurse|gp|care team)s?|"
                    r"discuss .{0,60} with (your|a|the) (doctor|dentist|clinician|physician|provider|pharmacist|nurse|gp))\b", re.I)
# Navigation advice must never carry a treatment decision.
DECISION_WORDS_RE = re.compile(r"\b(stop|start|increase|decrease|double|skip|dose|dosage|mg|switch)\b", re.I)
# Sentences framed as general information stay general even when they say "you".
GENERAL_FRAME_RE = re.compile(r"^\W*(in general|generally|typically|usually|most people|for most people)\b", re.I)
NO_RELATED_RE = re.compile(r"^\W*nothing in your records? (appears|seems|is) (directly )?(related|relevant) to (this|your) question\W*$", re.I)
GENERIC_WORDS = {"history", "record", "records", "previous", "recorded", "listed", "shows", "show", "result", "results",
                 "value", "values", "level", "levels", "date", "test", "tests", "visit", "visits", "time", "taking",
                 "medication", "medications", "condition", "conditions", "diagnosis", "diagnosed", "reported"}


@dataclass
class ClaimResult:
    claim_id: str
    text: str
    claim_type: str                 # PATIENT_SPECIFIC | GENERAL | SAFETY | STRUCTURAL
    cited_evidence: List[str] = field(default_factory=list)
    cited_references: List[str] = field(default_factory=list)
    status: str = "UNVERIFIED"      # SUPPORTED | UNSUPPORTED | INVALID_CITATION | SAFETY_ALLOWED | STRUCTURAL
    permitted: bool = False
    rationale: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class VerificationResult:
    claims: List[ClaimResult]
    final_text: str
    withheld: List[ClaimResult]
    stats: Dict[str, Any]

    def to_dict(self):
        return {"claims": [c.to_dict() for c in self.claims], "final_text": self.final_text,
                "withheld": [c.to_dict() for c in self.withheld], "stats": self.stats}


def _norm_num(s: str) -> str:
    try:
        return f"{float(s):g}"
    except ValueError:
        return s


def split_claims(text: str) -> List[str]:
    """Sentence / bullet segmentation that keeps headings as structural units."""
    units = []
    for line in text.splitlines():
        l = line.strip()
        if not l:
            continue
        if l.startswith("#") or re.match(r"^\*\*[^*]+\*\*:?$", l) or (len(l) < 60 and l.endswith(":")):
            units.append(l)
            continue
        bullet = re.match(r"^([-*•]|\d+\.)\s+", l)
        prefix = bullet.group(0) if bullet else ""
        body = l[len(prefix):]
        parts = re.split(r"(?<=[.!?])\s+(?=[A-Z])", body)
        for i, p in enumerate(parts):
            units.append((prefix if i == 0 else "") + p.strip())
    return units


class LongitudinalClaimVerifier:
    def __init__(self, clinical_vocabulary: Iterable[str] = (), min_reference_overlap: float = 0.25):
        self.vocab = sorted({v.lower() for v in clinical_vocabulary if v and len(v) >= 5}, key=len, reverse=True)
        self.min_overlap = min_reference_overlap

    def _entities(self, text: str) -> Set[str]:
        t = text.lower()
        found = set()
        for v in self.vocab:
            if re.search(r"\b" + re.escape(v) + r"\b", t) and not any(v in f for f in found):
                found.add(v)
        return found

    def verify(self, text: str, evidence: Dict[str, Dict[str, Any]], references: Dict[str, Dict[str, Any]],
               current_report: str = "", findings_text: str = "") -> VerificationResult:
        claims: List[ClaimResult] = []
        report_tokens = set(tokenize(current_report))
        finding_tokens = set(tokenize(findings_text))
        report_entities = self._entities(current_report)
        for i, unit in enumerate(split_claims(text), 1):
            cid = f"C{i:03d}"
            cites = [c.strip() for grp in CITE_RE.findall(unit) for c in grp.split(",")]
            e_ids = [c for c in cites if c.startswith("E")]
            r_ids = [c for c in cites if c.startswith("R")]
            body = CITE_RE.sub("", unit).strip()
            plain = re.sub(r"[*_`#>-]", " ", body).strip()
            if unit.startswith("#") or (len(plain.split()) < 4 and not cites):
                claims.append(ClaimResult(cid, unit, "STRUCTURAL", status="STRUCTURAL", permitted=True))
                continue
            is_patient = bool(e_ids) or (bool(PATIENT_RE.search(body)) and not GENERAL_FRAME_RE.search(body))
            if SAFETY_RE.search(body) and not e_ids and not NUM_RE.search(body):
                claims.append(ClaimResult(cid, unit, "SAFETY", e_ids, r_ids, "SAFETY_ALLOWED", True,
                                          "Safety / navigation statement."))
                continue
            if (NAV_RE.search(body) and not e_ids and not NUM_RE.search(body) and all(r in references for r in r_ids)
                    and not DECISION_WORDS_RE.search(body) and not self._entities(body) - report_entities):
                claims.append(ClaimResult(cid, unit, "SAFETY", e_ids, r_ids, "SAFETY_ALLOWED", True,
                                          "Navigation advice with no record facts, numbers or treatment decisions."))
                continue
            if NO_RELATED_RE.search(plain) and not cites:
                claims.append(ClaimResult(cid, unit, "STRUCTURAL", status="STRUCTURAL", permitted=True,
                                          rationale="States that no retrieved record is related to the question."))
                continue
            if finding_tokens and not cites and not NUM_RE.search(body):
                content = [t for t in tokenize(body) if t not in GENERIC_WORDS]
                if content and sum(t in finding_tokens for t in content) / len(content) >= 0.7:
                    claims.append(ClaimResult(cid, unit, "RECORD_GAP", status="SUPPORTED", permitted=True,
                                              rationale="Restates a conflict / missing-information finding (section I)."))
                    continue
            bad = [c for c in e_ids if c not in evidence] + [c for c in r_ids if c not in references]
            if bad:
                claims.append(ClaimResult(cid, unit, "PATIENT_SPECIFIC" if is_patient else "GENERAL", e_ids, r_ids,
                                          "INVALID_CITATION", False, f"Cited IDs not in assembled context: {bad}"))
                continue
            if is_patient and not cites:
                # (a) restatement of what the patient reports NOW (section A/B), no record facts added
                content = [t for t in tokenize(body) if t not in GENERIC_WORDS]
                if (report_tokens and content and not NUM_RE.search(body)
                        and not self._entities(body) - self._entities(current_report)
                        and sum(t in report_tokens for t in content) / len(content) >= 0.6):
                    claims.append(ClaimResult(cid, unit, "PATIENT_REPORTED_NOW", status="SUPPORTED", permitted=True,
                                              rationale="Restates the patient's current report (sections A/B)."))
                    continue
                # (b) deterministic post-hoc attribution to assembled evidence
                found = self._attribute(body, evidence)
                if found:
                    res = self._verify_patient(cid, unit, body, found, [], evidence)
                    if res.permitted:
                        res.text = _append_citations(unit, found)
                        res.status = "SUPPORTED_AUTO_ATTRIBUTED"
                        res.rationale = "No citation from the model; evidence attributed deterministically. " + res.rationale
                        claims.append(res)
                        continue
            if not is_patient and not cites:
                found_r = self._attribute_reference(body, references)
                if found_r:
                    res = self._verify_general(cid, unit, body, found_r, references)
                    if res.permitted:
                        res.text = _append_citations(unit, found_r)
                        res.status = "SUPPORTED_AUTO_ATTRIBUTED"
                        res.rationale = "No citation from the model; reference attributed deterministically. " + res.rationale
                        claims.append(res)
                        continue
            if is_patient:
                claims.append(self._verify_patient(cid, unit, body, e_ids, r_ids, evidence))
            else:
                claims.append(self._verify_general(cid, unit, body, r_ids, references))
        permitted = [c for c in claims if c.permitted]
        withheld = [c for c in claims if not c.permitted]
        final = _reassemble(permitted)
        n_pat = sum(1 for c in claims if c.claim_type == "PATIENT_SPECIFIC")
        n_pat_bad = sum(1 for c in claims if c.claim_type == "PATIENT_SPECIFIC" and not c.permitted)
        n_gen = sum(1 for c in claims if c.claim_type == "GENERAL")
        n_gen_ok = sum(1 for c in claims if c.claim_type == "GENERAL" and c.permitted)
        stats = {"total_claims": len(claims), "patient_specific_claims": n_pat,
                 "unsupported_patient_claims": n_pat_bad,
                 "unsupported_patient_claim_rate": (n_pat_bad / n_pat) if n_pat else 0.0,
                 "general_claims": n_gen, "supported_general_claims": n_gen_ok,
                 "invalid_citations": sum(1 for c in claims if c.status == "INVALID_CITATION"),
                 "auto_attributed_claims": sum(1 for c in claims if c.status == "SUPPORTED_AUTO_ATTRIBUTED"),
                 "current_report_claims": sum(1 for c in claims if c.claim_type == "PATIENT_REPORTED_NOW"),
                 "withheld_claims": len(withheld)}
        return VerificationResult(claims, final, withheld, stats)

    def _attribute(self, body: str, evidence: Dict[str, Dict[str, Any]], max_items: int = 3) -> List[str]:
        """Greedy cover: pick evidence items that jointly contain every number/date and clinical
        entity of the claim. Returns [] if the claim's requirements cannot all be covered."""
        need = {("n", _norm_num(n)) for n in NUM_RE.findall(body) if not _is_small_ordinal(n, body)}
        need |= {("e", e) for e in self._entities(body)}
        content = [t for t in tokenize(body) if t not in GENERIC_WORDS and not t.isdigit()]
        if not need and len(content) < 2:
            return []
        def covers(alias):
            t = _evidence_text(evidence[alias]).lower()
            nums = _evidence_numbers(t)
            return {x for x in need if (x[0] == "n" and x[1] in nums) or (x[0] == "e" and x[1] in t)}
        def overlap(alias):
            t = _evidence_text(evidence[alias]).lower()
            return sum(1 for w in content if w in t) / max(1, len(content))
        ranked = sorted(evidence, key=lambda a: (-len(covers(a)), -overlap(a)))
        chosen, covered = [], set()
        for a in ranked:
            gain = covers(a) - covered
            if gain or (not need and overlap(a) >= 0.5 and not chosen):
                chosen.append(a)
                covered |= gain
            if covered >= need and chosen:
                break
            if len(chosen) >= max_items:
                break
        if not chosen or not covered >= need:
            return []
        joint = " ".join(_evidence_text(evidence[a]).lower() for a in chosen)
        if content and sum(1 for w in content if w in joint) / len(content) < 0.35:
            return []
        return chosen

    def _attribute_reference(self, body: str, references: Dict[str, Dict[str, Any]]) -> List[str]:
        content = [t for t in tokenize(body) if len(t) > 3]
        if len(content) < 3:
            return []
        best, score = None, 0.0
        for alias, r in references.items():
            toks = set(tokenize(r["text"]))
            s = sum(1 for t in content if t in toks) / len(content)
            if s > score:
                best, score = alias, s
        return [best] if best and score >= 0.4 else []

    def _verify_patient(self, cid, unit, body, e_ids, r_ids, evidence) -> ClaimResult:
        if not e_ids:
            why = ("Patient-specific statement supported only by a general reference — not permitted."
                   if r_ids else "Patient-specific statement without patient evidence citation.")
            return ClaimResult(cid, unit, "PATIENT_SPECIFIC", e_ids, r_ids, "UNSUPPORTED", False, why)
        ev_text = " ".join(_evidence_text(evidence[e]) for e in e_ids).lower()
        ev_nums = _evidence_numbers(ev_text)
        missing_nums = [n for n in NUM_RE.findall(body) if _norm_num(n) not in ev_nums and not _is_small_ordinal(n, body)]
        if missing_nums:
            return ClaimResult(cid, unit, "PATIENT_SPECIFIC", e_ids, r_ids, "UNSUPPORTED", False,
                               f"Numbers/dates not found in cited evidence: {missing_nums}")
        missing_ents = [e for e in self._entities(body) if e not in ev_text]
        if missing_ents:
            return ClaimResult(cid, unit, "PATIENT_SPECIFIC", e_ids, r_ids, "UNSUPPORTED", False,
                               f"Clinical entities not present in cited evidence: {missing_ents}")
        content = [t for t in tokenize(body) if t not in GENERIC_WORDS and not t.isdigit()]
        overlap = sum(1 for t in content if t in ev_text) / max(1, len(content))
        if content and overlap < 0.2:
            return ClaimResult(cid, unit, "PATIENT_SPECIFIC", e_ids, r_ids, "UNSUPPORTED", False,
                               f"Low lexical support from cited evidence ({overlap:.2f}).")
        return ClaimResult(cid, unit, "PATIENT_SPECIFIC", e_ids, r_ids, "SUPPORTED", True,
                           f"Names, numbers and dates match cited evidence (overlap {overlap:.2f}).")

    def _verify_general(self, cid, unit, body, r_ids, references) -> ClaimResult:
        if not r_ids:
            return ClaimResult(cid, unit, "GENERAL", [], r_ids, "UNSUPPORTED", False,
                               "General medical statement without a reference citation.")
        ref_tokens = set(tokenize(" ".join(references[r]["text"] for r in r_ids)))
        content = [t for t in tokenize(body) if len(t) > 3]
        overlap = sum(1 for t in content if t in ref_tokens) / max(1, len(content))
        ok = overlap >= self.min_overlap
        return ClaimResult(cid, unit, "GENERAL", [], r_ids, "SUPPORTED" if ok else "UNSUPPORTED", ok,
                           f"Token overlap with cited passages {overlap:.2f} (threshold {self.min_overlap}).")


def _evidence_text(e: Dict[str, Any]) -> str:
    return " ".join(str(x) for x in (e.get("text"), e.get("concept_display"), e.get("effective_start"),
                                     e.get("value_num"), e.get("unit"), e.get("value_text")) if x is not None)


def _evidence_numbers(text: str) -> Set[str]:
    """Numbers in evidence, plus the year and year-month of every ISO date (so 'in 2020' matches 2020-10-26)."""
    nums = {_norm_num(n) for n in NUM_RE.findall(text)}
    for d in re.findall(r"\b(\d{4})-(\d{2})-\d{2}\b", text):
        nums.add(_norm_num(d[0]))
    return nums


def _append_citations(unit: str, aliases: List[str]) -> str:
    tag = "".join(f" [{a}]" for a in aliases)
    m = re.search(r"([.!?])\s*$", unit)
    return (unit[:m.start()] + tag + m.group(1)) if m else unit + tag


def _is_small_ordinal(n: str, body: str) -> bool:
    # list numbering like "1." or counts such as "2 medications" are not factual values to check
    return n.isdigit() and int(n) <= 3 and not re.search(rf"\b{n}\s*(mg|mcg|ml|%|mmol|mm|kg|cm|years?)\b", body, re.I)


def _reassemble(claims: List[ClaimResult]) -> str:
    lines, cur = [], []
    for c in claims:
        t = c.text
        if c.claim_type == "STRUCTURAL" or re.match(r"^([-*•]|\d+\.)\s+", t):
            if cur:
                lines.append(" ".join(cur)); cur = []
            lines.append(t)
        else:
            cur.append(t)
    if cur:
        lines.append(" ".join(cur))
    # drop headings left without content
    out = []
    for i, l in enumerate(lines):
        if l.startswith("#") and (i + 1 == len(lines) or lines[i + 1].startswith("#")):
            continue
        out.append(l)
    return "\n".join(out)
