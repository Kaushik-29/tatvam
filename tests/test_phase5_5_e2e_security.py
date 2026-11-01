"""
MedResolve — Phase 5.5
Full Workflow & Document Security Audit Tests
"""

import io
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.main import app, UPLOADED_DOCS_STORE

BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE_DIR / "data" / "processed" / "phase5_5_ocr"


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_full_synthetic_workflow(client):
    """Workflow: Synthetic patient selection -> upload -> review -> confirm -> correct -> assess."""
    # 1. Select patient
    from backend.main import LEDGERS_STORE
    from backend.synthetic_data import build_synthetic_ledger
    p_id = "SYNTH_PATIENT_02"
    LEDGERS_STORE[p_id] = build_synthetic_ledger(p_id)


    # 2. Upload document
    pdf_path = DOCS_DIR / "DOC_DIG_LAB_01.pdf"
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    up_resp = client.post(
        "/api/documents/upload",
        data={"patient_id": p_id, "document_type": "LABORATORY_REPORT"},
        files={"file": ("DOC_DIG_LAB_01.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert up_resp.status_code == 200
    doc_id = up_resp.json()["document_id"]

    # 3. Review document
    rev_resp = client.get(f"/api/documents/{p_id}/{doc_id}")
    assert rev_resp.status_code == 200

    # 4. Check ledger
    led_resp = client.get(f"/api/evidence-ledger/{p_id}")
    assert led_resp.status_code == 200
    items = led_resp.json()["items"]
    assert len(items) >= 1
    ev_id = items[0]["evidence_id"]

    # 5. User confirm
    conf_resp = client.post(
        f"/api/evidence-ledger/{p_id}/confirm-item",
        data={"evidence_id": ev_id, "action": "CONFIRM"},
    )
    assert conf_resp.status_code == 200

    # 6. User correct
    cor_resp = client.post(
        f"/api/evidence-ledger/{p_id}/update-item",
        data={"evidence_id": ev_id, "action": "CORRECT", "corrected_value": "114.5", "corrected_unit": "mg/dL"},
    )
    assert cor_resp.status_code == 200

    # 7. Assess patient
    asmt_resp = client.post(f"/api/assess/{p_id}")
    assert asmt_resp.status_code == 200
    asmt_data = asmt_resp.json()
    assert asmt_data["workflow_stage"] == "COMPLETED"
    assert "policy_decision" in asmt_data


def test_security_upload_size_limit_15mb(client):
    """Verify uploads exceeding 15MB are rejected with 400 Bad Request."""
    oversized = b"%PDF-1.4\n" + b"X" * (15 * 1024 * 1024 + 100)
    resp = client.post(
        "/api/documents/upload",
        data={"patient_id": "SYNTH_PATIENT_01"},
        files={"file": ("huge.pdf", io.BytesIO(oversized), "application/pdf")},
    )
    assert resp.status_code == 400
    assert "15 MB" in resp.json()["detail"]


def test_security_magic_bytes_validation(client):
    """Verify files with mismatched magic bytes are rejected."""
    fake_pdf = b"NOT_A_PDF_MAGIC_BYTES_HEADER"
    resp = client.post(
        "/api/documents/upload",
        data={"patient_id": "SYNTH_PATIENT_01"},
        files={"file": ("fake.pdf", io.BytesIO(fake_pdf), "application/pdf")},
    )
    assert resp.status_code == 400
    assert "magic bytes" in resp.json()["detail"].lower()


def test_security_cross_patient_document_isolation(client):
    """Verify document ID cannot be used by another patient."""
    # Upload document for SYNTH_PATIENT_01
    pdf_path = DOCS_DIR / "DOC_DIG_LAB_01.pdf"
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    up_resp = client.post(
        "/api/documents/upload",
        data={"patient_id": "SYNTH_PATIENT_01", "document_type": "LAB_REPORT"},
        files={"file": ("isolation_test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    doc_id = up_resp.json()["document_id"]

    # Attempt cross-patient access using SYNTH_PATIENT_02
    cross_resp = client.get(f"/api/documents/SYNTH_PATIENT_02/{doc_id}")
    cross_file_resp = client.get(f"/api/documents/SYNTH_PATIENT_02/{doc_id}/file")

    assert cross_resp.status_code == 404
    assert cross_file_resp.status_code == 404
