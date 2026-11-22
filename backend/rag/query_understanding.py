"""
Rule-based clinical query understanding.

Extracts symptoms, medication mentions, organ systems, clinical concepts,
temporal expressions and the question intent from a free-text patient question.
Deterministic and inspectable by design (no LLM), so that it can run before
any generation and be unit tested.
"""

import re
from backend import config
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Sequence

from backend.patient_memory.classify import SYMPTOM_TERMS

# lay phrase -> canonical symptom term (canonical terms come from SYMPTOM_TERMS)
SYMPTOM_SYNONYMS: Dict[str, str] = {
    "dizzy": "dizziness", "lightheaded": "dizziness", "light-headed": "dizziness", "vertigo": "dizziness",
    "breathless": "shortness of breath", "short of breath": "shortness of breath", "can't breathe": "shortness of breath",
    "cannot breathe": "shortness of breath", "trouble breathing": "shortness of breath", "dyspnea": "shortness of breath",
    "tired": "fatigue", "exhausted": "fatigue", "tiredness": "fatigue", "worn out": "fatigue",
    "throwing up": "vomiting", "vomited": "vomiting", "nauseous": "nausea", "sick to my stomach": "nausea",
    "stomach ache": "abdominal pain", "stomach pain": "abdominal pain", "belly pain": "abdominal pain",
    "tummy pain": "abdominal pain", "temperature": "fever", "feverish": "fever", "high temperature": "fever",
    "migraine": "headache", "head hurts": "headache", "racing heart": "palpitations", "heart racing": "palpitations",
    "heart pounding": "palpitations", "passed out": "syncope", "fainted": "syncope", "blacked out": "syncope",
    "peeing a lot": "frequent urination", "urinating often": "frequent urination", "always thirsty": "thirst",
    "pins and needles": "tingling", "chest tightness": "chest pressure", "chest tight": "chest pressure",
    "forgetful": "memory loss", "forgetting things": "memory loss", "runny nose": "nasal congestion",
    "stuffy nose": "nasal congestion", "blocked nose": "nasal congestion", "achy muscles": "muscle pain",
    "body aches": "muscle pain", "sore muscles": "muscle pain", "joint ache": "joint pain", "aching joints": "joint pain",
    "swollen legs": "swelling", "swollen ankles": "swelling", "itchy": "itching", "blurry vision": "blurred vision",
    "coughing": "cough", "wheezy": "wheezing", "loose stools": "diarrhea", "chills": "chill", "shivering": "chill",
}

# symptom -> concepts in history that are clinically relevant (curated, documented)
SYMPTOM_RELATED_CONDITIONS: Dict[str, List[str]] = {
    "dizziness": ["hypertension", "hypotension", "anemia", "diabetes", "atrial fibrillation", "arrhythmia",
                  "heart failure", "stroke", "cerebrovascular", "concussion", "vertigo"],
    "chest pain": ["ischemic heart", "coronary", "myocardial infarction", "angina", "hypertension",
                   "hyperlipidemia", "heart failure", "atrial fibrillation", "pulmonary embol"],
    "chest pressure": ["ischemic heart", "coronary", "myocardial infarction", "angina", "hypertension",
                       "hyperlipidemia", "heart failure"],
    "shortness of breath": ["asthma", "chronic obstructive", "emphysema", "heart failure", "pneumonia",
                            "bronchitis", "anemia", "pulmonary", "covid"],
    "cough": ["asthma", "chronic obstructive", "bronchitis", "pneumonia", "sinusitis", "heart failure",
              "covid", "pharyngitis"],
    "wheezing": ["asthma", "chronic obstructive", "bronchitis", "emphysema"],
    "frequent urination": ["diabetes", "prediabetes", "urinary tract infection", "cystitis", "prostat", "kidney"],
    "thirst": ["diabetes", "prediabetes", "kidney"],
    "fatigue": ["anemia", "diabetes", "hypothyroid", "depression", "heart failure", "kidney", "sleep apnea"],
    "headache": ["hypertension", "migraine", "sinusitis", "concussion", "brain"],
    "joint pain": ["arthritis", "osteoarthritis", "rheumatoid", "gout", "lupus"],
    "back pain": ["low back pain", "osteoporosis", "osteoarthritis", "fracture", "disc"],
    "abdominal pain": ["appendicitis", "gallstone", "cholelithiasis", "cholecystitis", "ulcer", "pancreatitis",
                       "crohn", "colitis", "gastro"],
    "swelling": ["heart failure", "kidney", "venous", "thrombosis", "cirrhosis"],
    "tingling": ["diabetes", "neuropathy", "stroke"],
    "numbness": ["diabetes", "neuropathy", "stroke"],
    "memory loss": ["alzheimer", "dementia", "stroke", "cognitive"],
    "confusion": ["alzheimer", "dementia", "stroke", "infection", "diabetes"],
    "palpitations": ["atrial fibrillation", "arrhythmia", "hyperthyroid", "anxiety", "heart"],
    "fever": ["infection", "pneumonia", "sinusitis", "pharyngitis", "bronchitis", "otitis", "covid", "sepsis"],
    "syncope": ["atrial fibrillation", "arrhythmia", "heart failure", "hypotension", "diabetes", "seizure"],
    "blurred vision": ["diabetes", "diabetic retinopathy", "hypertension", "glaucoma", "cataract"],
    "nausea": ["gastro", "pregnancy", "migraine", "ulcer", "pancreatitis"],
    "vomiting": ["gastro", "pregnancy", "migraine", "ulcer", "pancreatitis"],
    "diarrhea": ["gastro", "colitis", "crohn", "infection"],
    "sore throat": ["pharyngitis", "streptococcal", "sinusitis", "tonsillitis"],
    "anxiety": ["anxiety", "panic", "depression", "posttraumatic stress"],
}

# organ system -> lab name keywords (lowercase substrings of LOINC displays)
SYSTEM_LABS: Dict[str, List[str]] = {
    "kidney": ["creatinine", "glomerular filtration", "urea nitrogen", "microalbumin", "albumin/creatinine",
               "protein [presence] in urine", "potassium"],
    "liver": ["alanine aminotransferase", "aspartate aminotransferase", "bilirubin", "alkaline phosphatase",
              "albumin [mass/volume] in serum"],
    "cholesterol": ["cholesterol", "triglyceride", "low density lipoprotein", "high density lipoprotein"],
    "blood sugar": ["glucose", "hemoglobin a1c"],
    "blood count": ["hemoglobin [mass/volume] in blood", "hematocrit", "erythrocytes", "leukocytes", "platelets",
                    "mcv", "mch", "rdw"],
    "thyroid": ["thyrotropin", "thyroxine", "thyroid"],
    "electrolyte": ["sodium", "potassium", "chloride", "carbon dioxide", "calcium"],
    "urine": ["urine", "urinalysis"],
}
SYSTEM_SYNONYMS = {
    "kidney": ["kidney", "renal", "kidneys"], "liver": ["liver", "hepatic", "lft", "lfts", "liver enzymes"],
    "cholesterol": ["cholesterol", "lipid", "lipids", "fats", "lipid panel", "lipid profile"],
    "blood sugar": ["blood sugar", "sugar", "sugars", "glucose", "diabetes", "a1c", "hba1c", "glycated"],
    "blood count": ["blood count", "blood counts", "blood cell count", "blood cell counts", "cbc", "full blood count",
                    "red blood cells", "white blood cells", "platelets", "anemia", "anaemia", "hemoglobin", "haemoglobin"],
    "thyroid": ["thyroid", "tsh"], "electrolyte": ["electrolyte", "electrolytes", "salt", "sodium", "potassium",
                                                 "metabolic panel"],
    "urine": ["urine", "urinalysis"],
}

VITAL_SYNONYMS = {
    "blood pressure": ["systolic blood pressure", "diastolic blood pressure"],
    "bp": ["systolic blood pressure", "diastolic blood pressure"],
    "heart rate": ["heart rate"], "pulse": ["heart rate"], "weight": ["body weight"], "height": ["body height"],
    "bmi": ["body mass index"], "temperature": ["body temperature"], "oxygen": ["oxygen saturation"],
    "breathing rate": ["respiratory rate"], "respiratory rate": ["respiratory rate"], "pain score": ["pain severity"],
}

CONDITION_LAY = {
    "essential hypertension": "high blood pressure", "hypertension": "high blood pressure",
    "hyperlipidemia": "high cholesterol", "hypertriglyceridemia": "high triglycerides",
    "prediabetes": "prediabetes", "diabetes mellitus type 2": "type 2 diabetes", "anemia": "anemia",
    "chronic obstructive bronchitis": "COPD", "pulmonary emphysema": "emphysema",
    "acute viral pharyngitis": "a sore throat infection", "viral sinusitis": "a sinus infection",
    "acute bronchitis": "bronchitis", "otitis media": "an ear infection", "gingivitis": "gum disease",
    "ischemic heart disease": "heart disease", "chronic congestive heart failure": "heart failure",
    "body mass index 30+ - obesity": "obesity", "osteoarthritis of knee": "knee arthritis",
}

MED_NOUN = r"(medications?|medicines?|drugs?|meds|pills|prescriptions?|regimen|dos(e|es|age|ages)|administration)"
# trend / course-over-time vocabulary (shared by the intent and the temporal relation)
TREND_RE = re.compile(
    r"\b(trend\w*|over time|over the (years|months|course|period)|changed|chang(es|ing) in|getting (better|worse)"
    r"|improv\w*|worsen\w*|deteriorat\w*|evolv\w*|progress(ed|ion|ing)?|fluctuat\w*|vari(ed|ation|ations)"
    r"|pattern|trajectory|(going|gone|went) (up|down)|upward|downward|increas\w*|decreas\w*|rising|falling"
    r"|across (visits|tests|time)|track\w*)\b")
INTENT_KEYWORDS = [
    ("medication_during_episode", [r"\b(taking|on)\b.*\b(when|during)\b", r"\bduring (my|the|their)? ?(previous|last|earlier)\b",
                                   r"\b" + MED_NOUN + r"\b.*\b(when|while|at the time)\b"]),
    ("medication_changes", [r"\bdose\b.*\bchang", r"\bchang\w*\b.*\b(dose|medication|medicine|prescription)", r"\bstopp?ed\b.*\b(medication|medicine|taking)", r"\bdiscontinu",
                            r"\b" + MED_NOUN + r"\b.*\b(chang|adjust|modif|alter|vari|switch|stopp|increas|decreas)\w*",
                            r"\b(chang|adjust|modif|alter|switch)\w*\b.*\b" + MED_NOUN + r"\b"]),
    ("allergy_check", [r"\ballerg", r"\bintoleran", r"\breaction to\b"]),
    ("current_medications", [r"\b(current|currently|right now|now)\b.*\b(medication|medicine|drugs|pills|taking)", r"\bwhat (medications|medicines|drugs) (am i|is the patient|are)\b",
                             r"\b(active|current|currently|presently|at present)\b.*\b" + MED_NOUN + r"\b",
                             r"\b" + MED_NOUN + r"\b.*\b(currently|presently|right now|at present|active)\b"]),
    ("lab_trend", [r"\b(history of my)\b", TREND_RE.pattern]),
    ("latest_measurement", [r"\b(latest|most recent|most current|newest|last|current)\b.*\b(reading|value|result|measurement|level|blood pressure|weight|bmi|heart rate|pulse|height|temperature|oxygen)\b"]),
    ("lab_lookup", [r"\b(lab|labs|laboratory|blood tests?|blood work|bloodwork|test results|tests|panels?|function tests?|blood (cell )?counts?)\b"]),
    ("relevant_history", [r"\b(associated|related|connected|linked|relevant) (with|to)\b"]),
    ("similar_symptoms", [r"\b(before|previously|in the past|again|ever (had|experienced))\b"]),
    ("last_visit", [r"\b(last|most recent|previous|latest)\b.*\b(visit|appointment|saw a doctor|see a doctor|consultation|seen|encounter|check-?up)\b", r"\bwhen did i (last )?(see|visit)\b"]),
    ("procedure_history", [r"\b(procedure|surgery|operation|screening|scan|x-ray|colonoscopy|undergo|undergone|underwent|removal of)\b"]),
    ("immunization_history", [r"\b(vaccin|immuni[sz]|shot|booster|flu jab)\w*"]),
    ("condition_status", [r"\b(still have|resolved|cured|active|gone away|still (present|there|ongoing)|ongoing|persist\w*)\b",
                          r"\b(status|diagnos\w*)\b"]),
    ("relevant_history", [r"\b(relevant|related|connected|history)\b", r"\b(new|started|starting|recently)\b"]),
]

MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                       "september", "october", "november", "december"], 1)}


COMPARE_RE = re.compile(r"\b(compared? (to|with)|than (it was |they were )?(last|before|previous|earlier|my last)|versus|vs\.?"
                        r"|better than|worse than|difference between|since (my )?last)\b")


@dataclass
class QueryUnderstanding:
    raw_query: str
    symptoms: List[str] = field(default_factory=list)
    medications: List[str] = field(default_factory=list)
    organ_systems: List[str] = field(default_factory=list)
    vitals: List[str] = field(default_factory=list)
    concepts: List[str] = field(default_factory=list)
    intent: str = "general_question"
    time_start: Optional[str] = None
    time_end: Optional[str] = None
    temporal_relation: Optional[str] = None   # most_recent | trend | during_episode | range | None
    temporal_intent: Optional[str] = None     # recent | long_term | compare | None (TA-RAG-style)
    episode_phrase: Optional[str] = None      # "when I had <X> in <month>": the condition/symptom named as anchor
    is_new_concern: bool = False
    expanded_terms: List[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


PAIN_STOP = {"had", "have", "has", "reported", "report", "any", "my", "the", "of", "in", "with", "some", "a"}
_MONTH_ALT = "january|february|march|april|may|june|july|august|september|october|november|december"
# "when I had <X> back in <Month Year>", "when the patient reported <X> in ...",
# "during their previous <X> episode ...", "active when the patient reported <X> ..."
_WHO = r"(?:i|the patient|they|he|she|my (?:child|son|daughter)|the person)"
_HAD = (r"(?:first\s+)?(?:had|have had|reported|mentioned|noticed|experienced|was experiencing|suffered from|was suffering from"
        r"|was (?:first\s+)?diagnosed with|got|developed|came down with|was treated for|presented with|dealt with|went through"
        r"|experiencing|having|suffering from|being treated for)")
_ARTICLE = (r"(?:(?:a|an|the|my|their|his|her|that|this|previous|last|earlier|prior|past|recent"
            r"|episode of|bout of|case of|attack of)\s+)*")
# the anchor ends at a date, a clause break or the end of the question
_ANCHOR_END = (r"(?=\s+(?:episode|bout|attack|flare)\b|\s+back\b"
               r"|\s+(?:in|during|around|on|from|at)\s+(?:the\s+(?:month|year)\s+(?:of\s+)?)?(?:" + _MONTH_ALT + r"|(?:19|20|21)\d\d)\b"
               r"|\s+(?:in|on|from)\s+(?:the patient'?s|my|their|his|her)\s+(?:record|chart|history|file)"
               r"|\s*,\s*(?:what|which|how|can|could|please|and|did|were|was)\b|\s*\?|\s*\.|$|\s+(?:what|which|and)\b)")
EPISODE_PATTERNS = [
    # "when I had <X>", "when the patient was diagnosed with <X>", "while they were experiencing <X>"
    re.compile(r"\b(?:when|while|at the time)\s+" + _WHO + r"\s+(?:was\s+|were\s+)?" + _HAD + r"\s+" + _ARTICLE
               + r"(.+?)" + _ANCHOR_END),
    # "during my previous <X> episode", "at the time of their last <X>"
    re.compile(r"\b(?:during|throughout|at the time of|in the course of)\s+(?:my|their|the|his|her|that)\s+"
               r"(?:previous|last|earlier|prior|past|recent)\s+" + _ARTICLE + r"(.+?)" + _ANCHOR_END),
    # "when <X> first started / began / presented", "when the sinus infection first started"
    re.compile(r"\b(?:when|while|at the time)\s+" + _ARTICLE + r"(.+?)\s+(?:first\s+)?(?:started|began|presented|appeared"
               r"|occurred|developed|flared|happened|was (?:first\s+)?(?:diagnosed|reported|noted|recorded))\b"),
    # "an episode of <X>", "the bout of <X>"
    re.compile(r"\b(?:episode|bout|attack|case)\s+of\s+" + _ARTICLE + r"(.+?)" + _ANCHOR_END),
]
_STRIP_ARTICLE = re.compile(r"^(?:(?:a|an|the|my|their|his|her|that|this)\s+)+")
_NOT_ANCHOR = re.compile(r"(?:it|this|that|them|they|so|there|ill|sick|i|you|he|she)")


def episode_anchor(q: str) -> Optional[str]:
    """The condition / symptom a 'medications during that episode' question is anchored on, or None."""
    for pat in EPISODE_PATTERNS:
        m = pat.search(q)
        if m:
            phrase = _STRIP_ARTICLE.sub("", m.group(1).strip(" ,.?"))
            phrase = re.sub(r"\s+(?:episode|bout|attack|flare)$", "", phrase)
            if phrase and not _NOT_ANCHOR.fullmatch(phrase):
                return phrase
    return None


def _find_terms(q: str, terms: Sequence[str]) -> List[str]:
    return [t for t in terms if re.search(r"\b" + re.escape(t) + r"\b", q)]


def understand(query: str, known_medications: Sequence[str] = (), known_concepts: Sequence[str] = (),
               today: Optional[date] = None) -> QueryUnderstanding:
    q = " ".join(query.lower().split())
    today = today or config.today()
    qu = QueryUnderstanding(raw_query=query)

    syms = set(_find_terms(q, [s for s in SYMPTOM_TERMS if s != "pain"]))
    for lay, canon in SYMPTOM_SYNONYMS.items():
        if re.search(r"\b" + re.escape(lay) + r"\b", q):
            syms.add(canon)
    if "pain" in q and not any("pain" in s for s in syms):
        m = re.search(r"\b(\w+)\s+pain\b", q)
        syms.add(f"{m.group(1)} pain" if m and m.group(1) not in PAIN_STOP else "pain")
    qu.symptoms = sorted(syms)

    qu.medications = sorted({m for m in known_medications if m and re.search(r"\b" + re.escape(m.lower()) + r"\b", q)})
    qu.concepts = sorted({c for c in known_concepts if c and len(c) > 3 and c.lower() in q})

    for system, syns in SYSTEM_SYNONYMS.items():
        if any(re.search(r"\b" + re.escape(s) + r"\b", q) for s in syns):
            qu.organ_systems.append(system)
    for v in VITAL_SYNONYMS:
        if re.search(r"\b" + re.escape(v) + r"\b", q):
            qu.vitals.append(v)

    for intent, pats in INTENT_KEYWORDS:
        if any(re.search(p, q) for p in pats):
            qu.intent = intent
            break
    qu.is_new_concern = bool(re.search(r"\b(new|started|starting|recently|since|today|this week|i have|i've got|i am having|i'm having|i feel|i'm feeling)\b", q)) and bool(qu.symptoms)

    # ------------------------------------------------------------- temporal
    if re.search(r"\b(latest|most recent|most current|newest|last|up[- ]to[- ]date)\b", q):
        qu.temporal_relation = "most_recent"
    if TREND_RE.search(q):
        qu.temporal_relation = "trend"
    # "during 2003" / "during the visit" are not episodes: only an episode construction or a named anchor is
    if re.search(r"\b(when i had|when the patient had|at the time (of|when))\b", q):
        qu.temporal_relation = "during_episode"
    phrase = episode_anchor(q)
    if phrase:
        # the anchor is named by the condition / symptom itself, which may be outside the symptom vocabulary
        # (e.g. "sepsis, pulmonary", "asthma"): keep the phrase so retrieval can match record names
        qu.episode_phrase = phrase
        qu.temporal_relation = "during_episode"
    # dates: "<month> <year>" / "<month> of <year>" anywhere; date-shifted sources (MIMIC) use 21xx years
    m = re.search(r"\b(" + "|".join(MONTHS) + r")\s+(?:of\s+)?((?:19|20|21)\d\d)\b", q)
    if m:
        mo, yr = MONTHS[m.group(1)], int(m.group(2))
        qu.time_start = f"{yr:04d}-{mo:02d}-01"
        qu.time_end = f"{yr + (mo == 12):04d}-{(mo % 12) + 1:02d}-01"
        qu.temporal_relation = qu.temporal_relation or "range"
    else:
        m = re.search(r"\b(?:in|during|from|back in|around|throughout|within|for|of|year)\s+(?:the\s+(?:calendar\s+)?year\s+)?"
                      r"((?:19|20|21)\d\d)\b", q)
        if m:
            yr = int(m.group(1))
            qu.time_start, qu.time_end = f"{yr}-01-01", f"{yr + 1}-01-01"
            qu.temporal_relation = qu.temporal_relation or "range"
    m = re.search(r"\b(?:past|last)\s+(\d+|one|two|three|five|ten)\s+(year|month|week)s?\b", q)
    if m:
        n = {"one": 1, "two": 2, "three": 3, "five": 5, "ten": 10}.get(m.group(1), None) or int(m.group(1))
        days = {"year": 365, "month": 30, "week": 7}[m.group(2)] * n
        qu.time_start, qu.time_end = (today - timedelta(days=days)).isoformat(), None
        qu.temporal_relation = "range"
    # Temporal intent (after Li & Liu, TA-RAG, HBD 2026): recent state, long-term course, or a
    # comparison between periods. A comparison needs the whole series, so it is retrieved as a trend.
    if COMPARE_RE.search(q):
        qu.temporal_intent = "compare"
        qu.temporal_relation = "trend"
        qu.time_start = qu.time_end = None
    elif qu.temporal_relation == "trend":
        qu.temporal_intent = "long_term"
    elif qu.temporal_relation == "most_recent":
        qu.temporal_intent = "recent"

    expanded = set(qu.symptoms) | set(qu.medications)
    for s in qu.symptoms:
        expanded.update(SYMPTOM_RELATED_CONDITIONS.get(s, []))
    for sysname in qu.organ_systems:
        expanded.update(SYSTEM_LABS.get(sysname, []))
    for v in qu.vitals:
        expanded.update(VITAL_SYNONYMS[v])
    qu.expanded_terms = sorted(expanded)
    return qu


def lay_name(display: str) -> str:
    """'Creatinine [Mass/volume] in Serum or Plasma' -> 'creatinine'; 'Essential hypertension (disorder)' -> 'high blood pressure'."""
    d = re.sub(r"\s*\((disorder|finding|procedure|situation|morphologic abnormality|regime/therapy|substance|organism)\)\s*$", "", display or "")
    low = d.lower().strip()
    if low in CONDITION_LAY:
        return CONDITION_LAY[low]
    d = re.sub(r"\s*\[.*?\]", "", d)
    d = re.sub(r"\s+(in|by|from)\s+(serum|plasma|blood|urine|arterial|venous|capillary).*$", "", d, flags=re.I)
    d = re.sub(r"\s+by\s+.*$", "", d, flags=re.I)
    return d.strip().lower() or low
