# MedResolve: Controlled Synthetic Conflict Benchmark

## 1. Benchmark Purpose & Design Philosophy
To evaluate automated clinical conflict detection before training neural or agentic policies, MedResolve establishes a **controlled synthetic conflict benchmark**.

Evaluating conflict detection on raw unperturbed datasets is infeasible because ground-truth conflict labels do not exist in standard benchmarks. Rather than fabricating ad-hoc or untracked clinical scenarios, MedResolve grounds all benchmark cases in verified **DDXPlus patient profiles** while applying controlled, reproducible perturbations.

---

## 2. Dataset Separation & Non-Overlap Guarantees

To prevent data contamination and snooping, the benchmark enforces three mathematical isolation rules:

1. **Strict Non-Overlap with Classifier Training:**
   - In Phase 2, a stratified development subset of 50,000 cases was drawn from `release_train_patients.csv` (`seed=42`).
   - The conflict benchmark draws patient cases exclusively from the remaining **975,602 unused training rows**.
   - **Verification:** Unit test `tests/test_conflict_detector.py::test_benchmark_cohort_disjointness_with_classifier_training` strictly asserts that the intersection of classifier training IDs and conflict benchmark IDs is $\emptyset$ (empty set).
2. **Official DDXPlus Test Split Untouched:**
   - The official DDXPlus test set (`release_test_patients.csv`, 134,529 cases) is preserved 100% untouched for final external evaluation in later project phases.
3. **Dev vs. Held-Out Evaluation Cohort Disjointness:**
   - The conflict benchmark is split into two non-overlapping 500-case cohorts:
     - **Development Cohort (Tuning Set):** 500 cases used to calibrate detector thresholds and verify rule logic.
     - **Held-Out Evaluation Cohort:** 500 cases reserved exclusively for unbiased metric reporting.

---

## 3. Cohort Composition & Class Balance

Both the Dev and Evaluation cohorts are balanced across conflict categories and include clean controls:

| Category / Cohort Partition | Dev Cohort (Cases) | Held-Out Eval Cohort (Cases) | Total Cases |
|---|---|---|---|
| `VALUE_OR_UNIT_DISCREPANCY` | 70 | 70 | 140 |
| `TEMPORAL_DISCREPANCY` | 70 | 70 | 140 |
| `SOURCE_STATEMENT_DISAGREEMENT` | 70 | 70 | 140 |
| `LOW_CONFIDENCE_EXTRACTION` | 70 | 70 | 140 |
| `MISSING_INFORMATION` | 70 | 70 | 140 |
| `ENTERED_OPINION_DISAGREEMENT` | 70 | 70 | 140 |
| **Clean Control Cases (No Conflict)** | **80** | **80** | **160** |
| **Total Cases** | **500** | **500** | **1,000** |

---

## 4. Controlled Perturbation Methodology

For each perturbed case, the original DDXPlus patient profile is first transformed into a baseline `EvidenceLedger` and then subjected to an isolated perturbation:

1. **`VALUE_OR_UNIT_DISCREPANCY`:**
   - Injects a paired vital observation (e.g. body temperature) from an external laboratory report with a divergent quantitative value ($103.8^\circ\text{F}$ vs. $98.6^\circ\text{F}$) during the same observation window.
2. **`TEMPORAL_DISCREPANCY`:**
   - Injects an impossible future observation date (`event_timestamp` set 10 days after `recorded_timestamp`).
3. **`SOURCE_STATEMENT_DISAGREEMENT`:**
   - Introduces an acute symptom entry where the patient self-reports `evidence_status=ABSENT`, but a simultaneous clinical progress note documents `evidence_status=PRESENT`.
4. **`LOW_CONFIDENCE_EXTRACTION`:**
   - Injects an OCR-extracted laboratory finding with confidence score $0.48 < 0.70$.
5. **`MISSING_INFORMATION`:**
   - Injects a numerical serum electrolyte finding with missing unit (`unit=None`).
6. **`ENTERED_OPINION_DISAGREEMENT`:**
   - Injects a second external physician opinion documenting a conflicting diagnostic impression.

---

## 5. Artifact Manifest & Reproducibility

Benchmark files are versioned in [`results/conflicts/`](file:///d:/MedResolve/results/conflicts):
- [`dev_conflict_ledgers.json`](file:///d:/MedResolve/results/conflicts/dev_conflict_ledgers.json) (500 patient ledgers)
- [`dev_conflict_ground_truth.json`](file:///d:/MedResolve/results/conflicts/dev_conflict_ground_truth.json) (500 ground-truth labels)
- [`eval_conflict_ledgers.json`](file:///d:/MedResolve/results/conflicts/eval_conflict_ledgers.json) (500 patient ledgers)
- [`eval_conflict_ground_truth.json`](file:///d:/MedResolve/results/conflicts/eval_conflict_ground_truth.json) (500 ground-truth labels)
- [`conflict_benchmark_manifest.json`](file:///d:/MedResolve/results/conflicts/conflict_benchmark_manifest.json) (Master metadata recording exact source indices and random seed `101`)

To regenerate the benchmark:
```powershell
python experiments/synthetic_conflict_generator.py
```
