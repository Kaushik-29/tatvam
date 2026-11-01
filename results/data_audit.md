# MedResolve — DDXPlus Comprehensive Dataset Audit Report

**Audit Timestamp:** 2026-10-29 19:24:07 UTC  
**Dataset:** DDXPlus (Mila / IQIA release)  
**Audit Status:** COMPLETED  
**Execution Runtime:** 86.99 seconds  

---

## 1. Executive Summary

The official DDXPlus diagnostic benchmark files were successfully validated, extracted, and audited. The dataset is complete, structurally sound, and exhibits 100% adherence to its documented specification across all splits.

- **Total Patient Records:** 1,292,579
- **Total Uncompressed Size:** 807.32 MB
- **Diagnostic Target Pathologies:** 49 classes (all covered across splits)
- **Engineered Evidence Tokens:** 972 tokens (974 total input features including normalized Age and Sex)
- **Feature Sparsity:** 97.83% (enables ultra-fast CPU training via sparse CSR matrices)
- **Data Hygiene:** 0 missing values across all 1,292,579 rows and all columns.

---

## 2. Dataset Split Breakdown

| Split | Records | Uncompressed Size | Unique Classes | Age Range | Sex Ratio (M / F) | Missing Values |
|---|---|---|---|---|---|---|
| **Train** | 1,025,602 | 639.5 MB | 49 / 49 | 0 - 109 yrs | 497,804 / 527,798 | 0 |
| **Validate** | 132,448 | 83.3 MB | 49 / 49 | 0 - 109 yrs | 64,315 / 68,133 | 0 |
| **Test** | 134,529 | 84.5 MB | 49 / 49 | 0 - 109 yrs | 65,187 / 69,342 | 0 |
| **Total** | **1,292,579** | **807.32 MB** | **49 / 49** | **1 - 104 yrs** | — | **0** |

---

## 3. Evidence & Pathology Metadata

- **Conditions Cataloged:** 49
- **Raw Evidence Definitions:** 223
  - Binary Evidences (`B`): 208
  - Categorical Evidences (`C`): 10
  - Multi-Choice Evidences (`M`): 5
- **Antecedents vs. Symptoms:** 113 Antecedents, 110 Symptoms
- **Engineered Sparse Feature Dimensions:** 974 features (1 Age normalized + 1 Sex binary + 972 Evidence tokens)

### Condition Severity Distribution
Pathology severity ratings defined in `release_conditions.json` (where lower values denote higher acuity):
- **Severity 1 (Critical / Emergent):** 5 conditions
- **Severity 2 (Urgent):** 12 conditions
- **Severity 3 (Semi-urgent):** 17 conditions
- **Severity 4 (Non-urgent / Routine):** 12 conditions
- **Severity 5 (Minor / Chronic):** 3 conditions

---

## 4. Ground-Truth Pathology & Differential Diagnosis Analysis

Each patient record contains:
1. `PATHOLOGY`: Ground-truth condition diagnosed.
2. `DIFFERENTIAL_DIAGNOSIS`: Expert-system generated probability distribution over candidate pathologies.

### Differential Diagnosis Quality (10k Sample Benchmark)
| Metric | Validate Split | Test Split | Train Split |
|---|---|---|---|
| **Average Differential Candidates** | 9.32 | 9.15 | 9.06 |
| **Ground Truth in Top-1 of Differential** | 72.88% | 73.51% | 73.87% |
| **Ground Truth in Top-3 of Differential** | 92.89% | 92.76% | 93.00% |
| **Average Evidences per Patient** | 20.2 | 20.0 | 19.2 |

---

## 5. Data Hygiene & Leakage Prevention Verification

- **Schema Check:** All 6 expected columns (`AGE`, `DIFFERENTIAL_DIAGNOSIS`, `SEX`, `PATHOLOGY`, `EVIDENCES`, `INITIAL_EVIDENCE`) are present and identical across train, validate, and test.
- **Null Values:** Zero missing or NaN values detected in any split.
- **Target Leakage Safeguard:** Feature matrix extraction explicitly asserts that `PATHOLOGY` and `DIFFERENTIAL_DIAGNOSIS` are never included in the input feature space.
- **50,000 Record Dev Subset:** Evaluated in 8.26 MB of RAM using scipy CSR representation (185.78 MB dense equivalent).

---

## 6. Recommendations for Baseline Experimentation

1. **Development Subset:** Use the reproducible 50,000-sample dev subset (seed 42) for initial model iterations to maintain sub-minute experiment cycles.
2. **Classifier Selection:** Use `SGDClassifier(loss='log_loss')` or `LogisticRegression` as the primary linear baseline. Both support probabilistic ranked predictions needed for Top-3 accuracy.
3. **Benchmark Comparisons:** Compare against `DummyClassifier(strategy='most_frequent')` as the absolute lower bound.
