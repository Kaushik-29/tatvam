# MedResolve: Experiment Protocol & Evaluation Standards

## 1. Experimental Integrity & Data Hygiene Rules

To ensure scientific validity and reproducibility, all MedResolve experiments must comply with the following standards:

1. **Strict Partition Preservation:**
   - Under no circumstances may records from `validate` or `test` be merged into `train`.
   - The official splits must be respected:
     - Train: 1,025,602 cases (or official dev subset)
     - Validate: 132,448 cases
     - Test: 134,529 cases
2. **Zero Target Leakage Policy:**
   - `PATHOLOGY` is strictly reserved as the target array $y$.
   - `DIFFERENTIAL_DIAGNOSIS` is an expert target probability distribution and must NEVER be transformed into input features.
   - Any model found using target-derived signals in feature matrix $X$ is disqualified.
3. **Reproducibility Guarantee:**
   - All subset selections, random initializations, and model seeds must be explicitly set (`seed=42`).
   - Every experiment must record script parameters, subset size, hardware specs, and software versions.

---

## 2. Benchmark Metrics

Diagnostic models are evaluated on multi-class classification across 49 candidate pathologies:

### Primary Metrics
- **Top-1 Accuracy:** Percentage of cases where the model's highest probability prediction matches the ground-truth `PATHOLOGY`.
  $$\text{Top-1} = \frac{1}{N} \sum_{i=1}^N \mathbb{I}(\hat{y}_{i, \text{rank}=1} = y_i)$$
- **Top-3 Accuracy:** Percentage of cases where ground-truth `PATHOLOGY` appears in the top-3 ranked predicted probabilities.
  $$\text{Top-3} = \frac{1}{N} \sum_{i=1}^N \mathbb{I}(y_i \in \hat{\mathcal{Y}}_{i, \text{top-3}})$$
- **Macro-Averaged F1 Score:** Unweighted mean of F1 scores across all 49 classes. Ensures equal consideration of rare/critical acute pathologies regardless of class prevalence.
  $$\text{Macro-F1} = \frac{1}{C} \sum_{c=1}^C F1_c$$

### Secondary & Diagnostic Metrics
- **Per-Class Precision & Recall:** Assesses performance disparities across conditions (e.g., high-risk conditions like *Anaphylaxis* or *Spontaneous pneumothorax* vs. common conditions like *URTI*).
- **Confusion Matrix:** Identifies systemic pairwise confusions between clinically similar conditions.

---

## 3. Development Subset Strategy
- Full training on 1,025,602 cases is computationally demanding for rapid prototyping.
- A **development subset of 50,000 cases** (`seed=42`) with stratified representation across all 49 pathologies is designated for model tuning and architecture selection.
- Once hyperparameter decisions are fixed, full-scale runs may be executed for final publication benchmarks.

---

## 4. Evaluation Settings: Full Evidence vs. Initial Presentation

To rigorously evaluate diagnostic triage and provide empirical justification for active inquiry agents, MedResolve standardizes two distinct input evidence regimes:

1. **Full Evidence Setting (`evidence_mode="all"`):**
   - The model observes `AGE`, `SEX`, and the complete multi-hot vector of all positive symptoms and antecedents (`EVIDENCES`).
   - Represents the theoretical upper bound for static supervised classification when an exhaustive clinical inquiry has already occurred.
2. **Initial Presentation Setting (`evidence_mode="initial"`):**
   - The model observes only `AGE`, `SEX`, and the single starting complaint (`INITIAL_EVIDENCE`).
   - Models the initial triage state at patient arrival before follow-up questions or diagnostic tests.
   - Demonstrates the necessity for active information-seeking agents (EviDx paradigm) to resolve clinical ambiguity.

---

## 5. Phase 2 Empirical Baseline Results (Validation Split: 132,448 cases)

Trained on a reproducible 50,000-sample dev subset (`seed=42`) sampled from the official training split, and evaluated on the full official validation split:

| Model | Evidence Mode | Top-1 Accuracy | Top-3 Accuracy | Macro-F1 | Weighted-F1 | Training Fit Time | Primary Failure Mode / Characteristic |
|---|---|---|---|---|---|---|---|
| **Majority-Class** | ALL | 6.54% | 13.17% | 0.0025 | 0.0080 | 0.00s | Trivial lower bound. Predicts most frequent class across all cases. |
| **SGD Log-Loss** | ALL | **99.62%** | **100.00%** | **0.9942** | **0.9962** | 0.52s | Static upper bound. Full evidence set allows near-perfect condition separation. |
| **Majority-Class** | INITIAL | 6.54% | 13.17% | 0.0025 | 0.0080 | 0.00s | Trivial lower bound. Unaffected by evidence input. |
| **SGD Log-Loss** | INITIAL | **36.71%** | **60.66%** | **0.3475** | **0.3604** | 0.34s | Initial triage triage bound. Severe ambiguity in generic acute presentations. |

### Clinical Insights from the Initial Presentation Setting
- **Pathognomonic presentations succeed:** Conditions with unique starting symptoms achieve high triage accuracy (e.g., *Acute dystonic reactions* F1=0.8896, *Whooping cough* F1=0.8423, *Guillain-Barré syndrome* F1=0.7507).
- **Generic respiratory / pulmonary symptoms collapse:** Conditions that initially present with non-specific cough, fever, or chest pain collapse into near-zero recognition without active questioning (e.g., *Spontaneous pneumothorax* F1=0.0000, *Tuberculosis* F1=0.0040, *Pneumonia* F1=0.0097).
- **Motivation for Phase 3 & 4:** Confirms the core thesis of MedResolve: static classification on initial patient complaints is clinically insufficient; active evidence acquisition, source tracking, and uncertainty-aware abstention are mandatory.

