"""Answer modes: "memory" (uses the health record), "normal" (general answer, the record is not read)
and "both" (the two answers side by side, so the patient can see what the record changes)."""

import collections
import json

import pytest
from fastapi.testclient import TestClient

import backend.api.auth as auth
import backend.api.patient_routes as routes
import backend.rag.pipeline as pipeline
from backend.fhir_ingestion.synthea_ingest import BundleMapper
from backend.patient_memory import db as dbmod
from backend.patient_memory.db import session_scope
from backend.patient_memory.models import ClinicalRecord, Patient
from backend.rag.pipeline import NORMAL_MODE_NOTE, PipelineDeps
from backend.stair_retriever.selector import StructuralSelector
from tests.fixtures.fhir_fixture import bundle

FEVER = "I have had a fever since this morning, which medicine can I take?"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    dbmod.get_engine(f"sqlite:///{(tmp_path / 'modes.db').as_posix()}")
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


def _register(client, email="meera@example.org", onboarded=True):
    r = client.post("/api/v2/auth/register", json={"email": email, "password": "correct-horse-1",
                                                     "given_name": "Meera", "birth_date": "1995-05-05"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    if onboarded:
        client.put("/api/v2/profile", json={"onboarding_complete": True}, headers=h)
    return h


def test_both_mode_shows_what_the_record_changes(client):
    h = _register(client)
    assert client.post("/api/v2/records", json={"leaf_path": "allergy_history", "display": "Paracetamol"},
                       headers=h).status_code in (200, 201)
    r = client.post("/api/v2/consult", json={"query": FEVER, "mode": "both"}, headers=h)
    assert r.status_code == 200
    out = r.json()
    normal, memory = out["normal"], out["memory"]
    assert out["mode"] == "both" and out["pair_id"] and normal["pair_id"] == memory["pair_id"] == out["pair_id"]
    assert normal["memory_mode"] == "normal" and memory["memory_mode"] == "memory"
    assert normal["action"] == memory["action"] == "GENERAL_OPTIONS"
    # normal mode does not know about the allergy; memory mode removes paracetamol because of it
    assert "paracetamol" in normal["medicine_options"]["options"]
    assert "paracetamol" not in memory["medicine_options"]["options"]
    assert "allergy" in memory["final_text"].lower()
    assert "Not checked against your records" in normal["final_text"]
    assert "Checked against your records" in memory["final_text"]
    assert normal["final_text"].startswith(NORMAL_MODE_NOTE)
    assert "not checked against your records" in normal["action_reason"]
    assert normal["evidence"] == [] and normal["medicine_options"]["record_aliases"] == []
    assert "record_offer" not in normal and memory["record_offer"]["status"] == "pending"
    # both answers are kept, and the history says which mode each used
    modes = sorted(c["memory_mode"] for c in client.get("/api/v2/consultations", headers=h).json())
    assert modes == ["memory", "normal"]


def test_normal_mode_never_reads_the_record(client):
    demo = client.post("/api/v2/auth/demo-login/syn-a").json()["access_token"]
    dh = {"Authorization": f"Bearer {demo}"}
    q = {"query": "Do I have any allergies I should mention to my dentist before an antibiotic?"}
    memory = client.post("/api/v2/consult", json={**q, "mode": "memory"}, headers=dh).json()
    normal = client.post("/api/v2/consult", json={**q, "mode": "normal"}, headers=dh).json()
    assert any("penicillin" in e["concept_display"].lower() for e in memory["evidence"])
    assert normal["evidence"] == [] and normal["findings"] == [] and normal["retrieval_trace"] is None
    assert "penicillin" not in normal["final_text"].lower()


def test_normal_mode_answers_even_without_history(client):
    h = _register(client, onboarded=False)          # set-up never finished, no records
    q = {"query": "What are common causes of a headache that comes back every afternoon for two weeks?"}
    assert client.post("/api/v2/consult", json={**q, "mode": "memory"}, headers=h).json()["action"] == "ASK"
    normal = client.post("/api/v2/consult", json={**q, "mode": "normal"}, headers=h).json()
    assert normal["action"] == "EXPLAIN" and normal["final_text"].startswith(NORMAL_MODE_NOTE)
    assert "Not used: normal mode does not read your health records." in normal["final_text"]


def test_emergency_screen_still_runs_in_normal_and_both_modes(client):
    h = _register(client)
    q = "I have crushing chest pain going to my left arm and I am sweating"
    assert client.post("/api/v2/consult", json={"query": q, "mode": "normal"}, headers=h).json()["action"] == "EMERGENCY_OVERRIDE"
    both = client.post("/api/v2/consult", json={"query": q, "mode": "both"}, headers=h).json()
    assert both["normal"]["action"] == both["memory"]["action"] == "EMERGENCY_OVERRIDE"


def test_safety_blocks_still_apply_in_normal_mode(client):
    h = _register(client)
    r = client.post("/api/v2/consult", json={"query": "My 4 year old son has a fever, which syrup can I give?", "mode": "normal"},
                    headers=h).json()
    assert r["action"] == "ABSTAIN_AND_NAVIGATE"


def test_stream_both_labels_every_event_with_its_panel(client):
    h = _register(client)
    with client.stream("POST", "/api/v2/consult/stream", json={"query": FEVER, "mode": "both"}, headers=h) as r:
        body = "".join(r.iter_text())
    events = []
    for block in body.strip().split("\n\n"):
        ev = next(l[7:] for l in block.splitlines() if l.startswith("event: "))
        data = json.loads(next(l[6:] for l in block.splitlines() if l.startswith("data: ")))
        events.append((ev, data))
    assert all("panel" in d for _, d in events)
    done = [d for e, d in events if e == "done"]
    assert [d["panel"] for d in done] == ["normal", "memory"]            # normal is ready first
    assert [d["memory_mode"] for d in done] == ["normal", "memory"]
    stages = {p: [d["stage"] for e, d in events if e == "stage" and d["panel"] == p] for p in ("normal", "memory")}
    assert "retrieving_patient_context" not in stages["normal"] and "retrieving_patient_context" in stages["memory"]


def test_default_is_memory_and_unknown_modes_are_rejected(client):
    h = _register(client)
    assert client.post("/api/v2/consult", json={"query": FEVER}, headers=h).json()["memory_mode"] == "memory"
    assert client.post("/api/v2/consult", json={"query": FEVER, "mode": "everything"}, headers=h).status_code == 422
