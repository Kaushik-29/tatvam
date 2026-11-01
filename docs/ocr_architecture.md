# MedResolve — Optical Character Recognition (OCR) Architecture

**Document Version:** 1.0.0 (Phase 5.4)  
**Module Identifier:** `backend.ocr_service.MedicalDocumentProcessor`  
**Execution Platform:** CPU-Only Execution, Python 3.11, Open-Source ONNX Runtime  

---

## 1. Architectural Overview

MedResolve replaces simulated document extraction with a genuine, CPU-compatible, open-source document ingestion and clinical information extraction pipeline.

The architecture employs a **dual-path extraction strategy**:
1. **Direct Digital Text Extraction (PyMuPDF):** When a PDF contains native digital text streams, PyMuPDF directly extracts character sequences, line structures, and font metadata. This path bypasses image rendering, token prediction, and neural inference, achieving sub-20ms latency.
2. **Optical Character Recognition (RapidOCR via ONNX Runtime):** When dealing with scanned PDF pages, photographs of paper prescriptions, or clinical report image files (`.png`, `.jpg`, `.jpeg`), the system renders pages at 200 DPI and invokes RapidOCR's lightweight deep learning models executed on CPU via ONNX Runtime.

```
                    +------------------------------------+
                    |        Uploaded Document           |
                    |   (PDF, PNG, JPG, JPEG, TXT)       |
                    +-----------------+------------------+
                                      |
                         [Security & Magic Bytes]
                                      v
                    +-----------------+------------------+
                    | Format & Extension Discrimination  |
                    +--------+------------------+--------+
                             |                  |
                       Is Digital PDF?     Is Image or Scanned?
                             |                  |
                             v                  v
                    +--------+---------+   +----+----------------+
                    | PyMuPDF (fitz)   |   | RapidOCR (ONNX CPU) |
                    | Direct Text Stream|  | Text Detection (DBNet)|
                    | (15–20 ms / page)|   | Text Recognition    |
                    +--------+---------+   | (CRNN / SVTR-LCNet) |
                             |             +----+----------------+
                             |                  |
                             +--------+---------+
                                      |
                                      v
                    +-----------------+------------------+
                    |    Clinical Entity Parser Engine   |
                    |   (Labs, Vitals, Medications)      |
                    +-----------------+------------------+
                                      |
                                      v
                    +-----------------+------------------+
                    | 5-Way Unit Provenance Classifier  |
                    | (EXPLICIT, NORMALIZED, INFERRED,   |
                    |  MISSING, INVALID)                 |
                    +-----------------+------------------+
                                      |
                                      v
                    +-----------------+------------------+
                    | Patient Evidence Ledger Ingestion  |
                    | (Status: UNCONFIRMED, Traceable)   |
                    +------------------------------------+
```

---

## 2. Component Specifications

### 2.1 Optical Character Recognition Engine: RapidOCR
- **Framework:** `rapidocr-onnxruntime` v1.4.4
- **Runtime Environment:** `onnxruntime` CPU provider (x86_64 SIMD AVX2 acceleration)
- **Model Architecture:**
  - **Text Detection:** DBNet (Differentiable Binarization Network) with lightweight MobileNetV3 backbone. Computes probability maps and bounding boxes for text regions.
  - **Direction Classification:** Lightweight CNN for page orientation correction (0°, 90°, 180°, 270°).
  - **Text Recognition:** SVTR-LCNet (Single Visual Model for Text Recognition / Lightweight Convolutional Network) trained for English alphanumeric and medical symbols.
- **Hardware Footprint:** ~85 MB total model weights in memory; peak working set < 250 MB during page batch inference.
- **Operating Constraint:** Fully offline; zero outbound network telemetry; zero proprietary cloud API requirements.

### 2.2 Digital PDF Parsing Engine: PyMuPDF (`fitz`)
- **Version:** `PyMuPDF` v1.25.0+
- **Execution Path:** `doc[page_idx].get_text("text")`
- **Selective OCR Heuristic:**
  ```python
  extracted_text = page.get_text("text").strip()
  if len(extracted_text) >= 30:
      # Direct text stream valid -> bypass OCR
      return process_digital_text(extracted_text)
  else:
      # Scanned image or raster PDF -> render page at 200 DPI and run RapidOCR
      pix = page.get_pixmap(dpi=200)
      img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
      return run_rapid_ocr(img)
  ```

---

## 3. Clinical Entity & Measurement Structuring

The extracted text is parsed into structured clinical observations via deterministic medical entity extractors:

### 3.1 Laboratory Test Extractor
Targets standard hematology, metabolic, and clinical chemistry markers:
- **Hemoglobin (`E_HEMOGLOBIN`):** Regex pattern matching `(?:hemoglobin|hb|hgb)[\s:]*([0-9]+\.?[0-9]*)`
- **Fasting Blood Glucose (`E_BLOOD_GLUCOSE_FASTING`):** Fasting blood sugar, FBS, glucose measurements
- **HbA1c (`E_HBA1C`):** Glycated hemoglobin percentages
- **D-dimer (`E_D_DIMER`):** Venous thromboembolism marker in `mcg/mL` or `ng/mL`
- **Serum Creatinine (`E_SERUM_CREATININE`):** Renal function in `mg/dL` or `umol/L`
- **Platelets (`E_PLATELETS`):** Thrombocyte count in `/mcL` or `k/uL`

### 3.2 Vital Signs Extractor
- **Blood Pressure (`E_VITALS_BP`):** Systolic and diastolic pairs (e.g., `124/82 mmHg`, `210/120 mmHg`)
- **Body Temperature (`E_VITALS_TEMP`):** Oral, axillary, or tympanic temperature
- **Oxygen Saturation (`E_VITALS_SPO2`):** Pulse oximetry percentage
- **Heart Rate (`E_VITALS_HR`):** Beats per minute (bpm)

### 3.3 Prescription & Medication Extractor
- Extracts medication name, dosage strength (`mg`, `mcg`, `g`), formulation (`tablet`, `capsule`), and frequency (`OD`, `BD`, `TID`, `QID`, `as needed`).

---

## 4. 5-Way Unit Provenance Classification

Measurement units undergo rigorous provenance auditing:

| Unit Provenance Code | Classification Rule | Confirmation Invariant | Example |
| :--- | :--- | :--- | :--- |
| `EXPLICIT` | The measurement unit was explicitly printed in the text adjacent to the numeric value. | Follows standard confidence thresholds. | `"14.2 g/dL"` -> `g/dL` (EXPLICIT) |
| `NORMALIZED` | The unit was explicitly printed in an alternate or colloquial spelling and converted to canonical representation. | Follows standard confidence thresholds. | `"gm/dl"` -> `g/dL` (NORMALIZED) |
| `INFERRED` | The unit was completely omitted from the text, but inferred from physiological plausibility bounds. | **Must be flagged with `requires_confirmation = True`**. | `"Temp 104.8"` -> `degF` (INFERRED) |
| `MISSING` | The numeric value was extracted but cannot be matched to any plausible unit range. | **Must be flagged with `requires_confirmation = True`**. | `"Potassium 4.1"` (unit missing) |
| `INVALID` | The extracted unit is nonsensical or physically impossible for the clinical concept. | **Must be flagged with `requires_confirmation = True`**. | `"Heart rate 72 mg"` (INVALID) |

---

## 5. Provenance & Audit Trail Preservation

To ensure full clinical traceability, every observation ingested into the evidence ledger preserves:
1. `source_document_id`: Unique identifier of the uploaded file on disk.
2. `source_page`: Exact page number where the observation occurred.
3. `confidence`: Bounding-box confidence score in `[0.0, 1.0]`.
4. `raw_text`: The unnormalized line text exactly as extracted by OCR.
5. `user_confirmation_status`: Initialized to `UNCONFIRMED`.
6. `notes`: JSON audit metadata containing unit provenance, confirmation triggers, and user edits.

When a clinician or patient modifies an observation in the OCR Review screen:
- The updated value is assigned to `normalized_value`.
- `user_confirmation_status` is transitioned to `CONFIRMED_BY_PATIENT`.
- The audit trail immutably records:
  ```
  User corrected: '<previous_value>' (<prev_unit>) -> '<new_value>' (<new_unit>) [Original raw text: '<raw_text>']. Notes: <user_justification>
  ```
