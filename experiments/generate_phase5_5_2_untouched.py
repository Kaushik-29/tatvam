"""
MedResolve — Phase 5.5.2
Independent Untouched Held-Out Test Set Generator

Generates 10 brand-new, genuinely untouched synthetic medical documents
with zero prior exposure to Phase 5.4, 5.5, or 5.5.1 development or testing.
Uses independent healthcare facility names, novel fictional patients, distinct
timestamps, and diverse clinical test rows.

Outputs:
- data/processed/phase5_5_2_untouched/{filename}
- data/processed/phase5_5_2_untouched/ground_truth/{doc_id}.json
"""

import json
import math
import os
from pathlib import Path
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import fitz  # PyMuPDF

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DOCS_DIR = BASE_DIR / "data" / "processed" / "phase5_5_2_untouched"
OUTPUT_GT_DIR = OUTPUT_DOCS_DIR / "ground_truth"

OUTPUT_DOCS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_GT_DIR.mkdir(parents=True, exist_ok=True)

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
# Rendering Functions
# ==============================================================================

def create_digital_pdf(doc_id, pages_data, output_path):
    """Creates a native digital vector PDF with embedded text using PyMuPDF."""
    doc = fitz.open()
    for page_info in pages_data:
        page = doc.new_page(width=595, height=842)  # A4 size
        # Header banner
        page.draw_rect(fitz.Rect(40, 40, 555, 90), color=(0.1, 0.25, 0.5), fill=(0.94, 0.96, 0.99))
        page.insert_text(fitz.Point(55, 65), page_info.get("facility", "CITY GENERAL HOSPITAL PATHOLOGY"), fontsize=14, fontname="helv", color=(0.1, 0.25, 0.5))
        page.insert_text(fitz.Point(55, 82), "Accredited Clinical Pathology & Diagnostic Services", fontsize=9, fontname="helv", color=(0.4, 0.4, 0.4))

        # Patient & Doctor Info
        y = 115
        p_info = page_info.get("patient_header", {})
        page.draw_line(fitz.Point(40, 100), fitz.Point(555, 100), color=(0.8, 0.8, 0.8))
        page.insert_text(fitz.Point(40, y), f"Patient: {p_info.get('name', 'Devika Menon')}", fontsize=10, fontname="helv", color=(0.1, 0.1, 0.1))
        page.insert_text(fitz.Point(300, y), f"Patient ID: {p_info.get('id', 'SYNTH-U101')}", fontsize=10, fontname="helv", color=(0.1, 0.1, 0.1))
        y += 18
        page.insert_text(fitz.Point(40, y), f"Age/Sex: {p_info.get('age_sex', '47 Y / F')}", fontsize=10, fontname="helv", color=(0.1, 0.1, 0.1))
        page.insert_text(fitz.Point(300, y), f"Date of Collection: {p_info.get('date', '2026-04-02')}", fontsize=10, fontname="helv", color=(0.1, 0.1, 0.1))
        y += 18
        page.insert_text(fitz.Point(40, y), f"Ref. Doctor: {p_info.get('doctor', 'Dr. M. S. Varma, MD')}", fontsize=10, fontname="helv", color=(0.1, 0.1, 0.1))
        page.insert_text(fitz.Point(300, y), f"Status: Final Approved Report", fontsize=10, fontname="helv", color=(0.1, 0.5, 0.2))

        y += 25
        page.draw_line(fitz.Point(40, y), fitz.Point(555, y), color=(0.2, 0.3, 0.6), width=1.5)
        y += 20

        # Section Header
        page.insert_text(fitz.Point(40, y), page_info.get("section_title", "METABOLIC INVESTIGATION PANEL"), fontsize=11, fontname="helv", color=(0.1, 0.2, 0.5))
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
    """Creates a native PDF containing formal medical tables with grid lines and columns."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    # Title
    page.draw_rect(fitz.Rect(40, 40, 555, 85), color=(0.15, 0.3, 0.5), fill=(0.95, 0.97, 1.0))
    page.insert_text(fitz.Point(50, 65), table_data.get("facility", "NATIONAL REFERENCE LABORATORY"), fontsize=14, fontname="helv", color=(0.1, 0.25, 0.5))
    page.insert_text(fitz.Point(50, 78), "Department of Clinical Biochemistry", fontsize=9, fontname="helv", color=(0.4, 0.4, 0.4))

    # Patient info
    y = 110
    p = table_data.get("patient_header", {})
    page.insert_text(fitz.Point(40, y), f"Patient Name: {p.get('name', 'Bipin Chandra')}", fontsize=10, fontname="helv")
    page.insert_text(fitz.Point(320, y), f"Sample ID: {p.get('id', 'SYNTH-U109')}", fontsize=10, fontname="helv")
    y += 18
    page.insert_text(fitz.Point(40, y), f"Date of Collection: {p.get('date', '2026-04-14')}", fontsize=10, fontname="helv")
    page.insert_text(fitz.Point(320, y), f"Doctor: {p.get('doctor', 'Dr. A. K. Mitra, MD')}", fontsize=10, fontname="helv")
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
    """Renders a realistic scanned document (report or prescription) as a PNG."""
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
    facility = image_data.get("facility", "SUNRISE DIAGNOSTIC SERVICES")
    draw.text((80, 70), facility, fill=(20, 45, 90), font=f_title)
    draw.text((80, 115), image_data.get("subtitle", "Clinical Diagnostic & Outpatient Services"), fill=(90, 90, 90), font=f_sub)
    draw.line([(80, 155), (1120, 155)], fill=(180, 180, 180), width=2)

    # Patient details
    p = image_data.get("patient_header", {})
    y = 175
    draw.text((80, y), f"Patient: {p.get('name', 'Patient')}", fill=(30, 30, 30), font=f_body)
    draw.text((650, y), f"Patient ID: {p.get('id', 'SYNTH-U100')}", fill=(30, 30, 30), font=f_body)
    y += 35
    draw.text((80, y), f"Age / Gender: {p.get('age_sex', '48 Y / F')}", fill=(30, 30, 30), font=f_body)
    draw.text((650, y), f"Date: {p.get('date', '2026-04-06')}", fill=(30, 30, 30), font=f_body)
    y += 35
    draw.text((80, y), f"Doctor: {p.get('doctor', 'Dr. N. K. Pillai, MD')}", fill=(30, 30, 30), font=f_body)
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

    if noise_level > 0:
        pixels = img.load()
        for _ in range(int(noise_level * 5000)):
            rx = random.randint(0, width - 1)
            ry = random.randint(0, height - 1)
            val = random.randint(0, 255)
            pixels[rx, ry] = (val, val, val)
        if noise_level >= 2:
            img = img.filter(ImageFilter.GaussianBlur(radius=0.7))

    if skew_angle != 0:
        img = img.rotate(skew_angle, expand=True, fillcolor=(255, 255, 255))

    img.save(str(output_path), "PNG")


# ==============================================================================
# 10 Brand-New Untouched Document Specifications
# ==============================================================================

UNTOUCHED_DOCS_SPEC = [
    # 1. Digital Lab PDF: Metabolic Investigation Panel
    {
        "id": "DOC_UNTOUCHED_01",
        "category": "digital_lab_pdf",
        "filename": "DOC_UNTOUCHED_01.pdf",
        "type": "pdf",
        "facility": "CITY GENERAL HOSPITAL PATHOLOGY",
        "patient": {"name": "Devika Menon", "id": "SYNTH-U101", "age_sex": "47 Y / F", "date": "2026-04-02", "doctor": "Dr. M. S. Varma, MD"},
        "pages": [{
            "page_num": 1,
            "title": "METABOLIC INVESTIGATION PANEL",
            "rows": [
                {"name": "Fasting Blood Glucose", "val": 108.0, "unit": "mg/dL", "ref": "70 - 99 mg/dL", "concept": "glucose", "prov": "EXPLICIT"},
                {"name": "Glycated Hemoglobin HbA1c", "val": 6.5, "unit": "%", "ref": "4.0 - 5.6 %", "concept": "hba1c", "prov": "EXPLICIT"},
                {"name": "Serum Creatinine", "val": 1.1, "unit": "mg/dL", "ref": "0.6 - 1.2 mg/dL", "concept": "creatinine", "prov": "EXPLICIT"},
                {"name": "Blood Urea Nitrogen (BUN)", "val": 18.0, "unit": "mg/dL", "ref": "7 - 20 mg/dL", "concept": "bun", "prov": "EXPLICIT"}
            ]
        }]
    },
    # 2. Digital Lab PDF: 2-Page Multi-Page Comprehensive Panel
    {
        "id": "DOC_UNTOUCHED_02",
        "category": "digital_lab_pdf",
        "filename": "DOC_UNTOUCHED_02.pdf",
        "type": "pdf",
        "facility": "MAXCARE DIAGNOSTIC INSTITUTE",
        "patient": {"name": "Farhan Qureshi", "id": "SYNTH-U102", "age_sex": "54 Y / M", "date": "2026-04-05", "doctor": "Dr. S. K. Roy, MD"},
        "pages": [
            {
                "page_num": 1,
                "title": "LIPID PROFILE REPORT",
                "rows": [
                    {"name": "Total Cholesterol", "val": 230.0, "unit": "mg/dL", "ref": "< 200 mg/dL", "concept": "cholesterol", "prov": "EXPLICIT"},
                    {"name": "Serum Triglycerides", "val": 175.0, "unit": "mg/dL", "ref": "< 150 mg/dL", "concept": "triglycerides", "prov": "EXPLICIT"},
                    {"name": "HDL Cholesterol", "val": 39.0, "unit": "mg/dL", "ref": "> 40 mg/dL", "concept": "hdl", "prov": "EXPLICIT"}
                ]
            },
            {
                "page_num": 2,
                "title": "SERUM ELECTROLYTES",
                "rows": [
                    {"name": "Serum Sodium", "val": 139.0, "unit": "mEq/L", "ref": "135 - 145", "concept": "sodium", "prov": "EXPLICIT"},
                    {"name": "Serum Potassium", "val": 4.8, "unit": "mEq/L", "ref": "3.5 - 5.0", "concept": "potassium", "prov": "EXPLICIT"},
                    {"name": "Serum Creatinine", "val": 1.3, "unit": "mg/dL", "ref": "0.6 - 1.2", "concept": "creatinine", "prov": "EXPLICIT"}
                ]
            }
        ]
    },
    # 3. Clean Scanned Lab: Lipid Panel
    {
        "id": "DOC_UNTOUCHED_03",
        "category": "clean_scanned_lab",
        "filename": "DOC_UNTOUCHED_03.png",
        "type": "png",
        "facility": "SUNRISE DIAGNOSTIC SERVICES",
        "patient": {"name": "Sunita Rao", "id": "SYNTH-U103", "age_sex": "50 Y / F", "date": "2026-04-06", "doctor": "Dr. N. K. Pillai, MD"},
        "section_title": "LIPID PANEL INVESTIGATION",
        "rows": [
            {"test_name": "Total Cholesterol", "value": 215.0, "unit": "mg/dL", "ref_range": "< 200 mg/dL", "concept": "cholesterol", "prov": "EXPLICIT"},
            {"test_name": "Serum Triglycerides", "value": 160.0, "unit": "mg/dL", "ref_range": "< 150 mg/dL", "concept": "triglycerides", "prov": "EXPLICIT"},
            {"test_name": "HDL Cholesterol", "value": 42.0, "unit": "mg/dL", "ref_range": "> 40 mg/dL", "concept": "hdl", "prov": "EXPLICIT"},
            {"test_name": "LDL Cholesterol", "value": 141.0, "unit": "mg/dL", "ref_range": "< 100 mg/dL", "concept": "ldl", "prov": "EXPLICIT"}
        ]
    },
    # 4. Clean Scanned Lab: Hematology CBC
    {
        "id": "DOC_UNTOUCHED_04",
        "category": "clean_scanned_lab",
        "filename": "DOC_UNTOUCHED_04.png",
        "type": "png",
        "facility": "HORIZON CLINICAL LABORATORIES",
        "patient": {"name": "Vikram Malhotra", "id": "SYNTH-U104", "age_sex": "39 Y / M", "date": "2026-04-08", "doctor": "Dr. T. Aggarwal, MD"},
        "section_title": "HEMATOLOGY INVESTIGATION REPORT",
        "rows": [
            {"test_name": "Hemoglobin", "value": 13.8, "unit": "g/dL", "ref_range": "13.0 - 17.0 g/dL", "concept": "hemoglobin", "prov": "EXPLICIT"},
            {"test_name": "Total Leucocyte Count (WBC)", "value": 7200, "unit": "cells/mcL", "ref_range": "4000 - 11000", "concept": "wbc", "prov": "EXPLICIT"},
            {"test_name": "Platelet Count", "value": 240000, "unit": "cells/mcL", "ref_range": "150000 - 450000", "concept": "platelets", "prov": "EXPLICIT"}
        ]
    },
    # 5. Scanned Prescription: Amlodipine
    {
        "id": "DOC_UNTOUCHED_05",
        "category": "scanned_prescription",
        "filename": "DOC_UNTOUCHED_05.png",
        "type": "png",
        "facility": "DR. S. SEN MEMORIAL CLINIC",
        "doc_type": "prescription",
        "patient": {"name": "Geeta Verma", "id": "SYNTH-U105", "age_sex": "62 Y / F", "date": "2026-04-09", "doctor": "Dr. S. Sen, MD"},
        "medications": [
            {"name": "Amlodipine", "strength": 5.0, "unit": "mg", "frequency": "OD", "duration": "30 days", "concept": "amlodipine", "prov": "EXPLICIT"}
        ]
    },
    # 6. Scanned Prescription: Metoprolol
    {
        "id": "DOC_UNTOUCHED_06",
        "category": "scanned_prescription",
        "filename": "DOC_UNTOUCHED_06.png",
        "type": "png",
        "facility": "APOLLO CARDIOLOGY CLINIC",
        "doc_type": "prescription",
        "patient": {"name": "Harish Iyer", "id": "SYNTH-U106", "age_sex": "58 Y / M", "date": "2026-04-10", "doctor": "Dr. V. Ramanathan, DM"},
        "medications": [
            {"name": "Metoprolol", "strength": 25.0, "unit": "mg", "frequency": "BD", "duration": "60 days", "concept": "metoprolol", "prov": "EXPLICIT"}
        ]
    },
    # 7. Noisy Scan: Liver Function Panel (Noise level = 2)
    {
        "id": "DOC_UNTOUCHED_07",
        "category": "noisy_scan",
        "filename": "DOC_UNTOUCHED_07.png",
        "type": "png",
        "noise_level": 2,
        "facility": "RURAL COMMUNITY HEALTH CENTER",
        "patient": {"name": "Mohan Lal", "id": "SYNTH-U107", "age_sex": "44 Y / M", "date": "2026-04-11", "doctor": "Dr. R. P. Singh, MBBS"},
        "section_title": "LIVER BIOCHEMISTRY PANEL",
        "rows": [
            {"test_name": "Alanine Aminotransferase (ALT)", "value": 45.0, "unit": "U/L", "ref_range": "7 - 56 U/L", "concept": "alt", "prov": "EXPLICIT"},
            {"test_name": "Aspartate Aminotransferase (AST)", "value": 38.0, "unit": "U/L", "ref_range": "10 - 40 U/L", "concept": "ast", "prov": "EXPLICIT"}
        ]
    },
    # 8. Skewed Document: Glycemic Control (Skew = -3.5 deg)
    {
        "id": "DOC_UNTOUCHED_08",
        "category": "skewed_document",
        "filename": "DOC_UNTOUCHED_08.png",
        "type": "png",
        "skew_angle": -3.5,
        "facility": "SUBURBAN HEALTH DISPENSARY",
        "patient": {"name": "Ananya Bose", "id": "SYNTH-U108", "age_sex": "36 Y / F", "date": "2026-04-12", "doctor": "Dr. K. G. Bannerjee, MD"},
        "section_title": "DIABETES MONITORING REPORT",
        "rows": [
            {"test_name": "Fasting Blood Glucose", "value": 135.0, "unit": "mg/dL", "ref_range": "70 - 99 mg/dL", "concept": "glucose", "prov": "EXPLICIT"},
            {"test_name": "Glycated Hemoglobin HbA1c", "value": 7.4, "unit": "%", "ref_range": "4.0 - 5.6 %", "concept": "hba1c", "prov": "EXPLICIT"}
        ]
    },
    # 9. Medical Table PDF: Formal Biochemistry Grid
    {
        "id": "DOC_UNTOUCHED_09",
        "category": "medical_table",
        "filename": "DOC_UNTOUCHED_09.pdf",
        "type": "pdf",
        "facility": "NATIONAL REFERENCE LABORATORY",
        "patient": {"name": "Bipin Chandra", "id": "SYNTH-U109", "age_sex": "59 Y / M", "date": "2026-04-14", "doctor": "Dr. A. K. Mitra, MD"},
        "rows": [
            {"test_name": "Fasting Blood Glucose", "value": 110.0, "unit": "mg/dL", "ref_range": "70 - 99", "concept": "glucose", "prov": "EXPLICIT"},
            {"test_name": "Serum Creatinine", "value": 1.2, "unit": "mg/dL", "ref_range": "0.6 - 1.2", "concept": "creatinine", "prov": "EXPLICIT"},
            {"test_name": "Blood Urea Nitrogen (BUN)", "value": 21.0, "unit": "mg/dL", "ref_range": "7 - 20", "concept": "bun", "prov": "EXPLICIT"}
        ]
    },
    # 10. Ambiguous / Missing Unit Document: Potassium
    {
        "id": "DOC_UNTOUCHED_10",
        "category": "ambiguous_or_missing_unit",
        "filename": "DOC_UNTOUCHED_10.png",
        "type": "png",
        "facility": "LEGACY HEALTH OUTPOST",
        "patient": {"name": "Meera Sen", "id": "SYNTH-U110", "age_sex": "65 Y / F", "date": "2026-04-15", "doctor": "Dr. P. Sen, MBBS"},
        "section_title": "LABORATORY INQUIRY SLIP",
        "rows": [
            {"test_name": "Serum Potassium", "value": 4.2, "unit": "", "ref_range": "Normal", "concept": "potassium", "prov": "MISSING"}
        ]
    }
]


def generate_all_untouched():
    print(f"Generating {len(UNTOUCHED_DOCS_SPEC)} brand-new untouched held-out documents...")

    for spec in UNTOUCHED_DOCS_SPEC:
        doc_id = spec["id"]
        filename = spec["filename"]
        doc_type = spec["type"]
        out_path = OUTPUT_DOCS_DIR / filename
        gt_path = OUTPUT_GT_DIR / f"{doc_id}.json"

        # 1. Render Document
        if doc_type == "pdf":
            if spec.get("category") == "medical_table":
                create_table_pdf(doc_id, {
                    "facility": spec["facility"],
                    "patient_header": spec["patient"],
                    "rows": spec["rows"]
                }, out_path)
            else:
                pages_data = []
                for pg in spec["pages"]:
                    pages_data.append({
                        "facility": spec["facility"],
                        "patient_header": spec["patient"],
                        "section_title": pg["title"],
                        "rows": [{"test_name": r["name"], "value": r["val"], "unit": r["unit"], "ref_range": r.get("ref")} for r in pg["rows"]]
                    })
                create_digital_pdf(doc_id, pages_data, out_path)
        else:
            img_data = {
                "facility": spec["facility"],
                "subtitle": "Clinical Diagnostic & Outpatient Services",
                "patient_header": spec["patient"],
                "section_title": spec.get("section_title", "INVESTIGATION RESULTS"),
                "doc_type": spec.get("doc_type", "report"),
            }
            if spec.get("doc_type") == "prescription":
                img_data["medications"] = spec["medications"]
            else:
                img_data["rows"] = spec["rows"]

            create_scanned_image(
                doc_id,
                img_data,
                out_path,
                noise_level=spec.get("noise_level", 0),
                skew_angle=spec.get("skew_angle", 0)
            )

        # 2. Build Independent Ground Truth Reference Text (WITHOUT fitz.get_text!)
        ref_lines = []
        p = spec["patient"]
        ref_lines.append(spec["facility"])
        if doc_type == "pdf" and spec.get("category") == "medical_table":
            ref_lines.append("Department of Clinical Biochemistry")
            ref_lines.append(f"Patient Name: {p['name']}")
            ref_lines.append(f"Sample ID: {p['id']}")
            ref_lines.append(f"Date of Collection: {p['date']}")
            ref_lines.append(f"Doctor: {p['doctor']}")
            ref_lines.append("TEST INVESTIGATION OBSERVED VALUE UNIT REFERENCE RANGE")
            for r in spec["rows"]:
                ref_lines.append(f"{r['test_name']} {r['value']} {r['unit']} {r.get('ref_range', '-')}")
            ref_lines.append("End of report. All laboratory assays calibrated against standard reference serums.")
        elif doc_type == "pdf":
            ref_lines.append("Accredited Clinical Pathology & Diagnostic Services")
            ref_lines.append(f"Patient: {p['name']}")
            ref_lines.append(f"Patient ID: {p['id']}")
            ref_lines.append(f"Age/Sex: {p['age_sex']}")
            ref_lines.append(f"Date of Collection: {p['date']}")
            ref_lines.append(f"Ref. Doctor: {p['doctor']}")
            ref_lines.append("Status: Final Approved Report")
            for pg_idx, pg in enumerate(spec["pages"], 1):
                ref_lines.append(pg["title"])
                for r in pg["rows"]:
                    ref_lines.append(f"{r['name']} {r['val']} {r['unit']}".strip())
                    if r.get("ref"):
                        ref_lines.append(f"Ref: {r['ref']}")
                ref_lines.append("Electronically verified clinical report. For research demonstration only.")
                ref_lines.append(f"Page {pg_idx} of {len(spec['pages'])}")
        else:
            ref_lines.append("Clinical Diagnostic & Outpatient Services")
            ref_lines.append(f"Patient: {p['name']}")
            ref_lines.append(f"Patient ID: {p['id']}")
            ref_lines.append(f"Age / Gender: {p['age_sex']}")
            ref_lines.append(f"Date: {p['date']}")
            ref_lines.append(f"Doctor: {p['doctor']}")
            ref_lines.append(spec.get("section_title", "INVESTIGATION RESULTS"))
            if spec.get("doc_type") == "prescription":
                ref_lines.append("Rx")
                for med in spec["medications"]:
                    ref_lines.append(f"{med['name']} {med['strength']} {med['unit']}")
                    ref_lines.append(f"Sig: Take {med.get('frequency', 'daily')} for {med.get('duration', '30 days')}")
            else:
                for r in spec["rows"]:
                    ref_lines.append(r["test_name"])
                    ref_lines.append(f"{r['value']} {r['unit']}".strip())
                    if r.get("ref_range"):
                        ref_lines.append(f"Ref: {r['ref_range']}")
            ref_lines.append("Computer generated diagnostic document. Fictional synthetic record.")

        independent_reference_text = " ".join(ref_lines)

        # 3. Build Expected Fields
        expected_fields = []
        if doc_type == "pdf" and spec.get("category") == "digital_lab_pdf":
            for pg in spec["pages"]:
                for r in pg["rows"]:
                    expected_fields.append({
                        "field_name": r["name"],
                        "page_number": pg["page_num"],
                        "normalized_concept": r["concept"],
                        "expected_value": r["val"],
                        "expected_unit": r["unit"],
                        "reference_interval": r.get("ref"),
                        "date": p["date"],
                        "medication_name": None,
                        "unit_provenance": r["prov"],
                    })
        elif doc_type == "pdf" and spec.get("category") == "medical_table":
            for r in spec["rows"]:
                expected_fields.append({
                    "field_name": r["test_name"],
                    "page_number": 1,
                    "normalized_concept": r["concept"],
                    "expected_value": r["value"],
                    "expected_unit": r["unit"],
                    "reference_interval": r.get("ref_range"),
                    "date": p["date"],
                    "medication_name": None,
                    "unit_provenance": r["prov"],
                })
        elif spec.get("doc_type") == "prescription":
            for med in spec["medications"]:
                expected_fields.append({
                    "field_name": f"{med['concept']}_{med['strength']}{med['unit']}",
                    "page_number": 1,
                    "normalized_concept": med["concept"],
                    "expected_value": med["strength"],
                    "expected_unit": med["unit"],
                    "reference_interval": None,
                    "date": p["date"],
                    "medication_name": med["name"],
                    "frequency": med["frequency"],
                    "duration": med["duration"],
                    "unit_provenance": med["prov"],
                })
        else:
            for r in spec["rows"]:
                expected_fields.append({
                    "field_name": r["test_name"],
                    "page_number": 1,
                    "normalized_concept": r["concept"],
                    "expected_value": r["value"],
                    "expected_unit": r["unit"] if r["unit"] else None,
                    "reference_interval": r.get("ref_range"),
                    "date": p["date"],
                    "medication_name": None,
                    "unit_provenance": r["prov"],
                })

        gt_record = {
            "document_id": doc_id,
            "category": spec["category"],
            "filename": filename,
            "file_type": doc_type,
            "page_count": len(spec.get("pages", [1])),
            "patient_id": p["id"],
            "patient_name": p["name"],
            "collection_date": p["date"],
            "facility": spec["facility"],
            "reference_generation_method": "INDEPENDENT_INTENDED_DOCUMENT_SPECIFICATION",
            "independent_reference_text": independent_reference_text,
            "expected_fields": expected_fields,
            "total_expected_fields": len(expected_fields),
        }

        with open(gt_path, "w", encoding="utf-8") as f:
            json.dump(gt_record, f, indent=2)

        print(f"  Generated {doc_id} ({spec['category']}) -> {out_path.name} with {len(expected_fields)} fields.")

    print(f"All 10 untouched held-out documents successfully generated under: {OUTPUT_DOCS_DIR}")


if __name__ == "__main__":
    generate_all_untouched()
