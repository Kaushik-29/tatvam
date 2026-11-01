"""
MedResolve — Phase 5.5.2.1
Automated Verification Tests for Reporting Reconciliation,
Template Independence Audit, Macro/Micro CER/WER Separation, and Benchmark Freeze.
"""

import json
from pathlib import Path
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
PHASE5_5_2_1_DIR = BASE_DIR / "results" / "rag" / "phase5_5_2_1"


def test_ground_truth_terminology_and_generator_derived():
    """Verify ground truth is strictly labelled Generator-Derived, Engine-Independent."""
    audit_path = PHASE5_5_2_1_DIR / "heldout_template_audit.json"
    assert audit_path.exists(), "heldout_template_audit.json missing"

    with open(audit_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["ground_truth_classification"] == "Generator-Derived, Engine-Independent Ground Truth"
    assert "synthetic ground truth" in data["human_review_status"].lower()
    assert "zero external human" in data["human_review_status"].lower()


def test_heldout_dataset_template_audit_reporting():
    """Verify 4-dimensional overlap analysis and unseen synthetic document declaration."""
    audit_path = PHASE5_5_2_1_DIR / "heldout_template_audit.json"
    with open(audit_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    overlap = data["overlap_analysis"]
    # 1. Document identity: 0%
    assert overlap["document_identity_overlap"]["overlap_percentage"] == "0.0%"
    assert overlap["document_identity_overlap"]["status"] == "COMPLETELY_DISJOINT"

    # 2. Patient / data: 0%
    assert overlap["patient_and_clinical_data_overlap"]["overlap_percentage"] == "0.0%"
    assert overlap["patient_and_clinical_data_overlap"]["status"] == "COMPLETELY_DISJOINT"

    # 3. Template / canvas: 100% (honest identification)
    assert overlap["template_and_canvas_overlap"]["overlap_percentage"] == "100.0%"
    assert overlap["template_and_canvas_overlap"]["shared_canvas_generators"] is True

    # 4. Layout variation: Moderate
    assert overlap["layout_and_visual_variation"]["variation_degree"] == "MODERATE"
    assert len(overlap["layout_and_visual_variation"]["sources_of_variation"]) >= 4

    # Formal declaration
    decl = data["formal_evaluation_declaration"].lower()
    assert "template independence is not established" in decl
    assert "unseen synthetic-document evaluation" in decl


def test_cer_wer_macro_micro_reconciliation():
    """Verify macro vs micro CER/WER reconciliation and modality naming separation."""
    summary_path = PHASE5_5_2_1_DIR / "cer_wer_macro_micro_summary.json"
    assert summary_path.exists(), "cer_wer_macro_micro_summary.json missing"

    with open(summary_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cohorts = data["cohorts"]
    assert "historical_50_documents" in cohorts
    assert "new_10_document_test_set" in cohorts
    assert "combined_60_documents" in cohorts

    # Check Combined 60 Documents
    comb = cohorts["combined_60_documents"]
    dig = comb["digital_pdf_vector_text_extraction"]
    scn = comb["scanned_image_ocr"]

    assert dig["document_count"] == 18
    assert dig["character_metrics"]["micro_cer"] == 0.0751
    assert dig["character_metrics"]["macro_mean_cer"] == 0.0538
    assert dig["word_metrics"]["micro_wer"] == 0.0697
    assert dig["word_metrics"]["macro_mean_wer"] == 0.0487

    assert scn["document_count"] == 42
    assert scn["character_metrics"]["micro_cer"] == 0.0930
    assert scn["character_metrics"]["macro_mean_cer"] == 0.0933
    assert scn["word_metrics"]["micro_wer"] == 0.5599
    assert scn["word_metrics"]["macro_mean_wer"] == 0.5676

    # Check Historical 50 Documents
    hist = cohorts["historical_50_documents"]
    assert hist["digital_pdf_vector_text_extraction"]["document_count"] == 15
    assert hist["scanned_image_ocr"]["document_count"] == 35

    # Check Untouched 10 Documents
    unt = cohorts["new_10_document_test_set"]
    assert unt["digital_pdf_vector_text_extraction"]["document_count"] == 3
    assert unt["scanned_image_ocr"]["document_count"] == 7


def test_per_document_cer_wer_reconciled():
    """Verify per-document records for all 60 documents exist and are valid."""
    per_doc_path = PHASE5_5_2_1_DIR / "cer_wer_per_document_reconciled.json"
    assert per_doc_path.exists(), "cer_wer_per_document_reconciled.json missing"

    with open(per_doc_path, "r", encoding="utf-8") as f:
        recs = json.load(f)

    assert len(recs) == 60
    for r in recs:
        assert r["reference_source"] == "Generator-Derived, Engine-Independent Ground Truth"
        assert r["modality"] in ["Digital PDF Vector Text Extraction", "Scanned-Image OCR"]
        assert 0.0 <= r["character_error_rate"] <= 1.0
        assert 0.0 <= r["word_error_rate"] <= 1.0


def test_final_benchmark_manifest_v2_freeze():
    """Verify permanent freeze declaration, seed, model hashes, and document checksums."""
    manifest_path = PHASE5_5_2_1_DIR / "final_benchmark_manifest_v2.json"
    assert manifest_path.exists(), "final_benchmark_manifest_v2.json missing"

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["manifest_version"] == "5.5.2.1_FINAL_FREEZE"
    assert "permanently frozen" in data["freeze_declaration"].lower()
    assert data["evaluation_seed"] == 42

    runtime = data["runtime_environment"]
    assert runtime["rapidocr_onnxruntime_version"] == "1.4.4"
    assert runtime["pymupdf_version"] == "1.24.10"

    models = data["onnx_model_assets"]
    assert "ch_PP-OCRv4_det_infer.onnx" in models
    assert "ch_PP-OCRv4_rec_infer.onnx" in models
    assert "ch_ppocr_mobile_v2.0_cls_infer.onnx" in models

    assert data["document_checksums_total"] == 60
    assert len(data["document_checksums"]) == 60
