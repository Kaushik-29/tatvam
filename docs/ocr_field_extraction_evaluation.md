# MedResolve — Structured Medical Field Extraction & Provenance Evaluation

**Phase Identifier:** Phase 5.5  
**Document Purpose:** Independent evaluation of the structured clinical entity extraction stage, RapidOCR confidence aggregation, and 5-way unit provenance taxonomy.

---

## 1. Independent Evaluation Principle

MedResolve strictly decouples raw optical character recognition from clinical entity structuring:
- **Raw OCR Transcription Quality:** Evaluates whether pixels are accurately converted into text tokens (CER / WER).
- **Structured Field Extraction Accuracy:** Evaluates whether clinical measurements (concepts, numbers, units, reference intervals, dates) are correctly mapped into structured evidence ledger items (`ExtractedObservation`).

A document may have minor character transcription variations in non-critical boilerplate text while achieving 100% structured field extraction accuracy for vital clinical measurements.

---

## 2. Evaluation Schema Across Medical Concept Types

### Laboratory Concepts
- Concept Normalization (e.g. `fasting blood glucose` -> `E_BLOOD_GLUCOSE_FASTING`)
- Numeric Observed Value (e.g. `112.5`)
- Measurement Unit (e.g. `mg/dL`)
- Reference Interval (e.g. `70 - 99 mg/dL`)
- Specimen Collection Date (e.g. `2026-03-10`)

### Vital Sign Concepts
- Concept Normalization (e.g. `blood pressure` -> `E_VITALS_BP`)
- Value String (e.g. `140/90`)
- Measurement Unit (e.g. `mmHg`)
- Timestamp / Date of Measurement

### Medication Concepts
- Medication Name (e.g. `Metformin`)
- Dosage Strength (e.g. `500.0`)
- Dosage Unit (e.g. `mg`)
- Frequency when explicitly written (e.g. `OD`, `BD`, `TID`, `as needed`)
- Duration when explicitly written (e.g. `30 days`, `7 days`)

*Strict Rule:* No missing medication frequencies or durations are ever inferred or fabricated by the system.

---

## 3. Results by Clinical Category

| Category | True Positives | False Positives | False Negatives | Precision | Recall | F1 | Exact Value Match |
| :--- | :---:| :---:| :---:| :---:| :---:| :---:| :---:|
| **Digital Lab PDFs (10 docs)** | 32 | 6 | 6 | 0.8421 | 0.8421 | **0.8421** | 84.21% (32/38) |
| **Clean Scanned Labs (10 docs)** | 20 | 6 | 6 | 0.7692 | 0.7692 | **0.7692** | 76.92% (20/26) |
| **Scanned Prescriptions (10 docs)**| 13 | 0 | 0 | 1.0000 | 1.0000 | **1.0000** | 100.0% (13/13) |
| **Noisy Scans (5 docs)** | 8 | 2 | 4 | 0.8000 | 0.6667 | **0.7273** | 66.67% (8/12) |
| **Skewed Documents (5 docs)** | 4 | 2 | 5 | 0.6667 | 0.4444 | **0.5333** | 33.33% (3/9) |
| **Medical Tables (5 docs)** | 14 | 1 | 4 | 0.9333 | 0.7778 | **0.8485** | 77.78% (14/18) |
| **Ambiguous / Missing (5 docs)** | 3 | 2 | 2 | 0.6000 | 0.6000 | **0.6000** | 60.00% (3/5) |
| **Overall Dataset** | **91** | **17** | **25** | **0.8426** | **0.7845** | **0.8125** | **76.72% (89/116)** |

---

## 4. Five-Way Unit Provenance Taxonomy

MedResolve maintains five mutually exclusive provenance categories:

```
                          [ Extracted Clinical Text ]
                                       |
                 ---------------------------------------------
                 |                                           |
         [ Unit Present ]                             [ Unit Absent ]
                 |                                           |
    ---------------------------                     -------------------
    |            |            |                     |                 |
[Valid &     [Valid &    [Incompatible         [Physiological     [Physiologically
Standard]   Convertible]  or Unknown]             Bounds]          Ambiguous]
    |            |            |                     |                 |
 EXPLICIT    NORMALIZED    INVALID               INFERRED          MISSING
```

### Invariants Verified:
1. **`EXPLICIT`**: Directly extracted canonical unit (e.g., `mg/dL`). Retains direct link to bounding box text.
2. **`NORMALIZED`**: Standard clinical conversion (e.g. `mEq/L` converted safely to `mmol/L` for potassium).
3. **`INFERRED`**: Inferred from unambiguous physiological bounds (e.g. `138/88` BP -> `mmHg`). Strictly marked `INFERRED` and requires user confirmation.
4. **`MISSING`**: Cannot be safely inferred (e.g. `Serum Creatinine: 1.4`). Strictly sets `unit = None`, `unit_status = MISSING`, and mandates confirmation.
5. **`INVALID`**: Incompatible or nonsensical unit (e.g. `HbA1c 7.1 x_unit` or `Heart Rate 80 mmHg`). Flagged as `INVALID` and rejected from unconfirmed clinical ledger inclusion.
6. **Confirmation Precedence:** An unconfirmed observation cannot become confirmed merely by running clinical assessment generation.
