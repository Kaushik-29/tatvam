"""Regression tests for the loopholes found in the security / safety audit (2026-11-25)."""

import collections

import pytest
from fastapi.testclient import TestClient

import backend.api.auth as auth
import backend.api.patient_routes as routes
import backend.rag.pipeline as pipeline
from backend.evidence_reconciliation.emergency import screen_text
from backend.fhir_ingestion.synthea_ingest import BundleMapper
from backend.patient_memory import db as dbmod
from backend.patient_memory.db import session_scope
from backend.patient_memory.models import ClinicalRecord, Patient
from backend.rag import medicine_options as M
from backend.rag.pipeline import PipelineDeps
from backend.stair_retriever.selector import StructuralSelector
from tests.fixtures.fhir_fixture import bundle


# ------------------------------------------------------------------ emergency red flags that were missed
@pytest.mark.parametrize("q", [
    "I took 20 dolo tablets, what should I do",                 # paracetamol overdose by count
    "I swallowed a whole strip of crocin",
    "I have chest burning and left arm pain, antacid?",          # possible heart attack
    "difficulty breathing and cough, which syrup?",
    "black stools and stomach pain, which medicine",             # possible GI bleed
    "I have fever and rash with bleeding gums, which tablet?",   # WHO severe-dengue warning sign
    "fever and vomiting again and again since morning",
])
def test_missed_red_flags_now_trigger_emergency(q):
    assert screen_text(q).is_emergency, q


@pytest.mark.parametrize("q", [
    "I took 2 dolo tablets for my fever",
    "no difficulty breathing, just a cough, which medicine?",
    "I have acidity after spicy food",
    "my gums bleed a little when I brush",                      # no fever: not the dengue rule
    "I have a cough and a runny nose",
])
def test_no_false_emergency_for_ordinary_questions(q):
    assert not screen_text(q).is_emergency, q


# ------------------------------------------------------------------ who the medicine is for
@pytest.mark.parametrize("q,why", [
    ("my 5 year old son has fever, which medicine should I give?", "children"),
    ("my baby has fever which medicine", "children"),
    ("I am 21 years old and my daughter has a cough, which syrup?", "children"),
    ("my mother has fever, which medicine", "another"),
    ("I am pregnant and have a headache, which medicine can I take?", "pregnancy"),
    ("I have diarrhoea and I am breastfeeding, which tablet?", "pregnancy"),
    ("fever for 5 days, which medicine", "lasted about 5 days"),
    ("I have had a cough for two weeks, which medicine?", "lasted about 14 days"),
])
def test_options_blocked_for_children_others_pregnancy_and_long_illness(q, why):
    g = M.detect(q)
    assert g and why in M.blocked_reason(q, g)


@pytest.mark.parametrize("q", ["I am 21 years old and have fever, which medicine?", "fever since 1 day, which medicine?",
                               "medicine for my kidney stone pain? no, for my headache"])
def test_adult_self_questions_still_get_options(q):
    g = M.detect(q)
    assert g and M.blocked_reason(q, g) is None


def test_pregnancy_in_record_blocks_options():
    rec = {"leaf_path": "medical_history/conditions", "concept_display": "Pregnancy", "value_text": "20 weeks"}
    assert "pregnancy" in M.blocked_reason("which medicine for headache", "pain", [rec])


def test_policy_turns_a_block_into_see_a_clinician():
    from types import SimpleNamespace
    no_em = SimpleNamespace(is_emergency=False, red_flags=[])
    act, why = pipeline._policy(no_em, SimpleNamespace(is_new_concern=True), [], 5, "x", "fever", 21, "children reason")
    assert act == "ABSTAIN_AND_NAVIGATE" and why == "children reason"


def test_malformed_birth_date_does_not_crash():
    assert M.age_years("29/08/2005") is None


# ------------------------------------------------------------------ API: input validation, demo privacy, login limit
@pytest.fixture()
def client(tmp_path, monkeypatch):
    dbmod.get_engine(f"sqlite:///{(tmp_path / 'audit.db').as_posix()}")
    with session_scope() as s:
        p, recs, _ = BundleMapper("fixture/a.json", collections.Counter(), collections.Counter()).map_bundle(bundle("syn-a", "a"))
        p["split"] = "test"
        s.add(Patient(**p)); s.flush()
        s.bulk_insert_mappings(ClinicalRecord, recs)
    monkeypatch.setattr(routes, "get_deps", lambda: PipelineDeps(selector=StructuralSelector(embedder=None)))
    monkeypatch.setattr(pipeline, "_vocab_cache", None)
    monkeypatch.setattr(auth, "_failed", {})
    from backend.main import app
    yield TestClient(app)
    dbmod._engine = None


def _register(c, email, **extra):
    return c.post("/api/v2/auth/register", json={"email": email, "password": "correct-horse-1", "given_name": "Ana", **extra})


def test_bad_dates_and_oversized_input_are_rejected(client):
    assert _register(client, "a@example.org", birth_date="29/08/2005").status_code == 422
    r = _register(client, "b@example.org", birth_date="2005-08-29")
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.put("/api/v2/profile", json={"birth_date": "last year"}, headers=h).status_code == 422
    bad = {"leaf_path": "medical_history/conditions", "display": "Dengue", "start": "last monsoon"}
    assert client.post("/api/v2/records", json=bad, headers=h).status_code == 422
    good = {**bad, "start": "2023-07-01"}
    assert client.post("/api/v2/records", json=good, headers=h).status_code == 200
    assert client.post("/api/v2/consult", json={"query": "x" * 2001}, headers=h).status_code == 422


def test_demo_visitors_cannot_see_each_others_questions(client):
    tok = lambda: {"Authorization": "Bearer " + client.post("/api/v2/auth/demo-login/syn-a").json()["access_token"]}
    a, b = tok(), tok()
    r = client.post("/api/v2/consult", json={"query": "I have been dizzy for three days, is it my blood pressure?"}, headers=a)
    assert r.status_code == 200
    cid = r.json()["consultation_id"]
    assert [c["consultation_id"] for c in client.get("/api/v2/consultations", headers=a).json()] == [cid]
    assert client.get("/api/v2/consultations", headers=b).json() == []
    assert client.get(f"/api/v2/consultations/{cid}", headers=b).status_code == 404
    assert client.delete("/api/v2/data/consultations", headers=b).json()["deleted"] == 0
    assert len(client.get("/api/v2/consultations", headers=a).json()) == 1


def test_repeated_failed_logins_are_limited(client):
    _register(client, "c@example.org")
    for _ in range(auth.MAX_FAILED_LOGINS):
        assert client.post("/api/v2/auth/login", json={"email": "c@example.org", "password": "wrong-pass"}).status_code == 401
    r = client.post("/api/v2/auth/login", json={"email": "c@example.org", "password": "correct-horse-1"})
    assert r.status_code == 429


def test_cors_does_not_allow_arbitrary_websites(client):
    r = client.options("/api/v2/profile", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") != "https://evil.example"


def test_legacy_upload_rejects_unknown_or_path_like_patient_ids(client):
    # backend/ocr_service.py is hash-frozen with the OCR evaluation, so the guard is the route itself:
    # only the fixed synthetic patient ids are accepted, before anything is written to disk.
    r = client.post("/api/documents/upload", data={"patient_id": "../../evil"},
                    files={"file": ("x.pdf", b"%PDF-1.4 %%EOF", "application/pdf")})
    assert r.status_code in (400, 404)


def test_healthy_user_with_no_history_gets_a_general_answer(client):
    h = {"Authorization": f"Bearer {_register(client, 'healthy@example.org').json()['access_token']}"}
    q = {"query": "I have had a mild headache for 3 days after long screen time, is it serious?"}
    # never finished setup: still asks for history
    assert client.post("/api/v2/consult", json=q, headers=h).json()["action"] == "ASK"
    # finished setup with nothing to add (a healthy person): answered, with an honest note
    assert client.put("/api/v2/profile", json={"onboarding_complete": True}, headers=h).status_code == 200
    r = client.post("/api/v2/consult", json=q, headers=h).json()
    assert r["action"] == "EXPLAIN"
    assert r["final_text"].startswith("_Your profile lists no past conditions, medicines or allergies")


# ------------------------------------------------------------------ red flags found with the 40 test cases
@pytest.mark.parametrize("q", [
    "I suddenly have weakness in my left arm and face and trouble speaking",
    "worst ever headache came on suddenly",
    "my father is confused and sweating, he takes insulin",
    "I'm 7 weeks pregnant with bleeding and stomach pain",
    "he drank some unknown liquid from the shed",
    "she swallowed some kerosene by mistake",
    "I had a loss of consciousness this morning",
    "I'm diabetic and keep vomiting since morning",
])
def test_red_flags_found_with_the_test_cases(q):
    assert screen_text(q).is_emergency, q


@pytest.mark.parametrize("q", [
    "I'm pregnant, is it safe to keep fit and walk daily?", "I am confused about how to take my cetirizine",
    "I'm diabetic, what foods are good for breakfast?", "I am pregnant, which fruits are good?",
    "my arm is weak after gym yesterday", "I fell asleep late and have a headache", "I drank some juice and feel bloated",
])
def test_new_red_flags_do_not_fire_on_everyday_questions(q):
    assert not screen_text(q).is_emergency, q


def test_test_cases_snapshot_matches_the_current_emergency_screen():
    import json
    from backend.api.patient_routes import TEST_CASES_FILE
    d = json.loads(TEST_CASES_FILE.read_text(encoding="utf-8"))
    assert len(d["cases"]) == 40
    for c in d["cases"]:      # rebuild with scripts/build_test_cases.py whenever the emergency screen changes
        assert c["patient_app"]["emergency"] == screen_text(c["vignette"]).is_emergency, c["id"]
        assert c["options"][c["ai_index"]] == c["ai_answer"]


def test_test_cases_route_requires_login(client):
    assert client.get("/api/v2/test-cases").status_code == 401
    h = {"Authorization": f"Bearer {_register(client, 'tc@example.org').json()['access_token']}"}
    assert len(client.get("/api/v2/test-cases", headers=h).json()["cases"]) == 40


def test_every_test_case_has_an_explanation_of_the_ai_choice():
    import json
    from backend.api.patient_routes import TEST_CASES_FILE
    d = json.loads(TEST_CASES_FILE.read_text(encoding="utf-8"))
    assert d["reasoning_run"]["model"] == d["ai_run"]["model"]          # same model that chose the answers
    assert all(c["ai_reasoning"] and len(c["ai_reasoning"].split()) >= 20 for c in d["cases"])


def test_rater_answers_are_recorded_as_a_rater_not_an_answer_key():
    import json
    from backend.api.patient_routes import TEST_CASES_FILE
    d = json.loads(TEST_CASES_FILE.read_text(encoding="utf-8"))
    assert d["rater"]["qualification"] == "MBBS graduate" and "not an answer key" in d["rater"]["note"].lower() \
        or "NOT an answer key" in d["rater"]["note"]
    assert all(c["rater_answer"] in c["options"] for c in d["cases"])
    assert sum(c["rater_answer"] == c["ai_answer"] for c in d["cases"]) == 34
    assert all(c["answer_index"] is None for c in d["cases"])          # no adjudicated key yet
