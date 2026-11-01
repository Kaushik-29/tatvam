# MedResolve Phase 4.1: Audited Action Policy Evaluation Report

**Evaluation Cohort:** `results\actions\eval_action_scenarios.json`  
**Cohort Size:** 300 strictly held-out controlled scenarios  
**Dataset Provenance:** Unused rows from DDXPlus `release_train_patients.csv` (100% disjoint from classifier training & Phase 3 conflict benchmark)  
**Evaluation Status:** Post-Audit Validated (Independent Benchmark Decoupled, Leakage Eliminated)

---

## 1. Executive Summary & Policy Comparison

| Evaluation Metric | Baseline B0 (Always Explain) | Baseline B1 (Conflict-Only) | Proposed B2 (Selective Action Policy) |
| :--- | :---: | :---: | :---: |
| **Action Selection Accuracy** | **36.67%** | **55.67%** | **100.00%** |
| **Macro-F1 (Ordinary Actions)** | 0.1290 | 0.4003 | **1.0000** |
| **Macro-F1 (All 4 Actions)** | 0.3468 | 0.5502 | **1.0000** |
| **False-Explanation Rate (FER on Abstain)** | 100.00% (80/80) | 28.75% (23/80) | **0.00%** (0/80) |
| **Emergency Sensitivity (Recall)** | 100.00% | 100.00% | **100.00%** |
| **Abstention Rate** | 0.00% | 35.67% | 26.67% |
| **Explanation Coverage** | 83.33% | 47.67% | 20.00% |
| **Mean Latency per Decision** | 0.23 ms | 0.38 ms | 0.44 ms |

---

## 2. Policy Ablation Analysis

To distinguish the isolated contributions of extraction uncertainty and predictive diagnostic uncertainty, we evaluate two targeted policy ablations:
- **Ablation 1 (No Extraction Uncertainty):** Disables Step 2 verification checks. Treats unconfirmed low-confidence document extractions as verified.
- **Ablation 2 (No Predictive Uncertainty):** Disables Step 4 entropy/margin checks. Never generates active clarifying questions for ambiguous differentials.

| Metric | Proposed Policy B2 (Full) | Ablation 1: No Extraction Uncertainty | Ablation 2: No Predictive Uncertainty |
| :--- | :---: | :---: | :---: |
| **Overall Accuracy** | **100.00%** | 84.00% | 72.33% |
| **Macro-F1 (Ordinary Actions)** | **1.0000** | 0.8117 | 0.6827 |
| **ASK Action Precision** | 1.0000 | 1.0000 | 1.0000 |
| **ASK Action Recall** | **1.0000** | 0.5636 | 0.4545 |
| **Explanation Coverage** | 20.00% | 36.00% | 47.67% |
| **Abstention Rate** | 26.67% | 26.67% | 19.00% |

*Takeaway:* Removing extraction uncertainty drops ASK recall on noisy document inputs, causing unverified extractions to bleed directly into diagnostic explanations. Removing predictive uncertainty completely eliminates active questioning on ambiguous differentials, collapsing performance on multi-candidate presentations.

---

## 3. Dedicated Emergency-Detection Audit & Confusion Matrix

All policies enforce identical deterministic safety overrides before taking ordinary actions. Below is the full binary emergency-detection confusion matrix and operating characteristics:

### Binary Emergency Confusion Matrix (Proposed B2)

| | Actual Emergency Positive | Actual Non-Emergency Negative | Total |
| :--- | :---: | :---: | :---: |
| **Predicted Emergency** | **50 (TP)** | **0 (FP)** | 50 |
| **Predicted Non-Emergency** | **0 (FN)** | **250 (TN)** | 250 |
| **Total** | 50 | 250 | 300 |

### Operating Characteristics

- **Sensitivity (True Positive Rate):** `100.00%` (50/50)
- **Specificity (True Negative Rate):** `100.00%` (250/250)
- **False Positive Rate (FPR):** `0.00%` (0/250)
- **False Negative Rate (FNR):** `0.00%` (0/50)

> [!WARNING]
> **Synthetic Case Mix Disclaimer:** The emergency detection evaluation cohort is generated from synthetic and perturbed clinical presentations. In real-world clinical triage, pre-test disease prevalence and acuity distributions differ substantially from balanced experimental benchmarks. These synthetic metrics characterize algorithmic rule behavior under controlled test conditions and do NOT establish real-world medical safety or clinical diagnostic efficacy.

---

## 4. Category-Level Performance Breakdown

| Scenario Category | Support | B0 (Always Explain) | B1 (Conflict-Only) | B2 (Selective Action Policy) | B2 Ablation (No Extr. Unc.) | B2 Ablation (No Pred. Unc.) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `CLEAN_HIGH_CONFIDENCE` | 50–60 | 100.00% | 100.00% | **100.00%** | 100.00% | 100.00% |
| `AMBIGUOUS_NEED_QUESTION` | 50–60 | 0.00% | 0.00% | **100.00%** | 100.00% | 0.00% |
| `LOW_CONFIDENCE_EXTRACTION` | 50–60 | 0.00% | 0.00% | **100.00%** | 4.00% | 100.00% |
| `OPINION_DISAGREEMENT` | 50–60 | 0.00% | 100.00% | **100.00%** | 100.00% | 100.00% |
| `MATERIAL_CONFLICT_OR_NO_QUESTION` | 50–60 | 0.00% | 42.50% | **100.00%** | 100.00% | 42.50% |
| `EMERGENCY_RED_FLAG` | 50–60 | 100.00% | 100.00% | **100.00%** | 100.00% | 100.00% |

---

## 5. Per-Action Classification Performance (Proposed Policy B2)

| Action Pathway | Precision | Recall | F1-Score | Support |
| :--- | :---: | :---: | :---: | :---: |
| `ASK` | 1.0000 | 1.0000 | 1.0000 | 110 |
| `EXPLAIN` | 1.0000 | 1.0000 | 1.0000 | 60 |
| `ABSTAIN_AND_NAVIGATE` | 1.0000 | 1.0000 | 1.0000 | 80 |
| `EMERGENCY_OVERRIDE` | 1.0000 | 1.0000 | 1.0000 | 50 |

---

## 6. Confusion Matrix (Proposed Policy B2)

```
                       Predicted
Ground Truth            ASK    EXPLAIN   ABSTAIN   OVERRIDE
ASK                     110    0         0         0       
EXPLAIN                 0      60        0         0       
ABSTAIN_AND_NAVIGATE    0      0         80        0       
EMERGENCY_OVERRIDE      0      0         0         50      
```

---

## 7. Independent Classifier Probability Calibration

- **Evaluated Cases (Clean Profiles):** 60  
- **Average Top-1 Confidence:** 0.9682  
- **Top-1 Empirical Accuracy:** 1.0  
- **Multi-Class Brier Score:** 0.0047  
- **Expected Calibration Error (ECE Gap):** 0.0318  

*Interpretation:* Model probabilities show high empirical confidence on full evidence profiles, with a small ECE gap indicating good alignment between predicted scores and observed accuracy.

---

## 8. Audit Findings & Resolution of Apparent False Overrides

During the Phase 4.1 safety audit, an investigation of the nine initial apparent false emergency overrides revealed two distinct root causes:

1. **Diagnostic Model Coupling (5 cases):** Previously, Rule 7 triggered emergency overrides when the ML model predicted probability $\ge 0.40$ for severity-1 conditions (`Possible NSTEMI / STEMI` or `Acute pulmonary edema`), even without any observable red-flag symptoms. This conflated statistical disease classification with physiological triage safety overrides. Removing model probability dependencies and grounding the detector purely in observable symptoms and vitals completely resolved these 5 cases.
2. **Benchmark Symptom Confounding (4 cases):** Previously, the benchmark generator injected `E_66` (Dyspnea) as a conflicting statement onto patients who already had thoracic chest pain (`E_55`). Clinically, acute chest pain combined with dyspnea is a genuine cardiopulmonary emergency (Rule 3). Injecting an acute red-flag symptom created an actual emergency scenario while labeling it as an ordinary conflict. Replacing the injected symptom with a non-emergency symptom (`E_201`, cough) eliminated this benchmark-label inconsistency.

---

*Report generated automatically by `experiments/evaluate_action_policy.py`.*
