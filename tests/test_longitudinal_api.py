"""API tests: auth, patient isolation, read-only synthetic patients, consult pipeline (LLM-free)."""

import collections

import pytest
from fastapi.testclient import TestClient

import backend.api.patient_routes as routes
import backend.rag.pipeline as pipeline
from backend.fhir_ingestion.synthea_ingest import BundleMapper
from backend.patient_memory import db as dbmod
from backend.patient_memory.db import session_scope
from backend.patient_memory.models import ClinicalRecord, Patient
from backend.rag.pipeline import PipelineDeps
from backend.stair_retriever.selector import StructuralSelector
from tests.fixtures.fhir_fixture import bundle


@pytest.fixture()
def client(tmp_path, monkeypatch):
    dbmod.get_engine(f"sqlite:///{(tmp_path / 'api.db').as_posix()}")
    with session_scope() as s:
        p, recs, _ = BundleMapper("fixture/a.json", collections.Counter(), collections.Counter()).map_bundle(bundle("syn-a", "a"))
        p["split"] = "test"
        s.add(Patient(**p)); s.flush()
        s.bulk_insert_mappings(ClinicalRecord, recs)
    monkeypatch.setattr(routes, "get_deps", lambda: PipelineDeps(selector=StructuralSelector(embedder=None)))
    monkeypatch.setattr(pipeline, "_vocab_cache", None)
    from backend.main import app
    yield TestClient(app)
    dbmod._engine = None


def _register(c, email):
    r = c.post("/api/v2/auth/register", json={"email": email, "password": "correct-horse-1", "given_name": "Ana"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_auth_required_and_bad_login(client):
    assert client.get("/api/v2/profile").status_code == 401
    assert client.get("/api/v2/profile", headers={"Authorization": "Bearer nonsense"}).status_code == 401
    _register(client, "ana@example.org")
    assert client.post("/api/v2/auth/login", json={"email": "ana@example.org", "password": "wrong-pass"}).status_code == 401
    assert client.post("/api/v2/auth/login", json={"email": "ana@example.org", "password": "correct-horse-1"}).status_code == 200
    assert client.post("/api/v2/auth/register", json={"email": "ana@example.org", "password": "correct-horse-1",
                                                      "given_name": "X"}).status_code == 409


def test_patient_isolation_between_users(client):
    ha, hb = _register(client, "a@example.org"), _register(client, "b@example.org")
    rec = client.post("/api/v2/records", headers=ha, json={"leaf_path": "allergy_history", "display": "Peanut"}).json()
    rid = rec["record_id"]
    assert rec["verification_status"] == "patient_reported"
    assert client.get(f"/api/v2/records/{rid}", headers=ha).status_code == 200
    assert client.get(f"/api/v2/records/{rid}", headers=hb).status_code == 404
    assert client.delete(f"/api/v2/records/{rid}", headers=hb).status_code == 404
    assert client.get("/api/v2/records", headers=hb).json() == []
    synthetic = client.get("/api/v2/records/Condition/a-cond-htn", headers=ha)
    assert synthetic.status_code == 404                     # synthetic patient's data not reachable


def test_empty_profile_asks_instead_of_inventing(client):
    h = _register(client, "new@example.org")
    r = client.post("/api/v2/consult", headers=h, json={"query": "I have had a headache for three days, is it related to my history?"}).json()
    assert r["action"] == "ASK"
    assert r["evidence"] == []
    assert "does not contain any medical history" in r["final_text"]


def test_demo_patient_read_only_and_consult(client):
    demo = client.get("/api/v2/auth/demo-patients").json()
    assert [d["patient_id"] for d in demo] == ["syn-a"]
    tok = client.post("/api/v2/auth/demo-login/syn-a").json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert client.post("/api/v2/records", headers=h, json={"leaf_path": "allergy_history", "display": "x"}).status_code == 403
    toc = client.get("/api/v2/toc", headers=h).json()
    assert any(n["path"] == "medication_history" for n in toc)
    r = client.post("/api/v2/consult", headers=h,
                    json={"query": "Find my previous kidney-related laboratory results and explain them"}).json()
    assert r["action"] in ("EXPLAIN", "ABSTAIN_AND_NAVIGATE")
    assert any("creatinine" in e["concept_key"] for e in r["evidence"])
    assert all(e["patient_id"] == "syn-a" for e in r["evidence"])
    # amoxicillin is active while a penicillin allergy is recorded -> high-severity conflict surfaced
    assert any(f["finding_type"] == "ALLERGY_MEDICATION_CONFLICT" for f in r["findings"])
    hist = client.get("/api/v2/consultations", headers=h).json()
    assert hist and hist[0]["consultation_id"] == r["consultation_id"]


def test_mimic_demo_patients_listed_read_only_but_credentialed_mimic_never(client):
    with session_scope() as s:
        for pid, source in (("mimic-demo-1", "mimic_iv_fhir_demo"), ("mimic-full-1", "mimic_iv")):
            p, recs, _ = BundleMapper("fixture/m.json", collections.Counter(), collections.Counter()).map_bundle(bundle(pid, "m" + pid[-1]))
            p.update(source=source, family_name="Patient_1")
            s.add(Patient(**p)); s.flush()
    listed = [d["patient_id"] for d in client.get("/api/v2/auth/demo-patients").json()]
    assert "mimic-demo-1" in listed and "mimic-full-1" not in listed
    assert client.post("/api/v2/auth/demo-login/mimic-full-1").status_code == 404
    h = {"Authorization": f"Bearer {client.post('/api/v2/auth/demo-login/mimic-demo-1').json()['access_token']}"}
    assert client.post("/api/v2/records", headers=h, json={"leaf_path": "allergy_history", "display": "x"}).status_code == 403
    assert client.get("/api/v2/profile", headers=h).json()["is_demo"] is True


def test_emergency_preempts_retrieval(client):
    tok = client.post("/api/v2/auth/demo-login/syn-a").json()["access_token"]
    r = client.post("/api/v2/consult", headers={"Authorization": f"Bearer {tok}"},
                    json={"query": "I have crushing chest pain spreading to my left arm and I am sweating"}).json()
    assert r["action"] == "EMERGENCY_OVERRIDE"
    assert r["evidence"] == [] and r["references"] == []
    assert r["engine"] == "deterministic_emergency"
