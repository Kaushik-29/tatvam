# MedResolve Phase 4.1: Audit of Apparent False Emergency Overrides

## Executive Summary

During Phase 4 evaluation of the proposed Uncertainty-Aware Selective Action Policy (B2) on the 300-case held-out benchmark (`eval_action_scenarios.json`), the confusion matrix revealed **9 apparent false emergency overrides** (cases where the reference action was `EXPLAIN`, `ASK`, or `ABSTAIN_AND_NAVIGATE`, but the policy selected `EMERGENCY_OVERRIDE`):

- **Reference `EXPLAIN` $\rightarrow$ Predicted `OVERRIDE`**: 3 cases (Cases 1, 2, 3)
- **Reference `ASK` $\rightarrow$ Predicted `OVERRIDE`**: 2 cases (Cases 4, 5)
- **Reference `ABSTAIN_AND_NAVIGATE` $\rightarrow$ Predicted `OVERRIDE`**: 4 cases (Cases 6, 7, 8, 9)

An exhaustive investigation was conducted into the evidence ledgers, model predictions, triggered safety rules, and benchmark generation logic for each of these 9 cases.

### Core Audit Findings

1. **Logical / Model-Coupling Error in Cases 1–5 (5 cases)**:
   - Triggered Rule: **Rule 7** (`Model-assisted severity-1 condition check`: model probability $\ge 0.40$ for conditions labeled with `severity: 1` in `release_conditions.json`).
   - Root Cause: Conflation of **diagnostic model inference** with **triage safety override**. The underlying Phase 2 classifier predicted $P(\text{Possible NSTEMI / STEMI}) \ge 0.94$ or $P(\text{Acute pulmonary edema}) \ge 0.99$ based on subtle symptom profiles. Although the patient presented with zero observable emergency red-flag symptoms (no stridor, no syncope, no concurrent dyspnea, no vitals extremes), Rule 7 triggered an emergency override purely because of the classifier's disease probability score.
   - Reference Label Inconsistency: The benchmark generator placed these cases into `CLEAN_HIGH_CONFIDENCE` (labeled `EXPLAIN`) or `LOW_CONFIDENCE_EXTRACTION` (labeled `ASK`) because their evidence items had no overt red flags. At evaluation time, passing classifier probabilities into `EmergencySafetyOverrideDetector` caused Rule 7 to fire.
   - Rectification: **Remove Rule 7**. An emergency safety override must be grounded strictly in **observed clinical evidence and explicitly defined warning indicators** (symptoms, signs, vitals), not in the classifier's predicted disease scores. A classifier output is an ordinary diagnostic signal, not an urgent triage red flag.

2. **Benchmark-Label Inconsistency in Cases 6–9 (4 cases)**:
   - Triggered Rule: **Rule 3** (`Potential acute cardiopulmonary syndrome: concurrent acute thoracic chest pain and severe dyspnea`).
   - Root Cause: In `action_benchmark_generator.py`, the generator constructed `SOURCE_STATEMENT_DISAGREEMENT` cases by injecting a clinical EHR note recording `E_66` (Dyspnea observed: `evidence_status = PRESENT`). However, the sampled patient rows from DDXPlus already naturally contained thoracic chest pain (`E_55_@_V_29`, `E_55_@_V_101`). Adding `E_66` created a clinically legitimate presentation of concurrent chest pain and resting dyspnea.
   - Reference Label Inconsistency: The benchmark generator blindly assigned `expected_action = ABSTAIN_AND_NAVIGATE` (intending to test source-conflict handling), ignoring the fact that injecting dyspnea onto a patient with chest pain creates an acute cardiopulmonary presentation. Under the safety override precedence rule, the policy was **clinically justified** in triggering `EMERGENCY_OVERRIDE`.
   - Rectification: The benchmark generator must not inject life-threatening emergency symptoms (`E_66` dyspnea) when testing ordinary data conflicts. Non-emergency symptoms (e.g., `E_201` cough, `E_91` fever, `E_97` sore throat) must be used instead so that conflict-handling logic can be evaluated without confounding cardiopulmonary red flags.

---

## Detailed Per-Case Error Analysis

### Case 1: `action_eval_0007_row541307`
- **Benchmark Scenario Category:** `CLEAN_HIGH_CONFIDENCE`
- **Reference Action:** `EXPLAIN`
- **Selected Action:** `EMERGENCY_OVERRIDE`
- **Triggered Safety Rule:** Rule 7 — `High-risk diagnostic consideration: clinical model identifies significant probability (0.99) for life-threatening condition 'Possible NSTEMI / STEMI'.`
- **Available Evidence in Ledger:**
  - `DEMO_AGE`: 74 years, `DEMO_SEX`: Male
  - Pain characteristics: `E_53` (pain present), `E_54_@_V_154`, `E_54_@_V_183`, `E_54_@_V_192`, `E_54_@_V_193`, `E_54_@_V_196`
  - Pain location: `E_55_@_V_29` (lower chest pain), `E_56_@_4` (moderate intensity)
  - Resting dyspnea: `E_50` (mild resting dyspnea), but **no severe acute dyspnea token `E_66`**
  - All symptoms confirmed by patient, extraction confidence = 1.0, zero data conflicts
- **Justification & Root Cause Analysis:**
  - Observable Red Flags: None. The patient did not have concurrent acute severe dyspnea (`E_66`), stridor, syncope, or abnormal vitals.
  - The Phase 2 classifier predicted $P(\text{Possible NSTEMI / STEMI}) = 0.9883$.
  - Rule 7 triggered solely because the model predicted a condition that has `severity: 1` in `release_conditions.json`.
  - Conflates model classification with emergency triage override.
- **Audit Verdict:** **Logical / Model-Coupling Error**. Removing Rule 7 restores the correct evidence-based decision (`EXPLAIN`), aligning with the reference label.

---

### Case 2: `action_eval_0038_row38802`
- **Benchmark Scenario Category:** `CLEAN_HIGH_CONFIDENCE`
- **Reference Action:** `EXPLAIN`
- **Selected Action:** `EMERGENCY_OVERRIDE`
- **Triggered Safety Rule:** Rule 7 — Model predicted probability $0.9896 \ge 0.40$ for `Possible NSTEMI / STEMI`.
- **Available Evidence in Ledger:**
  - `DEMO_AGE`: 61 years, `DEMO_SEX`: Male
  - Mild lower chest pain (`E_55_@_V_29`), mild pain intensity (`E_56_@_3`)
  - No acute dyspnea (`E_66`), no stridor, no syncope
- **Justification & Root Cause Analysis:**
  - Zero observable emergency red flags in ledger items.
  - Triggered exclusively by Rule 7 via the classifier's predicted probability.
- **Audit Verdict:** **Logical / Model-Coupling Error**. Corrected by removing model probability dependency from emergency detection.

---

### Case 3: `action_eval_0055_row766394`
- **Benchmark Scenario Category:** `CLEAN_HIGH_CONFIDENCE`
- **Reference Action:** `EXPLAIN`
- **Selected Action:** `EMERGENCY_OVERRIDE`
- **Triggered Safety Rule:** Rule 7 — Model predicted probability $0.9393 \ge 0.40$ for `Possible NSTEMI / STEMI`.
- **Available Evidence in Ledger:**
  - `DEMO_AGE`: 67 years, `DEMO_SEX`: Female
  - Upper chest pain (`E_55_@_V_101`), lower chest pain (`E_55_@_V_29`), intensity `E_56_@_4`
  - No acute dyspnea (`E_66`), no stridor, no syncope, normal vitals
- **Justification & Root Cause Analysis:**
  - Zero observable emergency red flags.
  - Triggered exclusively by Rule 7.
- **Audit Verdict:** **Logical / Model-Coupling Error**. Corrected by removing Rule 7.

---

### Case 4: `action_eval_0136_row892373`
- **Benchmark Scenario Category:** `LOW_CONFIDENCE_EXTRACTION`
- **Reference Action:** `ASK`
- **Selected Action:** `EMERGENCY_OVERRIDE`
- **Triggered Safety Rule:** Rule 7 — Model predicted probability $0.9910 \ge 0.40$ for `Acute pulmonary edema`.
- **Available Evidence in Ledger:**
  - `DEMO_AGE`: 72 years, `DEMO_SEX`: Male
  - Injected low-confidence OCR extraction: `E_91` (Fever, extraction confidence = 0.54, unconfirmed)
  - Lower chest pain (`E_55_@_V_29`), but no acute dyspnea token `E_66`
- **Justification & Root Cause Analysis:**
  - The benchmark intended to test whether the policy would choose `ASK` to clarify the unconfirmed OCR extraction (`E_91`).
  - However, because the patient's underlying disease was acute pulmonary edema, the classifier predicted $P(\text{Acute pulmonary edema}) = 0.9910$.
  - Rule 7 intercepted the presentation and forced `EMERGENCY_OVERRIDE`, preempting the intended `ASK` action.
- **Audit Verdict:** **Logical / Model-Coupling Error**. Corrected by removing Rule 7, allowing extraction uncertainty to trigger `ASK`.

---

### Case 5: `action_eval_0137_row574382`
- **Benchmark Scenario Category:** `LOW_CONFIDENCE_EXTRACTION`
- **Reference Action:** `ASK`
- **Selected Action:** `EMERGENCY_OVERRIDE`
- **Triggered Safety Rule:** Rule 7 — Model predicted probability $0.9889 \ge 0.40$ for `Possible NSTEMI / STEMI`.
- **Available Evidence in Ledger:**
  - `DEMO_AGE`: 58 years, `DEMO_SEX`: Male
  - Injected low-confidence OCR extraction: `E_91` (Fever, confidence = 0.48, unconfirmed)
  - Non-thoracic pain (`E_55_@_V_33`: epigastric pain), zero dyspnea tokens
- **Justification & Root Cause Analysis:**
  - Similar to Case 4: the intended action was `ASK` to verify the low-confidence OCR value.
  - Rule 7 fired on model probability alone.
- **Audit Verdict:** **Logical / Model-Coupling Error**. Corrected by removing Rule 7.

---

### Case 6: `action_eval_0221_row326099`
- **Benchmark Scenario Category:** `MATERIAL_CONFLICT_OR_NO_QUESTION`
- **Reference Action:** `ABSTAIN_AND_NAVIGATE`
- **Selected Action:** `EMERGENCY_OVERRIDE`
- **Triggered Safety Rule:** Rule 3 — `Potential acute cardiopulmonary syndrome: concurrent acute thoracic chest pain and severe dyspnea.`
- **Available Evidence in Ledger:**
  - `DEMO_AGE`: 68 years, `DEMO_SEX`: Male, Pathology: `Bronchitis`
  - Patient naturally presented with thoracic chest pain: `E_55_@_V_29` (lower chest pain), `E_55_@_V_101` (upper chest pain), `E_55_@_V_159`, `E_55_@_V_160`, `E_55_@_V_170`.
  - Injected conflict:
    - Patient self-report: `E_66` (Dyspnea: `evidence_status = ABSENT`)
    - EHR clinical note: `E_66` (Dyspnea: `evidence_status = PRESENT`)
- **Justification & Root Cause Analysis:**
  - Clinical Validity: An attending triage clinician presented with severe thoracic chest pain and an objective EHR note documenting acute resting dyspnea must treat this as a potentially life-threatening cardiopulmonary emergency (e.g., acute coronary syndrome or pulmonary embolism), regardless of patient denial.
  - Policy Decision: Rule 3 correctly fired based on observable evidence (`CHEST_PAIN_TOKENS` + `DYSPNEA_TOKENS`).
  - Benchmark Inconsistency: The generator author intended to evaluate source-conflict handling, but inadvertently chose a life-threatening red-flag symptom (`E_66` dyspnea) on a patient who already had chest pain.
- **Audit Verdict:** **Benchmark-Label Inconsistency**. The policy's emergency override was clinically sound. The benchmark generator erred by injecting a red-flag symptom instead of a benign symptom (e.g., cough or fever) for source-discrepancy testing.

---

### Case 7: `action_eval_0237_row953599`
- **Benchmark Scenario Category:** `MATERIAL_CONFLICT_OR_NO_QUESTION`
- **Reference Action:** `ABSTAIN_AND_NAVIGATE`
- **Selected Action:** `EMERGENCY_OVERRIDE`
- **Triggered Safety Rule:** Rule 3 — Concurrent thoracic chest pain (`E_55_@_V_29`, `E_55_@_V_148`) and dyspnea (`E_66` PRESENT in EHR note).
- **Audit Verdict:** **Benchmark-Label Inconsistency** (identical mechanism to Case 6).

---

### Case 8: `action_eval_0238_row346593`
- **Benchmark Scenario Category:** `MATERIAL_CONFLICT_OR_NO_QUESTION`
- **Reference Action:** `ABSTAIN_AND_NAVIGATE`
- **Selected Action:** `EMERGENCY_OVERRIDE`
- **Triggered Safety Rule:** Rule 3 — Concurrent thoracic chest pain (`E_55_@_V_29`) and dyspnea (`E_66` PRESENT in EHR note). Pathology: `GERD`.
- **Audit Verdict:** **Benchmark-Label Inconsistency** (identical mechanism to Case 6).

---

### Case 9: `action_eval_0242_row472323`
- **Benchmark Scenario Category:** `MATERIAL_CONFLICT_OR_NO_QUESTION`
- **Reference Action:** `ABSTAIN_AND_NAVIGATE`
- **Selected Action:** `EMERGENCY_OVERRIDE`
- **Triggered Safety Rule:** Rule 3 — Concurrent thoracic chest pain (`E_55_@_V_29`, `E_55_@_V_101`) and dyspnea (`E_66` PRESENT in EHR note). Pathology: `GERD`.
- **Audit Verdict:** **Benchmark-Label Inconsistency** (identical mechanism to Case 6).

---

## Summary of Corrective Actions

| Component | Identified Issue | Corrective Action |
| :--- | :--- | :--- |
| `experiments/action_policy.py` | Rule 7 used model probability of severity-1 conditions. | **Remove Rule 7**. Ground emergency overrides strictly in observable clinical evidence and defined vitals. |
| `experiments/action_policy.py` | Rule 8 checked `ledger.metadata.get("is_acute_emergency")`. | **Remove Rule 8**. Eliminate all synthetic generator metadata dependencies. |
| `experiments/action_benchmark_generator.py` | Injected `E_66` (dyspnea) for source conflicts on chest pain patients. | Use benign symptoms (`E_201` cough, `E_91` fever, `E_97` sore throat) for source conflict generation to prevent accidental cardiopulmonary red flags. |
| `experiments/action_benchmark_generator.py` | Shared `EmergencySafetyOverrideDetector` code with policy. | Decouple generator from policy implementation to ensure complete benchmark independence. |
