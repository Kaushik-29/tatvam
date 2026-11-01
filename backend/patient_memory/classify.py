"""
Deterministic concept classification, unit normalization and evidence rendering.

These rules are documented in docs/data_processing_pipeline.md. They are
intentionally simple, inspectable lexicons — never an LLM — so that gold labels
derived from them are programmatically verifiable.
"""

import re
from typing import Optional, Tuple

SNOMED_TAG_RE = re.compile(r"\(([a-z /]+)\)\s*$")

SYMPTOM_TERMS = [
    "fever", "cough", "sore throat", "headache", "fatigue", "dyspnea", "shortness of breath",
    "wheezing", "chill", "diarrhea", "nasal congestion", "muscle pain", "loss of taste",
    "loss of smell", "sputum", "hemoptysis", "chronic pain", "back pain", "neck pain",
    "respiratory distress", "nausea", "vomiting", "dizziness", "vertigo", "chest pain",
    "chest pressure", "abdominal pain", "joint pain", "rash", "itching", "palpitations",
    "anxiety", "panic", "conjunctival congestion", "frequent urination", "thirst", "hunger",
    "blurred vision", "memory loss", "confusion", "tingling", "numbness", "swelling",
    "syncope", "fainting", "insomnia", "weight loss", "sneezing", "earache", "ear pain",
    "toothache", "pain", "decreased visual perception", "decreased attentiveness",
    "decreased in judgement", "malaise", "runny nose",
]

SOCIAL_TERMS = [
    "employment", "employed", "unemployed", "labor force", "education", "educated",
    "school", "social isolation", "social contact", "housing", "homeless", "criminal",
    "violence", "abuse", "transport", "military", "stress", "smokes", "tobacco", "alcohol",
    "drinking", "misuses drugs", "risk activity", "socioeconomic", "refugee", "incarceration",
    "intimate partner", "lack of access", "income", "insurance",
]

ADMINISTRATIVE_TERMS = ["medication review due", "died in hospice"]


def snomed_semantic_tag(display: str) -> Optional[str]:
    m = SNOMED_TAG_RE.search(display or "")
    return m.group(1) if m else None


def strip_semantic_tag(display: str) -> str:
    return SNOMED_TAG_RE.sub("", display or "").strip()


def _matches(text: str, terms) -> bool:
    t = (text or "").lower()
    return any(re.search(r"\b" + re.escape(term) + r"\b", t) for term in terms)


def is_symptom(display: str) -> bool:
    tag = snomed_semantic_tag(display)
    if tag == "disorder":
        return False
    return _matches(strip_semantic_tag(display), SYMPTOM_TERMS)


def is_social(display: str) -> bool:
    return _matches(display, SOCIAL_TERMS)


def classify_condition(display: str) -> str:
    """Maps a FHIR Condition display to a STAIR-Clinical leaf path."""
    if is_social(display):
        return "medical_history/social_history"
    if is_symptom(display):
        return "clinical_encounters/previous_symptoms"
    if snomed_semantic_tag(display) == "disorder":
        return "medical_history/diagnoses"
    return "medical_history/conditions"


OBS_CATEGORY_TO_LEAF = {
    "laboratory": "laboratory_observations/laboratory_results",
    "vital-signs": "laboratory_observations/vital_signs",
    "social-history": "medical_history/social_history",
    "survey": "laboratory_observations/assessments_and_surveys",
    "exam": "laboratory_observations/assessments_and_surveys",
    "procedure": "laboratory_observations/assessments_and_surveys",
    "therapy": "laboratory_observations/assessments_and_surveys",
    "imaging": "laboratory_observations/assessments_and_surveys",
}

# (from_unit, to_unit, factor, offset); applied as value*factor + offset
UNIT_CONVERSIONS = {
    "[degF]": ("Cel", 5.0 / 9.0, -32.0 * 5.0 / 9.0),
    "degF": ("Cel", 5.0 / 9.0, -32.0 * 5.0 / 9.0),
    "[lb_av]": ("kg", 0.45359237, 0.0),
    "lb": ("kg", 0.45359237, 0.0),
    "[in_i]": ("cm", 2.54, 0.0),
    "g/L": ("g/dL", 0.1, 0.0),
}
UCUM_ALIASES = {"degC": "Cel", "°C": "Cel", "kg/m2": "kg/m2", "mm[Hg]": "mm[Hg]", "/min": "/min", "pH": "[pH]"}


def normalize_quantity(value: Optional[float], unit: Optional[str]) -> Tuple[Optional[float], Optional[str]]:
    """Returns (normalized_value, normalized_unit). The original pair is stored separately."""
    if value is None:
        return None, unit
    if unit in UNIT_CONVERSIONS:
        to, f, off = UNIT_CONVERSIONS[unit]
        return round(value * f + off, 4), to
    return value, UCUM_ALIASES.get(unit, unit)


def medication_ingredient(display: str) -> str:
    """'lisinopril 10 MG Oral Tablet' -> 'lisinopril'; '24 HR metformin ... 500 MG' -> 'metformin'."""
    d = re.sub(r"^\d+\s*(HR|ML|ACTUAT)\s+", "", display or "", flags=re.I)
    d = re.sub(r"^\{.*?\}\s*", "", d)
    m = re.split(r"\s\d", d, maxsplit=1)
    name = m[0].strip()
    name = re.sub(r"\s+(Oral|Injectable|Topical|Nasal|Inhalant|Prefilled|Transdermal).*$", "", name, flags=re.I)
    return name.lower() or (display or "").lower()


def medication_strength(display: str) -> Optional[str]:
    m = re.search(r"(\d+(\.\d+)?\s*(MG|MCG|UNT|ML|%|MG/ML|MEQ)(/\w+)?)", display or "", flags=re.I)
    return m.group(1).upper().replace("  ", " ") if m else None


def fmt_date(iso: Optional[str]) -> str:
    return (iso or "")[:10] or "undated"


def render_text(leaf_title: str, display: str, *, start: Optional[str] = None, end: Optional[str] = None,
                value: Optional[str] = None, status: Optional[str] = None,
                verification: Optional[str] = None, extra: Optional[str] = None) -> str:
    parts = [f"{leaf_title}: {strip_semantic_tag(display)}"]
    if value:
        parts.append(f"= {value}")
    if start and end and fmt_date(start) != fmt_date(end):
        parts.append(f"from {fmt_date(start)} to {fmt_date(end)}")
    elif start:
        parts.append(f"on {fmt_date(start)}")
    if status:
        parts.append(f"[status: {status}]")
    if verification and verification != "confirmed":
        parts.append(f"[{verification.replace('_', ' ')}]")
    if extra:
        parts.append(extra)
    return " ".join(parts)
