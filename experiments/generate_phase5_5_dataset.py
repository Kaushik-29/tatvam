"""
MedResolve — Phase 5.5
Synthetic Medical Document Dataset Generator

Generates 50 reproducible synthetic medical documents across 7 categories:
1. Digital laboratory PDFs (10 docs, including 2 multi-page)
2. Clean scanned laboratory reports (10 docs, PNG)
3. Scanned prescriptions (10 docs, PNG)
4. Low-resolution or noisy scans (5 docs, PNG)
5. Rotated or skewed documents (5 docs, PNG)
6. Documents containing medical tables (5 docs, PDF)
7. Ambiguous values and missing units (5 docs, PNG/PDF)

All documents feature fictional patients and programmatically specified ground truth.
Outputs:
- data/processed/phase5_5_ocr/{filename}
- data/processed/phase5_5_ocr/ground_truth/{doc_id}.json
- results/rag/phase5_5/ocr_ground_truth_manifest.json
"""

import json
import math
import os
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import fitz  # PyMuPDF

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DOCS_DIR = BASE_DIR / "data" / "processed" / "phase5_5_ocr"
OUTPUT_GT_DIR = OUTPUT_DOCS_DIR / "ground_truth"
MANIFEST_PATH = BASE_DIR / "results" / "rag" / "phase5_5" / "ocr_ground_truth_manifest.json"

OUTPUT_DOCS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_GT_DIR.mkdir(parents=True, exist_ok=True)
MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)

# Font selection for PIL
FONT_PATH = "C:/Windows/Fonts/arial.ttf"
if not os.path.exists(FONT_PATH):
    FONT_PATH = "arial.ttf"


def get_font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except Exception:
        return ImageFont.load_default()


# ==============================================================================
# Helper functions for PDF and Image rendering
# ==============================================================================

def create_digital_pdf(doc_id, pages_data, output_path):
    """
    Creates a native digital vector PDF with embedded selectable text using PyMuPDF.
    pages_data is a list of lists of text lines or sections.
    """
    doc = fitz.open()
    for page_info in pages_data:
        page = doc.new_page(width=595, height=842)  # A4 size
        # Header banner
        page.draw_rect(fitz.Rect(40, 40, 555, 90), color=(0.1, 0.25, 0.5), fill=(0.94, 0.96, 0.99))
        page.insert_text(fitz.Point(55, 65), page_info.get("facility", "MEDRESOLVE DIAGNOSTIC CENTER"), fontsize=14, fontname="helv", color=(0.1, 0.25, 0.5))
        page.insert_text(fitz.Point(55, 82), "Accredited Clinical Pathology & Diagnostic Services", fontsize=9, fontname="helv", color=(0.4, 0.4, 0.4))
        
        # Patient & Doctor Info
        y = 115
        p_info = page_info.get("patient_header", {})
        page.draw_line(fitz.Point(40, 100), fitz.Point(555, 100), color=(0.8, 0.8, 0.8))
        page.insert_text(fitz.Point(40, y), f"Patient: {p_info.get('name', 'Synthetic Patient')}", fontsize=10, fontname="helv", color=(0.1, 0.1, 0.1))
        page.insert_text(fitz.Point(300, y), f"Patient ID: {p_info.get('id', 'SYNTH-001')}", fontsize=10, fontname="helv", color=(0.1, 0.1, 0.1))
        y += 18
        page.insert_text(fitz.Point(40, y), f"Age/Sex: {p_info.get('age_sex', '52 Y / Male')}", fontsize=10, fontname="helv", color=(0.1, 0.1, 0.1))
        page.insert_text(fitz.Point(300, y), f"Date of Collection: {p_info.get('date', '2026-03-15')}", fontsize=10, fontname="helv", color=(0.1, 0.1, 0.1))
        y += 18
        page.insert_text(fitz.Point(40, y), f"Ref. Doctor: {p_info.get('doctor', 'Dr. Ramesh Rao, MD')}", fontsize=10, fontname="helv", color=(0.1, 0.1, 0.1))
        page.insert_text(fitz.Point(300, y), f"Status: Final Approved Report", fontsize=10, fontname="helv", color=(0.1, 0.5, 0.2))
        
        y += 25
        page.draw_line(fitz.Point(40, y), fitz.Point(555, y), color=(0.2, 0.3, 0.6), width=1.5)
        y += 20

        # Section Header
        page.insert_text(fitz.Point(40, y), page_info.get("section_title", "LABORATORY INVESTIGATION REPORT"), fontsize=11, fontname="helv", color=(0.1, 0.2, 0.5))
        y += 20

        # Test results
        for row in page_info.get("rows", []):
            page.insert_text(fitz.Point(40, y), row["test_name"], fontsize=10, fontname="helv", color=(0.1, 0.1, 0.1))
            val_text = f"{row['value']} {row['unit']}".strip()
            page.insert_text(fitz.Point(220, y), val_text, fontsize=10, fontname="helv", color=(0.0, 0.0, 0.0))
            if row.get("ref_range"):
                page.insert_text(fitz.Point(350, y), f"Ref: {row['ref_range']}", fontsize=9, fontname="helv", color=(0.4, 0.4, 0.4))
            y += 20

        # Footer
        page.draw_line(fitz.Point(40, 780), fitz.Point(555, 780), color=(0.8, 0.8, 0.8))
        page.insert_text(fitz.Point(40, 800), "Electronically verified clinical report. For research demonstration only.", fontsize=8, fontname="helv", color=(0.5, 0.5, 0.5))
        page.insert_text(fitz.Point(480, 800), f"Page {page.number + 1} of {len(pages_data)}", fontsize=8, fontname="helv", color=(0.5, 0.5, 0.5))

    doc.save(str(output_path))
    doc.close()


def create_table_pdf(doc_id, table_data, output_path):
    """
    Creates a native PDF containing formal medical tables with grid lines and columns.
    """
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    # Title
    page.draw_rect(fitz.Rect(40, 40, 555, 85), color=(0.15, 0.3, 0.5), fill=(0.95, 0.97, 1.0))
    page.insert_text(fitz.Point(50, 65), table_data.get("facility", "APEX PATHOLOGY LABORATORY"), fontsize=14, fontname="helv", color=(0.1, 0.25, 0.5))
    page.insert_text(fitz.Point(50, 78), "Department of Clinical Biochemistry", fontsize=9, fontname="helv", color=(0.4, 0.4, 0.4))

    # Patient info
    y = 110
    p = table_data.get("patient_header", {})
    page.insert_text(fitz.Point(40, y), f"Patient Name: {p.get('name', 'Synth Patient')}", fontsize=10, fontname="helv")
    page.insert_text(fitz.Point(320, y), f"Sample ID: {p.get('id', 'SMP-9021')}", fontsize=10, fontname="helv")
    y += 18
    page.insert_text(fitz.Point(40, y), f"Date of Collection: {p.get('date', '2026-03-20')}", fontsize=10, fontname="helv")
    page.insert_text(fitz.Point(320, y), f"Doctor: {p.get('doctor', 'Dr. V. Gupta')}", fontsize=10, fontname="helv")
    y += 25

    # Table Header Box
    page.draw_rect(fitz.Rect(40, y, 555, y + 25), color=(0.2, 0.35, 0.6), fill=(0.88, 0.92, 0.98))
    page.insert_text(fitz.Point(45, y + 17), "TEST INVESTIGATION", fontsize=10, fontname="helv", color=(0.1, 0.2, 0.4))
    page.insert_text(fitz.Point(220, y + 17), "OBSERVED VALUE", fontsize=10, fontname="helv", color=(0.1, 0.2, 0.4))
    page.insert_text(fitz.Point(340, y + 17), "UNIT", fontsize=10, fontname="helv", color=(0.1, 0.2, 0.4))
    page.insert_text(fitz.Point(420, y + 17), "REFERENCE RANGE", fontsize=10, fontname="helv", color=(0.1, 0.2, 0.4))
    y += 25

    # Table Rows
    for row in table_data.get("rows", []):
        row_height = 24
        page.draw_rect(fitz.Rect(40, y, 555, y + row_height), color=(0.8, 0.8, 0.8), width=0.5)
        # Vertical column separators
        page.draw_line(fitz.Point(210, y), fitz.Point(210, y + row_height), color=(0.8, 0.8, 0.8), width=0.5)
        page.draw_line(fitz.Point(330, y), fitz.Point(330, y + row_height), color=(0.8, 0.8, 0.8), width=0.5)
        page.draw_line(fitz.Point(410, y), fitz.Point(410, y + row_height), color=(0.8, 0.8, 0.8), width=0.5)

        page.insert_text(fitz.Point(45, y + 16), row["test_name"], fontsize=9.5, fontname="helv")
        page.insert_text(fitz.Point(220, y + 16), str(row["value"]), fontsize=9.5, fontname="helv")
        page.insert_text(fitz.Point(340, y + 16), row["unit"], fontsize=9.5, fontname="helv")
        page.insert_text(fitz.Point(420, y + 16), row.get("ref_range", "-"), fontsize=9.0, fontname="helv", color=(0.3, 0.3, 0.3))
        y += row_height

    # Footer
    page.draw_line(fitz.Point(40, 780), fitz.Point(555, 780), color=(0.8, 0.8, 0.8))
    page.insert_text(fitz.Point(40, 800), "End of report. All laboratory assays calibrated against standard reference serums.", fontsize=8, fontname="helv", color=(0.5, 0.5, 0.5))

    doc.save(str(output_path))
    doc.close()


def create_scanned_image(doc_id, image_data, output_path, noise_level=0, skew_angle=0):
    """
    Renders a realistic scanned document (report or prescription) as an image.
    Supports noise, blur, and rotation.
    """
    width, height = 1200, 1600
    img = Image.new("RGB", (width, height), color=(253, 253, 252))
    draw = ImageDraw.Draw(img)

    f_title = get_font(32)
    f_sub = get_font(20)
    f_header = get_font(22)
    f_body = get_font(20)
    f_bold = get_font(21)
    f_small = get_font(16)

    # Header
    facility = image_data.get("facility", "METROPOLIS HEALTH LAB")
    draw.text((80, 70), facility, fill=(20, 45, 90), font=f_title)
    draw.text((80, 115), image_data.get("subtitle", "Clinical Diagnostic & Outpatient Services"), fill=(90, 90, 90), font=f_sub)
    draw.line([(80, 155), (1120, 155)], fill=(180, 180, 180), width=2)

    # Patient details
    p = image_data.get("patient_header", {})
    y = 175
    draw.text((80, y), f"Patient: {p.get('name', 'Patient')}", fill=(30, 30, 30), font=f_body)
    draw.text((650, y), f"Patient ID: {p.get('id', 'SYNTH-001')}", fill=(30, 30, 30), font=f_body)
    y += 35
    draw.text((80, y), f"Age / Gender: {p.get('age_sex', '48 Y / F')}", fill=(30, 30, 30), font=f_body)
    draw.text((650, y), f"Date: {p.get('date', '2026-03-22')}", fill=(30, 30, 30), font=f_body)
    y += 35
    draw.text((80, y), f"Doctor: {p.get('doctor', 'Dr. K. Nair, MD')}", fill=(30, 30, 30), font=f_body)
    y += 45
    draw.line([(80, y), (1120, y)], fill=(30, 60, 120), width=3)
    y += 35

    # Document Section
    sec_title = image_data.get("section_title", "INVESTIGATION RESULTS")
    draw.text((80, y), sec_title, fill=(30, 60, 120), font=f_header)
    y += 45

    # Prescriptions or Test results
    if image_data.get("doc_type") == "prescription":
        draw.text((80, y), "Rx", fill=(20, 40, 100), font=get_font(40))
        y += 55
        for med in image_data.get("medications", []):
            line1 = f"{med['name']} {med['strength']} {med['unit']}"
            draw.text((100, y), line1, fill=(20, 20, 20), font=f_bold)
            y += 32
            line2 = f"Sig: Take {med.get('frequency', 'daily')} for {med.get('duration', '30 days')}"
            draw.text((120, y), line2, fill=(60, 60, 60), font=f_body)
            y += 45
    else:
        # Lab results
        for row in image_data.get("rows", []):
            draw.text((80, y), row["test_name"], fill=(25, 25, 25), font=f_body)
            val_str = f"{row['value']} {row['unit']}".strip()
            draw.text((500, y), val_str, fill=(15, 15, 15), font=f_bold)
            if row.get("ref_range"):
                draw.text((780, y), f"Ref: {row['ref_range']}", fill=(100, 100, 100), font=f_small)
            y += 40

    # Footer
    draw.line([(80, 1500), (1120, 1500)], fill=(200, 200, 200), width=1)
    draw.text((80, 1520), "Computer generated diagnostic document. Fictional synthetic record.", fill=(130, 130, 130), font=f_small)

    # Post-processing: Noise & Blur
    if noise_level > 0:
        # Add random pixel noise / salt & pepper
        pixels = img.load()
        for _ in range(int(noise_level * 5000)):
            rx = random.randint(0, width - 1)
            ry = random.randint(0, height - 1)
            val = random.randint(0, 255)
            pixels[rx, ry] = (val, val, val)
        if noise_level >= 2:
            img = img.filter(ImageFilter.GaussianBlur(radius=0.7))

    # Post-processing: Skew / Rotation
    if skew_angle != 0:
        img = img.rotate(skew_angle, expand=True, fillcolor=(255, 255, 255))

    img.save(str(output_path), "PNG")


# ==============================================================================
# Specification of 50 Documents and their Ground Truth
# ==============================================================================

DOCUMENTS_SPEC = [
    # --------------------------------------------------------------------------
    # CATEGORY 1: Digital laboratory PDFs (10 docs, 2 multi-page)
    # --------------------------------------------------------------------------
    {
        "id": "DOC_DIG_LAB_01",
        "category": "digital_lab_pdf",
        "filename": "DOC_DIG_LAB_01.pdf",
        "type": "pdf",
        "facility": "APEX CLINICAL LABORATORIES",
        "patient": {"name": "Aarav Sharma", "id": "SYNTH-P101", "age_sex": "45 Y / M", "date": "2026-03-10", "doctor": "Dr. N. Mehta, MD"},
        "pages": [
            {
                "page_num": 1,
                "title": "METABOLIC PANEL REPORT",
                "rows": [
                    {"name": "Fasting Blood Glucose", "val": 112.5, "unit": "mg/dL", "ref": "70 - 99 mg/dL", "concept": "glucose", "prov": "EXPLICIT"},
                    {"name": "Glycated Hemoglobin HbA1c", "val": 7.2, "unit": "%", "ref": "4.0 - 5.6 %", "concept": "hba1c", "prov": "EXPLICIT"},
                    {"name": "Serum Creatinine", "val": 1.4, "unit": "mg/dL", "ref": "0.6 - 1.2 mg/dL", "concept": "creatinine", "prov": "EXPLICIT"},
                    {"name": "Blood Urea Nitrogen (BUN)", "val": 24.0, "unit": "mg/dL", "ref": "7 - 20 mg/dL", "concept": "bun", "prov": "EXPLICIT"}
                ]
            }
        ]
    },
    {
        "id": "DOC_DIG_LAB_02",
        "category": "digital_lab_pdf",
        "filename": "DOC_DIG_LAB_02.pdf",
        "type": "pdf",
        "facility": "METRO DIAGNOSTICS CENTER",
        "patient": {"name": "Priya Venkat", "id": "SYNTH-P102", "age_sex": "52 Y / F", "date": "2026-03-11", "doctor": "Dr. S. Kulkarni, MD"},
        "pages": [
            {
                "page_num": 1,
                "title": "LIPID PROFILE REPORT",
                "rows": [
                    {"name": "Total Cholesterol", "val": 215.0, "unit": "mg/dL", "ref": "< 200 mg/dL", "concept": "cholesterol_total", "prov": "EXPLICIT"},
                    {"name": "Triglycerides", "val": 180.0, "unit": "mg/dL", "ref": "< 150 mg/dL", "concept": "triglycerides", "prov": "EXPLICIT"},
                    {"name": "HDL Cholesterol", "val": 42.0, "unit": "mg/dL", "ref": "> 40 mg/dL", "concept": "hdl", "prov": "EXPLICIT"},
                    {"name": "LDL Cholesterol", "val": 137.0, "unit": "mg/dL", "ref": "< 100 mg/dL", "concept": "ldl", "prov": "EXPLICIT"}
                ]
            }
        ]
    },
    {
        "id": "DOC_DIG_LAB_03",
        "category": "digital_lab_pdf",
        "filename": "DOC_DIG_LAB_03.pdf",
        "type": "pdf",
        "facility": "CAREPLUS PATHOLOGY LAB",
        "patient": {"name": "Vikram Malhotra", "id": "SYNTH-P103", "age_sex": "60 Y / M", "date": "2026-03-12", "doctor": "Dr. R. Sen, MD"},
        "pages": [
            {
                "page_num": 1,
                "title": "ELECTROLYTE & RENAL PANEL",
                "rows": [
                    {"name": "Serum Sodium", "val": 139.0, "unit": "mmol/L", "ref": "135 - 145 mmol/L", "concept": "sodium", "prov": "EXPLICIT"},
                    {"name": "Serum Potassium", "val": 4.8, "unit": "mmol/L", "ref": "3.5 - 5.0 mmol/L", "concept": "potassium", "prov": "EXPLICIT"},
                    {"name": "Serum Creatinine", "val": 1.1, "unit": "mg/dL", "ref": "0.7 - 1.3 mg/dL", "concept": "creatinine", "prov": "EXPLICIT"}
                ]
            }
        ]
    },
    {
        "id": "DOC_DIG_LAB_04",
        "category": "digital_lab_pdf",
        "filename": "DOC_DIG_LAB_04.pdf",
        "type": "pdf",
        "facility": "LIFECARE CLINICAL SERVICES",
        "patient": {"name": "Sunita Joshi", "id": "SYNTH-P104", "age_sex": "38 Y / F", "date": "2026-03-13", "doctor": "Dr. A. Verma, MD"},
        "pages": [
            {
                "page_num": 1,
                "title": "COMPLETE BLOOD COUNT REPORT",
                "rows": [
                    {"name": "Hemoglobin", "val": 13.8, "unit": "g/dL", "ref": "12.0 - 15.5 g/dL", "concept": "hemoglobin", "prov": "EXPLICIT"},
                    {"name": "WBC Count", "val": 7200.0, "unit": "/uL", "ref": "4500 - 11000 /uL", "concept": "wbc", "prov": "EXPLICIT"},
                    {"name": "Platelet Count", "val": 250000.0, "unit": "/uL", "ref": "150000 - 450000 /uL", "concept": "platelets", "prov": "EXPLICIT"}
                ]
            }
        ]
    },
    {
        "id": "DOC_DIG_LAB_05",
        "category": "digital_lab_pdf",
        "filename": "DOC_DIG_LAB_05.pdf",
        "type": "pdf",
        "facility": "TRUSTWELL BIO-LAB",
        "patient": {"name": "Rohan Deshmukh", "id": "SYNTH-P105", "age_sex": "49 Y / M", "date": "2026-03-14", "doctor": "Dr. M. Chawla, MD"},
        "pages": [
            {
                "page_num": 1,
                "title": "HEPATIC & THYROID EVALUATION",
                "rows": [
                    {"name": "Serum TSH", "val": 3.4, "unit": "mIU/L", "ref": "0.4 - 4.0 mIU/L", "concept": "tsh", "prov": "EXPLICIT"},
                    {"name": "Alanine Aminotransferase (ALT)", "val": 38.0, "unit": "U/L", "ref": "7 - 56 U/L", "concept": "alt", "prov": "EXPLICIT"},
                    {"name": "Aspartate Aminotransferase (AST)", "val": 32.0, "unit": "U/L", "ref": "10 - 40 U/L", "concept": "ast", "prov": "EXPLICIT"}
                ]
            }
        ]
    },
    {
        "id": "DOC_DIG_LAB_06",
        "category": "digital_lab_pdf",
        "filename": "DOC_DIG_LAB_06.pdf",
        "type": "pdf",
        "facility": "METROPOLIS CLINICAL LAB",
        "patient": {"name": "Ananya Iyer", "id": "SYNTH-P106", "age_sex": "56 Y / F", "date": "2026-03-15", "doctor": "Dr. P. Hegde, MD"},
        "pages": [
            {
                "page_num": 1,
                "title": "GLUCOSE MONITORING REPORT",
                "rows": [
                    {"name": "Fasting Blood Glucose", "val": 145.0, "unit": "mg/dL", "ref": "70 - 99 mg/dL", "concept": "glucose", "prov": "EXPLICIT"},
                    {"name": "Glycated Hemoglobin HbA1c", "val": 8.4, "unit": "%", "ref": "< 5.7 %", "concept": "hba1c", "prov": "EXPLICIT"}
                ]
            }
        ]
    },
    {
        "id": "DOC_DIG_LAB_07",
        "category": "digital_lab_pdf",
        "filename": "DOC_DIG_LAB_07.pdf",
        "type": "pdf",
        "facility": "MEDSTAR PATHOLOGY",
        "patient": {"name": "Karthik Reddy", "id": "SYNTH-P107", "age_sex": "50 Y / M", "date": "2026-03-16", "doctor": "Dr. D. Bannerjee, MD"},
        "pages": [
            {
                "page_num": 1,
                "title": "CARDIO-METABOLIC PANEL",
                "rows": [
                    {"name": "Fasting Blood Glucose", "val": 108.0, "unit": "mg/dL", "ref": "70 - 99 mg/dL", "concept": "glucose", "prov": "EXPLICIT"},
                    {"name": "Total Cholesterol", "val": 230.0, "unit": "mg/dL", "ref": "< 200 mg/dL", "concept": "cholesterol_total", "prov": "EXPLICIT"},
                    {"name": "LDL Cholesterol", "val": 148.0, "unit": "mg/dL", "ref": "< 100 mg/dL", "concept": "ldl", "prov": "EXPLICIT"},
                    {"name": "Triglycerides", "val": 190.0, "unit": "mg/dL", "ref": "< 150 mg/dL", "concept": "triglycerides", "prov": "EXPLICIT"}
                ]
            }
        ]
    },
    {
        "id": "DOC_DIG_LAB_08",
        "category": "digital_lab_pdf",
        "filename": "DOC_DIG_LAB_08.pdf",
        "type": "pdf",
        "facility": "APEX CLINICAL LABORATORIES",
        "patient": {"name": "Fatima Sheikh", "id": "SYNTH-P108", "age_sex": "62 Y / F", "date": "2026-03-17", "doctor": "Dr. N. Mehta, MD"},
        "pages": [
            {
                "page_num": 1,
                "title": "RENAL MONITORING REPORT",
                "rows": [
                    {"name": "Serum Creatinine", "val": 1.6, "unit": "mg/dL", "ref": "0.6 - 1.2 mg/dL", "concept": "creatinine", "prov": "EXPLICIT"},
                    {"name": "Blood Urea Nitrogen (BUN)", "val": 26.0, "unit": "mg/dL", "ref": "7 - 20 mg/dL", "concept": "bun", "prov": "EXPLICIT"},
                    {"name": "Serum Potassium", "val": 4.9, "unit": "mmol/L", "ref": "3.5 - 5.0 mmol/L", "concept": "potassium", "prov": "EXPLICIT"},
                    {"name": "Serum Sodium", "val": 137.0, "unit": "mmol/L", "ref": "135 - 145 mmol/L", "concept": "sodium", "prov": "EXPLICIT"}
                ]
            }
        ]
    },
    {
        "id": "DOC_DIG_LAB_09",
        "category": "digital_lab_pdf",
        "filename": "DOC_DIG_LAB_09.pdf",
        "type": "pdf",
        "facility": "REGIONAL MEDICAL DIAGNOSTICS",
        "patient": {"name": "Deepak Singhania", "id": "SYNTH-P109", "age_sex": "58 Y / M", "date": "2026-03-18", "doctor": "Dr. T. Roy, MD"},
        "pages": [
            {
                "page_num": 1,
                "title": "METABOLIC INVESTIGATION (PAGE 1 OF 2)",
                "rows": [
                    {"name": "Fasting Blood Glucose", "val": 126.0, "unit": "mg/dL", "ref": "70 - 99 mg/dL", "concept": "glucose", "prov": "EXPLICIT"},
                    {"name": "Glycated Hemoglobin HbA1c", "val": 7.6, "unit": "%", "ref": "4.0 - 5.6 %", "concept": "hba1c", "prov": "EXPLICIT"},
                    {"name": "Serum Creatinine", "val": 1.3, "unit": "mg/dL", "ref": "0.7 - 1.3 mg/dL", "concept": "creatinine", "prov": "EXPLICIT"}
                ]
            },
            {
                "page_num": 2,
                "title": "LIPID PROFILE (PAGE 2 OF 2)",
                "rows": [
                    {"name": "Total Cholesterol", "val": 220.0, "unit": "mg/dL", "ref": "< 200 mg/dL", "concept": "cholesterol_total", "prov": "EXPLICIT"},
                    {"name": "Triglycerides", "val": 175.0, "unit": "mg/dL", "ref": "< 150 mg/dL", "concept": "triglycerides", "prov": "EXPLICIT"},
                    {"name": "HDL Cholesterol", "val": 45.0, "unit": "mg/dL", "ref": "> 40 mg/dL", "concept": "hdl", "prov": "EXPLICIT"}
                ]
            }
        ]
    },
    {
        "id": "DOC_DIG_LAB_10",
        "category": "digital_lab_pdf",
        "filename": "DOC_DIG_LAB_10.pdf",
        "type": "pdf",
        "facility": "REGIONAL MEDICAL DIAGNOSTICS",
        "patient": {"name": "Meera Nambiar", "id": "SYNTH-P110", "age_sex": "44 Y / F", "date": "2026-03-19", "doctor": "Dr. T. Roy, MD"},
        "pages": [
            {
                "page_num": 1,
                "title": "SERUM ELECTROLYTES (PAGE 1 OF 2)",
                "rows": [
                    {"name": "Serum Sodium", "val": 142.0, "unit": "mmol/L", "ref": "135 - 145 mmol/L", "concept": "sodium", "prov": "EXPLICIT"},
                    {"name": "Serum Potassium", "val": 4.3, "unit": "mmol/L", "ref": "3.5 - 5.0 mmol/L", "concept": "potassium", "prov": "EXPLICIT"}
                ]
            },
            {
                "page_num": 2,
                "title": "LIVER ENZYMES & THYROID (PAGE 2 OF 2)",
                "rows": [
                    {"name": "Alanine Aminotransferase (ALT)", "val": 34.0, "unit": "U/L", "ref": "7 - 56 U/L", "concept": "alt", "prov": "EXPLICIT"},
                    {"name": "Aspartate Aminotransferase (AST)", "val": 28.0, "unit": "U/L", "ref": "10 - 40 U/L", "concept": "ast", "prov": "EXPLICIT"},
                    {"name": "Serum TSH", "val": 2.9, "unit": "mIU/L", "ref": "0.4 - 4.0 mIU/L", "concept": "tsh", "prov": "EXPLICIT"}
                ]
            }
        ]
    },

    # --------------------------------------------------------------------------
    # CATEGORY 2: Clean scanned laboratory reports (10 docs, PNG)
    # --------------------------------------------------------------------------
    {
        "id": "DOC_SCN_LAB_01",
        "category": "clean_scanned_lab",
        "filename": "DOC_SCN_LAB_01.png",
        "type": "png",
        "facility": "PRIME CLINICAL PATHOLOGY",
        "patient": {"name": "Sanjay Das", "id": "SYNTH-P201", "age_sex": "53 Y / M", "date": "2026-03-15", "doctor": "Dr. G. Saxena, MD"},
        "rows": [
            {"name": "Fasting Blood Glucose", "val": 142.0, "unit": "mg/dL", "ref": "70 - 99 mg/dL", "concept": "glucose", "prov": "EXPLICIT"},
            {"name": "Glycated Hemoglobin HbA1c", "val": 8.1, "unit": "%", "ref": "4.0 - 5.6 %", "concept": "hba1c", "prov": "EXPLICIT"}
        ]
    },
    {
        "id": "DOC_SCN_LAB_02",
        "category": "clean_scanned_lab",
        "filename": "DOC_SCN_LAB_02.png",
        "type": "png",
        "facility": "PRIME CLINICAL PATHOLOGY",
        "patient": {"name": "Neelam Kapoor", "id": "SYNTH-P202", "age_sex": "64 Y / F", "date": "2026-03-16", "doctor": "Dr. G. Saxena, MD"},
        "rows": [
            {"name": "Serum Creatinine", "val": 1.8, "unit": "mg/dL", "ref": "0.6 - 1.2 mg/dL", "concept": "creatinine", "prov": "EXPLICIT"},
            {"name": "Blood Urea Nitrogen (BUN)", "val": 28.0, "unit": "mg/dL", "ref": "7 - 20 mg/dL", "concept": "bun", "prov": "EXPLICIT"},
            {"name": "Serum Potassium", "val": 5.2, "unit": "mmol/L", "ref": "3.5 - 5.0 mmol/L", "concept": "potassium", "prov": "EXPLICIT"}
        ]
    },
    {
        "id": "DOC_SCN_LAB_03",
        "category": "clean_scanned_lab",
        "filename": "DOC_SCN_LAB_03.png",
        "type": "png",
        "facility": "GLOBAL DIAGNOSTIC NETWORK",
        "patient": {"name": "Rajeshwari Pillai", "id": "SYNTH-P203", "age_sex": "47 Y / F", "date": "2026-03-17", "doctor": "Dr. B. Dasgupta, MD"},
        "rows": [
            {"name": "Total Cholesterol", "val": 245.0, "unit": "mg/dL", "ref": "< 200 mg/dL", "concept": "cholesterol_total", "prov": "EXPLICIT"},
            {"name": "Triglycerides", "val": 210.0, "unit": "mg/dL", "ref": "< 150 mg/dL", "concept": "triglycerides", "prov": "EXPLICIT"},
            {"name": "HDL Cholesterol", "val": 38.0, "unit": "mg/dL", "ref": "> 40 mg/dL", "concept": "hdl", "prov": "EXPLICIT"},
            {"name": "LDL Cholesterol", "val": 165.0, "unit": "mg/dL", "ref": "< 100 mg/dL", "concept": "ldl", "prov": "EXPLICIT"}
        ]
    },
    {
        "id": "DOC_SCN_LAB_04",
        "category": "clean_scanned_lab",
        "filename": "DOC_SCN_LAB_04.png",
        "type": "png",
        "facility": "GLOBAL DIAGNOSTIC NETWORK",
        "patient": {"name": "Manish Tiwari", "id": "SYNTH-P204", "age_sex": "39 Y / M", "date": "2026-03-18", "doctor": "Dr. B. Dasgupta, MD"},
        "rows": [
            {"name": "Alanine Aminotransferase (ALT)", "val": 54.0, "unit": "U/L", "ref": "7 - 56 U/L", "concept": "alt", "prov": "EXPLICIT"},
            {"name": "Aspartate Aminotransferase (AST)", "val": 48.0, "unit": "U/L", "ref": "10 - 40 U/L", "concept": "ast", "prov": "EXPLICIT"}
        ]
    },
    {
        "id": "DOC_SCN_LAB_05",
        "category": "clean_scanned_lab",
        "filename": "DOC_SCN_LAB_05.png",
        "type": "png",
        "facility": "MAXIMA HEALTHCARE LAB",
        "patient": {"name": "Gita Sen", "id": "SYNTH-P205", "age_sex": "57 Y / F", "date": "2026-03-19", "doctor": "Dr. H. Swaminathan, MD"},
        "rows": [
            {"name": "Blood Pressure", "val": "140/90", "unit": "mmHg", "ref": "< 120/80 mmHg", "concept": "blood_pressure", "prov": "EXPLICIT"},
            {"name": "Heart Rate", "val": 82.0, "unit": "bpm", "ref": "60 - 100 bpm", "concept": "heart_rate", "prov": "EXPLICIT"},
            {"name": "Fasting Blood Glucose", "val": 108.0, "unit": "mg/dL", "ref": "70 - 99 mg/dL", "concept": "glucose", "prov": "EXPLICIT"}
        ]
    },
    {
        "id": "DOC_SCN_LAB_06",
        "category": "clean_scanned_lab",
        "filename": "DOC_SCN_LAB_06.png",
        "type": "png",
        "facility": "MAXIMA HEALTHCARE LAB",
        "patient": {"name": "Tariq Mansoor", "id": "SYNTH-P206", "age_sex": "35 Y / M", "date": "2026-03-20", "doctor": "Dr. H. Swaminathan, MD"},
        "rows": [
            {"name": "Serum TSH", "val": 5.8, "unit": "mIU/L", "ref": "0.4 - 4.0 mIU/L", "concept": "tsh", "prov": "EXPLICIT"}
        ]
    },
    {
        "id": "DOC_SCN_LAB_07",
        "category": "clean_scanned_lab",
        "filename": "DOC_SCN_LAB_07.png",
        "type": "png",
        "facility": "VITALIS PATH LAB",
        "patient": {"name": "Kavita Rane", "id": "SYNTH-P207", "age_sex": "42 Y / F", "date": "2026-03-21", "doctor": "Dr. S. Nadkarni, MD"},
        "rows": [
            {"name": "Hemoglobin", "val": 12.4, "unit": "g/dL", "ref": "12.0 - 15.5 g/dL", "concept": "hemoglobin", "prov": "EXPLICIT"},
            {"name": "Fasting Blood Glucose", "val": 95.0, "unit": "mg/dL", "ref": "70 - 99 mg/dL", "concept": "glucose", "prov": "EXPLICIT"},
            {"name": "Serum Creatinine", "val": 0.9, "unit": "mg/dL", "ref": "0.6 - 1.2 mg/dL", "concept": "creatinine", "prov": "EXPLICIT"}
        ]
    },
    {
        "id": "DOC_SCN_LAB_08",
        "category": "clean_scanned_lab",
        "filename": "DOC_SCN_LAB_08.png",
        "type": "png",
        "facility": "VITALIS PATH LAB",
        "patient": {"name": "Ashok Singhal", "id": "SYNTH-P208", "age_sex": "68 Y / M", "date": "2026-03-22", "doctor": "Dr. S. Nadkarni, MD"},
        "rows": [
            {"name": "Serum Sodium", "val": 141.0, "unit": "mmol/L", "ref": "135 - 145 mmol/L", "concept": "sodium", "prov": "EXPLICIT"},
            {"name": "Serum Potassium", "val": 4.1, "unit": "mmol/L", "ref": "3.5 - 5.0 mmol/L", "concept": "potassium", "prov": "EXPLICIT"}
        ]
    },
    {
        "id": "DOC_SCN_LAB_09",
        "category": "clean_scanned_lab",
        "filename": "DOC_SCN_LAB_09.png",
        "type": "png",
        "facility": "CITY CLINICAL ASSOCIATES",
        "patient": {"name": "Sarojini Devi", "id": "SYNTH-P209", "age_sex": "71 Y / F", "date": "2026-03-23", "doctor": "Dr. V. Kaushik, MD"},
        "rows": [
            {"name": "Fasting Blood Glucose", "val": 115.0, "unit": "mg/dL", "ref": "70 - 99 mg/dL", "concept": "glucose", "prov": "EXPLICIT"},
            {"name": "Serum Creatinine", "val": 1.1, "unit": "mg/dL", "ref": "0.6 - 1.2 mg/dL", "concept": "creatinine", "prov": "EXPLICIT"},
            {"name": "Serum Sodium", "val": 138.0, "unit": "mmol/L", "ref": "135 - 145 mmol/L", "concept": "sodium", "prov": "EXPLICIT"}
        ]
    },
    {
        "id": "DOC_SCN_LAB_10",
        "category": "clean_scanned_lab",
        "filename": "DOC_SCN_LAB_10.png",
        "type": "png",
        "facility": "CITY CLINICAL ASSOCIATES",
        "patient": {"name": "Girish Prasad", "id": "SYNTH-P210", "age_sex": "50 Y / M", "date": "2026-03-24", "doctor": "Dr. V. Kaushik, MD"},
        "rows": [
            {"name": "Glycated Hemoglobin HbA1c", "val": 6.9, "unit": "%", "ref": "4.0 - 5.6 %", "concept": "hba1c", "prov": "EXPLICIT"},
            {"name": "Triglycerides", "val": 165.0, "unit": "mg/dL", "ref": "< 150 mg/dL", "concept": "triglycerides", "prov": "EXPLICIT"},
            {"name": "Alanine Aminotransferase (ALT)", "val": 29.0, "unit": "U/L", "ref": "7 - 56 U/L", "concept": "alt", "prov": "EXPLICIT"}
        ]
    },

    # --------------------------------------------------------------------------
    # CATEGORY 3: Scanned prescriptions (10 docs, PNG)
    # --------------------------------------------------------------------------
    {
        "id": "DOC_RX_01",
        "category": "scanned_prescription",
        "filename": "DOC_RX_01.png",
        "type": "png",
        "facility": "SHARMA CLINIC & DIABETES CARE",
        "doc_type": "prescription",
        "patient": {"name": "Arjun Patel", "id": "SYNTH-P301", "age_sex": "55 Y / M", "date": "2026-03-18", "doctor": "Dr. A. K. Sharma, MD"},
        "medications": [
            {"name": "Metformin", "strength": 500.0, "unit": "mg", "frequency": "OD", "duration": "30 days", "concept": "metformin", "prov": "EXPLICIT"}
        ]
    },
    {
        "id": "DOC_RX_02",
        "category": "scanned_prescription",
        "filename": "DOC_RX_02.png",
        "type": "png",
        "facility": "HYPERTENSION CLINIC",
        "doc_type": "prescription",
        "patient": {"name": "Bhavna Trivedi", "id": "SYNTH-P302", "age_sex": "61 Y / F", "date": "2026-03-19", "doctor": "Dr. S. Mathur, MD"},
        "medications": [
            {"name": "Lisinopril", "strength": 10.0, "unit": "mg", "frequency": "OD", "duration": "30 days", "concept": "lisinopril", "prov": "EXPLICIT"}
        ]
    },
    {
        "id": "DOC_RX_03",
        "category": "scanned_prescription",
        "filename": "DOC_RX_03.png",
        "type": "png",
        "facility": "CARDIO-VASCULAR ASSOCIATES",
        "doc_type": "prescription",
        "patient": {"name": "Chetan Bhagat", "id": "SYNTH-P303", "age_sex": "59 Y / M", "date": "2026-03-20", "doctor": "Dr. R. Singhal, MD"},
        "medications": [
            {"name": "Losartan", "strength": 50.0, "unit": "mg", "frequency": "OD", "duration": "30 days", "concept": "losartan", "prov": "EXPLICIT"},
            {"name": "Atorvastatin", "strength": 20.0, "unit": "mg", "frequency": "OD", "duration": "30 days", "concept": "atorvastatin", "prov": "EXPLICIT"}
        ]
    },
    {
        "id": "DOC_RX_04",
        "category": "scanned_prescription",
        "filename": "DOC_RX_04.png",
        "type": "png",
        "facility": "FAMILY HEALTH CLINIC",
        "doc_type": "prescription",
        "patient": {"name": "Divya Murthy", "id": "SYNTH-P304", "age_sex": "32 Y / F", "date": "2026-03-21", "doctor": "Dr. P. Sen, MBBS"},
        "medications": [
            {"name": "Amoxicillin", "strength": 500.0, "unit": "mg", "frequency": "TID", "duration": "7 days", "concept": "amoxicillin", "prov": "EXPLICIT"}
        ]
    },
    {
        "id": "DOC_RX_05",
        "category": "scanned_prescription",
        "filename": "DOC_RX_05.png",
        "type": "png",
        "facility": "PULMOCARE CLINIC",
        "doc_type": "prescription",
        "patient": {"name": "Eshwar Chand", "id": "SYNTH-P305", "age_sex": "46 Y / M", "date": "2026-03-22", "doctor": "Dr. T. Roy, MD"},
        "medications": [
            {"name": "Azithromycin", "strength": 250.0, "unit": "mg", "frequency": "OD", "duration": "5 days", "concept": "azithromycin", "prov": "EXPLICIT"}
        ]
    },
    {
        "id": "DOC_RX_06",
        "category": "scanned_prescription",
        "filename": "DOC_RX_06.png",
        "type": "png",
        "facility": "ENDOCRINOLOGY CENTRE",
        "doc_type": "prescription",
        "patient": {"name": "Farida Begum", "id": "SYNTH-P306", "age_sex": "40 Y / F", "date": "2026-03-23", "doctor": "Dr. M. Chawla, MD"},
        "medications": [
            {"name": "Levothyroxine", "strength": 50.0, "unit": "mcg", "frequency": "OD", "duration": "60 days", "concept": "levothyroxine", "prov": "EXPLICIT"}
        ]
    },
    {
        "id": "DOC_RX_07",
        "category": "scanned_prescription",
        "filename": "DOC_RX_07.png",
        "type": "png",
        "facility": "CHEST CARE CLINIC",
        "doc_type": "prescription",
        "patient": {"name": "Govind Narang", "id": "SYNTH-P307", "age_sex": "28 Y / M", "date": "2026-03-24", "doctor": "Dr. H. Swaminathan, MD"},
        "medications": [
            {"name": "Salbutamol", "strength": 100.0, "unit": "mcg", "frequency": "as needed", "duration": "30 days", "concept": "salbutamol", "prov": "EXPLICIT"}
        ]
    },
    {
        "id": "DOC_RX_08",
        "category": "scanned_prescription",
        "filename": "DOC_RX_08.png",
        "type": "png",
        "facility": "DIABETIC SPECIALTY CLINIC",
        "doc_type": "prescription",
        "patient": {"name": "Harishankar Shukla", "id": "SYNTH-P308", "age_sex": "66 Y / M", "date": "2026-03-25", "doctor": "Dr. A. K. Sharma, MD"},
        "medications": [
            {"name": "Metformin", "strength": 1000.0, "unit": "mg", "frequency": "BD", "duration": "30 days", "concept": "metformin", "prov": "EXPLICIT"}
        ]
    },
    {
        "id": "DOC_RX_09",
        "category": "scanned_prescription",
        "filename": "DOC_RX_09.png",
        "type": "png",
        "facility": "HEART CARE INSTITUTE",
        "doc_type": "prescription",
        "patient": {"name": "Indira Ghosh", "id": "SYNTH-P309", "age_sex": "63 Y / F", "date": "2026-03-26", "doctor": "Dr. R. Singhal, MD"},
        "medications": [
            {"name": "Atorvastatin", "strength": 40.0, "unit": "mg", "frequency": "OD", "duration": "30 days", "concept": "atorvastatin", "prov": "EXPLICIT"}
        ]
    },
    {
        "id": "DOC_RX_10",
        "category": "scanned_prescription",
        "filename": "DOC_RX_10.png",
        "type": "png",
        "facility": "HYPERTENSION CLINIC",
        "doc_type": "prescription",
        "patient": {"name": "Javed Akhtar", "id": "SYNTH-P310", "age_sex": "57 Y / M", "date": "2026-03-27", "doctor": "Dr. S. Mathur, MD"},
        "medications": [
            {"name": "Lisinopril", "strength": 20.0, "unit": "mg", "frequency": "OD", "duration": "30 days", "concept": "lisinopril", "prov": "EXPLICIT"}
        ]
    },

    # --------------------------------------------------------------------------
    # CATEGORY 4: Low-resolution or noisy scans (5 docs, PNG)
    # --------------------------------------------------------------------------
    {
        "id": "DOC_NOISY_01",
        "category": "noisy_scan",
        "filename": "DOC_NOISY_01.png",
        "type": "png",
        "noise_level": 2,
        "facility": "DISTRICT HEALTH DISPENSARY",
        "patient": {"name": "Kamala Bai", "id": "SYNTH-P401", "age_sex": "51 Y / F", "date": "2026-03-14", "doctor": "Dr. O. P. Yadav, MBBS"},
        "rows": [
            {"name": "Fasting Blood Glucose", "val": 128.0, "unit": "mg/dL", "ref": "70 - 99 mg/dL", "concept": "glucose", "prov": "EXPLICIT"},
            {"name": "Serum Creatinine", "val": 1.3, "unit": "mg/dL", "ref": "0.6 - 1.2 mg/dL", "concept": "creatinine", "prov": "EXPLICIT"}
        ]
    },
    {
        "id": "DOC_NOISY_02",
        "category": "noisy_scan",
        "filename": "DOC_NOISY_02.png",
        "type": "png",
        "noise_level": 2,
        "facility": "COMMUNITY PATHOLOGY LAB",
        "patient": {"name": "Laxman Rao", "id": "SYNTH-P402", "age_sex": "60 Y / M", "date": "2026-03-15", "doctor": "Dr. O. P. Yadav, MBBS"},
        "rows": [
            {"name": "Glycated Hemoglobin HbA1c", "val": 7.5, "unit": "%", "ref": "4.0 - 5.6 %", "concept": "hba1c", "prov": "EXPLICIT"},
            {"name": "Blood Urea Nitrogen (BUN)", "val": 22.0, "unit": "mg/dL", "ref": "7 - 20 mg/dL", "concept": "bun", "prov": "EXPLICIT"}
        ]
    },
    {
        "id": "DOC_NOISY_03",
        "category": "noisy_scan",
        "filename": "DOC_NOISY_03.png",
        "type": "png",
        "noise_level": 2,
        "facility": "COMMUNITY PATHOLOGY LAB",
        "patient": {"name": "Mohan Lal", "id": "SYNTH-P403", "age_sex": "54 Y / M", "date": "2026-03-16", "doctor": "Dr. N. Joshi, MD"},
        "rows": [
            {"name": "Serum Potassium", "val": 4.6, "unit": "mmol/L", "ref": "3.5 - 5.0 mmol/L", "concept": "potassium", "prov": "EXPLICIT"},
            {"name": "Serum Sodium", "val": 140.0, "unit": "mmol/L", "ref": "135 - 145 mmol/L", "concept": "sodium", "prov": "EXPLICIT"}
        ]
    },
    {
        "id": "DOC_NOISY_04",
        "category": "noisy_scan",
        "filename": "DOC_NOISY_04.png",
        "type": "png",
        "noise_level": 2,
        "facility": "RURAL CLINIC & LAB",
        "patient": {"name": "Nandita Sen", "id": "SYNTH-P404", "age_sex": "48 Y / F", "date": "2026-03-17", "doctor": "Dr. N. Joshi, MD"},
        "rows": [
            {"name": "Total Cholesterol", "val": 230.0, "unit": "mg/dL", "ref": "< 200 mg/dL", "concept": "cholesterol_total", "prov": "EXPLICIT"},
            {"name": "Triglycerides", "val": 195.0, "unit": "mg/dL", "ref": "< 150 mg/dL", "concept": "triglycerides", "prov": "EXPLICIT"}
        ]
    },
    {
        "id": "DOC_NOISY_05",
        "category": "noisy_scan",
        "filename": "DOC_NOISY_05.png",
        "type": "png",
        "noise_level": 2,
        "facility": "OUTPATIENT HEALTH POST",
        "doc_type": "prescription",
        "patient": {"name": "Omkar Nath", "id": "SYNTH-P405", "age_sex": "58 Y / M", "date": "2026-03-18", "doctor": "Dr. P. Sen, MBBS"},
        "medications": [
            {"name": "Metformin", "strength": 500.0, "unit": "mg", "frequency": "OD", "duration": "30 days", "concept": "metformin", "prov": "EXPLICIT"}
        ]
    },

    # --------------------------------------------------------------------------
    # CATEGORY 5: Rotated or skewed documents (5 docs, PNG)
    # --------------------------------------------------------------------------
    {
        "id": "DOC_SKEW_01",
        "category": "skewed_document",
        "filename": "DOC_SKEW_01.png",
        "type": "png",
        "skew_angle": -3,
        "facility": "METROPOLITAN BIO-LAB",
        "patient": {"name": "Pooja Hegde", "id": "SYNTH-P501", "age_sex": "43 Y / F", "date": "2026-03-12", "doctor": "Dr. R. Bannerjee, MD"},
        "rows": [
            {"name": "Glycated Hemoglobin HbA1c", "val": 6.8, "unit": "%", "ref": "4.0 - 5.6 %", "concept": "hba1c", "prov": "EXPLICIT"},
            {"name": "Fasting Blood Glucose", "val": 105.0, "unit": "mg/dL", "ref": "70 - 99 mg/dL", "concept": "glucose", "prov": "EXPLICIT"}
        ]
    },
    {
        "id": "DOC_SKEW_02",
        "category": "skewed_document",
        "filename": "DOC_SKEW_02.png",
        "type": "png",
        "skew_angle": 4,
        "facility": "METROPOLITAN BIO-LAB",
        "patient": {"name": "Qadir Khan", "id": "SYNTH-P502", "age_sex": "61 Y / M", "date": "2026-03-13", "doctor": "Dr. R. Bannerjee, MD"},
        "rows": [
            {"name": "Serum Creatinine", "val": 1.5, "unit": "mg/dL", "ref": "0.6 - 1.2 mg/dL", "concept": "creatinine", "prov": "EXPLICIT"},
            {"name": "Serum Potassium", "val": 4.4, "unit": "mmol/L", "ref": "3.5 - 5.0 mmol/L", "concept": "potassium", "prov": "EXPLICIT"}
        ]
    },
    {
        "id": "DOC_SKEW_03",
        "category": "skewed_document",
        "filename": "DOC_SKEW_03.png",
        "type": "png",
        "skew_angle": -5,
        "facility": "EXCEL DIAGNOSTICS",
        "patient": {"name": "Radha Krishnan", "id": "SYNTH-P503", "age_sex": "50 Y / F", "date": "2026-03-14", "doctor": "Dr. S. Kulkarni, MD"},
        "rows": [
            {"name": "Total Cholesterol", "val": 210.0, "unit": "mg/dL", "ref": "< 200 mg/dL", "concept": "cholesterol_total", "prov": "EXPLICIT"},
            {"name": "LDL Cholesterol", "val": 130.0, "unit": "mg/dL", "ref": "< 100 mg/dL", "concept": "ldl", "prov": "EXPLICIT"}
        ]
    },
    {
        "id": "DOC_SKEW_04",
        "category": "skewed_document",
        "filename": "DOC_SKEW_04.png",
        "type": "png",
        "skew_angle": 3,
        "facility": "EXCEL CLINIC",
        "doc_type": "prescription",
        "patient": {"name": "Shailesh Verma", "id": "SYNTH-P504", "age_sex": "56 Y / M", "date": "2026-03-15", "doctor": "Dr. S. Kulkarni, MD"},
        "medications": [
            {"name": "Lisinopril", "strength": 10.0, "unit": "mg", "frequency": "OD", "duration": "30 days", "concept": "lisinopril", "prov": "EXPLICIT"}
        ]
    },
    {
        "id": "DOC_SKEW_05",
        "category": "skewed_document",
        "filename": "DOC_SKEW_05.png",
        "type": "png",
        "skew_angle": -4,
        "facility": "CITY CARDIAC CARE",
        "patient": {"name": "Tarun Mehra", "id": "SYNTH-P505", "age_sex": "62 Y / M", "date": "2026-03-16", "doctor": "Dr. A. Verma, MD"},
        "rows": [
            {"name": "Blood Pressure", "val": "135/85", "unit": "mmHg", "ref": "< 120/80 mmHg", "concept": "blood_pressure", "prov": "EXPLICIT"},
            {"name": "Heart Rate", "val": 76.0, "unit": "bpm", "ref": "60 - 100 bpm", "concept": "heart_rate", "prov": "EXPLICIT"}
        ]
    },

    # --------------------------------------------------------------------------
    # CATEGORY 6: Documents containing medical tables (5 docs, PDF)
    # --------------------------------------------------------------------------
    {
        "id": "DOC_TBL_01",
        "category": "medical_table",
        "filename": "DOC_TBL_01.pdf",
        "type": "pdf",
        "facility": "APEX PATHOLOGY LABORATORY",
        "patient": {"name": "Usha Narayanan", "id": "SYNTH-P601", "age_sex": "52 Y / F", "date": "2026-03-20", "doctor": "Dr. V. Gupta, MD"},
        "rows": [
            {"name": "Fasting Blood Glucose", "val": 118.0, "unit": "mg/dL", "ref": "70 - 99", "concept": "glucose", "prov": "EXPLICIT"},
            {"name": "Blood Urea Nitrogen (BUN)", "val": 19.0, "unit": "mg/dL", "ref": "7 - 20", "concept": "bun", "prov": "EXPLICIT"},
            {"name": "Serum Creatinine", "val": 1.2, "unit": "mg/dL", "ref": "0.6 - 1.2", "concept": "creatinine", "prov": "EXPLICIT"},
            {"name": "Serum Sodium", "val": 142.0, "unit": "mmol/L", "ref": "135 - 145", "concept": "sodium", "prov": "EXPLICIT"},
            {"name": "Serum Potassium", "val": 4.5, "unit": "mmol/L", "ref": "3.5 - 5.0", "concept": "potassium", "prov": "EXPLICIT"}
        ]
    },
    {
        "id": "DOC_TBL_02",
        "category": "medical_table",
        "filename": "DOC_TBL_02.pdf",
        "type": "pdf",
        "facility": "APEX PATHOLOGY LABORATORY",
        "patient": {"name": "Vijay Shankar", "id": "SYNTH-P602", "age_sex": "49 Y / M", "date": "2026-03-21", "doctor": "Dr. V. Gupta, MD"},
        "rows": [
            {"name": "Total Cholesterol", "val": 225.0, "unit": "mg/dL", "ref": "< 200", "concept": "cholesterol_total", "prov": "EXPLICIT"},
            {"name": "Triglycerides", "val": 175.0, "unit": "mg/dL", "ref": "< 150", "concept": "triglycerides", "prov": "EXPLICIT"},
            {"name": "HDL Cholesterol", "val": 45.0, "unit": "mg/dL", "ref": "> 40", "concept": "hdl", "prov": "EXPLICIT"},
            {"name": "LDL Cholesterol", "val": 145.0, "unit": "mg/dL", "ref": "< 100", "concept": "ldl", "prov": "EXPLICIT"}
        ]
    },
    {
        "id": "DOC_TBL_03",
        "category": "medical_table",
        "filename": "DOC_TBL_03.pdf",
        "type": "pdf",
        "facility": "BIO-METRIC DIAGNOSTIC HUB",
        "patient": {"name": "Wasim Akram", "id": "SYNTH-P603", "age_sex": "37 Y / M", "date": "2026-03-22", "doctor": "Dr. M. Chawla, MD"},
        "rows": [
            {"name": "Hemoglobin", "val": 14.2, "unit": "g/dL", "ref": "13.0 - 17.0", "concept": "hemoglobin", "prov": "EXPLICIT"},
            {"name": "WBC Count", "val": 6800.0, "unit": "/uL", "ref": "4000 - 11000", "concept": "wbc", "prov": "EXPLICIT"},
            {"name": "Platelet Count", "val": 240000.0, "unit": "/uL", "ref": "150000 - 450000", "concept": "platelets", "prov": "EXPLICIT"}
        ]
    },
    {
        "id": "DOC_TBL_04",
        "category": "medical_table",
        "filename": "DOC_TBL_04.pdf",
        "type": "pdf",
        "facility": "BIO-METRIC DIAGNOSTIC HUB",
        "patient": {"name": "Xavier D'Souza", "id": "SYNTH-P604", "age_sex": "55 Y / M", "date": "2026-03-23", "doctor": "Dr. M. Chawla, MD"},
        "rows": [
            {"name": "Alanine Aminotransferase (ALT)", "val": 42.0, "unit": "U/L", "ref": "7 - 56", "concept": "alt", "prov": "EXPLICIT"},
            {"name": "Aspartate Aminotransferase (AST)", "val": 36.0, "unit": "U/L", "ref": "10 - 40", "concept": "ast", "prov": "EXPLICIT"},
            {"name": "Serum TSH", "val": 2.8, "unit": "mIU/L", "ref": "0.4 - 4.0", "concept": "tsh", "prov": "EXPLICIT"}
        ]
    },
    {
        "id": "DOC_TBL_05",
        "category": "medical_table",
        "filename": "DOC_TBL_05.pdf",
        "type": "pdf",
        "facility": "CENTRAL CLINICAL SERVICES",
        "patient": {"name": "Yamini Mohan", "id": "SYNTH-P605", "age_sex": "58 Y / F", "date": "2026-03-24", "doctor": "Dr. R. Sen, MD"},
        "rows": [
            {"name": "Fasting Blood Glucose", "val": 135.0, "unit": "mg/dL", "ref": "70 - 99", "concept": "glucose", "prov": "EXPLICIT"},
            {"name": "Glycated Hemoglobin HbA1c", "val": 7.8, "unit": "%", "ref": "4.0 - 5.6", "concept": "hba1c", "prov": "EXPLICIT"},
            {"name": "Serum Creatinine", "val": 1.4, "unit": "mg/dL", "ref": "0.6 - 1.2", "concept": "creatinine", "prov": "EXPLICIT"}
        ]
    },

    # --------------------------------------------------------------------------
    # CATEGORY 7: Ambiguous values and missing units (5 docs, PNG)
    # --------------------------------------------------------------------------
    {
        "id": "DOC_AMB_01",
        "category": "ambiguous_or_missing_unit",
        "filename": "DOC_AMB_01.png",
        "type": "png",
        "facility": "LEGACY CLINICAL SLIP",
        "patient": {"name": "Zoya Akhtar", "id": "SYNTH-P701", "age_sex": "46 Y / F", "date": "2026-03-11", "doctor": "Dr. K. Nair, MD"},
        "rows": [
            # Creatinine without unit -> unit_provenance: MISSING
            {"name": "Serum Creatinine", "val": 1.4, "unit": "", "raw_unit": "", "ref_range": "Normal", "concept": "creatinine", "prov": "MISSING"}
        ]
    },
    {
        "id": "DOC_AMB_02",
        "category": "ambiguous_or_missing_unit",
        "filename": "DOC_AMB_02.png",
        "type": "png",
        "facility": "LEGACY CLINICAL SLIP",
        "patient": {"name": "Abhay Deol", "id": "SYNTH-P702", "age_sex": "53 Y / M", "date": "2026-03-12", "doctor": "Dr. K. Nair, MD"},
        "rows": [
            # Potassium with mEq/L -> normalized to mmol/L
            {"name": "Serum Potassium", "val": 4.8, "unit": "mEq/L", "expected_normalized_unit": "mmol/L", "ref_range": "3.5 - 5.0", "concept": "potassium", "prov": "NORMALIZED"}
        ]
    },
    {
        "id": "DOC_AMB_03",
        "category": "ambiguous_or_missing_unit",
        "filename": "DOC_AMB_03.png",
        "type": "png",
        "facility": "TRIAGE ASSESSMENT NOTE",
        "patient": {"name": "Bindu Madhavi", "id": "SYNTH-P703", "age_sex": "65 Y / F", "date": "2026-03-13", "doctor": "Dr. V. Kaushik, MD"},
        "rows": [
            # Blood Pressure written as "138/88" without mmHg
            {"name": "Blood Pressure", "val": "138/88", "unit": "", "expected_inferred_unit": "mmHg", "ref_range": "Stage 1 HTN", "concept": "blood_pressure", "prov": "INFERRED"}
        ]
    },
    {
        "id": "DOC_AMB_04",
        "category": "ambiguous_or_missing_unit",
        "filename": "DOC_AMB_04.png",
        "type": "png",
        "facility": "EMERGENCY OUTPATIENT SLIP",
        "patient": {"name": "Chirag Paswan", "id": "SYNTH-P704", "age_sex": "41 Y / M", "date": "2026-03-14", "doctor": "Dr. S. Nadkarni, MD"},
        "rows": [
            # Glucose without unit -> MISSING
            {"name": "Fasting Blood Glucose", "val": 115.0, "unit": "", "raw_unit": "", "ref_range": "Borderline", "concept": "glucose", "prov": "MISSING"}
        ]
    },
    {
        "id": "DOC_AMB_05",
        "category": "ambiguous_or_missing_unit",
        "filename": "DOC_AMB_05.png",
        "type": "png",
        "facility": "UNVALIDATED RESEARCH SLIP",
        "patient": {"name": "Damodar Das", "id": "SYNTH-P705", "age_sex": "57 Y / M", "date": "2026-03-15", "doctor": "Dr. G. Saxena, MD"},
        "rows": [
            # HbA1c with nonsense unit 'x_unit' -> INVALID
            {"name": "Glycated Hemoglobin HbA1c", "val": 7.1, "unit": "x_unit", "raw_unit": "x_unit", "ref_range": "Unspecified", "concept": "hba1c", "prov": "INVALID"}
        ]
    }
]


def generate_dataset():
    manifest_records = []
    print(f"Generating {len(DOCUMENTS_SPEC)} synthetic medical documents and ground-truth annotations...")

    for spec in DOCUMENTS_SPEC:
        doc_id = spec["id"]
        category = spec["category"]
        filename = spec["filename"]
        doc_path = OUTPUT_DOCS_DIR / filename
        gt_path = OUTPUT_GT_DIR / f"{doc_id}.json"

        # Determine document rendering method
        if spec["type"] == "pdf":
            if category == "medical_table":
                # Render table PDF
                table_data = {
                    "facility": spec.get("facility"),
                    "patient_header": spec["patient"],
                    "rows": [
                        {
                            "test_name": r["name"],
                            "value": r["val"],
                            "unit": r["unit"],
                            "ref_range": r.get("ref", "")
                        } for r in spec["rows"]
                    ]
                }
                create_table_pdf(doc_id, table_data, doc_path)
                pages_count = 1
                page_texts = [
                    f"{spec['facility']}\nPatient: {spec['patient']['name']} ({spec['patient']['id']})\n" +
                    "\n".join([f"{r['name']} {r['val']} {r['unit']}" for r in spec["rows"]])
                ]
            else:
                # Digital PDF (single or multi-page)
                pages_data = []
                page_texts = []
                for p_info in spec["pages"]:
                    p_rows = [
                        {
                            "test_name": r["name"],
                            "value": r["val"],
                            "unit": r["unit"],
                            "ref_range": r.get("ref", "")
                        } for r in p_info["rows"]
                    ]
                    pages_data.append({
                        "facility": spec.get("facility"),
                        "patient_header": spec["patient"],
                        "section_title": p_info.get("title"),
                        "rows": p_rows
                    })
                    raw_p = f"{spec['facility']}\nPatient: {spec['patient']['name']} ({spec['patient']['id']})\n" + \
                            "\n".join([f"{r['name']} {r['val']} {r['unit']}" for r in p_info["rows"]])
                    page_texts.append(raw_p)

                create_digital_pdf(doc_id, pages_data, doc_path)
                pages_count = len(pages_data)
        else:
            # PNG image rendering
            noise_lvl = spec.get("noise_level", 0)
            skew_ang = spec.get("skew_angle", 0)
            doc_type = spec.get("doc_type", "lab")

            if doc_type == "prescription":
                image_data = {
                    "facility": spec.get("facility"),
                    "patient_header": spec["patient"],
                    "doc_type": "prescription",
                    "medications": spec["medications"]
                }
                raw_text = f"{spec['facility']}\nPatient: {spec['patient']['name']} ({spec['patient']['id']})\n" + \
                           "\n".join([f"{m['name']} {m['strength']} {m['unit']} Sig: {m['frequency']}" for m in spec["medications"]])
            else:
                image_data = {
                    "facility": spec.get("facility"),
                    "patient_header": spec["patient"],
                    "doc_type": "lab",
                    "rows": [
                        {
                            "test_name": r["name"],
                            "value": r["val"],
                            "unit": r["unit"],
                            "ref_range": r.get("ref", r.get("ref_range", ""))
                        } for r in spec["rows"]
                    ]
                }
                raw_text = f"{spec['facility']}\nPatient: {spec['patient']['name']} ({spec['patient']['id']})\n" + \
                           "\n".join([f"{r['name']} {r['val']} {r['unit']}" for r in spec["rows"]])

            create_scanned_image(doc_id, image_data, doc_path, noise_level=noise_lvl, skew_angle=skew_ang)
            pages_count = 1
            page_texts = [raw_text]

        # Build machine-readable ground truth
        expected_fields = []
        if spec.get("doc_type") == "prescription":
            for med in spec["medications"]:
                expected_fields.append({
                    "field_name": f"{med['concept']}_{med['strength']}{med['unit']}",
                    "normalized_concept": med["concept"],
                    "expected_value": med["strength"],
                    "expected_unit": med["unit"],
                    "reference_interval": None,
                    "date": spec["patient"]["date"],
                    "medication_name": med["name"],
                    "medication_dosage": f"{med['strength']} {med['unit']}",
                    "frequency": med.get("frequency"),
                    "duration": med.get("duration"),
                    "unit_provenance": med.get("prov", "EXPLICIT"),
                    "confirmation_status": "UNCONFIRMED"
                })
        elif "pages" in spec:
            for p_info in spec["pages"]:
                p_num = p_info["page_num"]
                for r in p_info["rows"]:
                    expected_fields.append({
                        "field_name": r["name"],
                        "page_number": p_num,
                        "normalized_concept": r["concept"],
                        "expected_value": r["val"],
                        "expected_unit": r["unit"],
                        "reference_interval": r.get("ref"),
                        "date": spec["patient"]["date"],
                        "medication_name": None,
                        "medication_dosage": None,
                        "frequency": None,
                        "duration": None,
                        "unit_provenance": r.get("prov", "EXPLICIT"),
                        "confirmation_status": "UNCONFIRMED"
                    })
        else:
            for r in spec["rows"]:
                exp_unit = r.get("expected_normalized_unit", r.get("expected_inferred_unit", r["unit"]))
                expected_fields.append({
                    "field_name": r["name"],
                    "page_number": 1,
                    "normalized_concept": r["concept"],
                    "expected_value": r["val"],
                    "expected_unit": exp_unit,
                    "reference_interval": r.get("ref", r.get("ref_range")),
                    "date": spec["patient"]["date"],
                    "medication_name": None,
                    "medication_dosage": None,
                    "frequency": None,
                    "duration": None,
                    "unit_provenance": r.get("prov", "EXPLICIT"),
                    "confirmation_status": "UNCONFIRMED"
                })

        gt_data = {
            "document_id": doc_id,
            "category": category,
            "filename": filename,
            "file_type": spec["type"],
            "patient_id": spec["patient"]["id"],
            "patient_name": spec["patient"]["name"],
            "collection_date": spec["patient"]["date"],
            "page_count": pages_count,
            "expected_raw_texts": page_texts,
            "expected_fields": expected_fields
        }

        with open(gt_path, "w", encoding="utf-8") as f:
            json.dump(gt_data, f, indent=2)

        manifest_records.append({
            "document_id": doc_id,
            "category": category,
            "filename": filename,
            "file_type": spec["type"],
            "page_count": pages_count,
            "field_count": len(expected_fields),
            "file_path": str(doc_path.relative_to(BASE_DIR)),
            "ground_truth_path": str(gt_path.relative_to(BASE_DIR))
        })

    # Write Manifest
    manifest_summary = {
        "dataset_name": "MedResolve Phase 5.5 OCR Benchmark Dataset",
        "total_documents": len(manifest_records),
        "total_fields": sum(r["field_count"] for r in manifest_records),
        "categories": {
            "digital_lab_pdf": len([r for r in manifest_records if r["category"] == "digital_lab_pdf"]),
            "clean_scanned_lab": len([r for r in manifest_records if r["category"] == "clean_scanned_lab"]),
            "scanned_prescription": len([r for r in manifest_records if r["category"] == "scanned_prescription"]),
            "noisy_scan": len([r for r in manifest_records if r["category"] == "noisy_scan"]),
            "skewed_document": len([r for r in manifest_records if r["category"] == "skewed_document"]),
            "medical_table": len([r for r in manifest_records if r["category"] == "medical_table"]),
            "ambiguous_or_missing_unit": len([r for r in manifest_records if r["category"] == "ambiguous_or_missing_unit"])
        },
        "documents": manifest_records
    }

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest_summary, f, indent=2)

    print(f"Dataset generation complete!")
    print(f"Documents: {manifest_summary['total_documents']} across {len(manifest_summary['categories'])} categories.")
    print(f"Manifest saved to: {MANIFEST_PATH}")


if __name__ == "__main__":
    generate_dataset()
