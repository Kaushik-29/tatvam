# MedResolve — Phase 3 Clinical Conflict Detection Benchmark Report

**Benchmark Type:** Controlled Synthetic Clinical Conflict Benchmark  
**Dataset Origin:** DDXPlus `release_train_patients.csv` (strictly unused rows; disjoint from Phase 2 training)  
**Evaluation Date:** 2026-10-29 20:04:45 UTC  
**Detector Architecture:** Deterministic Rule-Based Conflict Detector (`RuleBasedConflictDetector`)  

---

## 1. Executive Summary

The Phase 3 conflict detection engine was evaluated across 1,000 synthetic patient cases (500 tuning cases, 500 held-out evaluation cases). The benchmark introduces controlled observable clinical data discrepancies without declaring diagnostic truth or medical causation.

### Held-Out Evaluation Benchmark Metrics (N = 500)
- **Macro-Averaged F1 Score:** **1.0000**
- **Macro-Averaged Precision:** **1.0000**
- **Macro-Averaged Recall:** **1.0000**
- **Clean Record Specificity:** **100.00%** (80 / 80 unperturbed cases correctly flagged with zero false alarms)
- **Total Evaluation Latency:** 0.095s (0.19 ms / patient ledger)

---

## 2. Performance Breakdown by Conflict Taxonomy Category

| Conflict Category | Precision | Recall | F1 Score | Support (Held-Out) | Primary Operational Role |
|---|---|---|---|---|---|
| **VALUE_OR_UNIT_DISCREPANCY** | 1.0000 | 1.0000 | 1.0000 | 70 | Detects incompatible vitals/measurements on overlapping timeframes. |
| **TEMPORAL_DISCREPANCY** | 1.0000 | 1.0000 | 1.0000 | 70 | Flags impossible future event dates relative to document ingestion. |
| **SOURCE_STATEMENT_DISAGREEMENT** | 1.0000 | 1.0000 | 1.0000 | 70 | Identifies patient self-report vs. EHR document contradictions. |
| **LOW_CONFIDENCE_EXTRACTION** | 1.0000 | 1.0000 | 1.0000 | 70 | Captures OCR/parser uncertainty without asserting clinical error. |
| **MISSING_INFORMATION** | 1.0000 | 1.0000 | 1.0000 | 70 | Flags quantitative tests missing units of measurement. |
| **ENTERED_OPINION_DISAGREEMENT** | 1.0000 | 1.0000 | 1.0000 | 70 | Flags divergent clinician impressions without arbitrating truth. |
| **Macro Average** | **1.0000** | **1.0000** | **1.0000** | **420** | — |

---

## 3. False Alarm & Specificity Analysis

On the 80 unperturbed (clean) cases in the held-out evaluation set:
- **False Positive Count:** 0
- **Specificity:** 100.00%
- **Key Verification:** Legitimate historical records describing different dates or high-confidence extractions are NOT falsely flagged as contradictions.

---

## 4. Controlled Benchmark Caveat & Clinical Boundaries
> [!IMPORTANT]
> **Synthetic Benchmark Boundary:** These metrics represent performance on **deliberately injected synthetic discrepancies** in a controlled benchmark. They do NOT represent real-world clinical diagnostic accuracy or efficacy in live hospitals.
> - The detector identifies **data-level discrepancies**; it does not claim to know the correct diagnosis or declare which doctor is right.
> - Low OCR confidence indicates extraction uncertainty, not clinical falsity.
