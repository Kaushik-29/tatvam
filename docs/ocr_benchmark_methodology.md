# MedResolve — OCR Benchmark Methodology

**Phase Identifier:** Phase 5.5  
**Document Purpose:** Mathematical specification of OCR evaluation metrics, text normalization rules, and ground-truth dataset construction.

---

## 1. Ground-Truth Construction Protocol

The 50-document ground-truth dataset was generated programmatically to ensure 100% reproducibility while maintaining fictional clinical validity:
- **Zero Real Patient Data:** All names, IDs, dates, facility banners, and clinical values were synthesized programmatically.
- **Independent Machine-Readable Specifications:** Ground truth was specified in JSON prior to OCR ingestion.
- **Seven Operational Categories:**
  1. `digital_lab_pdf` (10 documents): Vector text embedded via PyMuPDF. Evaluates direct digital text extraction.
  2. `clean_scanned_lab` (10 documents): Rendered at 200 DPI via Pillow. Evaluates clean RapidOCR ONNX inference.
  3. `scanned_prescription` (10 documents): Rendered prescriptions with Rx symbol, medication name, dosage strength, unit, frequency, and duration.
  4. `noisy_scan` (5 documents): Artificially degraded with Gaussian noise and salt-and-pepper artifacts.
  5. `skewed_document` (5 documents): Rotated from -5° to +4° to test orientation rectification.
  6. `medical_table` (5 documents): PDF documents with multi-column table borders and gridlines.
  7. `ambiguous_or_missing_unit` (5 documents): Documents specifically designed to test unit provenance states (`MISSING`, `NORMALIZED`, `INVALID`).

---

## 2. Text Normalization Rules

In academic OCR evaluation, raw text must be standardized to prevent trivial formatting variations from artificially penalizing the engine while strictly preserving all clinically relevant tokens.

### Normalization Pipeline:
1. **Case Normalization:** String is converted to lowercase for comparison: $\text{normalize\_case}(T) = T.\text{lower}()$.
2. **Whitespace Collapsing:** Line breaks (`\n`, `\r`), tabs (`\t`), and consecutive space sequences are collapsed into a single whitespace: `re.sub(r'\s+', ' ', T)`.
3. **Leading/Trailing Trimming:** String edges are stripped: `T.strip()`.

### Strict Clinical Invariants (NEVER Normalized Away):
- **Decimal Points:** The decimal period (`.`) is strictly preserved (e.g. `112.5` must not become `1125` or `112 5`).
- **Signs:** Plus (`+`), minus (`-`), less-than (`<`), and greater-than (`>`) are preserved for reference intervals.
- **Numeric Digits:** All integer and fractional digits `0`–`9` are preserved.
- **Medication Strengths:** Dosages (e.g. `500 mg`, `10 mg`, `50 mcg`) remain intact.
- **Measurement Units:** Clinical unit tokens (`mg/dL`, `mmol/L`, `g/dL`, `%`, `mmHg`, `bpm`, `U/L`, `/uL`) are preserved.

---

## 3. Mathematical Metric Definitions

### Character Error Rate (CER)
Character Error Rate is the standard Levenshtein edit distance between the reference character sequence $C_{\text{ref}}$ and the hypothesis character sequence $C_{\text{hyp}}$, divided by the total number of characters in the reference sequence:

$$\text{CER} = \frac{S_C + D_C + I_C}{N_C} = \frac{\text{Levenshtein}(C_{\text{ref}}, C_{\text{hyp}})}{|C_{\text{ref}}|}$$

Where:
- $S_C$: Number of character substitutions.
- $D_C$: Number of character deletions.
- $I_C$: Number of character insertions.
- $N_C$: Total character count in reference ground truth.

### Word Error Rate (WER)
Word Error Rate tokenizes the normalized strings by whitespace into word token sequences $W_{\text{ref}}$ and $W_{\text{hyp}}$ and evaluates token-level edit distance:

$$\text{WER} = \frac{S_W + D_W + I_W}{N_W} = \frac{\text{LevenshteinTokens}(W_{\text{ref}}, W_{\text{hyp}})}{|W_{\text{ref}}|}$$

Where:
- $S_W, D_W, I_W$: Word substitutions, deletions, and insertions.
- $N_W$: Total word token count in reference ground truth.

### Exact Document Text Match Rate
The exact document text match rate is the fraction of documents where the normalized extracted text is identical to the normalized reference text:

$$\text{EMR} = \frac{1}{M} \sum_{i=1}^{M} \mathbb{I}[T_{\text{hyp}}^{(i)} = T_{\text{ref}}^{(i)}]$$

Where $M = 50$ total benchmark documents.

---

## 4. Denominator and Sample Size Disclosure

All metrics reported in MedResolve Phase 5.5 include explicit numerators, denominators, and benchmark cohort definitions:

| Metric | Measured Value | Numerator | Denominator | Benchmark Sample |
| :--- | :---:| :---:| :---:| :--- |
| **Overall CER** | 2.1245 | 13,586 edits | 6,395 ref chars | 50 Synthetic Documents |
| **Overall WER** | 2.1601 | 1,862 edits | 862 ref words | 50 Synthetic Documents |
| **Exact Match Rate** | 0.00% | 0 matching docs | 50 documents | 50 Synthetic Documents |
| **Field Precision** | 84.26% | 91 true positives | 108 extractions | 116 Ground-Truth Fields |
| **Field Recall** | 78.45% | 91 true positives | 116 expected | 116 Ground-Truth Fields |
| **Field F1 Score** | 0.8125 | — | — | Harmonic Mean (P=0.8426, R=0.7845) |
| **Exact Value Match Rate** | 76.72% | 89 correct values | 116 expected | 116 Ground-Truth Fields |
| **Exact Unit Match Rate** | 62.07% | 72 correct units | 116 expected | 116 Ground-Truth Fields |
| **Medication Dosage Accuracy** | 92.31% | 12 correct dosages | 13 prescriptions | 13 Synthetic Prescriptions |
