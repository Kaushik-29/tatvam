"""After an answer about a new problem, the patient chooses whether it is added to their record."""

import collections

import pytest
from fastapi.testclient import TestClient

import backend.api.auth as auth
import backend.api.patient_routes as routes
import backend.rag.pipeline as pipeline
from backend.fhir_ingestion.synthea_ingest import BundleMapper
from backend.patient_memory import db as dbmod
from backend.patient_memory.db import session_scope
from backend.patient_memory.models import ClinicalRecord, Patient
from backend.rag.pipeline import PipelineDeps
from backend.stair_retriever.selector import StructuralSelector
from tests.fixtures.fhir_fixture import bundle

NEW_PROBLEM = {"query": "I have a cough since yesterday, which medicine can I take?"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    dbmod.get_engine(f"sqlite:///{(tmp_path / 'offer.db').as_posix()}")
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


@pytest.fixture()
def user(client):
    r = client.post("/api/v2/auth/register", json={"email": "ravi@example.org", "password": "correct-horse-1",
                                                     "given_name": "Ravi", "birth_date": "2000-01-01"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    client.put("/api/v2/profile", json={"onboarding_complete": True}, headers=h)
    return h


def _symptoms(client, h):
    return [r for r in client.get("/api/v2/records", headers=h).json()
            if r["leaf_path"] == "clinical_encounters/previous_symptoms"]


def test_new_problem_answer_offers_and_saves_only_on_request(client, user):
    r = client.post("/api/v2/consult", json=NEW_PROBLEM, headers=user).json()
    assert r["record_offer"]["status"] == "pending" and r["record_offer"]["suggested"]
    assert _symptoms(client, user) == []                                   # nothing saved automatically
    cid = r["consultation_id"]
    d = client.post(f"/api/v2/consultations/{cid}/record-decision", json={"save": True, "display": "Dry cough"},
                    headers=user).json()
    assert d["status"] == "saved"
    [rec] = _symptoms(client, user)
    assert rec["concept_display"] == "Dry cough" and rec["provenance"]["consultation_id"] == cid
    assert rec["verification_status"] == "patient_reported"
    # the choice is remembered and cannot be applied twice
    assert client.get(f"/api/v2/consultations/{cid}", headers=user).json()["record_offer"]["status"] == "saved"
    assert client.post(f"/api/v2/consultations/{cid}/record-decision", json={"save": True}, headers=user).status_code == 409
    assert len(_symptoms(client, user)) == 1


def test_declining_saves_nothing(client, user):
    cid = client.post("/api/v2/consult", json=NEW_PROBLEM, headers=user).json()["consultation_id"]
    assert client.post(f"/api/v2/consultations/{cid}/record-decision", json={"save": False}, headers=user).json()["status"] == "declined"
    assert _symptoms(client, user) == []


def test_questions_about_existing_records_have_no_offer(client, user):
    r = client.post("/api/v2/consult", json={"query": "Find my previous kidney-related laboratory results"}, headers=user).json()
    assert "record_offer" not in r


def test_demo_and_other_users_cannot_save(client, user):
    cid = client.post("/api/v2/consult", json=NEW_PROBLEM, headers=user).json()["consultation_id"]
    other = client.post("/api/v2/auth/register", json={"email": "x@example.org", "password": "correct-horse-1",
                                                         "given_name": "X"}).json()["access_token"]
    assert client.post(f"/api/v2/consultations/{cid}/record-decision", json={"save": True},
                       headers={"Authorization": f"Bearer {other}"}).status_code == 404
    demo = client.post("/api/v2/auth/demo-login/syn-a").json()["access_token"]
    dh = {"Authorization": f"Bearer {demo}"}
    dcid = client.post("/api/v2/consult", json=NEW_PROBLEM, headers=dh).json()["consultation_id"]
    assert client.post(f"/api/v2/consultations/{dcid}/record-decision", json={"save": True}, headers=dh).status_code == 403
