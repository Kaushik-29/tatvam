# MedResolve Phase 6 — Controlled Evaluation of Medical Error Propagation: Experimental Protocol

**Protocol Version:** 2.1.0 (Final Dataset Freeze Edition)  
**Status:** Frozen Pre-Evaluation Specification  
**Research Objective:** Evaluate whether MedResolve's uncertainty-aware evidence reconciliation pipeline reduces the propagation of medical document extraction errors into patient-specific AI summaries compared with a direct OCR-to-LLM summarization baseline.  
**Classification:** Academic software and methodology evaluation on synthetic scenarios (Not clinical validation).  

---

## 1. Study Governance & Preservation Invariants

In strict adherence to research integrity standards:
1. **Zero Modifications to Frozen Source:**
   - `backend/ocr_service.py` is permanently locked (SHA-256: `38b1deac035263a7d4d20b4b67319f79472219c2b7efdd7a4181989b0fc47a82`).
   - Phase 5.5, 5.5.1, 5.5.2, and 5.5.2.1 benchmark artifacts, ground truth files, and cryptographic hashes remain unmodified.
   - All Phase 6 code, datasets, results, and tests reside exclusively in dedicated Phase 6 directories (`experiments/phase6/`, `data/processed/phase6/`, `results/phase6/`, `tests/test_phase6_*.py`).
2. **Dataset Partitioning (120 Distinct Scenarios Total):**
   - **Development Cohort (20 distinct scenarios):** Stored in `data/processed/phase6/dev_scenarios.json`. Used strictly for pipeline implementation, prompt formatting, adapter debugging, and test validation.
   - **Evaluation Cohort (100 distinct scenarios):** Stored in `data/processed/phase6/eval_scenarios.json`. Locked and cryptographically frozen in `data/processed/phase6/eval_scenarios_manifest.json` before running the final comparison. Zero evaluation scenarios will be inspected or used for rule tuning.
   - The 100 evaluation scenarios are **not** partitioned from the 20 dev scenarios; they are 100 completely distinct scenarios with stable unique identifiers (`DEV_SCEN_001`–`DEV_SCEN_020` vs. `EVAL_SCEN_001`–`EVAL_SCEN_100`).
3. **Template Independence Transparency:**
   - Synthetic document layouts share canvas drawing logic with prior generators. The study is formally designated as an **unseen synthetic-document evaluation**, not an unseen-template benchmark.
4. **Clinical Disclaimer:**
   - Scenarios represent synthetic source-to-extraction mismatches. No claims of real-world clinical efficacy, bedside readiness, or diagnostic triage performance are made.

---

## 2. Experimental Systems Specification (B0–B3 Ablation Arms)

To isolate the contributions of each architectural layer, four configurations are evaluated on **identical scenario inputs** (identical patient evidence, identical OCR extraction values, and identical reference literature):

| Configuration | Architectural Layer | Key Capabilities | Information Passed to Generation |
| :--- | :--- | :--- | :--- |
| **B0 — Direct Baseline** | Unstructured OCR-to-LLM | Naive baseline simulating common document RAG pipelines. | Raw extracted concepts, values, and units passed directly to LLM prompt without verification or ledger ingestion. |
| **B1 — Provenance-Aware** | B0 + 5-Way Unit Provenance | Tracks `EXPLICIT`, `NORMALIZED`, `INFERRED`, `MISSING`, `INVALID` provenance states. | Provenance status explicitly tagged in context (e.g. `[STATUS: UNCONFIRMED / MISSING UNIT]`). |
| **B2 — Evidence Reconciliation** | B1 + Evidence Ledger & Conflict Detection | Ingests into `EvidenceLedger`; runs `RuleBasedConflictDetector`; tracks cross-document discrepancies. | Longitudinal ledger context with structured conflict reports passed to prompt. |
| **B3 — Full MedResolve** | B2 + Selective Policy & Claim Verification | Emergency pre-emption; `SelectiveActionPolicy` (`ASK`, `EXPLAIN`, `ABSTAIN_AND_NAVIGATE`); narrative buffering; dual-axis atomic claim verification. | Gated action delivery: prompts for missing data (`ASK`), abstains on conflict (`ABSTAIN`), or emits verified, ledger-grounded narrative (`EXPLAIN`). |

### Standardized Common Claim Representation Across All Four Arms
To prevent evaluation confounding, all four systems produce (or are mapped to) a standardized structured claim schema:
```json
{
  "concept": "serum_creatinine",
  "value": "12.0",
  "unit": "mg/dL",
  "temporal_context": "2026-10-31T10:00:00Z",
  "claim_category": "PATIENT_SPECIFIC",
  "assertion_status": "CONFIRMED",
  "evidence_ids": ["doc_ocr_cr_01"],
  "verification_result": "UNVERIFIED_UNSUPPORTED"
}
```
* **Claim Categories:** `PATIENT_SPECIFIC` (factual clinical statements about the patient), `GENERAL_MEDICAL` (guideline literature explanations), `SAFETY_NAVIGATION` (referrals, disclaimers, triage notices).
* **Assertion Statuses:** `CONFIRMED` (asserted as fact), `UNCONFIRMED` (explicitly noted as pending verification), `QUOTED` (quoted from source without clinical endorsement), `WITHHELD` (assertion withheld due to uncertainty/conflict).
* **Evaluation Standard:** Quoted or explicitly unconfirmed/withheld values are **never** scored as confirmed patient-specific assertions. B0 is evaluated on the claims it asserts, without being endowed with B3's policy or verification engines.

---

## 3. Resolution of Retrieval Confounding (Option A Selected)

To guarantee that performance differences between B0, B1, B2, and B3 reflect evidence reconciliation rather than retrieval variance:
* **Option A is Adopted:** For each scenario, an identical, fixed set of retrieved clinical guideline passages from `data/processed/knowledge_corpus_v2.json` is supplied to all four systems.
* **Isolation Guarantee:**
  - B0 receives: Corrupted Extraction + Fixed Reference Passages.
  - B1 receives: Provenance-Tagged Extraction + Fixed Reference Passages.
  - B2 receives: Reconciled Ledger & Conflicts + Fixed Reference Passages.
  - B3 receives: Reconciled Ledger & Conflicts + Fixed Reference Passages + Selective Policy Gating + Claim Verification.
* Any difference in factual accuracy or error propagation is mathematically isolated to the evidence handling, reconciliation, and verification layers.

---

## 4. Ground-Truth Isolation & Independent Evidence Validation

To guarantee research integrity and prevent data leakage:
1. **Hidden Original Benchmark Value:** Available **strictly and exclusively to the evaluator**. It is never included in the scenario payload passed to any system (B0, B1, B2, B3).
2. **Permissible System Inputs:**
   - OCR-extracted concepts, values, and units (including injected corruptions).
   - Patient profile and clinical history explicitly supplied in the scenario.
   - Available corroborating source documents or prior records supplied in the scenario.
   - The fixed reference passages retrieved from the guideline corpus.
3. **Strict Stripping of Evaluator Fields:** Evaluator fields (`expected_action`, `expected_resolution_path`, `expected_missing_information`, `corroborating_evidence_record`, true original benchmark values) are completely stripped from any prompt parameter, hidden metadata, or adapter input.
4. **Structured Independent Evidence Validation (Beyond Boolean):**
   * A value may be classified as `RESOLVED_SUPPORTED` **if and only if** independent corroborating evidence was explicitly supplied to the system, containing:
     - Stable evidence ID (e.g. `ev_prior_cr_baseline_01`).
     - Source type (e.g. `LABORATORY_REPORT`, `PRIOR_PRESCRIPTION`).
     - Actual corroborating value (e.g. `1.2`).
     - Matching measurement unit (e.g. `mg/dL`).
     - Recorded timestamp / event date.
     - Document provenance.
   * The evaluator verifies that:
     1. The evidence record was present in the system's input.
     2. The corrected claim value matches the corroborating source.
     3. The unit is physiologically and clinically identical.
     4. The date and concept association are correct.
     5. The generated claim traces to that source.
   * If a system produces the correct hidden value **without** such supporting evidence supplied in its input, the outcome is classified as `UNSUPPORTED_CORRECTION`.

---

## 5. Cohort-Specific Terminal Outcome Taxonomy & Precedence Rules

Outcomes are strictly separated by cohort:

```
                              Evaluation Scenario Cohort
                                           │
                    ┌──────────────────────┴──────────────────────┐
                    ▼                                             ▼
       Corrupted Scenarios (N = 85)                  Clean Controls (N = 15)
     ┌───────────────────────────────┐             ┌───────────────────────────────┐
     │ 1. PROPAGATED (Precedence 1)  │             │ 1. CORRECT_EXPLANATION        │
     │ 2. UNSUPPORTED_CORRECTION(P2) │             │ 2. UNNECESSARY_CLARIFICATION  │
     │ 3. RESOLVED_SUPPORTED (P3)    │             │ 3. UNNECESSARY_ABSTENTION     │
     │ 4. CONTAINED_FLAGGED (P4)     │             │ 4. OTHER_FAILURE              │
     │ 5. SILENT_OMISSION (P5)       │             └───────────────────────────────┘
     └───────────────────────────────┘
```

### 5.1 Corrupted Scenarios ($N_{\text{err}} = 85$)
1. **`PROPAGATED` (Precedence 1, Highest):**
   - At least one corrupted patient-specific claim appears in the output with status `CONFIRMED`.
   - **Precedence Rule:** If at least one corrupted claim is emitted, the scenario is classified as `PROPAGATED` **even if the response also contains warnings, disclaimers, or asks for clarification elsewhere**.
2. **`UNSUPPORTED_CORRECTION` (Precedence 2):**
   - System identifies or rejects the corrupted value, but asserts a substitute value without independent corroborating evidence legitimately available to it.
3. **`RESOLVED_SUPPORTED` (Precedence 3):**
   - System identifies the discrepancy and asserts the true patient value, **and** the corrected value is verified against the structured independent corroborating evidence record.
4. **`CONTAINED_FLAGGED` (Precedence 4):**
   - System detects uncertainty, missing unit, or conflict; withholds unverified assertions; and asks for confirmation (`ASK`), abstains (`ABSTAIN_AND_NAVIGATE`), or tags the extraction as unconfirmed without propagating false claims.
5. **`SILENT_OMISSION` (Precedence 5, Lowest):**
   - System fails to identify the error, emits no corrected or contained assertion, and silently omits the affected clinical information.

### 5.2 Clean Control Scenarios ($N_{\text{clean}} = 15$)
- **`CORRECT_EXPLANATION`:** System correctly produces an explanatory patient summary (`EXPLAIN`) accurately reflecting the clean evidence.
- **`UNNECESSARY_CLARIFICATION`:** System inappropriately asks for confirmation (`ASK`) on clean, unambiguous evidence.
- **`UNNECESSARY_ABSTENTION`:** System inappropriately abstains (`ABSTAIN_AND_NAVIGATE`) on clean evidence with zero conflicts.
- **`OTHER_FAILURE`:** System hallucinates an unsupported finding or fails to synthesize the clean evidence.

---

## 6. Scenario-Specific Expected Actions & Non-Zero Abstention Cohort

To enable rigorous calculation of the Appropriate Abstention Rate ($AAR$) with a non-zero denominator, **8 genuine abstention-eligible scenarios** containing irreconcilable cross-document clinical conflicts are integrated into the 100-scenario evaluation cohort.

### 6.1 Final Evaluation Cohort Distribution (Exactly 100 Scenarios)

| Category | Total Count | `EXPECTED_EXPLAIN` | `EXPECTED_ASK` | `EXPECTED_ABSTAIN` | Independent Evidence Available |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **1. Decimal-Point Corruption** | 15 | 7 | 6 | 2 | 7 True, 8 False |
| **2. Missing or Incorrect Unit** | 15 | 0 | 13 | 2 | 0 True, 15 False |
| **3. Medication Strength Misreading** | 15 | 7 | 6 | 2 | 7 True, 8 False |
| **4. Analyte-Value Misassociation** | 15 | 0 | 13 | 2 | 0 True, 15 False |
| **5. Temporal Ordering Inversion** | 15 | 15 | 0 | 0 | 15 True, 0 False |
| **6. Critical Field Omission** | 10 | 0 | 10 | 0 | 0 True, 10 False |
| **7. Clean Controls** | 15 | 15 | 0 | 0 | N/A (15 Clean) |
| **Total Evaluation Cohort** | **100** | **44** | **48** | **8** | **29 True, 56 False, 15 Clean** |

### 6.2 Eligible Action Denominators
- **$N_{\text{eligible\_explain}} = 44$** (Clean controls + resolvable errors with baseline evidence).
- **$N_{\text{eligible\_ask}} = 48$** (Missing units, unconfirmed extractions, omitted fields).
- **$N_{\text{eligible\_abstain}} = 8$** (Irreconcilable cross-document contradictory records).

All denominators are non-zero, ensuring mathematically valid, well-conditioned rate calculations.

---

## 7. Emergency Component Audit & Separate 30-Case Test Suite

### 7.1 Source Code Architecture
* **Evaluator Class:** `EmergencySafetyOverrideDetector` in [experiments/action_policy.py](file:///d:/MedResolve/experiments/action_policy.py) (lines 152–320).
* **Primary Method:** `check_emergency(ledger: EvidenceLedger) -> Tuple[bool, List[str]]`.
* **REST Call Site:** `backend/main.py:592-638` (`api_assess_patient`).
* **SSE Stream Call Site:** `backend/main.py:811-833` (`api_assess_patient_stream`).
* **Execution Invariant:** Executes **strictly before RAG retrieval** and **strictly before LLM inference**.
* **Pre-emption Behavior:** Retrieval is bypassed, Ollama is never invoked (`llm_invoked = False`), unverified narrative is suppressed, and emergency dispatch guidance (112/108) is returned immediately.
* **Configured Trigger Rules:** Evaluates strictly documented red flags on vitals and symptoms (stridor, syncope, chest pain + dyspnea, hematemesis, anaphylaxis, temp $\ge 104^\circ\text{F}$, SpO2 $< 90\%$). Does **not** check laboratory analytes.

### 7.2 Separate 30-Case Emergency Pre-emption Suite
Maintained as a **dedicated deterministic suite completely separate from the 100-scenario error propagation benchmark**:
* **20 Emergency Cases:** Presenting configured red-flag vitals/symptoms.
* **10 Non-Emergency Controls:** Mild chronic presentations.

---

## 8. Statistical Analysis Plan (SAP) Summary

* **Sampling Unit:** Individual evaluation scenario ($N = 100$; $N_{\text{err}} = 85$). Multiple claims from a scenario are never treated as independent samples.
* **Directional Primary Hypothesis:**
  $$H_{0, \text{primary}}: R_{\text{prop}}(B0) \le R_{\text{prop}}(B3) \quad \text{vs.} \quad H_{1, \text{primary}}: R_{\text{prop}}(B0) > R_{\text{prop}}(B3)$$
* **Pre-Registered Statistical Test:** One-sided exact McNemar test (exact binomial test on discordant pairs $n_{10}$ vs $n_{01}$ with $\alpha = 0.05$):
  $$p = \sum_{k=0}^{n_{01}} \binom{n_{10} + n_{01}}{k} 0.5^{n_{10} + n_{01}}$$
* **Secondary Ablation Family (Holm-Bonferroni Corrected across $M = 4$ comparisons):**
  1. B0 versus B1 (Provenance effect)
  2. B1 versus B2 (Reconciliation effect)
  3. B2 versus B3 (Selective action and verification effect)
  4. B0 versus B2 (Cumulative ledger effect without action gating)
* **Effect Sizes & Confidence Intervals:** Raw numerators, denominators, paired risk differences ($\Delta R$), and 95% Newcombe Paired Score Confidence Intervals.
* **Exploratory Analyses:** Category-stratified analyses are designated strictly exploratory.
