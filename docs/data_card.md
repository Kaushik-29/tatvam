# MedResolve: Dataset Card — DDXPlus

## 1. Dataset Summary
- **Dataset Name:** DDXPlus
- **Origin / Creators:** Mila – Quebec AI Institute & Dialogue Technologies (Fraiwan et al., 2022 / 2023)
- **License:** Creative Commons Attribution (CC-BY 4.0)
- **Official Repository:** [https://mila-iqia.github.io/ddxplus/](https://mila-iqia.github.io/ddxplus/)
- **Target Task:** Automatic Symptom Detection (ASD) and Automatic Diagnosis (AD) in primary and acute care.

---

## 2. Dataset Composition & Dimensions

| Partition | Record Count | Uncompressed Size | Format | Primary Role |
|---|---|---|---|---|
| **Train** | 1,025,602 | 670.6 MB | CSV (UTF-8) | Benchmark model training |
| **Validate** | 132,448 | 87.4 MB | CSV (UTF-8) | Hyperparameter tuning and validation |
| **Test** | 134,529 | 88.6 MB | CSV (UTF-8) | Final unbiased benchmark evaluation |
| **Total** | **1,292,579** | **846.6 MB** | — | — |

---

## 3. Data Schema & Feature Definitions

Each record in `release_<split>_patients.csv` contains 6 fields:

1. **`AGE`** (*integer*): Age of the patient in years (observed range: 1 to 104).
2. **`SEX`** (*categorical*): Biological sex (`M` for male, `F` for female).
3. **`PATHOLOGY`** (*string*): Ground-truth target condition diagnosed. Drawn from a closed set of 49 distinct pathologies (e.g., `Anemia`, `Influenza`, `Spontaneous pneumothorax`, `GERD`).
4. **`EVIDENCES`** (*list of strings*): Complete set of active signs, symptoms, and antecedents experienced by the patient. Encoded as:
   - Binary evidence: `[evidence_name]` (e.g., `'E_53'`)
   - Categorical / Multi-choice: `[evidence_name]_@_[value]` (e.g., `'E_54_@_V_180'`)
5. **`INITIAL_EVIDENCE`** (*string*): The initial presenting complaint provided by the patient at the start of an interaction (randomly drawn from the patient's binary evidence list).
6. **`DIFFERENTIAL_DIAGNOSIS`** (*list of pairs*): Expert-system generated probability distribution over candidate diagnoses: `[[patho_1, prob_1], [patho_2, prob_2], ...]`.

### Metadata Files
- **`release_conditions.json`**: Catalogs 49 pathologies with English/French names, ICD-10 identifiers, clinical severity ratings (1 to 5), and known symptom/antecedent associations.
- **`release_evidences.json`**: Catalogs 223 evidence definitions across binary (`B`: 208), categorical (`C`: 10), and multi-choice (`M`: 5) types, mapping to 972 unique token values.

---

## 4. Synthesis Methodology & Clinical Assumptions
DDXPlus was constructed using a proprietary medical knowledge graph and a commercial rule-based diagnostic engine.
- Synthetic generation simulates acute care visits.
- Pathologies were curated focusing on acute and emergent presentations with high morbidity/mortality risks.
- Probabilistic Bayesian sampling was applied to generate realistic symptom co-occurrences conditioned on pathology and demographics.

---

## 5. Critical Clinical Limitations & Biases
> [!IMPORTANT]
> **Synthetic Cohort Caveat:** DDXPlus does NOT contain actual human clinical encounters. As acknowledged by the original authors (Mila):
> 1. Results obtained on DDXPlus cannot establish safety or efficacy in real-world clinical practice.
> 2. The dataset exhibits acute-care bias: routine primary care and multi-morbid chronic conditions are under-represented relative to emergency presentations.
> 3. Negative findings: in real clinical environments, negative observations (absence of fever, absence of chest pain) carry vital discriminating power; DDXPlus primarily records positive activations.
> 4. Closed Pathology Space: 49 conditions do not cover the complete ICD-10 diagnostic ontology. Models trained on it cannot diagnose out-of-distribution conditions.
