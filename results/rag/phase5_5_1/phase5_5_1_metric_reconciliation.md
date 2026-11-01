# MedResolve — Phase 5.5.1 Metric Reconciliation & Accounting Audit

**Phase Identifier:** Phase 5.5.1  
**Audit Date:** October 31, 2026  
**Audited Artifacts:** `results/rag/phase5_5/` vs `results/rag/phase5_5_1/`  
**Classification:** Scientific Benchmark Integrity Audit  

---

## 1. Ground-Truth Field Count Reconciliation (Task 1)

In the Phase 5.5 report (`docs/phase5_5_results.md`), the summary rows in the text table did not match the arithmetic sum of the individual category rows. This discrepancy was audited against original machine-readable ground-truth files (`data/processed/phase5_5_ocr/ground_truth/*.json`) and per-document extraction records.

### Root Cause Analysis:
1. **Typographical & Drafting Discrepancies:** The category rows in the markdown table of `docs/phase5_5_results.md` were manually entered from an intermediate drafting run:
   - `scanned_prescription`: Listed in markdown table with 13 expected fields; actual ground truth is 11 fields (the author confused total medications [13 across all categories] with prescription category fields).
   - `noisy_scan`: Listed with 12 expected fields; actual ground truth is 9 fields.
   - `digital_lab_pdf`: Listed with 38 extracted / 6 FP; actual is 37 extracted / 5 FP.
   - `skewed_document`: Listed with 4 TP / 2 FP / 5 FN; actual is 5 TP / 1 FP / 4 FN.
   - `medical_table`: Listed with 15 extracted / 1 FP; actual is 17 extracted / 3 FP.
2. **Multi-Page Document Status:** `DOC_DIG_LAB_09` and `DOC_DIG_LAB_10` (2 multi-page documents, 2 pages each) were treated in some notes as an additional subset, but they are strictly an **overlapping subset within `digital_lab_pdf`** (accounting for 11 of the 38 fields in that category), not an 8th mutually exclusive category.
3. **Machine-Readable Truth:** The machine-readable JSON files (`ocr_ground_truth_manifest.json` and `ocr_field_extraction_results.json`) were internally consistent and summed exactly to 116 expected fields.

### Reconciled Micro-Averaged Field Count Table:

| Category | Documents | Expected Fields | Extracted Fields | True Positives (TP) | False Positives (FP) | False Negatives (FN) | Precision | Recall | F1 Score | Exact Value Match |
| :--- | :---:| :---:| :---:| :---:| :---:| :---:| :---:| :---:| :---:| :---:|
| `digital_lab_pdf` | 10 | 38 | 37 | 32 | 5 | 6 | 0.8649 | 0.8421 | 0.8533 | 84.21% (32/38) |
| `clean_scanned_lab` | 10 | 26 | 26 | 20 | 6 | 6 | 0.7692 | 0.7692 | 0.7692 | 76.92% (20/26) |
| `scanned_prescription` | 10 | 11 | 11 | 11 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 100.0% (11/11) |
| `noisy_scan` | 5 | 9 | 6 | 6 | 0 | 3 | 1.0000 | 0.6667 | 0.8000 | 66.67% (6/9) |
| `skewed_document` | 5 | 9 | 6 | 5 | 1 | 4 | 0.8333 | 0.5556 | 0.6667 | 33.33% (3/9) |
| `medical_table` | 5 | 18 | 17 | 14 | 3 | 4 | 0.8235 | 0.7778 | 0.8000 | 77.78% (14/18) |
| `ambiguous_or_missing_unit`| 5 | 5 | 5 | 3 | 2 | 2 | 0.6000 | 0.6000 | 0.6000 | 60.00% (3/5) |
| **Reconciled Overall Sum** | **50** | **116** | **108** | **91** | **17** | **25** | **0.8426** | **0.7845** | **0.8125** | **76.72% (89/116)** |
| *Multi-Page Subset* | 2 | 11 | 11 | 9 | 2 | 2 | 0.8182 | 0.8182 | 0.8182 | 81.82% (9/11) |

*Multi-page documents (`DOC_DIG_LAB_09`, `DOC_DIG_LAB_10`) are an overlapping subset of `digital_lab_pdf` and are not double-counted.*

### Macro-Averaged Metrics:
- **Macro-Precision by Category:** 0.8416
- **Macro-Recall by Category:** 0.7445
- **Macro-F1 by Category:** 0.7842
- **Macro-Precision by Document:** 0.8227
- **Macro-Recall by Document:** 0.7760
- **Macro-F1 by Document:** 0.7920

---

## 2. CER and WER Boundary Reconciliation (Task 2)

### Why CER and WER Exceeded 1.0 in Phase 5.5:
In Phase 5.5, the ground truth reference body was constructed with only test rows (~150 characters), whereas the visual documents included facility header banners, patient demographics, reference ranges, and disclaimers (~500 characters). Because RapidOCR and PyMuPDF transcribed all visible page text, the Levenshtein edit distance counted the extra ~350 characters as **insertions**.
$$\text{CER} = \frac{\text{Insertions} + \text{Deletions} + \text{Substitutions}}{\text{Reference Characters}} = \frac{350 + \dots}{150} \approx 2.12$$
**CER and WER are Levenshtein edit ratios relative to reference length. They are NOT accuracy percentages.**

### Evaluation under Defensible Boundary Approaches:

| Boundary Approach | Methodology Description | Total Ref Chars | Total Char Edits | Recomputed CER | Total Ref Words | Total Word Edits | Recomputed WER |
| :--- | :--- | :---:| :---:| :---:| :---:| :---:| :---:|
| **Reconciled Approach A** | Full visible page text (header, demographics, test rows, ref ranges, footer) | **20,288** | **1,191** | **0.0587** | **3,098** | **1,034** | **0.3338** |
| **Phase 5.5 Baseline** | Body-only snippet vs full-page OCR output (boundary mismatch) | 6,395 | 13,586 | 2.1245 | 862 | 1,862 | 2.1601 |

---

## 3. Held-Out Document Partition Evaluation (Task 3)

The 50 benchmark documents were partitioned into three fixed disjoint sets with random seed 42, stratified across all 7 categories:

| Partition | Documents | Expected Fields | True Positives | Precision | Recall | F1 Score | Exact Value Match | Approach A CER |
| :--- | :---:| :---:| :---:| :---:| :---:| :---:| :---:| :---:|
| **Development** | 30 | 70 | 55 | 0.8594 | 0.7857 | 0.8209 | 77.14% | 0.0606 |
| **Validation** | 10 | 22 | 15 | 0.7143 | 0.6818 | 0.6977 | 63.64% | 0.0638 |
| **Held-Out Test** | 10 | 24 | 21 | 0.9130 | 0.8750 | 0.8936 | 87.50% | 0.0486 |

*Extraction rules were strictly frozen prior to evaluating the held-out test partition.*

---

## 4. OCR Confidence Re-Analysis (Task 4)

- **Superseded Term:** "Calibration Gap"
- **Correct Reproducible Term:** `Confidence Separation Between Correct and Incorrect Detections`
- **Correction Made:** Removed artificial 0.0 confidence imputation for false negatives (missed fields). Missed fields have no bounding box and are treated as missing observations (`None`).

### Optical Confidence Separation:
- **Mean Optical Confidence for Correct Extractions (n = 89):** 0.9787
- **Mean Optical Confidence for Incorrect / False Positive Extractions (n = 19):** 0.9808
- **Confidence Separation:** **+-0.0021**

### Reliability Bins (Observed Transcription Accuracy):
- **Bin [0.50, 0.70):** n = 0, Mean Optical Conf = 0.0000, Observed Value Accuracy = 0.00%
- **Bin [0.70, 0.85):** n = 0, Mean Optical Conf = 0.0000, Observed Value Accuracy = 0.00%
- **Bin [0.85, 0.95):** n = 17, Mean Optical Conf = 0.9216, Observed Value Accuracy = 88.24%
- **Bin [0.95, 1.00]:** n = 91, Mean Optical Conf = 0.9898, Observed Value Accuracy = 81.32%

---

## 5. Security & Boundary Scope Audit (Task 7)

- **Patient-ID Consistency:** Confirmed that `GET /api/documents/{patient_id}/{doc_id}` enforces document-to-patient binding (returns HTTP 404 on cross-patient access).
- **Authentication Scope:** Differentiated internal patient-ID binding from real enterprise user authentication. MedResolve remains a local academic demonstration without multi-user authentication.
- **Upload Hardening:** Malformed uploads return controlled HTTP 400 Bad Request errors with zero stack trace or internal path leakage.
