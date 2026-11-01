"""
MedResolve — Phase 5.5.1
Automated Verification Tests for Benchmark Integrity, Metric Reconciliation,
Held-Out Document Partitions, and Reproducibility Audit.
"""

import io
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.main import app

BASE_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = BASE_DIR / "results" / "rag" / "phase5_5_1"
GT_DIR = BASE_DIR / "data" / "processed" / "phase5_5_ocr" / "ground_truth"


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_field_counts_reconciliation_exact_sum():
    """Verify that category totals sum exactly to overall totals with zero accounting drift."""
    metrics_path = RESULTS_DIR / "ocr_field_metrics_recomputed.json"
    assert metrics_path.exists(), "Recomputed field metrics artifact missing"

    with open(metrics_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    micro = data["micro_averaged_metrics"]
    cats = data["category_breakdown"]

    sum_exp = sum(c["expected_fields"] for c in cats.values())
    sum_ext = sum(c["extracted_fields"] for c in cats.values())
    sum_tp = sum(c["true_positives"] for c in cats.values())
    sum_fp = sum(c["false_positives"] for c in cats.values())
    sum_fn = sum(c["false_negatives"] for c in cats.values())

    # Overall totals must exactly equal the category sums
    assert sum_exp == micro["expected_fields"] == 116
    assert sum_ext == micro["extracted_fields"] == 108
    assert sum_tp == micro["true_positives"] == 91
    assert sum_fp == micro["false_positives"] == 17
    assert sum_fn == micro["false_negatives"] == 25

    # Check arithmetic consistency: TP + FN == Expected; TP + FP == Extracted
    assert micro["true_positives"] + micro["false_negatives"] == micro["expected_fields"]
    assert micro["true_positives"] + micro["false_positives"] == micro["extracted_fields"]


def test_bipartite_matching_uniqueness():
    """Verify each ground-truth field and each extracted field is counted exactly once."""
    doc_recs_path = RESULTS_DIR / "ocr_per_document_recomputed.json"
    assert doc_recs_path.exists()

    with open(doc_recs_path, "r", encoding="utf-8") as f:
        docs = json.load(f)

    assert len(docs) == 50

    total_tp = 0
    total_fp = 0
    total_fn = 0

    for d in docs:
        tp = d["true_positives"]
        fp = d["false_positives"]
        fn = d["false_negatives"]
        exp = d["expected_field_count"]
        ext = d["extracted_field_count"]

        assert tp + fn == exp, f"Doc {d['document_id']}: TP ({tp}) + FN ({fn}) != Exp ({exp})"
        assert tp + fp == ext, f"Doc {d['document_id']}: TP ({tp}) + FP ({fp}) != Ext ({ext})"

        total_tp += tp
        total_fp += fp
        total_fn += fn

    assert total_tp == 91
    assert total_fp == 17
    assert total_fn == 25


def test_multi_page_documents_overlapping_subset():
    """Verify DOC_DIG_LAB_09 and DOC_DIG_LAB_10 are strictly an overlapping subset of digital_lab_pdf."""
    metrics_path = RESULTS_DIR / "ocr_field_metrics_recomputed.json"
    with open(metrics_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    mp = data["multi_page_overlapping_subset"]
    dig = data["category_breakdown"]["digital_lab_pdf"]

    assert mp["document_count"] == 2
    assert mp["expected_fields"] == 11
    # Multi-page fields are strictly contained within digital_lab_pdf's 38 fields
    assert mp["expected_fields"] < dig["expected_fields"]
    assert dig["expected_fields"] == 38


def test_recomputed_cer_wer_approach_a():
    """Verify recomputed CER under Approach A resolves boundary mismatch and digital PDFs have 0 edits."""
    cer_wer_path = RESULTS_DIR / "ocr_cer_wer_recomputed.json"
    assert cer_wer_path.exists()

    with open(cer_wer_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    app_a = data["reconciled_approach_a_full_page_text"]
    assert app_a["overall_cer"] < 0.10, f"Approach A CER too high: {app_a['overall_cer']}"
    assert app_a["overall_cer"] == pytest.approx(0.0587, abs=1e-3)

    # Native vector PDFs must have exact 0 character edits under PyMuPDF direct text extraction
    dig_pdf = app_a["category_breakdown"]["digital_lab_pdf"]
    assert dig_pdf["character_edit_distance"] == 0
    assert dig_pdf["character_error_rate"] == 0.0

    tbl_pdf = app_a["category_breakdown"]["medical_table"]
    assert tbl_pdf["character_edit_distance"] == 0
    assert tbl_pdf["character_error_rate"] == 0.0


def test_held_out_partitions_integrity():
    """Verify reproducible 30 / 10 / 10 partitions are mutually disjoint and sum to 50 documents."""
    holdout_path = RESULTS_DIR / "ocr_holdout_evaluation.json"
    assert holdout_path.exists()

    with open(holdout_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    dev_ids = set(data["development_partition"]["document_ids"])
    val_ids = set(data["validation_partition"]["document_ids"])
    test_ids = set(data["held_out_test_partition"]["document_ids"])

    assert len(dev_ids) == 30
    assert len(val_ids) == 10
    assert len(test_ids) == 10

    # Mutually disjoint
    assert dev_ids.isdisjoint(val_ids)
    assert dev_ids.isdisjoint(test_ids)
    assert val_ids.isdisjoint(test_ids)

    # Union covers all 50 documents
    assert len(dev_ids | val_ids | test_ids) == 50


def test_optical_confidence_no_artificial_zero_imputation():
    """Verify missed fields have None optical_confidence and are not imputed with artificial 0.0."""
    conf_path = RESULTS_DIR / "ocr_confidence_reanalysis.json"
    assert conf_path.exists()

    with open(conf_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["metric_terminology_correction"]["approved_reproducible_term"] == "Confidence Separation Between Correct and Incorrect Detections"
    assert data["optical_confidence_separation"]["missed_ground_truth_fields_count"] == 25

    # Check that reliability bins only cover valid detected observation counts
    total_binned = sum(b["observation_count"] for b in data["reliability_bins"])
    # 89 correct + 19 incorrect detections = 108 detected items
    assert total_binned == 108


def test_sse_audit_execution_trace_and_preemption():
    """Verify SSE audit trace proves emergency preemption suppresses LLM and generation events."""
    sse_path = RESULTS_DIR / "sse_execution_trace_audit.json"
    assert sse_path.exists()

    with open(sse_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Normal in-domain scenario
    normal = data["scenario_a_in_domain_normal"]
    assert normal["llm_invoked"] is True
    assert normal["unverified_content_buffering_verified"] is True
    assert any("generation_buffered" in ev for ev in normal["event_lifecycle_sequence"])
    assert any("final_result" in ev for ev in normal["event_lifecycle_sequence"])

    # Emergency scenario
    emerg = data["scenario_b_emergency_preemption"]
    assert emerg["llm_invoked"] is False
    assert emerg["completion_status"] == "EMERGENCY_PREEMPTED"
    assert not any("generation_buffered" in ev for ev in emerg["event_lifecycle_sequence"])
    assert not any("knowledge_retrieval" in ev for ev in emerg["event_lifecycle_sequence"])


def test_security_audit_and_malformed_upload_handling(client):
    """Verify corrupted / malformed PDF upload returns controlled HTTP 400 without leaking file paths."""
    # Create corrupted PDF: valid magic header '%PDF-1.4\n' followed by corrupt bytes that fitz cannot decode
    corrupted_pdf = b"%PDF-1.4\nCORRUPTED_MALFORMED_TRAILER_EOF_TRUNCATED"

    resp = client.post(
        "/api/documents/upload",
        data={"patient_id": "SYNTH_PATIENT_01", "document_type": "LAB_REPORT"},
        files={"file": ("malformed.pdf", io.BytesIO(corrupted_pdf), "application/pdf")},
    )

    # Must return client error HTTP 400 Bad Request
    assert resp.status_code == 400
    detail = resp.json().get("detail", "")
    assert "Document parsing failed" in detail
    # Strictly zero local filesystem paths or stack traces exposed
    assert "d:\\" not in detail.lower()
    assert "d:/" not in detail.lower()
    assert "c:\\" not in detail.lower()
    assert "c:/" not in detail.lower()
    assert "traceback" not in detail.lower()
    assert "fitz" not in detail.lower()
    assert "data/uploads" not in detail.lower()
