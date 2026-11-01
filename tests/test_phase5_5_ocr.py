"""
MedResolve — Phase 5.5
OCR Accuracy Benchmark & Structured Extraction Tests
"""

import json
from pathlib import Path
import pytest

from backend.ocr_service import MedicalDocumentProcessor, ExtractedObservation

BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE_DIR / "data" / "processed" / "phase5_5_ocr"
GT_DIR = DOCS_DIR / "ground_truth"


@pytest.fixture(scope="module")
def ocr_processor():
    return MedicalDocumentProcessor()


def test_ocr_processor_initialization(ocr_processor):
    """Verify processor initializes with PyMuPDF and RapidOCR."""
    assert ocr_processor is not None
    assert ocr_processor.ocr_engine is not None


def test_digital_pdf_direct_extraction(ocr_processor):
    """Verify digital PDF uses direct text extraction and extracts fields."""
    pdf_path = DOCS_DIR / "DOC_DIG_LAB_01.pdf"
    assert pdf_path.exists(), "DOC_DIG_LAB_01.pdf must exist"

    result = ocr_processor.process_document(pdf_path)
    assert result["total_pages"] == 1
    assert result["pages"][0]["method"] == "DIGITAL_TEXT_EXTRACTION"
    assert result["total_extracted_items"] >= 3

    concepts = [item["concept"] for item in result["structured_items"]]
    assert "E_BLOOD_GLUCOSE_FASTING" in concepts
    assert "E_HBA1C" in concepts
    assert "E_SERUM_CREATININE" in concepts


def test_scanned_image_rapid_ocr(ocr_processor):
    """Verify scanned PNG image triggers RapidOCR ONNX."""
    rx_path = DOCS_DIR / "DOC_RX_01.png"
    assert rx_path.exists(), "DOC_RX_01.png must exist"

    result = ocr_processor.process_document(rx_path)
    assert result["total_pages"] == 1
    assert result["pages"][0]["method"] == "RAPID_OCR_ONNX"
    assert len(result["structured_items"]) >= 1

    rx_item = result["structured_items"][0]
    assert rx_item["concept"] == "E_RX_METFORMIN"
    assert rx_item["medication_name"] == "Metformin"
    assert rx_item["dosage_unit"] == "mg"
    assert rx_item["frequency"] == "OD"
    assert rx_item["duration"] == "30 days"


def test_five_way_provenance_classification(ocr_processor):
    """Verify all 5 provenance states: EXPLICIT, NORMALIZED, INFERRED, MISSING, INVALID."""
    # 1. EXPLICIT: canonical unit matching
    u, s, r = ocr_processor._classify_unit_provenance("E_BLOOD_GLUCOSE_FASTING", "mg/dL", "mg/dL", "110.0")
    assert s == "EXPLICIT"
    assert u == "mg/dL"
    assert r is None

    # 2. NORMALIZED: safe clinical conversion (mEq/L -> mmol/L)
    u, s, r = ocr_processor._classify_unit_provenance("E_POTASSIUM", "mEq/L", "mmol/L", "4.5")
    assert s == "NORMALIZED"
    assert u == "mmol/L"

    # 3. INFERRED: blood pressure without unit
    u, s, r = ocr_processor._classify_unit_provenance("E_VITALS_BP", None, "mmHg", "120/80")
    assert s == "INFERRED"
    assert u == "mmHg"
    assert r is not None

    # 4. MISSING: creatinine without unit cannot be safely inferred
    u, s, r = ocr_processor._classify_unit_provenance("E_SERUM_CREATININE", None, "mg/dL", "1.4")
    assert s == "MISSING"
    assert u is None
    assert r is not None

    # 5. INVALID: physiologically incompatible or unrecognized unit
    u, s, r = ocr_processor._classify_unit_provenance("E_HBA1C", "x_unit", "%", "7.2")
    assert s == "INVALID"
    assert r is not None


def test_unconfirmed_items_mandate_confirmation(ocr_processor):
    """Verify items with INFERRED, MISSING, or INVALID units require confirmation."""
    amb_path = DOCS_DIR / "DOC_AMB_01.png"
    if amb_path.exists():
        result = ocr_processor.process_document(amb_path)
        for item in result["structured_items"]:
            if item["unit_status"] in ["INFERRED", "MISSING", "INVALID"]:
                assert item["requires_confirmation"] is True
