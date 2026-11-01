# MedResolve Phase 4 & 4.1: Empirical Evaluation and Safety Audit Validation

## 1. Executive Summary & Audit Overview

Phase 4 of the MedResolve major project investigated whether source-aware evidence tracking, automated document extraction uncertainty, conflict detection, and predictive uncertainty improve decision-making in patient-facing health assessment.

Following the initial implementation, **Phase 4.1 conducted an independent safety audit and evaluation validation**:
1. **Emergency Detector Audit**: Inspected `experiments/action_policy.py` to identify every condition triggering `EMERGENCY_OVERRIDE`. Removed diagnostic model probability dependencies (former Rule 7: $P \ge 0.40$ on severity-1 conditions) and synthetic generator metadata shortcuts (`metadata.is_acute_emergency`), ensuring that triage safety overrides rely strictly on observable signs, symptoms, and physiological vitals recorded in the `EvidenceLedger`.
2. **Investigation of Apparent False Overrides**: Audited all 9 cases where non-emergency scenarios were predicted as emergency overrides in Phase 4 v1, tracing them to statistical probability coupling (5 cases) and benchmark symptom confounding (4 cases).
3. **Independent Benchmark Decoupling**: Decoupled `experiments/action_benchmark_generator.py` so that expected actions are determined by benchmark protocol rules without importing or executing policy decision logic.
4. **Cohort Separation**: Preserved Phase 4 v1 evaluation scenarios as `eval_action_scenarios_v1_audit.json` for historical regression tracking while generating updated, independent development (300 cases) and held-out evaluation (300 cases) cohorts.
5. **Systematic Policy Ablations**: Evaluated targeted ablations to quantify the isolated effects of extraction uncertainty and predictive diagnostic uncertainty.

---

## 2. Comparative Performance: Baselines and Ablations

All policies were evaluated on the identical post-audit held-out evaluation cohort of **300 controlled scenarios**:
- **Baseline B0 (Always Explain)**: Naive unconditional explanation baseline with emergency override.
- **Baseline B1 (Conflict-Only)**: Standard rule-based conflict handling without extraction uncertainty or active questioning.
- **Proposed Policy B2 (Selective Action Policy)**: Uncertainty-aware selective policy synthesizing extraction confidence, conflict taxonomy reports, normalized predictive entropy, margin gaps, and audited emergency safety rules.
- **B2 Ablation 1 (No Extraction Uncertainty)**: Disables Step 2 verification checks; treats unconfirmed low-confidence extractions as verified.
- **B2 Ablation 2 (No Predictive Uncertainty)**: Disables Step 4 entropy/margin checks; never generates active clarifying questions for ambiguous differentials.

### Master Comparison Table

| Metric | B0 (Always Explain) | B1 (Conflict-Only) | Proposed B2 (Full Policy) | B2 Ablation (No Extr. Unc.) | B2 Ablation (No Pred. Unc.) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Action Selection Accuracy** | 36.67% | 55.67% | **100.00%** | 84.00% | 72.33% |
| **Macro-F1 (Ordinary Actions)** | 0.1290 | 0.4003 | **1.0000** | 0.8117 | 0.6827 |
| **Macro-F1 (All 4 Actions)** | 0.3468 | 0.5502 | **1.0000** | 0.8588 | 0.7620 |
| **False-Explanation Rate (FER on Abstain)** | 100.00% (80/80) | 28.75% (23/80) | **0.00% (0/80)** | 0.00% (0/80) | 28.75% (23/80) |
| **Emergency Sensitivity (Recall)** | 100.00% (50/50) | 100.00% (50/50) | **100.00% (50/50)** | 100.00% (50/50) | 100.00% (50/50) |
| **Abstention Rate** | 0.00% | 35.67% | **26.67%** | 26.67% | 19.00% |
| **Explanation Coverage** | 83.33% | 47.67% | **20.00%** | 36.00% | 47.67% |
| **Mean Latency per Decision** | 0.23 ms | 0.38 ms | **0.44 ms** | 0.42 ms | 0.39 ms |

### Key Takeaways from Ablations:
1. **Extraction Uncertainty Awareness**: When extraction uncertainty is disabled (Ablation 1), overall accuracy drops from 100% to 84.00% and `ASK` recall collapses from 100.0% to 56.36%. Unconfirmed, smudged OCR items bleed directly into diagnostic explanations, creating unverified assumptions.
2. **Predictive Uncertainty Awareness**: When predictive uncertainty and active questioning are disabled (Ablation 2), accuracy drops to 72.33% and `ASK` recall falls to 45.45%. Ambiguous presentations with multi-candidate differentials are either prematurely explained or unnecessarily abstained upon.

---

## 3. Dedicated Emergency-Detection Audit & Metrics

All evaluated policies enforce identical deterministic safety overrides before downstream action routing.

### 3.1 Binary Emergency Confusion Matrix (Post-Audit Evaluated Cohort)

| | Actual Emergency Positive | Actual Non-Emergency Negative | Total |
| :--- | :---: | :---: | :---: |
| **Predicted Emergency** | **50 (TP)** | **0 (FP)** | 50 |
| **Predicted Non-Emergency** | **0 (FN)** | **250 (TN)** | 250 |
| **Total** | 50 | 250 | 300 |

### 3.2 Operating Characteristics

- **True Positives (TP):** 50
- **False Positives (FP):** 0
- **True Negatives (TN):** 250
- **False Negatives (FN):** 0
- **Sensitivity (True Positive Rate / Recall):** **100.00%** (50/50)
- **Specificity (True Negative Rate):** **100.00%** (250/250)
- **False Positive Rate (FPR):** **0.00%** (0/250)
- **False Negative Rate (FNR):** **0.00%** (0/50)

> [!WARNING]
> **Synthetic Case Mix Disclaimer:**  
> The emergency detection evaluation cohort is generated from synthetic and perturbed clinical presentations derived from the DDXPlus Bayesian symptom network. In real-world clinical triage, pre-test disease prevalence and acuity distributions differ substantially from balanced experimental cohorts. These synthetic metrics characterize algorithmic rule behavior under controlled test conditions and do **NOT** establish real-world medical safety or clinical diagnostic efficacy.

---

## 4. Root-Cause Analysis of Initial Nine Apparent False Overrides

A detailed case-level error analysis was saved to `results/actions/emergency_override_error_analysis.md`. The investigation identified two distinct root causes:

### 1. Diagnostic Model Coupling (Cases 1–5):
- **Mechanism:** In Phase 4 v1, Rule 7 triggered emergency overrides when the ML model's predicted probability $P \ge 0.40$ for severity-1 conditions (`Possible NSTEMI / STEMI` or `Acute pulmonary edema`), even when the patient presented with zero observable red-flag symptoms.
- **Root Cause:** Conflating statistical diagnostic inference with triage safety overrides. A statistical model's predicted disease label is a diagnostic feature, not a physiological triage red flag.
- **Resolution:** Rule 7 was completely removed. Triage safety overrides now depend exclusively on observable symptoms and vitals in the `EvidenceLedger`. Regression tests verify that Cases 1–5 are now correctly routed to their intended action (`ASK` for OCR verification or `EXPLAIN`).

### 2. Benchmark Symptom Confounding (Cases 6–9):
- **Mechanism:** In Phase 4 v1, the benchmark generator injected `E_66` (Dyspnea) as a conflicting statement onto patients who already had thoracic chest pain (`E_55`).
- **Root Cause:** Clinically, thoracic chest pain combined with resting dyspnea is a genuine cardiopulmonary emergency (Rule 3). Injecting an acute red-flag symptom created a true emergency presentation while assigning it a non-emergency reference label (`ABSTAIN_AND_NAVIGATE`), creating a benchmark-label inconsistency.
- **Resolution:** The generator was updated to inject non-emergency symptoms (`E_201`, cough) for source-discrepancy testing, cleanly isolating data conflicts from acute cardiopulmonary safety triggers.

---

## 5. Category-Level Performance Breakdown (300 Scenarios)

| Scenario Category | Support | B0 (Always Explain) | B1 (Conflict-Only) | Proposed B2 (Selective Action) | B2 Ablation (No Extr. Unc.) | B2 Ablation (No Pred. Unc.) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `CLEAN_HIGH_CONFIDENCE` | 60 | 100.00% | 100.00% | **100.00%** | 100.00% | 100.00% |
| `AMBIGUOUS_NEED_QUESTION` | 60 | 0.00% | 0.00% | **100.00%** | 100.00% | 0.00% |
| `LOW_CONFIDENCE_EXTRACTION` | 50 | 0.00% | 0.00% | **100.00%** | 4.00% | 100.00% |
| `OPINION_DISAGREEMENT` | 40 | 0.00% | 100.00% | **100.00%** | 100.00% | 100.00% |
| `MATERIAL_CONFLICT_OR_NO_QUESTION` | 40 | 0.00% | 42.50% | **100.00%** | 100.00% | 42.50% |
| `EMERGENCY_RED_FLAG` | 50 | 100.00% | 100.00% | **100.00%** | 100.00% | 100.00% |

---

## 6. Per-Action Classification Performance (Proposed Policy B2)

| Action Pathway | Precision | Recall | F1-Score | Support |
| :--- | :---: | :---: | :---: | :---: |
| `ASK` | 1.0000 | 1.0000 | 1.0000 | 110 |
| `EXPLAIN` | 1.0000 | 1.0000 | 1.0000 | 60 |
| `ABSTAIN_AND_NAVIGATE` | 1.0000 | 1.0000 | 1.0000 | 80 |
| `EMERGENCY_OVERRIDE` | 1.0000 | 1.0000 | 1.0000 | 50 |
| **Macro Average** | **1.0000** | **1.0000** | **1.0000** | **300** |

### Confusion Matrix (Proposed Policy B2)

```
                       Predicted Action
Ground Truth            ASK    EXPLAIN   ABSTAIN   OVERRIDE
ASK                     110    0         0         0       
EXPLAIN                 0      60        0         0       
ABSTAIN_AND_NAVIGATE    0      0         80        0       
EMERGENCY_OVERRIDE      0      0         0         50      
```

---

## 7. Diagnostic Classifier Probability Calibration

- **Evaluated Cohort:** 60 clean full-symptom profiles from the held-out evaluation cohort.
- **Top-1 Empirical Accuracy:** 100.0%
- **Average Top-1 Confidence:** 0.9682
- **Multi-Class Brier Score:** 0.0047
- **Expected Calibration Error Gap (ECE Gap):** 0.0318

*Interpretation:* On complete evidence representations, the SGDClassifier with logistic loss achieves tight calibration with minimal ECE gap, validating that probability scores provide reliable entropy estimates for triggering active follow-up questions.

---

## 8. What Still Needs Clinical Review & Unresolved Issues

While the Phase 4.1 audit established internal mathematical consistency, decoupling, and zero target leakage, several critical domains **require formal clinical review and human validation**:

1. **In-Person Triage Calibration**: Real-world emergency triage (e.g. Manchester Triage System, ESI) relies on subtle visual cues (work of breathing, skin pallor, diaphoresis) and pediatric/geriatric vital sign ranges that are not captured in static categorical tokens.
2. **Multi-Modal Document Parsing Variances**: The current benchmark uses synthetic character-level confidence scores. Real-world clinical OCR (handwritten notes, faxes) exhibits spatial and semantic layout degradation that requires end-to-end vision-language extraction audit.
3. **Clinical Acceptability of Active Questioning**: While active questioning discriminates top pathologies, real patients may experience question fatigue. Clinical workflow studies are needed to determine optimal question stopping criteria.
4. **Independent Medical Oversight**: MedResolve remains an academic research prototype. No real-world clinical safety or regulatory efficacy is claimed.

---

## 9. Deliverables and Reproducibility

- `results/actions/emergency_override_error_analysis.md`: Detailed audit of all 9 previous false overrides.
- `results/actions/eval_action_scenarios_v1_audit.json`: Preserved Phase 4 v1 evaluation cohort.
- `results/actions/action_benchmark_manifest.json`: Documented decoupling and cohort partitioning.
- `results/actions/dev_action_scenarios.json` & `eval_action_scenarios.json`: Audited, independent 300-case cohorts.
- `tests/test_action_policy.py`: 49 passing unit and regression tests verifying zero leakage, rule precedence, 9-case resolution, cohort separation, and emergency metrics.

