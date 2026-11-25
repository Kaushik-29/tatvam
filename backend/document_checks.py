"""
Line-level checks on values extracted from uploaded documents.

backend/ocr_service.py is hash-frozen with the OCR evaluation, so its extraction is not changed. This
layer runs after it, on the v2 upload path only. For each extracted lab value it finds the value's own
line in the document text (the line that names the test and contains the value) and takes the unit and
reference range written on that line. This catches the extractor attaching a unit or range from a
neighbouring row (e.g. platelets 95000 /uL stored as "95000 x10^9/L" with the glucose range 70-100).
Values whose line cannot be found are left as extracted, flagged, and stay unconfirmed for patient review.
"""
import re
from typing import Any, Dict, List, Optional

RANGE_RE = r"\d[\d.,]*\s*-\s*\d[\d.,]*"


SYNONYMS = {"sugar": "glucose", "glucose": "sugar", "haemoglobin": "hemoglobin", "hemoglobin": "haemoglobin",
            "platelets": "platelet", "platelet": "platelets"}
GENERIC = {"blood", "test", "serum", "level", "count", "total"}


def _name_words(item: Dict[str, Any]) -> List[str]:
    name = re.sub(r"\(.*?\)", " ", (item.get("concept_name_en") or "").lower())   # "Hemoglobin (blood test)"
    words = [w for w in re.findall(r"[a-z]{4,}", name) if w not in GENERIC]
    return words + [SYNONYMS[w] for w in words if w in SYNONYMS]


def _own_line(item: Dict[str, Any], lines: List[str]) -> Optional[str]:
    """The single line that names this test (any key word) AND contains this exact value."""
    words, value = _name_words(item), str(item.get("normalized_value") or "")
    if not words or not value:
        return None
    hits = [ln for ln in lines if any(w in ln.lower() for w in words)
            and re.search(rf"(?<![\d.]){re.escape(value)}(?![\d.])", ln)]
    return hits[0] if len(hits) == 1 else None          # ambiguous or missing -> not verified


def check_items(items: List[Dict[str, Any]], full_text: str) -> List[Dict[str, Any]]:
    """Return the items with unit / reference range taken from each value's own line where possible.
    Adds item["line_check"]: "verified" | "corrected" | "line_not_found"."""
    lines = [ln.strip() for ln in (full_text or "").splitlines() if ln.strip()]
    out = []
    for it in items:
        it = dict(it)
        if it.get("medication_name"):
            out.append(it)
            continue
        ln = _own_line(it, lines)
        if ln is None:
            it["line_check"] = "line_not_found"
            it["requires_confirmation"] = True
            it["confirmation_reason"] = it.get("confirmation_reason") or "Value could not be matched to its own line"
            out.append(it)
            continue
        value = re.escape(str(it["normalized_value"]))
        m = re.search(rf"(?<![\d.]){value}(?![\d.])\s+(?P<unit>[^\s\d][^\s]*)?\s*(?P<range>{RANGE_RE})?", ln)
        unit = (m.group("unit") if m else None) or None
        rng = re.sub(r"\s+", "", m.group("range")) if m and m.group("range") else None
        changed = []
        if unit and unit != it.get("unit"):
            changed.append(f"unit {it.get('unit')} -> {unit}")
            it["unit"], it["unit_status"] = unit, "EXPLICIT"
        if (it.get("reference_range") or None) != rng:
            changed.append(f"range {it.get('reference_range')} -> {rng}")
            it["reference_range"] = rng
        if changed:
            it["line_check"] = "corrected"
            it["requires_confirmation"] = True
            it["confirmation_reason"] = "Unit / range corrected from the value's own line: " + "; ".join(changed)
        else:
            it["line_check"] = "verified"
        out.append(it)
    return out
