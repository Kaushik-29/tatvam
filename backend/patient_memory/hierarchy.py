"""
STAIR-Clinical patient record hierarchy.

The hierarchy plays the role of the book Table of Contents (ToC) in the original
STAIR paper (arXiv:2609.03874). It has two parts:

* A STABLE clinical skeleton (levels 1-2, `LEAVES` below) that is identical for
  every patient. The STAIR-Clinical selector is trained to route questions over it.
* A DYNAMIC, patient-specific level 3 ("concept groups", e.g. one node per lab
  test or medication) that is rebuilt from the database at query time. Patient
  data therefore lives in the database, never in model weights.

Path IDs are slash-separated and are the only identifiers the selector may emit.
Every generated path must be validated with `is_valid_leaf` / against the
patient's ToC before it is resolved to database records.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Leaf:
    path: str          # stable path ID, e.g. "medication_history/current_medications"
    number: str        # ToC numbering, e.g. "3.1"
    title: str         # human title shown in the ToC
    description: str   # what lives here (documentation + structural scorer)
    in_spec: bool = True       # False = MedResolve extension beyond the requested tree
    virtual: bool = False      # resolved from another leaf's records (no own records)
    virtual_source: Optional[str] = None


BRANCHES: Dict[str, str] = {
    "demographics": "1 Demographics",
    "medical_history": "2 Medical History",
    "medication_history": "3 Medication History",
    "allergy_history": "4 Allergy History",
    "clinical_encounters": "5 Clinical Encounters",
    "laboratory_observations": "6 Laboratory and Observations",
    "medical_documents": "7 Medical Documents",
}

LEAVES: List[Leaf] = [
    Leaf("demographics", "1", "Demographics", "age, sex, birth date, deceased status, location"),
    Leaf("medical_history/conditions", "2.1", "Conditions",
         "health conditions and clinical findings that are not formal disorders, e.g. prediabetes, obesity, pregnancy, injuries"),
    Leaf("medical_history/diagnoses", "2.2", "Diagnoses",
         "diagnosed disorders and diseases, chronic and resolved, e.g. hypertension, diabetes, asthma, infections"),
    Leaf("medical_history/procedures", "2.3", "Procedures",
         "procedures, surgeries, screenings, imaging and therapies performed"),
    Leaf("medical_history/immunizations", "2.4", "Immunizations", "vaccines administered", in_spec=False),
    Leaf("medical_history/care_plans", "2.5", "Care Plans", "care plans, self-management and lifestyle plans", in_spec=False),
    Leaf("medical_history/social_history", "2.6", "Social History",
         "smoking, alcohol, employment, education, housing, stress and other social determinants", in_spec=False),
    Leaf("medication_history/current_medications", "3.1", "Current Medications",
         "medications currently active / being taken"),
    Leaf("medication_history/previous_medications", "3.2", "Previous Medications",
         "medications taken in the past that are completed or stopped"),
    Leaf("medication_history/medication_changes", "3.3", "Medication Changes",
         "medication starts, dose changes and discontinuations over time"),
    Leaf("allergy_history", "4", "Allergy History", "allergies and intolerances to drugs, foods and environment, with reactions"),
    Leaf("clinical_encounters/previous_symptoms", "5.1", "Previous Symptoms",
         "symptoms recorded at previous encounters, e.g. fever, cough, headache, dizziness, fatigue"),
    Leaf("clinical_encounters/complaints", "5.2", "Complaints",
         "chief complaints and reasons for visits reported by the patient"),
    Leaf("clinical_encounters/consultations", "5.3", "Consultations",
         "visits, consultations, admissions and emergency encounters with providers"),
    Leaf("clinical_encounters/encounter_dates", "5.4", "Encounter Dates",
         "chronological dates of visits; when the patient was last or first seen", virtual=True,
         virtual_source="clinical_encounters/consultations"),
    Leaf("laboratory_observations/laboratory_results", "6.1", "Laboratory Results",
         "blood and urine laboratory test results, e.g. glucose, creatinine, cholesterol, hemoglobin"),
    Leaf("laboratory_observations/vital_signs", "6.2", "Vital Signs",
         "blood pressure, heart rate, temperature, weight, height, BMI, oxygen saturation, respiratory rate"),
    Leaf("laboratory_observations/historical_trends", "6.3", "Historical Trends",
         "how laboratory values and vital signs changed over time: first, latest, min, max, direction"),
    Leaf("laboratory_observations/assessments_and_surveys", "6.4", "Assessments and Surveys",
         "questionnaires and scores, e.g. depression, anxiety, pain scores, exam findings", in_spec=False),
    Leaf("medical_documents/prescriptions", "7.1", "Prescriptions", "uploaded or entered prescription documents"),
    Leaf("medical_documents/discharge_summaries", "7.2", "Discharge Summaries", "hospital inpatient discharge notes"),
    Leaf("medical_documents/diagnostic_reports", "7.3", "Diagnostic Reports",
         "laboratory panels and imaging study reports"),
    Leaf("medical_documents/clinical_notes", "7.4", "Clinical Notes",
         "outpatient visit notes (history, physical, assessment and plan)", in_spec=False),
]

LEAF_BY_PATH: Dict[str, Leaf] = {l.path: l for l in LEAVES}
LEAF_PATHS: List[str] = [l.path for l in LEAVES]
STORED_LEAF_PATHS: List[str] = [l.path for l in LEAVES if not l.virtual]


def is_valid_leaf(path: str) -> bool:
    return path in LEAF_BY_PATH


def leaf_of(path: str) -> Optional[str]:
    """Returns the level-2 leaf that a level-3 concept-group path belongs to."""
    for lp in sorted(LEAF_PATHS, key=len, reverse=True):
        if path == lp or path.startswith(lp + "/"):
            return lp
    return None


def resolve_virtual(leaf_path: str) -> str:
    leaf = LEAF_BY_PATH[leaf_path]
    return leaf.virtual_source if leaf.virtual else leaf_path


_slug_re = re.compile(r"[^a-z0-9]+")


def slugify(text: str, max_len: int = 64) -> str:
    s = _slug_re.sub("_", text.lower()).strip("_")
    return s[:max_len] or "unspecified"


def concept_group_path(leaf_path: str, concept_key: str) -> str:
    return f"{leaf_path}/{slugify(concept_key)}"


@dataclass
class TocNode:
    path: str
    number: str
    title: str
    is_leaf: bool
    count: int = 0
    date_range: Optional[str] = None
    children: List["TocNode"] = field(default_factory=list)

    def line(self) -> str:
        extra = ""
        if self.count:
            extra = f" ({self.count} record{'s' if self.count != 1 else ''}"
            extra += f", {self.date_range})" if self.date_range else ")"
        prefix = "leaf " if self.is_leaf else ""
        return f"{prefix}{self.number} {self.title}{extra}"


def skeleton_toc_lines() -> List[str]:
    """Static level-1/2 ToC (stage-1 routing input; identical for all patients)."""
    lines, emitted = [], set()
    for leaf in LEAVES:
        branch = leaf.path.split("/")[0]
        if "/" in leaf.path and branch not in emitted:
            lines.append(BRANCHES[branch])
            emitted.add(branch)
        lines.append(f"leaf {leaf.number} {leaf.title}")
    return lines


def skeleton_leaf_titles() -> Dict[str, str]:
    """Maps the constrained-generation target string -> leaf path."""
    return {f"{l.number} {l.title}": l.path for l in LEAVES}
