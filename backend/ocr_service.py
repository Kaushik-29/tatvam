"""
MedResolve — Real OCR and Medical Document Processing Pipeline
Phase 5.4 Component

Provides CPU-compatible, open-source document parsing and clinical information extraction:
1. Digital PDF extraction via PyMuPDF (fitz) when embedded text is present.
2. Optical Character Recognition via RapidOCR (ONNX runtime) for scanned PDFs and image formats (PNG, JPG, JPEG).
3. Clinical entity extraction: tests, vitals, prescriptions, numeric values, units, reference ranges, and report dates.
4. Strict unit provenance tracking: EXPLICIT, NORMALIZED, INFERRED, MISSING, INVALID.
5. Inferred units are explicitly marked and require clinical/user confirmation.
"""

from dataclasses import asdict, dataclass
import io
import logging
import os
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF
import numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

logger = logging.getLogger("MedResolve.OCRService")
logger.setLevel(logging.INFO)

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Allowed file extensions and maximum size (15 MB)
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".txt"}
MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024


@dataclass
class ExtractedObservation:
    """Structured clinical observation extracted from document."""
    concept: str
    concept_name_en: str
    raw_text: str
    normalized_value: str
    unit: Optional[str]
    unit_status: str  # EXPLICIT, NORMALIZED, INFERRED, MISSING, INVALID
    reference_range: Optional[str]
    document_date: Optional[str]
    page_number: int
    confidence: float
    extraction_method: str  # DIGITAL_TEXT_EXTRACTION or RAPID_OCR_ONNX
    requires_confirmation: bool
    confirmation_reason: Optional[str] = None
    medication_name: Optional[str] = None
    dosage_strength: Optional[str] = None
    dosage_unit: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MedicalDocumentProcessor:
    """
    Processes medical PDFs and images, extracting text and structuring clinical data.
    """

    def __init__(self):
        self._ocr_engine: Optional[RapidOCR] = None

    @property
    def ocr_engine(self) -> RapidOCR:
        if self._ocr_engine is None:
            logger.info("Initializing RapidOCR ONNX runtime engine...")
            self._ocr_engine = RapidOCR()
        return self._ocr_engine

    def validate_file(self, filename: str, content: bytes) -> Tuple[bool, Optional[str]]:
        """Validates extension, size, magic bytes, and security constraints."""
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            return False, f"Unsupported file extension '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"

        if len(content) > MAX_FILE_SIZE_BYTES:
            return False, f"File size ({len(content)} bytes) exceeds 15 MB limit."

        if len(content) == 0:
            return False, "Uploaded file is empty."

        # Magic bytes validation for security against extension spoofing
        if ext == ".pdf" and not content.startswith(b"%PDF"):
            return False, "Invalid PDF file: Missing %PDF header magic bytes."
        elif ext == ".png" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
            return False, "Invalid PNG file: Corrupt or invalid PNG header magic bytes."
        elif ext in {".jpg", ".jpeg"} and not (content.startswith(b"\xff\xd8\xff") or content.startswith(b"\xff\xd8")):
            return False, "Invalid JPEG file: Corrupt or invalid JPEG header magic bytes."

        return True, None

    def save_upload(self, patient_id: str, filename: str, content: bytes) -> Tuple[str, Path]:
        """Saves file to secure directory with unique ID."""
        safe_name = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", Path(filename).name)
        timestamp = int(time.time() * 1000)
        doc_id = f"DOC_{patient_id}_{timestamp}"
        saved_filename = f"{doc_id}_{safe_name}"
        save_path = UPLOAD_DIR / saved_filename

        with open(save_path, "wb") as f:
            f.write(content)

        return doc_id, save_path

    def process_document(
        self,
        file_path: Path,
        document_type: str = "MEDICAL_REPORT",
    ) -> Dict[str, Any]:
        """
        Extracts raw text and structures clinical measurements from a document.
        """
        ext = file_path.suffix.lower()
        pages_data: List[Dict[str, Any]] = []

        t0 = time.perf_counter()

        if ext == ".pdf":
            pages_data = self._process_pdf(file_path)
        elif ext in {".png", ".jpg", ".jpeg"}:
            pages_data = self._process_image_file(file_path)
        elif ext == ".txt":
            pages_data = self._process_text_file(file_path)
        else:
            raise ValueError(f"Unsupported format: {ext}")

        full_text = "\n\n".join([f"--- Page {p['page']} ---\n" + p["text"] for p in pages_data])
        structured_items = self._structure_clinical_entities(pages_data, document_type)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

        return {
            "file_path": str(file_path),
            "file_name": file_path.name,
            "document_type": document_type,
            "total_pages": len(pages_data),
            "pages": pages_data,
            "full_text": full_text,
            "structured_items": [item.to_dict() for item in structured_items],
            "total_extracted_items": len(structured_items),
            "unconfirmed_count": sum(1 for item in structured_items if item.requires_confirmation),
            "processing_latency_ms": elapsed_ms,
        }

    def _process_pdf(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """Processes PDF: uses digital text extraction if available; falls back to RapidOCR."""
        doc = fitz.open(str(pdf_path))
        pages_data = []

        for page_idx in range(len(doc)):
            page_num = page_idx + 1
            page = doc[page_idx]
            extracted_text = page.get_text("text").strip()

            if len(extracted_text) >= 30:
                pages_data.append({
                    "page": page_num,
                    "method": "DIGITAL_TEXT_EXTRACTION",
                    "text": extracted_text,
                    "confidence": 1.0,
                    "lines": [{"text": l.strip(), "confidence": 1.0} for l in extracted_text.splitlines() if l.strip()],
                })
            else:
                pix = page.get_pixmap(dpi=200)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                ocr_result = self._run_ocr_on_image(img, page_num)
                pages_data.append(ocr_result)

        doc.close()
        return pages_data

    def _process_image_file(self, img_path: Path) -> List[Dict[str, Any]]:
        """Processes an image file with RapidOCR."""
        img = Image.open(str(img_path)).convert("RGB")
        ocr_result = self._run_ocr_on_image(img, page_num=1)
        return [ocr_result]

    def _process_text_file(self, text_path: Path) -> List[Dict[str, Any]]:
        """Processes plain text document."""
        with open(text_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        lines = [{"text": l.strip(), "confidence": 1.0} for l in text.splitlines() if l.strip()]
        return [{
            "page": 1,
            "method": "DIGITAL_TEXT_EXTRACTION",
            "text": text,
            "confidence": 1.0,
            "lines": lines,
        }]

    def _classify_unit_provenance(
        self,
        concept_id: str,
        extracted_unit: Optional[str],
        standard_unit: str,
        val_raw: str,
    ) -> Tuple[Optional[str], str, Optional[str]]:
        """
        Implements strict 5-state unit provenance classification:
        1. EXPLICIT: Directly reported in document, exact match to canonical standard.
        2. NORMALIZED: Directly reported, recognized clinical variant normalized to canonical standard.
        3. INFERRED: Unit was absent, but bounded physiological range allows safe candidate inference.
                     Explicitly marked INFERRED and mandates clinical confirmation.
        4. MISSING: Unit was absent and cannot be safely/unambiguously inferred. Requires confirmation.
        5. INVALID: Reported unit is physiologically incompatible with the measurement concept. Requires confirmation.

        Returns: (final_unit, unit_status, reason_for_confirmation)
        """
        VALID_UNITS_BY_CONCEPT = {
            "E_HEMOGLOBIN": {"g/dl", "g/l", "gm/dl", "g%"},
            "E_BLOOD_GLUCOSE_FASTING": {"mg/dl", "mg%", "mmol/l"},
            "E_BLOOD_GLUCOSE_RANDOM": {"mg/dl", "mg%", "mmol/l"},
            "E_HBA1C": {"%", "mmol/mol"},
            "E_SERUM_CREATININE": {"mg/dl", "umol/l", "micromol/l"},
            "E_BUN": {"mg/dl", "mmol/l"},
            "E_CHOLESTEROL_TOTAL": {"mg/dl", "mmol/l"},
            "E_TRIGLYCERIDES": {"mg/dl", "mmol/l"},
            "E_HDL_CHOLESTEROL": {"mg/dl", "mmol/l"},
            "E_LDL_CHOLESTEROL": {"mg/dl", "mmol/l"},
            "E_POTASSIUM": {"mmol/l", "meq/l"},
            "E_SODIUM": {"mmol/l", "meq/l"},
            "E_WBC_COUNT": {"/ul", "cells/mcl", "cells/ul", "x10^9/l", "x10^3/ul", "/mm3"},
            "E_PLATELETS": {"/ul", "cells/mcl", "cells/ul", "x10^9/l", "x10^3/ul", "/mm3"},
            "E_TSH": {"miu/l", "uiu/ml", "uu/ml", "mu/l"},
            "E_ALT_SGPT": {"u/l", "iu/l"},
            "E_AST_SGOT": {"u/l", "iu/l"},
            "E_VITALS_BP": {"mmhg"},
            "E_VITALS_HR": {"bpm", "beats/min", "/min"},
            "E_VITALS_RESP_RATE": {"/min", "breaths/min", "cpm"},
            "E_VITALS_TEMP": {"degf", "°f", "f", "degc", "°c", "c"},
            "E_VITALS_SPO2": {"%"},
        }

        if extracted_unit:
            u_clean = extracted_unit.lower().replace(" ", "")
            # Check concept-specific valid unit sets
            concept_valid = VALID_UNITS_BY_CONCEPT.get(concept_id)
            if concept_id.startswith("E_RX_"):
                concept_valid = {"mg", "mcg", "g", "ml", "iu", "tablets", "pills"}

            if concept_valid is not None and u_clean not in concept_valid:
                return (extracted_unit, "INVALID", f"Invalid or unrecognized unit '{extracted_unit}' for {concept_id}")

            norm = self._normalize_unit(extracted_unit, standard_unit)
            if extracted_unit.strip() == norm:
                return (norm, "EXPLICIT", None)
            else:
                return (norm, "NORMALIZED", None)

        # No unit extracted from text - evaluate physiological inference vs missing
        if concept_id == "E_VITALS_TEMP":
            try:
                t = float(val_raw)
                if 90.0 <= t <= 115.0:
                    return ("degF", "INFERRED", "Temperature unit missing; inferred degF from physiological range [90, 115]")
                elif 30.0 <= t <= 45.0:
                    return ("degC", "INFERRED", "Temperature unit missing; inferred degC from physiological range [30, 45]")
            except ValueError:
                pass
            return (None, "MISSING", "Core temperature unit is missing and physiologically ambiguous")

        elif concept_id == "E_VITALS_SPO2":
            try:
                s = float(val_raw)
                if 40.0 <= s <= 100.0:
                    return ("%", "INFERRED", "SpO2 unit missing; inferred % from physiological range [40, 100]")
            except ValueError:
                pass
            return (None, "MISSING", "SpO2 measurement unit is missing")

        elif concept_id == "E_VITALS_BP":
            return ("mmHg", "INFERRED", "Blood pressure unit missing; inferred mmHg standard")

        elif concept_id.startswith("E_RX_"):
            return ("mg", "INFERRED", "Oral prescription dose unit missing; inferred mg standard")

        return (None, "MISSING", f"Measurement unit is missing for {concept_id}; unconfirmed clinical extraction")


    def _run_ocr_on_image(self, img: Image.Image, page_num: int) -> Dict[str, Any]:
        """Runs RapidOCR on a PIL image and formats lines with confidence scores."""
        img_np = np.array(img)
        results, elapse = self.ocr_engine(img_np)

        lines = []
        text_parts = []
        confidences = []

        if results:
            for item in results:
                line_text = str(item[1]).strip()
                conf = float(item[2])
                if line_text:
                    lines.append({"text": line_text, "confidence": round(conf, 3), "box": item[0]})
                    text_parts.append(line_text)
                    confidences.append(conf)

        avg_conf = round(float(np.mean(confidences)), 3) if confidences else 0.0
        return {
            "page": page_num,
            "method": "RAPID_OCR_ONNX",
            "text": "\n".join(text_parts),
            "confidence": avg_conf,
            "lines": lines,
            "ocr_latency_breakdown": elapse,
        }

    def _structure_clinical_entities(
        self,
        pages_data: List[Dict[str, Any]],
        document_type: str,
    ) -> List[ExtractedObservation]:
        """
        Scans extracted lines and structures clinical observations using regex and domain patterns.
        """
        extracted: List[ExtractedObservation] = []

        # Clinical patterns: (concept_id, display_name, regex, default_unit, ref_range_pattern)
        PATTERNS = [
            # Laboratory Measurements
            (
                "E_HEMOGLOBIN",
                "Hemoglobin (blood test)",
                r"(?:hemoglobin|hb|hgb)\s*[:=\-\.]?\s*(\d+(?:\.\d+)?)\s*([a-zA-Z\/]+)?",
                "g/dL",
                r"(?:ref|reference|normal)?\s*[:=\-\.]?\s*\(?(\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?)\)?",
            ),
            (
                "E_BLOOD_GLUCOSE_FASTING",
                "Fasting Blood Sugar",
                r"(?:fasting\s+blood\s+(?:sugar|glucose)|fasting\s+glucose|fbs|blood\s+glucose(?:\s+fasting)?)\s*[:=\-\.]?\s*(\d+(?:\.\d+)?)\s*([a-zA-Z\/]+)?",
                "mg/dL",
                r"(?:ref|reference)?\s*[:=\-\.]?\s*\(?(\d+\s*-\s*\d+)\)?",
            ),
            (
                "E_HBA1C",
                "Glycated Hemoglobin (HbA1c)",
                r"(?:glycated\s+hemoglobin\s*hba1c|glycated\s+hemoglobin|hba1c|a1c)\s*[:=\-\.]?\s*(\d+(?:\.\d+)?)\s*([a-zA-Z\/%]+)?",
                "%",
                r"(?:ref|target)?\s*[:=\-\.]?\s*\(?([<>]?\s*\d+(?:\.\d+)?(?:\s*-\s*\d+(?:\.\d+)?)?)\)?",
            ),

            (
                "E_D_DIMER",
                "D-dimer (plasma)",
                r"(?:d-dimer|ddimer|d\s+dimer)\s*[:=\-\.]?\s*(\d+(?:\.\d+)?)\s*([a-zA-Z\/]+)?",
                "mcg/mL",
                r"(?:ref|reference)?\s*[:=\-\.]?\s*\(?([<>]?\s*\d+(?:\.\d+)?)\)?",
            ),
            (
                "E_SERUM_CREATININE",
                "Serum Creatinine",
                r"(?:serum\s+creatinine|creatinine)\s*[:=\-\.]?\s*(\d+(?:\.\d+)?)\s*([a-zA-Z\/]+)?",
                "mg/dL",
                r"(?:ref)?\s*[:=\-\.]?\s*\(?(\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?)\)?",
            ),
            (
                "E_PLATELET_COUNT",
                "Platelet Count",
                r"(?:platelet\s+count|platelets|plt)\s*[:=\-\.]?\s*(\d+(?:,\d+)?(?:\.\d+)?)\s*([a-zA-Z0-9\/\^\s]+)?",
                "x10^9/L",
                r"(?:ref)?\s*[:=\-\.]?\s*\(?(\d+\s*-\s*\d+)\)?",
            ),
            (
                "E_WBC_COUNT",
                "Total Leucocyte Count (WBC)",
                r"(?:total\s+leucocyte\s+count|wbc|tlc|white\s+blood\s+cells?)\s*[:=\-\.]?\s*(\d+(?:,\d+)?(?:\.\d+)?)\s*([a-zA-Z0-9\/\^\s]+)?",
                "cells/mcL",
                r"(?:ref)?\s*[:=\-\.]?\s*\(?(\d+(?:,\d+)?\s*-\s*\d+(?:,\d+)?)\)?",
            ),
            (
                "E_TROPONIN_I",
                "Troponin I (High Sensitivity)",
                r"(?:troponin\s*i|hs-ctni|troponin)\s*[:=\-\.]?\s*(\d+(?:\.\d+)?)\s*([a-zA-Z\/]+)?",
                "ng/mL",
                r"(?:ref)?\s*[:=\-\.]?\s*\(?([<>]?\s*\d+(?:\.\d+)?)\)?",
            ),
            # Vital Signs
            (
                "E_VITALS_BP",
                "Blood Pressure",
                r"(?:blood\s+pressure|bp)\s*[:=\-\.]?\s*(\d{2,3}\s*\/\s*\d{2,3})\s*([a-zA-Z\/°]+)?",
                "mmHg",
                None,
            ),
            (
                "E_VITALS_HR",
                "Heart Rate / Pulse",
                r"(?:heart\s+rate|pulse\s+rate|pulse|hr)\s*[:=\-\.]?\s*(\d{2,3})\s*([a-zA-Z\/]+)?",
                "bpm",
                r"(?:ref)?\s*\(?(\d+\s*-\s*\d+)\)?",
            ),
            (
                "E_VITALS_TEMP",
                "Core Body Temperature",
                r"(?:temperature|body\s+temp|temp)\s*[:=\-\.]?\s*(\d{2,3}(?:\.\d+)?)\s*([a-zA-Z\/°]+)?",
                "degF",
                None,
            ),
            (
                "E_VITALS_SPO2",
                "Pulse Oximetry (SpO2)",
                r"(?:spo2|pulse\s+oximetry|oxygen\s+saturation|o2\s+sat)\s*[:=\-\.]?\s*(\d{2,3}(?:\.\d+)?)\s*(%|[a-zA-Z\/]+)?",
                "%",
                r"(?:ref)?\s*\(?([<>]?\s*\d+)\)?",
            ),
            # Additional Clinical Chemistry & Lipids
            (
                "E_BUN",
                "Blood Urea Nitrogen (BUN)",
                r"(?:blood\s+urea\s+nitrogen\s*\(bun\)|blood\s+urea\s+nitrogen|bun)\s*[:=\-\.]?\s*(\d+(?:\.\d+)?)\s*([a-zA-Z\/]+)?",
                "mg/dL",
                r"(?:ref)?\s*[:=\-\.]?\s*\(?(\d+\s*-\s*\d+)\)?",
            ),
            (
                "E_TSH",
                "Thyroid Stimulating Hormone (TSH)",
                r"(?:serum\s+tsh|tsh|thyroid\s+stimulating\s+hormone)\s*[:=\-\.]?\s*(\d+(?:\.\d+)?)\s*([a-zA-Z\/]+)?",
                "mIU/L",
                r"(?:ref)?\s*[:=\-\.]?\s*\(?(\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?)\)?",
            ),
            (
                "E_ALT_SGPT",
                "Alanine Aminotransferase (ALT)",
                r"(?:alanine\s+aminotransferase\s*\(alt\)|alanine\s+aminotransferase|alt|sgpt)\s*[:=\-\.]?\s*(\d+(?:\.\d+)?)\s*([a-zA-Z\/]+)?",
                "U/L",
                r"(?:ref)?\s*[:=\-\.]?\s*\(?(\d+\s*-\s*\d+)\)?",
            ),
            (
                "E_AST_SGOT",
                "Aspartate Aminotransferase (AST)",
                r"(?:aspartate\s+aminotransferase\s*\(ast\)|aspartate\s+aminotransferase|ast|sgot)\s*[:=\-\.]?\s*(\d+(?:\.\d+)?)\s*([a-zA-Z\/]+)?",
                "U/L",
                r"(?:ref)?\s*[:=\-\.]?\s*\(?(\d+\s*-\s*\d+)\)?",
            ),
            (
                "E_POTASSIUM",
                "Serum Potassium",
                r"(?:potassium|serum\s+potassium|k\+?)\s*[:=\-\.]?\s*(\d+(?:\.\d+)?)\s*([a-zA-Z\/]+)?",
                "mEq/L",
                r"(?:ref)?\s*[:=\-\.]?\s*\(?(\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?)\)?",
            ),
            (
                "E_SODIUM",
                "Serum Sodium",
                r"(?:sodium|serum\s+sodium|na\+?)\s*[:=\-\.]?\s*(\d+(?:\.\d+)?)\s*([a-zA-Z\/]+)?",
                "mEq/L",
                r"(?:ref)?\s*[:=\-\.]?\s*\(?(\d+\s*-\s*\d+)\)?",
            ),
            (
                "E_CHOLESTEROL_TOTAL",
                "Total Cholesterol",
                r"(?:total\s+cholesterol|serum\s+cholesterol|cholesterol)\s*[:=\-\.]?\s*(\d+(?:\.\d+)?)\s*([a-zA-Z\/]+)?",
                "mg/dL",
                r"(?:ref)?\s*[:=\-\.]?\s*\(?([<>]?\s*\d+)\)?",
            ),
            (
                "E_TRIGLYCERIDES",
                "Serum Triglycerides",
                r"(?:triglycerides|serum\s+triglycerides|triglyceride|tg)\s*[:=\-\.]?\s*(\d+(?:\.\d+)?)\s*([a-zA-Z\/]+)?",
                "mg/dL",
                r"(?:ref)?\s*[:=\-\.]?\s*\(?([<>]?\s*\d+)\)?",
            ),
            (
                "E_HDL_CHOLESTEROL",
                "HDL Cholesterol",
                r"(?:hdl\s+cholesterol|hdl)\s*[:=\-\.]?\s*(\d+(?:\.\d+)?)\s*([a-zA-Z\/]+)?",
                "mg/dL",
                r"(?:ref)?\s*[:=\-\.]?\s*\(?([<>]?\s*\d+)\)?",
            ),
            (
                "E_LDL_CHOLESTEROL",
                "LDL Cholesterol",
                r"(?:ldl\s+cholesterol|ldl)\s*[:=\-\.]?\s*(\d+(?:\.\d+)?)\s*([a-zA-Z\/]+)?",
                "mg/dL",
                r"(?:ref)?\s*[:=\-\.]?\s*\(?([<>]?\s*\d+)\)?",
            ),
            # Prescriptions
            (
                "E_RX_OMEPRAZOLE",
                "Omeprazole oral prescription",
                r"(?:omeprazole|prilosec)\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]+)?",
                "mg",
                None,
            ),
            (
                "E_RX_AMLODIPINE",
                "Amlodipine oral prescription",
                r"(?:amlodipine|norvasc)\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]+)?",
                "mg",
                None,
            ),
            (
                "E_RX_ATORVASTATIN",
                "Atorvastatin oral prescription",
                r"(?:atorvastatin|lipitor)\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]+)?",
                "mg",
                None,
            ),
            (
                "E_RX_METOPROLOL",
                "Metoprolol prescription",
                r"(?:metoprolol|lopressor)\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]+)?",
                "mg",
                None,
            ),
            (
                "E_RX_PARACETAMOL",
                "Paracetamol prescription",
                r"(?:paracetamol|acetaminophen|tylenol|crocin)\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]+)?",
                "mg",
                None,
            ),
            (
                "E_RX_METFORMIN",
                "Metformin oral prescription",
                r"(?:metformin|glucophage)\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]+)?",
                "mg",
                None,
            ),
            (
                "E_RX_LISINOPRIL",
                "Lisinopril prescription",
                r"(?:lisinopril|zestril|prinivil)\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]+)?",
                "mg",
                None,
            ),
            (
                "E_RX_LOSARTAN",
                "Losartan prescription",
                r"(?:losartan|cozaar)\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]+)?",
                "mg",
                None,
            ),
            (
                "E_RX_AZITHROMYCIN",
                "Azithromycin prescription",
                r"(?:azithromycin|zithromax)\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]+)?",
                "mg",
                None,
            ),
            (
                "E_RX_AMOXICILLIN",
                "Amoxicillin prescription",
                r"(?:amoxicillin|amoxil)\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]+)?",
                "mg",
                None,
            ),
            (
                "E_RX_LEVOTHYROXINE",
                "Levothyroxine prescription",
                r"(?:levothyroxine|synthroid|eltroxin)\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]+)?",
                "mcg",
                None,
            ),
            (
                "E_RX_SALBUTAMOL",
                "Salbutamol inhaler prescription",
                r"(?:salbutamol|albuterol|ventolin)\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]+)?",
                "mcg",
                None,
            ),

        ]

        # Pre-scan for document-level dates (e.g. from header lines)
        doc_level_date = None
        for p in pages_data:
            d_found = self._extract_date_from_text(p.get("text", ""))
            if d_found:
                doc_level_date = d_found
                break

        for page_entry in pages_data:
            page_num = page_entry["page"]
            method = page_entry["method"]
            lines = page_entry.get("lines", [])

            # Generate evaluation windows: single line, 2-line sliding window, 3-line sliding window
            segments = []
            for i, line_info in enumerate(lines):
                segments.append((line_info["text"], line_info.get("confidence", 1.0)))
                if i + 1 < len(lines):
                    combo2 = line_info["text"] + " " + lines[i + 1]["text"]
                    c2 = min(line_info.get("confidence", 1.0), lines[i + 1].get("confidence", 1.0))
                    segments.append((combo2, c2))
                if i + 2 < len(lines):
                    combo3 = line_info["text"] + " " + lines[i + 1]["text"] + " " + lines[i + 2]["text"]
                    c3 = min(line_info.get("confidence", 1.0), lines[i + 1].get("confidence", 1.0), lines[i + 2].get("confidence", 1.0))
                    segments.append((combo3, c3))

            for seg_text, seg_conf in segments:
                seg_lower = seg_text.lower()

                for concept_id, display_name, val_regex, standard_unit, ref_pattern in PATTERNS:
                    match = re.search(val_regex, seg_lower)
                    if match:
                        val_raw = match.group(1).replace(",", "").strip()

                        extracted_unit = None
                        if len(match.groups()) >= 2 and match.group(2):
                            start_idx, end_idx = match.span(2)
                            extracted_unit = seg_text[start_idx:end_idx].strip()

                        unit, unit_status, unit_reason = self._classify_unit_provenance(
                            concept_id=concept_id,
                            extracted_unit=extracted_unit,
                            standard_unit=standard_unit,
                            val_raw=val_raw,
                        )

                        ref_range = None
                        if ref_pattern:
                            # Search for reference interval strictly after the measurement value in the segment
                            ref_match = re.search(ref_pattern, seg_lower[match.end():])
                            if ref_match:
                                ref_range = ref_match.group(1).strip()


                        requires_confirmation = False
                        confirmation_reasons = []

                        if seg_conf < 0.85:
                            requires_confirmation = True
                            confirmation_reasons.append(f"Low OCR confidence ({round(seg_conf*100, 1)}%)")

                        if unit_status in {"INFERRED", "MISSING", "INVALID"}:
                            requires_confirmation = True
                            if unit_reason:
                                confirmation_reasons.append(unit_reason)


                        # Conservative handling for potentially serious boundary measurements
                        if concept_id == "E_VITALS_SPO2":
                            try:
                                v_float = float(val_raw)
                                if v_float <= 90.0:
                                    requires_confirmation = True
                                    confirmation_reasons.append("Severe hypoxemia reading requires clinical review")
                            except ValueError:
                                pass

                        if concept_id == "E_VITALS_TEMP":
                            try:
                                t_float = float(val_raw)
                                if (unit == "degF" and t_float >= 104.0) or (unit == "degC" and t_float >= 40.0) or t_float >= 104.0:
                                    requires_confirmation = True
                                    confirmation_reasons.append("Hyperpyrexia critical value requires verification")
                            except ValueError:
                                pass

                        # Medication structured attributes
                        med_name = None
                        dosage_str = None
                        dosage_u = None
                        frequency = None
                        duration = None

                        if concept_id.startswith("E_RX_"):
                            med_name = display_name.split()[0]
                            dosage_str = val_raw
                            dosage_u = unit or standard_unit

                            freq_m = re.search(r"\b(od|bd|bid|tid|qid|once\s+daily|twice\s+daily|three\s+times\s+daily|four\s+times\s+daily|daily|sos|as\s+needed|at\s+bedtime|hs)\b", seg_lower)
                            if freq_m:
                                frequency = freq_m.group(1).upper()

                            dur_m = re.search(r"\b(\d+\s*(?:days?|weeks?|months?))\b", seg_lower)
                            if dur_m:
                                duration = dur_m.group(1)

                        obs_date = self._extract_date_from_text(seg_text) or doc_level_date

                        obs = ExtractedObservation(
                            concept=concept_id,
                            concept_name_en=display_name,
                            raw_text=seg_text,
                            normalized_value=val_raw,
                            unit=unit,
                            unit_status=unit_status,
                            reference_range=ref_range,
                            document_date=obs_date,
                            page_number=page_num,
                            confidence=round(seg_conf, 3),
                            extraction_method=method,
                            requires_confirmation=requires_confirmation,
                            confirmation_reason="; ".join(confirmation_reasons) if confirmation_reasons else None,

                            medication_name=med_name,
                            dosage_strength=dosage_str,
                            dosage_unit=dosage_u,
                            frequency=frequency,
                            duration=duration,
                        )

                        existing = next((e for e in extracted if e.concept == concept_id and e.page_number == page_num), None)
                        if existing is None:
                            extracted.append(obs)
                        else:
                            # Enrich existing observation if a larger window found additional metadata
                            if not existing.reference_range and obs.reference_range:
                                existing.reference_range = obs.reference_range
                            if not existing.document_date and obs.document_date:
                                existing.document_date = obs.document_date
                            if not existing.frequency and obs.frequency:
                                existing.frequency = obs.frequency
                            if not existing.duration and obs.duration:
                                existing.duration = obs.duration


        return extracted

    def _normalize_unit(self, raw_unit: str, standard: str) -> str:
        """Standardizes unit strings."""
        u = raw_unit.lower().replace(" ", "")
        if u in {"g/dl", "g/l", "gm/dl"}:
            return "g/dL"
        if u in {"mg/dl", "mg%"}:
            return "mg/dL"
        if u in {"mmol/l", "meq/l"}:
            return "mmol/L"
        if u in {"miu/l", "uiu/ml", "uu/ml", "mu/l"}:
            return "mIU/L"
        if u in {"u/l", "iu/l"}:
            return "U/L"
        if u in {"/ul", "cells/mcl", "cells/ul", "/mm3"}:
            return "/uL"
        if u in {"degf", "°f", "f"}:
            return "degF"
        if u in {"degc", "°c", "c"}:
            return "degC"
        if u in {"bpm", "beats/min"}:
            return "bpm"
        if u in {"mmhg"}:
            return "mmHg"
        if u in {"%"}:
            return "%"
        if u in {"mcg/ml", "ug/ml"}:
            return "mcg/mL"
        if u in {"mg", "milligram", "milligrams"}:
            return "mg"
        if u in {"mcg", "ug", "microgram", "micrograms"}:
            return "mcg"
        return standard


    def _extract_date_from_text(self, text: str) -> Optional[str]:
        """Extracts standard date string if present in line."""
        m = re.search(r"\b(\d{4}[-/]\d{2}[-/]\d{2})\b", text)
        if m:
            return m.group(1).replace("/", "-")
        m2 = re.search(r"\b(\d{2}[-/]\d{2}[-/]\d{4})\b", text)
        if m2:
            parts = re.split(r"[-/]", m2.group(1))
            return f"{parts[2]}-{parts[1]}-{parts[0]}"
        return None
