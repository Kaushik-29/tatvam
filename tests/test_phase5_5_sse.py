"""
MedResolve — Phase 5.5
Server-Sent Events (SSE) Streaming Integration Tests
"""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.main import app


def parse_sse(text: str):
    events = []
    curr_ev = "message"
    curr_data = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            if curr_data:
                try:
                    payload = json.loads("\n".join(curr_data))
                except Exception:
                    payload = "\n".join(curr_data)
                events.append({"event": curr_ev, "data": payload})
                curr_ev = "message"
                curr_data = []
            continue
        if line.startswith("event:"):
            curr_ev = line[len("event:"):].strip()
        elif line.startswith("data:"):
            curr_data.append(line[len("data:"):].strip())
    if curr_data:
        try:
            payload = json.loads("\n".join(curr_data))
        except Exception:
            payload = "\n".join(curr_data)
        events.append({"event": curr_ev, "data": payload})
    return events


def test_sse_endpoint_content_type():
    client = TestClient(app)
    response = client.get("/api/assess-stream/SYNTH_PATIENT_01")
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")


def test_sse_in_domain_events_sequence():
    """Verify in-domain patient produces correct event sequence without premature claim delivery."""
    from backend.main import LEDGERS_STORE
    from backend.synthetic_data import build_synthetic_ledger
    LEDGERS_STORE["SYNTH_PATIENT_02"] = build_synthetic_ledger("SYNTH_PATIENT_02")

    client = TestClient(app)
    response = client.get("/api/assess-stream/SYNTH_PATIENT_02")
    assert response.status_code == 200


    events = parse_sse(response.text)
    event_names = [e["event"] for e in events]

    assert "intake" in event_names
    assert "evidence_ledger" in event_names
    assert "conflict_detection" in event_names
    assert "knowledge_retrieval" in event_names
    assert "generation_buffered" in event_names
    assert "claim_verification" in event_names
    assert "final_result" in event_names
    assert "completion" in event_names

    # Check unverified claims are never published before final_result
    early_events = [e for e in events if e["event"] not in ["final_result", "completion"]]
    for ev in early_events:
        assert "generated_text" not in str(ev["data"])


def test_sse_emergency_override_preemption():
    """Verify emergency patient bypasses LLM and returns deterministic safety dispatch."""
    client = TestClient(app)
    response = client.get("/api/assess-stream/SYNTH_PATIENT_07")
    assert response.status_code == 200

    events = parse_sse(response.text)
    event_names = [e["event"] for e in events]

    assert "emergency_override" in event_names
    assert "completion" in event_names

    # Assert that LLM generation and knowledge retrieval are strictly suppressed
    assert "knowledge_retrieval" not in event_names
    assert "generation_buffered" not in event_names

    # Verify dispatch number presence
    em_ev = next(e for e in events if e["event"] == "emergency_override")
    assert "112 / 108" in em_ev["data"]["safety_dispatch"]

    comp_ev = next(e for e in events if e["event"] == "completion")
    assert comp_ev["data"]["llm_invoked"] is False


def test_sse_missing_patient_returns_404():
    """Verify non-existent patient returns HTTP 404 cleanly."""
    client = TestClient(app)
    response = client.get("/api/assess-stream/UNKNOWN_PATIENT_XYZ")
    assert response.status_code == 404
