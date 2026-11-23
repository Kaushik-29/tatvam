"""General over-the-counter medicine options: detection, record checks, and policy boundaries."""
from datetime import date
from types import SimpleNamespace

from backend.rag import medicine_options as M
from backend.rag.pipeline import _policy

NO_EMERGENCY = SimpleNamespace(is_emergency=False, red_flags=[])
QU = SimpleNamespace(is_new_concern=True)


def ev(**recs):
    return {a: {"alias": a, **r} for a, r in recs.items()}


DENGUE = {"leaf_path": "medical_history/conditions", "concept_display": "Dengue", "value_text": "Previous infection"}
CETIRIZINE = {"leaf_path": "medication_history/current_medications", "concept_display": "Cetirizine", "value_text": None}
LEMON = {"leaf_path": "allergy_history", "concept_display": "Lemon", "value_text": "Mild reaction"}


def test_detects_only_general_medicine_requests_for_covered_symptoms():
    assert M.detect("High temperature for 2 hours. Which medicine should I take? I need the medicine name.") == "fever"
    assert M.detect("I keep sneezing, what tablet can I take?") == "allergy"
    assert M.detect("Should I stop my cetirizine?") is None              # change to an existing medicine
    assert M.detect("Which medicine should I take instead of metformin?") is None
    assert M.detect("Which medicine for my knee pain?") is None            # symptom not covered
    assert M.detect("Is my fever connected to my history?") is None       # not a medicine request


def test_fever_answer_uses_dengue_history_allergies_and_current_medicines():
    a = M.build_answer("fever", ev(E1=DENGUE, E2=CETIRIZINE, E3=LEMON))
    t = a["text"]
    assert a["options"] == ["paracetamol"] and "Dolo 650" in t
    assert "Avoid ibuprofen and aspirin until dengue is ruled out" in t
    assert "had dengue before" in t and "[E1]" in t                       # history cited
    assert "Lemon [E3]" in t and "Cetirizine [E2]" in t
    assert "dengue test" in t and "S5" in a["sources"]


def test_allergic_option_is_not_offered_and_duplicate_is_flagged():
    a = M.build_answer("fever", ev(E1={"leaf_path": "allergy_history", "concept_display": "Paracetamol",
                                       "value_text": "rash"}))
    assert a["options"] == [] and "allergy to it [E1]" in a["text"]
    b = M.build_answer("allergy", ev(E1=CETIRIZINE))
    assert "You already take cetirizine [E1]" in b["text"]


def test_dengue_caution_is_general_without_history():
    t = M.build_answer("fever", {})["text"]
    assert "Avoid ibuprofen and aspirin" in t and "had dengue before" not in t
    assert "No allergies are recorded" in t


def test_policy_adults_only_and_decisions_still_abstain():
    q = "Which medicine should I take for fever?"
    assert _policy(NO_EMERGENCY, QU, [], 5, q, "fever", 21)[0] == "GENERAL_OPTIONS"
    assert _policy(NO_EMERGENCY, QU, [], 5, q, "fever", 12)[0] == "ABSTAIN_AND_NAVIGATE"
    assert _policy(NO_EMERGENCY, QU, [], 5, "Should I stop my lisinopril?", None, 21)[0] == "ABSTAIN_AND_NAVIGATE"
    emergency = SimpleNamespace(is_emergency=True, red_flags=["chest pain"])
    assert _policy(emergency, QU, [], 5, q, "fever", 21)[0] == "EMERGENCY_OVERRIDE"


def test_age_years():
    assert M.age_years("2005-08-29", date(2026, 11, 23)) == 21
    assert M.age_years(None) is None


def test_headache_gets_paracetamol_with_record_dependent_nsaid_caution():
    for q in ["I have a headache, which medicine should I take?", "give me a tablet for headache",
              "medicine for body pain"]:
        assert M.detect(q) == "pain", q
    a = M.build_answer("pain", ev(E1=DENGUE, E2=LEMON))
    t = a["text"]
    assert a["options"] == ["paracetamol"] and "mild to moderate pain" in t
    assert "If you also have a fever, avoid ibuprofen and aspirin" in t and "[E1]" in t
    assert "NSAIDs" not in t                                   # no ulcer / kidney / heart record -> not shown
    assert "stiff neck" in t and "S7" in a["sources"]
    ulcer = {"leaf_path": "medical_history/diagnoses", "concept_display": "Peptic ulcer", "value_text": None}
    assert "NSAIDs" in M.build_answer("pain", ev(E1=ulcer))["text"]
    assert "S2" not in M.build_answer("pain", ev(E1=DENGUE))["sources"]   # caution not shown -> source not listed
