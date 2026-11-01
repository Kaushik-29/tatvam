"""
MedResolve — Phase 5.5.2
Automated Verification Tests for Independent Ground Truth,
Held-Out Test Integrity, Field Metric Reproducibility, and Final Frozen Manifest.
"""

import hashlib
import json
from pathlib import Path
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
PHASE5_5_2_DIR = BASE_DIR / "results" / "rag" / "phase5_5_2"
UNTOUCHED_DOCS_DIR = BASE_DIR / "data" / "processed" / "phase5_5_2_untouched"


def test_independent_ground_truth_audit_integrity():
    """Verify digital PDF ground truth is independent of the extraction engine (Task 1)."""
    gt_audit_path = PHASE5_5_2_DIR / "independent_ground_truth_audit.json"
    assert gt_audit_path.exists(), "independent_ground_truth_audit.json missing"

    with open(gt_audit_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["total_documents_audited"] == 60
    assert "Strictly Engine-Independent Reference Specification" in data["methodology"]

    # Verify separation of digital vector PDF from scanned OCR
    dig_summary = data["digital_pdf_transcription_summary"]
    scn_summary = data["scanned_image_ocr_summary"]

    assert dig_summary["document_count"] == 18
    assert dig_summary["extraction_engine"] == "PyMuPDF_Direct_Vector_Text"
    assert dig_summary["reference_source"] == "GENERATOR_INTENDED_SPECIFICATION"
    assert dig_summary["exact_document_match_count"] == 15

    assert scn_summary["document_count"] == 42
    assert scn_summary["extraction_engine"] == "RapidOCR_ONNX_CPU"
    assert scn_summary["reference_source"] == "GENERATOR_INTENDED_SPECIFICATION"
    assert scn_summary["exact_document_match_count"] == 0

    # Ensure every single record has reference_source == GENERATOR_INTENDED_SPECIFICATION
    records = data["per_document_audit_records"]
    assert len(records) == 60
    for r in records:
        assert r["reference_source"] == "GENERATOR_INTENDED_SPECIFICATION"
        assert r["character_denominator"] > 0
        assert r["word_denominator"] > 0
        assert 0.0 <= r["character_error_rate"] <= 1.0
        assert 0.0 <= r["word_error_rate"] <= 1.0


def test_heldout_contamination_audit_isolation():
    """Verify test-set contamination audit and untouched test partition isolation (Task 2)."""
    audit_path = PHASE5_5_2_DIR / "heldout_contamination_audit.json"
    assert audit_path.exists(), "heldout_contamination_audit.json missing"

    with open(audit_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Check historical exposure analysis
    hist_analysis = data["historical_contamination_analysis"]
    assert hist_analysis["historical_overlap_detected"] is True
    assert hist_analysis["overlap_fraction"] == "10/10 (100%)"
    assert "historical exposure" in hist_analysis["root_cause_explanation"].lower()

    # Check brand-new untouched partition
    untouched = data["phase5_5_2_untouched_partition"]
    assert untouched["untouched_cohort_size"] == 10
    assert untouched["overlap_with_historical_corpus"] == 0
    assert untouched["overlap_fraction"] == "0/10 (0.0%)"
    assert untouched["unseen_templates_verified"] is True

    # Verify set disjointness
    hist_set = set(hist_analysis["historical_document_ids"])
    untouched_set = set(untouched["untouched_document_ids"])
    assert len(hist_set.intersection(untouched_set)) == 0

    # Verify rule freeze code hash matches actual ocr_service.py
    ocr_service_bytes = (BASE_DIR / "backend" / "ocr_service.py").read_bytes()
    expected_sha256 = hashlib.sha256(ocr_service_bytes).hexdigest()
    assert data["rule_freeze_code_hash_sha256"] == expected_sha256


def test_field_metrics_bipartite_accounting():
    """Verify field metrics reproducibility, 1:1 bipartite matching, and error tracking (Task 3)."""
    metrics_path = PHASE5_5_2_DIR / "final_ocr_field_metrics.json"
    assert metrics_path.exists(), "final_ocr_field_metrics.json missing"

    with open(metrics_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["accounting_integrity_verified"] is True
    assert data["single_counting_verified"] is True

    # 1. Historical cohort checks
    hist = data["historical_50_benchmark_cohort"]["micro_metrics"]
    assert hist["expected_fields"] == 116
    assert hist["extracted_fields"] == 108
    assert hist["true_positives"] == 91
    assert hist["false_positives"] == 17
    assert hist["false_negatives"] == 25
    assert hist["true_positives"] + hist["false_negatives"] == hist["expected_fields"]
    assert hist["true_positives"] + hist["false_positives"] == hist["extracted_fields"]
    assert hist["exact_value_matches"] == 89
    assert hist["exact_value_match_rate_among_tp"] == 0.978

    # 2. Untouched cohort checks (brand new 10 docs)
    unt = data["untouched_10_heldout_cohort"]["micro_metrics"]
    assert unt["expected_fields"] == 27
    assert unt["extracted_fields"] == 23
    assert unt["true_positives"] == 19
    assert unt["false_positives"] == 4
    assert unt["false_negatives"] == 8
    assert unt["true_positives"] + unt["false_negatives"] == unt["expected_fields"]
    assert unt["true_positives"] + unt["false_positives"] == unt["extracted_fields"]
    assert unt["precision"] == 0.8261
    assert unt["recall"] == 0.7037
    assert unt["f1_score"] == 0.7600
    assert unt["exact_value_matches"] == 19
    assert unt["exact_value_match_rate_among_tp"] == 1.0  # 100% value accuracy among TP

    # 3. Combined checks
    comb = data["combined_60_document_total"]["micro_metrics"]
    assert comb["expected_fields"] == 116 + 27 == 143
    assert comb["extracted_fields"] == 108 + 23 == 131
    assert comb["true_positives"] == 91 + 19 == 110
    assert comb["false_positives"] == 17 + 4 == 21
    assert comb["false_negatives"] == 25 + 8 == 33
    assert comb["exact_value_matches"] == 89 + 19 == 108

    # Check error breakdown records
    err_bk = data["error_breakdown"]
    assert err_bk["total_incorrect_or_missed_fields"] == len(err_bk["incorrect_field_records"])
    for rec in err_bk["incorrect_field_records"]:
        assert rec["error_type"] in ["MISSED_FIELD_IN_EXTRACTION", "NUMERIC_TRANSCRIPTION_MISMATCH"]
        assert "document_id" in rec
        assert "field_identifier" in rec


def test_cer_wer_divergence_investigation():
    """Verify CER vs WER difference investigation across all 7 categories (Task 4)."""
    cer_wer_path = PHASE5_5_2_DIR / "final_ocr_cer_wer_metrics.json"
    assert cer_wer_path.exists(), "final_ocr_cer_wer_metrics.json missing"

    with open(cer_wer_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    inv = data["cer_vs_wer_divergence_investigation"]
    assert len(inv["underlying_causes"]) >= 4
    causes = [c["factor"] for c in inv["underlying_causes"]]
    assert any("Segmentation" in c for c in causes)
    assert any("Levenshtein" in c for c in causes)
    assert any("Delimiter" in c for c in causes)
    assert any("Bounding Box" in c for c in causes)

    cat_metrics = data["category_metrics_independent_reference"]
    assert len(cat_metrics) == 7

    # In scanned categories, WER is significantly higher than CER
    for scn_cat in ["clean_scanned_lab", "scanned_prescription", "noisy_scan", "ambiguous_or_missing_unit"]:
        m = cat_metrics[scn_cat]
        assert m["word_error_rate"] > m["character_error_rate"] * 3, (
            f"Category {scn_cat}: WER ({m['word_error_rate']}) should be > 3x CER ({m['character_error_rate']})"
        )

    # Tables with structured text have 0 edit distance
    tbl = cat_metrics["medical_table"]
    assert tbl["character_error_rate"] == 0.0
    assert tbl["word_error_rate"] == 0.0
    assert tbl["exact_match_rate"] == 1.0


def test_confidence_separation_no_artificial_zeros():
    """Verify confidence separation terminology, sample counts, and lack of 0.0 imputation (Task 5)."""
    conf_path = PHASE5_5_2_DIR / "final_ocr_confidence_analysis.json"
    assert conf_path.exists(), "final_ocr_confidence_analysis.json missing"

    with open(conf_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["approved_terminology"] == "Confidence Separation Between Correct and Incorrect Detections"

    sep = data["optical_confidence_separation"]
    assert sep["correctly_detected_extractions"]["sample_count"] == 108
    assert sep["correctly_detected_extractions"]["mean_optical_confidence"] > 0.95

    assert sep["incorrect_or_false_positive_extractions"]["sample_count"] == 23
    assert sep["incorrect_or_false_positive_extractions"]["mean_optical_confidence"] > 0.95

    assert sep["missed_extractions_count"] == 33
    assert "no artificial zero imputation" in sep["missed_extractions_handling"].lower()

    # Clinical trustworthiness warning
    trust_stmt = data["clinical_trustworthiness_statement"]
    assert "rapidocr confidence alone must never be used" in trust_stmt.lower()


def test_frozen_benchmark_manifest():
    """Verify cryptographic manifest integrity, code hash, and document inventory (Task 7)."""
    manifest_path = PHASE5_5_2_DIR / "final_benchmark_manifest.json"
    assert manifest_path.exists(), "final_benchmark_manifest.json missing"

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    meta = data["metadata"]
    assert meta["evaluation_phase"] == "Phase 5.5.2"
    assert meta["total_documents_evaluated"] == 60

    # Verify all 10 untouched files exist and their SHA256 hashes match the manifest
    untouched_docs = data["datasets"]["untouched_held_out_partition"]["documents"]
    assert len(untouched_docs) == 10

    for d in untouched_docs:
        file_path = UNTOUCHED_DOCS_DIR / d["filename"]
        assert file_path.exists(), f"Untouched file {d['filename']} missing"
        actual_sha256 = hashlib.sha256(file_path.read_bytes()).hexdigest()
        assert actual_sha256 == d["file_sha256"], f"SHA256 mismatch for {d['filename']}"
