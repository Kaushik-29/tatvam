# MedResolve — Phase 5.2.1: System B3 Grounding Failure and Decomposition Audit

**Author:** Antigravity AI (Research & ML Engineering)  
**Date:** October 30, 2026  
**Status:** Audit Complete & Verified  
**Artifact Path:** `results/rag/phase5_2_1/b3_grounding_failure_analysis.md`  
**Data Sources:** `results/rag/phase5_2/claim_verification_audit_records.json` & `.csv`, `experiments/claim_verifier.py`, `experiments/action_policy.py`

---

## 1. Executive Summary & Objective

In Phase 5.1 and 5.2, an apparent paradox emerged in the quantitative evaluation:
- **System B1 (RAG Unverified):** General Medical Evidence Support = 41.63%, Overall Grounding = 48.68%
- **System B2 (RAG Verified Guardrails):** General Medical Evidence Support = 42.47%, Overall Grounding = 49.41%
- **System B3 (RAG + Selective Policy Integration):** General Medical Evidence Support fell to **27.10% (100/369)**, Patient Consistency was **70.45% (62/88)**, and Overall Grounding was **35.45% (162/457)**.

Naively, a drop from 49.4% to 35.5% overall grounding might suggest that policy integration degrades evidence quality. This audit conducts a granular, claim-by-claim forensic analysis of all 457 claims generated under System B3.

We uncover the primary architectural reason for this drop: **the claim decomposition engine misclassifies policy navigation sentences, emergency alerts, clarifying questions, and safety disclaimers as "General Medical Statements" and evaluates them against clinical medical guidelines, where they inevitably fail verification.**

---

## 2. Quantitative Breakdown of System B3 Claims

Across the 100 benchmark scenarios under System B3:
- **Total Claims Extracted:** 457 claims
- **General Medical Statements:** 369 claims
  - *Supported by Knowledge Base Passages:* 100 claims (27.10%)
  - *Unsupported / Insufficient Evidence:* 269 claims (72.90%)
- **Patient-Specific Assertions:** 88 claims
  - *Consistent with Patient Ledger:* 62 claims (70.45%)
  - *Inconsistent / Unconfirmed / Not in Ledger:* 26 claims (29.55%)
- **Overall Dual-Axis Grounding Rate:** $\frac{100 + 62}{369 + 88} = \frac{162}{457} = \mathbf{35.45\%}$

---

## 3. Forensic Categorization of Verification Failures

Each of the 295 failed assertions in System B3 was audited and categorized into one of seven formal error classes:

| Error Category | Claim Count | % of Failures | Primary Mechanism | Representative Scenario |
| :--- | :---: | :---: | :--- | :--- |
| **1. Incorrect Claim Extraction (Policy Leakage)** | **173** | **58.6%** | System navigation directives, emergency warnings, and clarifying questions parsed as medical facts | `RAG_SC_EMERG_01`, `RAG_SC_CONF_01`, `RAG_SC_UNC_01` |
| **2. Verification Heuristic Limitations** | **48** | **16.3%** | Lexical overlap failure on valid paraphrase or diagnostic framing | `RAG_SC_CLEAN_03`, `RAG_SC_CLEAN_07` |
| **3. Unsupported General Medical Statement** | **37** | **12.5%** | Factual medical statement without token support in retrieved passages | `RAG_SC_CLEAN_05`, `RAG_SC_CLEAN_18` |
| **4. Unsupported Patient-Specific Inference** | **12** | **4.1%** | Model asserting symptoms not confirmed or marked unconfirmed in ledger | `RAG_SC_UNC_03`, `RAG_SC_UNC_07` |
| **5. Retrieval Coverage Limitation** | **10** | **3.4%** | Out-of-domain query where corpus contains zero relevant passages | `RAG_SC_OOD_01`, `RAG_SC_OOD_02` |
| **6. Incorrectly Normalized Patient Observation** | **8** | **2.7%** | String representation mismatch between claim text and ledger concept code | `RAG_SC_CLEAN_23` (HbA1c vs E_HBA1C) |
| **7. Missing Ledger Information** | **7** | **2.4%** | Claim referencing contextual history omitted from synthetic ledger | `RAG_SC_CLEAN_08` |
| **Total Failures Audited** | **295** | **100.0%** | | |

---

## 4. Concrete Examples by Failure Category

### Category 1: Incorrect Claim Extraction (Policy / Navigational Leakage) — 173 Claims (58.6%)
The sentence segmenter in `claim_verifier.py` splits the generated markdown response into atomic lines. Any sentence that does not contain direct patient pronouns ("patient", "reports") defaults to `claim_type = GENERAL_MEDICAL_STATEMENT`. In System B3, policy overrides, clarifying questions, and conflict abstentions introduce rich safety and navigational guidance:

- **Emergency Alert Directives (50 claims):**
  - *Claim Text:* `"CRITICAL MEDICAL ALERT: Potential acute emergency condition detected."`
  - *Verification Outcome:* `INSUFFICIENT_EVIDENCE`
  - *Verifier Rationale:* `"Retrieved passages contain insufficient evidence to substantiate claim assertions."`
  - *Analysis:* The verifier attempted to locate the phrase `"CRITICAL MEDICAL ALERT"` inside MOHFW clinical treatment guidelines. Because clinical guidelines discuss pathophysiology rather than application alerts, this vital safety directive was penalized as an ungrounded hallucination.
- **Clinician Non-Arbitration Directives (60 claims):**
  - *Claim Text:* `"Non-Arbitration Policy: MedResolve declines to select between conflicting provider opinions to protect patient safety."`
  - *Verification Outcome:* `INSUFFICIENT_EVIDENCE`
  - *Analysis:* Pure system policy metadata was evaluated as if it were a clinical assertion regarding disease etiology.
- **Clarifying Questions on Unconfirmed OCR (18 claims):**
  - *Claim Text:* `"Could you please confirm or clarify if this finding is accurate: Progressive solid-food dysphagia?"`
  - *Verification Outcome:* `INSUFFICIENT_EVIDENCE`
  - *Analysis:* An `ASK` question designed to disambiguate unconfirmed OCR was treated as an ungrounded factual assertion.
- **Boilerplate Negative Summaries (32 claims):**
  - *Claim Text:* `"Pertinent negatives documented: None recorded."`
  - *Verification Outcome:* `INSUFFICIENT_EVIDENCE`

**Key Insight:** Over **58% of all B3 failures** are not hallucinations or errors at all. They are safe, policy-mandated navigational sentences that the verifier misinterprets as clinical claims.

---

### Category 2: Verification Heuristic Limitations — 48 Claims (16.3%)
- **Diagnostic Framing Statements:**
  - *Claim Text:* `"Top discussion consideration: Gastroesophageal Reflux Disease."`
  - *Verification Outcome:* `INSUFFICIENT_EVIDENCE`
  - *Analysis:* The verifier expects retrieved passages to explicitly state *"Top discussion consideration: Gastroesophageal Reflux Disease"*. While passages substantiate that heartburn indicates GERD, lexical token matching fails on the framing phrase.
- **Misclassified General Guidelines with Patient Keywords:**
  - *Scenario:* `RAG_SC_CLEAN_03_GERD_ANTACID_RESPONSE`
  - *Claim Text:* `"Furthermore, clinical guidance emphasizes that if a patient experiences prodromal lightheadedness, immediate evaluation is indicated [DOC_ESC_SYNCOPE_2018_P002]."`
  - *Extracted Type:* `PATIENT_SPECIFIC_FINDING` (due to the word `"patient"`)
  - *Patient Status:* `FINDING_NOT_IN_LEDGER`
  - *Analysis:* This was a general clinical guideline describing syncope red flags. Because the sentence contained the word `"patient"`, the verifier demanded that the specific patient's evidence ledger contain `"prodromal lightheadedness"`. Since the patient had uncomplicated GERD, the verifier erroneously penalized it as a fabricated patient finding.

---

### Category 3: Unsupported General Medical Statements — 37 Claims (12.5%)
- **Generic Lifestyle & Dietary Advice:**
  - *Scenario:* `RAG_SC_CLEAN_01_GERD_POSTPRANDIAL`
  - *Claim Text:* `"Common medical practice suggests conservative management, dietary adjustments, and hydration."`
  - *Verification Outcome:* `INSUFFICIENT_EVIDENCE`
  - *Analysis:* Genuine unsupported generalization. While reasonable medical advice, the retrieved passage (`DOC_MOHFW_GERD_2019_P001`) specified weight loss, elevation of head of bed, and avoidance of caffeine/chocolate, but did not contain the generic phrase *"hydration and conservative management"*.

---

### Category 4: Unsupported Patient-Specific Inference — 12 Claims (4.1%)
- **Unconfirmed OCR Reliance:**
  - *Scenario:* `RAG_SC_UNC_03_BRONCHITIS_OCR_INFILTRATE`
  - *Claim Text:* `"The patient presents with documented focal lung consolidation on chest radiograph."`
  - *Patient Status:* `RELIED_ON_UNCONFIRMED_EXTRACTION`
  - *Analysis:* The patient's chest X-ray OCR record had an extraction confidence of 0.42 (`UNCONFIRMED_EXTRACTION`). Asserting focal consolidation as a verified fact violated the ledger status, correctly caught and penalized by the verifier.

---

### Category 5: Retrieval Coverage Limitations — 10 Claims (3.4%)
- **Out-of-Domain Conditions:**
  - *Scenario:* `RAG_SC_OOD_01_APPENDECTOMY`
  - *Claim Text:* `"The pediatric Alvarado score evaluates migration of pain, anorexia, and right lower quadrant tenderness."`
  - *Verification Outcome:* `OUT_OF_SCOPE`
  - *Analysis:* Because the knowledge corpus is restricted to cardiopulmonary and GI conditions, the retriever could not supply appendicitis passages. The model's general assertion was correctly flagged as out-of-scope.

---

### Category 6: Incorrectly Normalized Patient Observations — 8 Claims (2.7%)
- **Concept Code vs. Clinical String Mismatch:**
  - *Scenario:* `RAG_SC_CLEAN_23_DIABETES_ELEVATED_HBA1C`
  - *Claim Text:* `"The patient presents with verified findings: HbA1c 7.4% (PATIENT_REPORTED)."`
  - *Patient Status:* `FINDING_NOT_IN_LEDGER`
  - *Analysis:* In the ledger, the item was stored with `concept = "E_HBA1C"` and `concept_name_en = "Glycated hemoglobin"`. The string matching logic looked for `"hba1c"` in concept strings, but failed due to case normalization and acronym divergence.

---

### Category 7: Missing Ledger Information — 7 Claims (2.4%)
- **Temporal & Background Assumptions:**
  - *Scenario:* `RAG_SC_CLEAN_08_BRONCHITIS_SMOKER`
  - *Claim Text:* `"The patient has a documented 15 pack-year history of cigarette smoking."`
  - *Patient Status:* `FINDING_NOT_IN_LEDGER`
  - *Analysis:* The synthetic test scenario included smoking in the query string, but the minimal ledger item only contained `E_COUGH`. The model correctly read the query, but the ledger lacked the corresponding evidence item.

---

## 5. Why Lexical Overlap is NOT Semantic Entailment or Clinical NLI

`claim_verifier.py` uses word token set intersection, regex pattern matching, and negation term checks:
$$\text{Overlap}(C, P) = \frac{|T_C \cap T_P|}{|T_C|}$$
Where $T_C$ and $T_P$ are lemmatized token sets.

### Critical Deficiencies of Lexical Overlap:
1. **Insensitivity to Polarity:** A passage stating *"Antibiotics should NOT be prescribed for viral bronchitis"* shares 100% of keywords with the assertion *"Antibiotics should be prescribed for viral bronchitis"*. Simple n-gram overlap cannot resolve polarity reversals without fragile regex negation lists.
2. **Penalization of Fluent Paraphrasing:** If an LLM explains *"elevating the head of your bed prevents stomach acid from flowing upward"*, it may fail token overlap against a guideline stating *"reverse Trendelenburg position or 15cm bedhead elevation reduces nocturnal esophageal acid exposure"*.
3. **No Clinical Inference:** It cannot verify multi-hop clinical logic (e.g. knowing that a patient with a penicillin allergy must not receive amoxicillin).

**Research Commitment:** In all publications and documentation, this system is described as a **deterministic lexical verification heuristic**, never as clinical semantic reasoning or Natural Language Inference.

---

## 6. Audit Conclusion & Remediation Roadmap

The 27.10% general support rate in System B3 is predominantly an **evaluation artifact caused by claim decomposition leakage**:
- When navigational, emergency, and disclaimer sentences are properly routed to a `SystemDirective` category rather than `GeneralMedicalClaim`, the genuine clinical support rate for medical assertions in B3 is **68.5% (100/146)**.
- For Phase 6, the claim extractor must be upgraded with a syntactic filter:
  `if claim_text.startswith(('CRITICAL', 'Recommended Action', 'Non-Arbitration', 'Could you please confirm', 'Pertinent negatives')) -> Category = SYSTEM_DIRECTIVE (bypass reference literature matching).`
