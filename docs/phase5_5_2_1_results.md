# MedResolve — Phase 5.5.2.1 Results: Final Reporting Reconciliation, Macro/Micro Metric Unification, and Benchmark Freeze

**Evaluation Date:** October 31, 2026  
**Auditor / Methodology:** Automated Reproducibility & Research Integrity Engine (MedResolve Phase 5.5.2.1)  
**Ground Truth Standard:** `Generator-Derived, Engine-Independent Ground Truth`  
**Result Classification:** `Internally reconciled and verified result` (Unseen synthetic-document evaluation only)  
**Extraction Engine Hash (SHA-256):** `38b1deac035263a7d4d20b4b67319f79472219c2b7efdd7a4181989b0fc47a82` (`backend/ocr_service.py`)  
**Evaluation Seed:** `42`  
**Benchmark Status:** **PERMANENTLY FROZEN**  
**Primary Artifacts Directory:** `results/rag/phase5_5_2_1/`  

---

## 1. Executive Summary & Purpose

Phase 5.5.2 resolved circular ground truth in digital PDFs and audited held-out test contamination. Phase 5.5.2.1 executes the final reporting reconciliation and permanent benchmark freeze requested prior to academic manuscript submission:

1. **Standardized Ground Truth Classification:** Strictly adopted the terminology `Generator-Derived, Engine-Independent Ground Truth`. The benchmark explicitly avoids describing synthetic ground truth as "independently human-reviewed" or "clinician-validated."
2. **Template Independence Audit & Benchmark Scope:** Conducted a rigorous 4-dimensional overlap analysis of the 10 held-out documents (`DOC_UNTOUCHED_01`–`10`). While patient data, timestamps, and document IDs have **0.0% overlap** with the historical corpus, the rendering canvas functions and coordinate geometries are shared (100% template overlap). Therefore, template independence is **not established**, and this benchmark is formally designated as an **unseen synthetic-document evaluation only**.
3. **CER/WER Metric Reconciliation:** Reconciled macro means (mean of per-document error rates) with micro aggregates (ratio of total edits to total character/word tokens) across both modalities (**Digital PDF Vector Text Extraction** vs. **Scanned-Image OCR**) across all three cohorts:
   - Historical 50 Documents
   - New 10-Document Test Set
   - Combined 60 Documents
4. **Final Benchmark Manifest v2:** Cryptographically recorded OCR source code, reconciliation scripts, RapidOCR ONNX model weights (`det`, `rec`, `cls`), runtime package versions, individual document checksums, and random seed.
5. **Benchmark Freeze:** Extraction rules and test sets are declared permanently frozen with zero subsequent tuning.

---

## 2. Ground Truth Terminology & Evidentiary Standard

To maintain academic rigor and transparency:
* **Approved Standard:** `Generator-Derived, Engine-Independent Ground Truth`
* **Independence Mechanism:** Reference text is constructed directly from programmatic document specifications (`DOCUMENTS_SPEC` and `UNTOUCHED_DOCS_SPEC`) using Python string templating. It never invokes PyMuPDF, RapidOCR, or any image processing pipeline to generate the reference string.
* **Distinction from External Annotation:**
  - This reference text represents the *intended ground truth* of the document generator.
  - It is **NOT** manual transcription by certified medical record abstractors or independent clinical panels.
  - No claims of real-world clinical certification or EHR-readiness are made from synthetic generation alone.

---

## 3. Held-Out Dataset Overlap & Template Independence Audit

The 10 newly generated documents (`DOC_UNTOUCHED_01` to `DOC_UNTOUCHED_10`) were audited along four distinct dimensions of potential data leakage and similarity against the historical 50 documents:

| Overlap Dimension | Historical Cohort | Held-Out Cohort | Observed Overlap | Overlap Status | Analytical Finding |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **1. Document Identity Overlap** | 50 IDs | 10 IDs | **0 / 10 (0.0%)** | `COMPLETELY_DISJOINT` | Brand-new document identifiers (`DOC_UNTOUCHED_01`..`10`). Zero ID collision. |
| **2. Patient & Clinical Data Overlap** | 50 Patients | 10 Patients | **0 / 10 (0.0%)** | `COMPLETELY_DISJOINT` | Novel fictional patients (`Devika Menon`, `Farhan Qureshi`, etc.), novel facility names (`CITY GENERAL HOSPITAL`), unseen collection dates (April 2026), and distinct clinical analyte row values. |
| **3. Template & Canvas Overlap** | 3 Canvas Types | 3 Canvas Types | **10 / 10 (100.0%)** | `IDENTICAL_CANVAS_CODE` | Both generators invoke the same canvas rendering functions (`create_digital_pdf`, `create_table_pdf`, `create_scanned_image`), with identical banner heights, coordinate anchors, line thicknesses, and typography. |
| **4. Layout & Visual Variation** | Standard | Perturbed | **MODERATE** | `INTRINSIC_VARIATION` | Variations arise from differing row counts, variable text line lengths, skew angles ($\pm 3.5^{\circ}$ to $\pm 4.5^{\circ}$), Gaussian noise, and pagination. |

### Formal Evaluation Declaration
> **BENCHMARK CLASSIFICATION:**  
> Because the underlying canvas rendering primitives, coordinate anchors, and font hierarchies are shared between the historical generator and the held-out generator, **template independence is NOT established**.  
> In accordance with research integrity standards, this evaluation must be strictly described as an **unseen synthetic-document evaluation**, and must **not** be presented as an out-of-distribution or unseen-template benchmark.

---

## 4. CER / WER Reconciliation: Macro vs. Micro Across All Cohorts

In Phase 5.5.2, reporting differences arose because the methodology text highlighted macro means of per-document error rates, while category tables summarized micro corpus-level rates. Below, both metrics are reconciled across all three document cohorts, keeping **Digital PDF Vector Text Extraction** strictly separate from **Scanned-Image OCR**.

*(Note: PyMuPDF digital vector text extraction is text parsing, NOT OCR.)*

### Comprehensive Macro vs. Micro Reconciliation Table
| Document Cohort | Modality / Engine | Document Count | Total Char Edits | Total Char Denom | Micro CER | Macro Mean CER | Total Word Edits | Total Word Denom | Micro WER | Macro Mean WER | Exact Document Matches |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Historical 50 Documents** | **Digital PDF Vector Text** (`PyMuPDF`) | 15 | 471 | 7,737 | **0.0609** (6.09%) | **0.0423** (4.23%) | 68 | 1,208 | **0.0563** (5.63%) | **0.0376** (3.76%) | 13 / 15 (**86.67%**) |
| | **Scanned-Image OCR** (`RapidOCR`) | 35 | 1,122 | 12,157 | **0.0923** (9.23%) | **0.0927** (9.27%) | 1,027 | 1,836 | **0.5594** (55.94%)| **0.5675** (56.75%)| 0 / 35 (0.0%) |
| | *Historical Cohort Total* | *50* | *1,593* | *19,894* | ***0.0801*** *(8.01%)* | ***0.0776*** *(7.76%)* | *1,095* | *3,044* | ***0.3597*** *(35.97%)*| ***0.4086*** *(40.86%)*| *13 / 50 (26.0%)* |
| **New 10-Document Test Set**| **Digital PDF Vector Text** (`PyMuPDF`) | 3 | 238 | 1,707 | **0.1394** (13.94%)| **0.1116** (11.16%)| 35 | 269 | **0.1301** (13.01%)| **0.1042** (10.42%)| 2 / 3 (**66.67%**) |
| | **Scanned-Image OCR** (`RapidOCR`) | 7 | 250 | 2,597 | **0.0963** (9.63%) | **0.0958** (9.58%) | 221 | 393 | **0.5623** (56.23%)| **0.5678** (56.78%)| 0 / 7 (0.0%) |
| | *New 10-Doc Cohort Total* | *10* | *488* | *4,304* | ***0.1134*** *(11.34%)*| ***0.1005*** *(10.05%)*| *256* | *662* | ***0.3867*** *(38.67%)*| ***0.4287*** *(42.87%)*| *2 / 10 (20.0%)* |
| **Combined 60 Documents** | **Digital PDF Vector Text** (`PyMuPDF`) | 18 | 709 | 9,444 | **0.0751** (7.51%) | **0.0538** (5.38%) | 103 | 1,477 | **0.0697** (6.97%) | **0.0487** (4.87%) | 15 / 18 (**83.33%**) |
| | **Scanned-Image OCR** (`RapidOCR`) | 42 | 1,372 | 14,754 | **0.0930** (9.30%) | **0.0933** (9.33%) | 1,248 | 2,229 | **0.5599** (55.99%)| **0.5676** (56.76%)| 0 / 42 (0.0%) |
| | **Grand Combined Total** | **60** | **2,081** | **24,198** | **0.0860** (8.60%) | **0.0814** (8.14%) | **1,351** | **3,706** | **0.3645** (36.45%)| **0.4119** (41.19%)| **15 / 60 (25.0%)** |

### Reconciliation Explanation
- **Digital PDF Vector Text Extraction:**
  - Macro Mean CER across all 18 PDFs is **0.0538** (5.38%), while Micro CER is **0.0751** (7.51%).
  - Macro Mean WER across all 18 PDFs is **0.0487** (4.87%), while Micro WER is **0.0697** (6.97%).
  - The 3 multi-page PDFs (`DOC_DIG_LAB_09`, `DOC_DIG_LAB_10`, and `DOC_UNTOUCHED_02`) carry larger character counts (higher denominator) and slight header concatenation offsets, causing the micro rate to be slightly higher than the macro mean.
  - 15 out of 15 single-page digital PDFs achieved an **exact 100% document match** (CER = 0.0, WER = 0.0).
- **Scanned-Image OCR:**
  - Macro Mean CER is **0.0933** (9.33%) and Micro CER is **0.0930** (9.30%), demonstrating near-perfect alignment between macro and micro rates.
  - Macro Mean WER is **0.5676** (56.76%) and Micro WER is **0.5599** (55.99%).
  - Zero scanned images achieved exact string matches due to bounding-box whitespace variations and unit attachments (`mg/dL` vs. `mg / dL`).

---

## 5. Complete Per-Document Results Inventory

All 60 documents were processed against the Generator-Derived, Engine-Independent Ground Truth. Detailed per-document metrics are recorded in [cer_wer_per_document_reconciled.json](file:///d:/MedResolve/results/rag/phase5_5_2_1/cer_wer_per_document_reconciled.json).

### Representative Sampling Across Cohorts & Categories
| Document ID | Cohort | Category | Modality | Engine | Ref Chars | Char Edits | CER | Ref Words | Word Edits | WER | Exact Match | Latency |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `DOC_DIG_LAB_01` | Historical | Digital Lab PDF | Vector Text | PyMuPDF | 546 | 0 | **0.00%** | 89 | 0 | **0.00%** | TRUE | 29.6 ms |
| `DOC_DIG_LAB_09` | Historical | Digital Lab PDF (2-Page) | Vector Text | PyMuPDF | 792 | 248 | **31.31%** | 122 | 34 | **27.87%** | FALSE | 13.9 ms |
| `DOC_SCN_LAB_01` | Historical | Clean Scanned Lab | Image OCR | RapidOCR | 342 | 14 | **4.09%** | 57 | 20 | **35.09%** | FALSE | 258.9 ms |
| `DOC_RX_01` | Historical | Prescription | Image OCR | RapidOCR | 321 | 20 | **6.23%** | 50 | 28 | **56.00%** | FALSE | 338.4 ms |
| `DOC_NOISY_01` | Historical | Noisy Scan | Image OCR | RapidOCR | 325 | 35 | **10.75%** | 57 | 47 | **82.46%** | FALSE | 357.7 ms |
| `DOC_SKEW_01` | Historical | Skewed Scan ($-3^{\circ}$) | Image OCR | RapidOCR | 349 | 96 | **27.52%** | 56 | 30 | **53.57%** | FALSE | 272.2 ms |
| `DOC_TBL_01` | Historical | Medical Table | Vector Text | PyMuPDF | 550 | 0 | **0.00%** | 81 | 0 | **0.00%** | TRUE | 10.9 ms |
| `DOC_AMB_01` | Historical | Missing Unit Slip | Image OCR | RapidOCR | 293 | 17 | **5.80%** | 42 | 24 | **57.14%** | FALSE | 211.3 ms |
| `DOC_UNTOUCHED_01`| Untouched | Digital Lab PDF | Vector Text | PyMuPDF | 542 | 0 | **0.00%** | 88 | 0 | **0.00%** | TRUE | 10.5 ms |
| `DOC_UNTOUCHED_02`| Untouched | Digital Lab PDF (2-Page) | Vector Text | PyMuPDF | 711 | 238 | **33.47%** | 112 | 35 | **31.25%** | FALSE | 13.2 ms |
| `DOC_UNTOUCHED_03`| Untouched | Clean Scanned Lab | Image OCR | RapidOCR | 418 | 20 | **4.79%** | 71 | 27 | **38.03%** | FALSE | 328.0 ms |
| `DOC_UNTOUCHED_07`| Untouched | Noisy Scan (Noise=2) | Image OCR | RapidOCR | 354 | 38 | **10.74%** | 60 | 54 | **90.00%** | FALSE | 363.3 ms |
| `DOC_UNTOUCHED_08`| Untouched | Skewed Scan ($-3.5^{\circ}$)| Image OCR | RapidOCR | 356 | 99 | **27.82%** | 59 | 32 | **54.24%** | FALSE | 299.7 ms |
| `DOC_UNTOUCHED_09`| Untouched | Medical Table | Vector Text | PyMuPDF | 454 | 0 | **0.00%** | 69 | 0 | **0.00%** | TRUE | 12.1 ms |
| `DOC_UNTOUCHED_10`| Untouched | Missing Unit Slip | Image OCR | RapidOCR | 294 | 21 | **7.14%** | 43 | 29 | **67.44%** | FALSE | 231.8 ms |

---

## 6. Final Benchmark Manifest v2 & Cryptographic Freeze

All software assets, model weights, and document files are locked under permanent SHA-256 cryptographic verification in [final_benchmark_manifest_v2.json](file:///d:/MedResolve/results/rag/phase5_5_2_1/final_benchmark_manifest_v2.json):

```json
{
  "manifest_version": "5.5.2.1_FINAL_FREEZE",
  "freeze_declaration": "OCR Benchmark is hereby permanently FROZEN. Zero further tuning on benchmark corpus.",
  "timestamp_utc": "2026-10-31T15:40:59Z",
  "evaluation_seed": 42,
  "runtime_environment": {
    "python_version": "3.11.0",
    "rapidocr_onnxruntime_version": "1.4.4",
    "onnxruntime_version": "1.26.0",
    "pymupdf_version": "1.24.10"
  },
  "cryptographic_hashes": {
    "ocr_source_hash_sha256": "38b1deac035263a7d4d20b4b67319f79472219c2b7efdd7a4181989b0fc47a82",
    "reconciliation_script_sha256": "c4b78c8f53e1bdb7263fcfe85b35e7a6d79ef1d5ffee699da78dddbac7ee7e85",
    "phase5_5_gt_manifest_sha256": "e94217c912b2616d2413d975ec4a7ea27d4779842e854ac078e6cf472a1f9dd2"
  },
  "onnx_model_assets": {
    "ch_PP-OCRv4_det_infer.onnx": {
      "size_bytes": 4745517,
      "sha256": "d2a7720d45a54257208b1e13e36a8479894cb74155a5efe29462512d42f49da9"
    },
    "ch_PP-OCRv4_rec_infer.onnx": {
      "size_bytes": 10857958,
      "sha256": "48fc40f24f6d2a207a2b1091d3437eb3cc3eb6b676dc3ef9c37384005483683b"
    },
    "ch_ppocr_mobile_v2.0_cls_infer.onnx": {
      "size_bytes": 585532,
      "sha256": "e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c"
    }
  },
  "document_checksums_total": 60
}
```

---

## 7. Automated Test Suite and Build Verification

1. **Python Pytest Suite:**
   - **109 passing tests** across the entire workspace (all existing Phase 1–5.5.2 tests preserved).
   - Dedicated Phase 5.5.2.1 verification suite: [tests/test_phase5_5_2_1_freeze.py](file:///d:/MedResolve/tests/test_phase5_5_2_1_freeze.py) (**5 passed in 0.10s**):
     - `test_ground_truth_terminology_and_generator_derived`
     - `test_heldout_dataset_template_audit_reporting`
     - `test_cer_wer_macro_micro_reconciliation`
     - `test_per_document_cer_wer_reconciled`
     - `test_final_benchmark_manifest_v2_freeze`
2. **Frontend Production Build:**
   - Vite 8.3.5 production client build: `tsc -b && vite build` succeeded in `490ms` with **0 errors**.
   - Oxlint static code analyzer: **0 errors**.

---

## 8. Permanent Freeze Declaration & Synthetic Limitations

### Permanent Freeze Declaration
As of Phase 5.5.2.1, the MedResolve OCR Benchmark is **formally and permanently FROZEN**:
- No further tuning of regex expressions, bounding-box sliding windows, or decimal tolerance rules will be conducted against the 50 historical or 10 held-out benchmark documents.
- Any future research iterations targeting broader hospital document types must be evaluated on entirely distinct real-world or separate synthetic distributions.

### Explicit Synthetic Data Limitations
1. **Shared Canvas Primitives:** Because synthetic documents were produced via Python PIL and PyMuPDF drawing scripts, font kerning and layout structures follow uniform geometry. Real-world documents exhibit infinite font variability, faded dot-matrix print, multi-generation photocopying, and handwriting.
2. **Clinical Nomenclature Variation:** The regex extractor targets canonical biomarker names (e.g., `Serum Creatinine`). Hospital discharge summaries and outpatient encounter notes frequently use non-standard abbreviations, local lab shorthand, or unstructured narrative descriptions that require clinical LLM extraction rather than rule-based regex parsing.
3. **Absence of Real Patient Data:** Zero protected health information (PHI) was processed. This guarantees privacy and HIPAA compliance for open-source benchmarking, but requires clinical validation on de-identified real EHR archives prior to bedside or diagnostic deployment.
