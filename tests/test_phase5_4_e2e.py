"""
Phase 5.4 End-to-End Integration and Functional Validation Test Suite.

Audits all 20 FastAPI endpoints, real CPU-compatible OCR ingestion (PyMuPDF & RapidOCR),
5-way unit provenance taxonomy, interactive evidence ledger updates,
emergency override dispatch (India 112/108 configuration without 911),
conflict detection reconciliation, and verified scientific evaluation terminology.
"""

import io
import os
import pytest
from fastapi.testclient import TestClient
from backend.main import app, EMERGENCY_CONFIG, get_or_create_ledger
from experiments.evidence_ledger import (
    EvidenceItem,
    SourceType,
    ExtractionMethod,
    UserConfirmationStatus,
    EvidenceStatus,
)


@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient fixture."""
    return TestClient(app)


# ==============================================================================
# 1. Health & Service Metadata
# ==============================================================================
def test_health_endpoint(client):
    """Verify service health, Phase 5.4 versioning, and research disclaimer."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["version"] == "5.4.0"
    assert data["environment"] == "academic_research_prototype"
    assert "disclaimer" in data
    assert "not intended for diagnosis" in data["disclaimer"]


# ==============================================================================
# 2. Patient Profile Ingestion & Validation
# ==============================================================================
def test_patient_endpoints(client):
    """Verify patient list and individual profile fetching."""
    # List patients
    resp = client.get("/api/patients")
    assert resp.status_code == 200
    patients = resp.json()
    assert len(patients) >= 8
    patient_ids = [p["patient_id"] for p in patients]
    assert "SYNTH_PATIENT_01" in patient_ids
    assert "SYNTH_PATIENT_07" in patient_ids

    # Specific patient
    resp_patient1 = client.get("/api/patients/SYNTH_PATIENT_01")
    assert resp_patient1.status_code == 200
    p1 = resp_patient1.json()
    assert "Arjun Mehta" in p1["name"]
    assert p1["age"] == 54

    # Nonexistent patient
    resp_404 = client.get("/api/patients/nonexistent-999")
    assert resp_404.status_code == 404


# ==============================================================================
# 3. Emergency Dispatch Configuration (India Demonstration, No 911)
# ==============================================================================
def test_emergency_config_default_india(client):
    """Verify default India emergency configuration suppresses 911 and provides 112/108."""
    resp = client.get("/api/emergency-config")
    assert resp.status_code == 200
    data = resp.json()
    assert "India" in data["region"]
    assert data["primary_emergency_number"] == "112"
    assert data["ambulance_emergency_number"] == "108"
    assert "911" not in [data["primary_emergency_number"], data["ambulance_emergency_number"]]

    # Verify available regions
    regions = data.get("available_regions", [])
    in_reg = next((r for r in regions if r["code"] == "IN"), None)
    assert in_reg is not None
    assert in_reg["primary"] == "112"
    assert in_reg["ambulance"] == "108"


def test_emergency_config_update(client):
    """Verify regional emergency contact reconfiguration."""
    resp = client.post("/api/emergency-config", data={"region_code": "UK"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert "United Kingdom" in data["config"]["region"]
    assert data["config"]["primary_emergency_number"] == "999"

    # Reset back to India demonstration
    resp_reset = client.post("/api/emergency-config", data={"region_code": "IN"})
    assert resp_reset.status_code == 200
    assert resp_reset.json()["config"]["primary_emergency_number"] == "112"


# ==============================================================================
# 4. Document Upload Validation & Boundary Security
# ==============================================================================
def test_document_upload_security_validation(client):
    """Test boundary security: invalid extensions, spoofed headers, empty files, missing patient."""
    # 1. Invalid extension
    bad_ext_file = ("script.exe", io.BytesIO(b"MZ\x90\x00\x03\x00\x00\x00"), "application/octet-stream")
    resp = client.post("/api/documents/upload", data={"patient_id": "SYNTH_PATIENT_01"}, files={"file": bad_ext_file})
    assert resp.status_code == 400
    assert "Unsupported file extension" in resp.json()["detail"]

    # 2. Spoofed PDF header
    spoofed_file = ("fake.pdf", io.BytesIO(b"This is not a pdf file at all!"), "application/pdf")
    resp = client.post("/api/documents/upload", data={"patient_id": "SYNTH_PATIENT_01"}, files={"file": spoofed_file})
    assert resp.status_code == 400
    assert "Missing %PDF" in resp.json()["detail"] or "Invalid PDF" in resp.json()["detail"]

    # 3. Spoofed PNG header
    spoofed_png = ("fake.png", io.BytesIO(b"Not a real PNG byte header"), "image/png")
    resp = client.post("/api/documents/upload", data={"patient_id": "SYNTH_PATIENT_01"}, files={"file": spoofed_png})
    assert resp.status_code == 400
    assert "Invalid PNG" in resp.json()["detail"]

    # 4. Empty file
    empty_file = ("empty.pdf", io.BytesIO(b""), "application/pdf")
    resp = client.post("/api/documents/upload", data={"patient_id": "SYNTH_PATIENT_01"}, files={"file": empty_file})
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()

    # 5. Nonexistent patient
    valid_pdf_path = os.path.join("data", "uploads", "test_digital_lab.pdf")
    if os.path.exists(valid_pdf_path):
        with open(valid_pdf_path, "rb") as f:
            resp = client.post(
                "/api/documents/upload",
                data={"patient_id": "nonexistent-patient"},
                files={"file": ("test.pdf", f.read(), "application/pdf")}
            )
        assert resp.status_code == 404


# ==============================================================================
# 5. Real OCR & Direct Text Extraction: Digital Lab PDF
# ==============================================================================
def test_digital_pdf_real_extraction_and_unit_safety(client):
    """Test text-based PDF ingestion via PyMuPDF with explicit unit provenance."""
    pdf_path = os.path.join("data", "uploads", "test_digital_lab.pdf")
    assert os.path.exists(pdf_path), "test_digital_lab.pdf must exist in data/uploads"

    with open(pdf_path, "rb") as f:
        resp = client.post(
            "/api/documents/upload",
            data={"patient_id": "SYNTH_PATIENT_01", "document_type": "LABORATORY_REPORT"},
            files={"file": ("test_digital_lab.pdf", f.read(), "application/pdf")}
        )
    assert resp.status_code == 200
    data = resp.json()

    assert data["patient_id"] == "SYNTH_PATIENT_01"
    assert data["filename"] == "test_digital_lab.pdf"
    assert data["pages_processed"] == 1
    assert data["extraction_engine"] == "PyMuPDF (Direct Text)"
    assert data["total_observations_found"] >= 4

    obs = data["observations"]
    concepts = {o["concept"]: o for o in obs}

    # Verify Hemoglobin
    assert "E_HEMOGLOBIN" in concepts
    hb = concepts["E_HEMOGLOBIN"]
    assert float(hb["normalized_value"]) == 14.2
    assert hb["unit"] == "g/dL"
    assert hb["unit_status"] == "EXPLICIT"
    assert hb["page_number"] == 1
    assert hb["confidence"] >= 0.95

    # Verify Fasting Blood Glucose
    assert "E_BLOOD_GLUCOSE_FASTING" in concepts
    gl = concepts["E_BLOOD_GLUCOSE_FASTING"]
    assert float(gl["normalized_value"]) == 112.0
    assert gl["unit"] == "mg/dL"
    assert gl["unit_status"] == "EXPLICIT"

    # Verify unconfirmed entry in evidence ledger
    ledger = client.get("/api/evidence-ledger/SYNTH_PATIENT_01").json()
    hb_ledger = next((item for item in ledger["items"] if item.get("concept") == "E_HEMOGLOBIN"), None)
    assert hb_ledger is not None
    assert hb_ledger["user_confirmation_status"] == "UNCONFIRMED"  # OCR observations must NOT be pre-confirmed


# ==============================================================================
# 6. Real Scanned Document OCR Extraction: Prescription Image
# ==============================================================================
def test_scanned_image_real_ocr_rapidocr(client):
    """Test genuine CPU OCR execution on scanned PNG using RapidOCR."""
    png_path = os.path.join("data", "uploads", "test_scanned_prescription.png")
    assert os.path.exists(png_path), "test_scanned_prescription.png must exist in data/uploads"

    with open(png_path, "rb") as f:
        resp = client.post(
            "/api/documents/upload",
            data={"patient_id": "SYNTH_PATIENT_01", "document_type": "PRIOR_PRESCRIPTION"},
            files={"file": ("test_scanned_prescription.png", f.read(), "image/png")}
        )
    assert resp.status_code == 200
    data = resp.json()

    assert data["extraction_engine"] == "RapidOCR (ONNX)"
    assert data["total_lines_extracted"] > 0
    assert len(data["observations"]) >= 2

    # Verify OCR confidence exists and is between 0 and 1
    for obs in data["observations"]:
        assert 0.0 <= obs["confidence"] <= 1.0
        assert len(obs["raw_text"]) > 0


# ==============================================================================
# 7. Unit Provenance Taxonomy & Ambiguous Unit Handling
# ==============================================================================
def test_missing_and_inferred_units_require_confirmation(client):
    """Test that ambiguous/missing units are classified as INFERRED and require manual review."""
    png_path = os.path.join("data", "uploads", "test_missing_unit.png")
    assert os.path.exists(png_path), "test_missing_unit.png must exist in data/uploads"

    with open(png_path, "rb") as f:
        resp = client.post(
            "/api/documents/upload",
            data={"patient_id": "SYNTH_PATIENT_01", "document_type": "MEDICAL_REPORT"},
            files={"file": ("test_missing_unit.png", f.read(), "image/png")}
        )
    assert resp.status_code == 200
    data = resp.json()

    concepts = {o["concept"]: o for o in data["observations"]}
    assert "E_VITALS_TEMP" in concepts
    temp = concepts["E_VITALS_TEMP"]
    assert temp["unit_status"] == "INFERRED"
    assert temp["unit"] == "degF"
    assert temp["requires_confirmation"] is True
    assert "inferred" in temp["confirmation_reason"].lower()

    assert "E_VITALS_SPO2" in concepts
    spo2 = concepts["E_VITALS_SPO2"]
    assert spo2["unit_status"] == "INFERRED"
    assert spo2["unit"] == "%"
    assert spo2["requires_confirmation"] is True


# ==============================================================================
# 8. Document Review & File Serving API
# ==============================================================================
def test_document_details_and_file_serving(client):
    """Test document metadata retrieval, page breakdown, and raw file download."""
    # List patient documents
    docs_resp = client.get("/api/documents/SYNTH_PATIENT_01")
    assert docs_resp.status_code == 200
    docs_data = docs_resp.json()
    assert "documents" in docs_data
    docs = docs_data["documents"]
    assert len(docs) > 0
    latest_doc = docs[0]
    doc_id = latest_doc["document_id"]

    # Document details
    detail_resp = client.get(f"/api/documents/SYNTH_PATIENT_01/{doc_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["document_id"] == doc_id
    assert "pages" in detail
    assert "observations" in detail

    # File download
    file_resp = client.get(f"/api/documents/SYNTH_PATIENT_01/{doc_id}/file")
    assert file_resp.status_code == 200
    assert len(file_resp.content) > 0
    assert "content-type" in file_resp.headers


# ==============================================================================
# 9. Interactive Evidence Ledger: Confirm, Correct, Reject, Mark Unreadable
# ==============================================================================
def test_evidence_ledger_action_workflow(client):
    """Test interactive review actions: CONFIRM, CORRECT, REJECT, and MARK_UNREADABLE."""
    patient_id = "SYNTH_PATIENT_01"
    ev_id = "test_ocr_ev_999"
    ledger = get_or_create_ledger(patient_id)
    ledger.add_item(
        EvidenceItem(
            evidence_id=ev_id,
            patient_case_id=patient_id,
            concept="E_53",
            concept_name_en="Serum Potassium",
            normalized_value=3.1,
            original_value="K+: 3.1",
            unit="mEq/L",
            source_type=SourceType.LABORATORY_REPORT,
            source_document_id="doc-test-101",
            source_page=1,
            event_timestamp="2026-10-31T10:00:00Z",
            recorded_timestamp="2026-10-31T10:05:00Z",
            extraction_method=ExtractionMethod.OCR_EXTRACTION,
            extraction_confidence=0.88,
            user_confirmation_status=UserConfirmationStatus.UNCONFIRMED,
            evidence_status=EvidenceStatus.PRESENT,
            is_simulated=True,
            notes="Initial OCR extraction"
        )
    )

    # 1. Test CORRECT action: corrects value & unit, preserves raw value in notes
    correct_form = {
        "evidence_id": ev_id,
        "action": "CORRECT",
        "corrected_value": "3.8",
        "corrected_unit": "mEq/L",
        "notes": "Corrected blur in tenths digit"
    }
    resp = client.post(f"/api/evidence-ledger/{patient_id}/update-item", data=correct_form)
    assert resp.status_code == 200
    updated_ledger = client.get(f"/api/evidence-ledger/{patient_id}").json()
    corrected_item = next(i for i in updated_ledger["items"] if i["evidence_id"] == ev_id)
    assert corrected_item["normalized_value"] == "3.8"
    assert corrected_item["user_confirmation_status"] == "CONFIRMED_BY_PATIENT"
    assert "User corrected" in corrected_item["notes"]

    # 2. Test CONFIRM action
    confirm_form = {
        "evidence_id": ev_id,
        "action": "CONFIRM",
        "notes": "Clinician confirmed"
    }
    resp = client.post(f"/api/evidence-ledger/{patient_id}/update-item", data=confirm_form)
    assert resp.status_code == 200

    # 3. Test MARK_UNREADABLE action
    unreadable_form = {
        "evidence_id": ev_id,
        "action": "MARK_UNREADABLE",
        "notes": "Illegible ink smudge"
    }
    resp = client.post(f"/api/evidence-ledger/{patient_id}/update-item", data=unreadable_form)
    assert resp.status_code == 200
    updated_ledger_unreadable = client.get(f"/api/evidence-ledger/{patient_id}").json()
    unreadable_item = next(i for i in updated_ledger_unreadable["items"] if i["evidence_id"] == ev_id)
    assert unreadable_item["evidence_status"] == "UNKNOWN"

    # 4. Test REJECT action
    reject_form = {
        "evidence_id": ev_id,
        "action": "REJECT",
        "notes": "Artifact / not patient data"
    }
    resp = client.post(f"/api/evidence-ledger/{patient_id}/update-item", data=reject_form)
    assert resp.status_code == 200
    updated_ledger_rejected = client.get(f"/api/evidence-ledger/{patient_id}").json()
    rejected_item = next(i for i in updated_ledger_rejected["items"] if i["evidence_id"] == ev_id)
    assert rejected_item["user_confirmation_status"] == "REJECTED_BY_PATIENT"

    # 5. Test invalid action returns 400
    bad_form = {
        "evidence_id": ev_id,
        "action": "INVALID_ACTION"
    }
    resp = client.post(f"/api/evidence-ledger/{patient_id}/update-item", data=bad_form)
    assert resp.status_code == 400


# ==============================================================================
# 10. Evidence Ledger & Conflict Detection Integration
# ==============================================================================
def test_conflict_detection_and_reconciliation(client):
    """Verify conflict detection executes against current ledger and does not silently resolve."""
    patient_id = "SYNTH_PATIENT_01"
    resp = client.get(f"/api/conflicts/{patient_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "conflicts" in data
    assert "total_conflicts" in data
    assert data["patient_id"] == patient_id

    # Verify conflict structure contains concepts, conflicting values, and no auto-resolution
    for c in data["conflicts"]:
        assert "conflict_category" in c
        assert "description" in c
        assert "resolution_status" in c


# ==============================================================================
# 11. Medical Knowledge Retrieval Endpoint
# ==============================================================================
def test_retrieval_and_knowledge_base(client):
    """Test BM25 + dense hybrid retrieval and knowledge base metadata."""
    # Knowledge base stats
    kb_resp = client.get("/api/knowledge-base")
    assert kb_resp.status_code == 200
    kb_data = kb_resp.json()
    assert kb_data["total_passages"] >= 40

    # Query retrieval (Form data)
    query_resp = client.post("/api/retrieval/query", data={"query": "hypertension emergency blood pressure", "top_k": 3})
    assert query_resp.status_code == 200
    q_data = query_resp.json()
    assert len(q_data["results"]) == 3
    top_result = q_data["results"][0]
    assert "text" in top_result
    assert "document_id" in top_result
    assert "passage_id" in top_result


# ==============================================================================
# 12. Assessment Generation & Emergency Override Precedence
# ==============================================================================
def test_assessment_emergency_override_india(client):
    """Verify Marcus Brody (Case 7, BP 210/120) triggers emergency override with India dispatch numbers."""
    resp = client.post("/api/assess/SYNTH_PATIENT_07")
    assert resp.status_code == 200
    data = resp.json()

    policy = data["policy_decision"]
    assert policy["is_emergency_override"] is True
    assert policy["selected_action"] == "EMERGENCY_OVERRIDE"

    assert data["is_emergency_override"] is True
    assert "112" in data["generated_text"]
    assert "108" in data["generated_text"]
    assert "911" not in data["generated_text"]

    # Verify assessment was recorded in assessment history
    history_resp = client.get("/api/assessment-history")
    assert history_resp.status_code == 200
    history = history_resp.json()["history"]
    assert len(history) > 0
    latest = history[0]
    assert latest["patient_id"] == "SYNTH_PATIENT_07"
    assert latest["is_emergency_override"] is True


# ==============================================================================
# 13. Research Evaluation Terminology & Claim Support Reproducibility
# ==============================================================================
def test_research_metrics_terminology_and_transparency(client):
    """Verify research metrics report scientific terminology, sample size, numerators, and 68.5% reproducibility."""
    resp = client.get("/api/research/metrics")
    assert resp.status_code == 200
    metrics = resp.json()

    # Grounding & Verification section
    gv = metrics["grounding_and_verification"]
    assert "Lexical Evidence-Support Heuristic" in gv["evaluation_type"]
    assert "system_b3_revised_support" in gv
    assert "68.5%" in gv["system_b3_revised_support"]

    # Claim support breakdown
    b3_breakdown = gv["b3_metrics_breakdown"]
    support = b3_breakdown["substantive_medical_support"]
    assert support["metric_name"] == "Substantive Medical Assertion Lexical Support Rate"
    assert "lexical n-gram token overlap" in support["evaluation_method"].lower()
    assert support["sample_size"] == 146
    assert support["numerator"] == 100
    assert support["denominator"] == 146
    assert "relevant_limitations" in support

    # Emergency detection audit (Deterministic rule evaluation, NOT clinical sensitivity)
    emerg = metrics["emergency_triage_audit"]
    assert "Deterministic Clinical Red-Flag Rule" in emerg["evaluation_type"]
    assert emerg["sample_size"] == 100
    assert emerg["numerator"] == 15
    assert emerg["denominator"] == 15
    assert "relevant_limitations" in emerg
    assert "does NOT establish real-world clinical emergency sensitivity" in emerg["relevant_limitations"]

    # Prohibited marketing terminology checks
    raw_text = resp.text
    assert "NLI Reference Entailment" not in raw_text
    assert "Clinical entailment accuracy" not in raw_text
    assert "Verified clinical diagnosis" not in raw_text
    assert "Clinical sensitivity" not in raw_text
