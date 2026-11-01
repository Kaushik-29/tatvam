# MedResolve Phase 6 — Component Capability Audit and Provenance Specification

**Document Version:** 2.1.0 (Final Dataset Freeze Edition)  
**Status:** Frozen Pre-Evaluation Specification  
**Scope:** Exhaustive code-level inspection of existing MedResolve modules, standardized 5-way unit provenance, detailed emergency execution call sequence, capability matrix across error categories, and genuine abstention-conflict mechanisms.  

---

## 1. Executive Summary & Objective

Before designing and generating the Phase 6 evaluation scenarios, this audit examines the actual source code and automated tests of the core MedResolve components. In accordance with methodological standards, **unsupported error categories are treated as empirical challenge scenarios rather than assumed successes**.

This document establishes:
1. Canonical 5-way unit provenance mapping across OCR extraction and ledger schemas.
2. Complete architectural tracing of the emergency pre-emption mechanism (source paths, line numbers, call sequence, trigger rules, and tests).
3. A formal Component Capability Matrix mapping each error category to its responsible classes, existing tests, adapter requirements, and expected failure modes.
4. Mechanism mapping for the 8 genuine abstention-eligible scenarios in the final evaluation cohort.

---

## 2. Standardized Five-Way Unit Provenance Specification

Phase 5.4 introduced unit provenance in `backend/ocr_service.py`, while Phase 5.1 introduced the `EvidenceItem` schema in `experiments/evidence_ledger.py`. To ensure zero ambiguity or silent data loss (especially for normalized units), the following canonical mapping is established:

| Canonical State | Definition | `backend/ocr_service.py` Representation | `EvidenceItem` Representation | Downstream System Implication |
| :--- | :--- | :--- | :--- | :--- |
| **`EXPLICIT`** | Unit was explicitly transcribed from document text and matches the canonical clinical standard (e.g., `mg/dL` for glucose). | `unit_status = "EXPLICIT"`, `requires_confirmation = False` | `unit = "mg/dL"`, `user_confirmation_status = UNCONFIRMED` (or `CONFIRMED`), `notes` contains `{"unit_status": "EXPLICIT"}` | System accepts unit as primary factual assertion; requires no mandatory confirmation unless contradicted. |
| **`NORMALIZED`** | Unit was explicitly transcribed from document text as a recognized clinical synonym and converted to the canonical standard (e.g., `gm/dl` $\to$ `g/dL`, `mmol/l` $\to$ `mmol/L`, `cells/mcl` $\to$ `/uL`). | `unit_status = "NORMALIZED"`, `requires_confirmation = False` | `unit = standard_unit`, `original_value` retains raw string, `notes` contains `{"unit_status": "NORMALIZED"}` | **Never discarded.** System retains full traceability to raw text; treated as high confidence with explicit provenance history. |
| **`INFERRED`** | Unit was absent in document text, but a bounded, unambiguous physiological range allowed candidate unit assignment (e.g., core temperature $98.6$ inferred as `degF`; SpO2 $97$ inferred as `%`). | `unit_status = "INFERRED"`, `requires_confirmation = True` | `unit = inferred_unit`, `user_confirmation_status = UNCONFIRMED`, `notes` records inference rationale and `requires_confirmation = True` | System treats value as uncertain; mandates clinical/patient confirmation before assimilation into definitive assessment. |
| **`MISSING`** | Unit was absent in document text and cannot be safely or unambiguously inferred (e.g., Fasting Glucose $110$ without unit; could be `mg/dL` or legacy `mg%`). | `unit_status = "MISSING"`, `unit = None`, `requires_confirmation = True` | `unit = None`, `user_confirmation_status = UNCONFIRMED`, `notes` records `unit_status = "MISSING"` | System flags value as lacking essential measurement unit; triggers `MISSING_INFORMATION` conflict or `ASK` policy. |
| **`INVALID`** | Unit was explicitly transcribed but is physiologically incompatible with the analyte concept (e.g., Serum Creatinine transcribed as `bpm` or `mmol/mol`). | `unit_status = "INVALID"`, `requires_confirmation = True` | `unit = raw_unit`, `user_confirmation_status = UNCONFIRMED`, `notes` records invalidity reason | System flags unit mismatch; prevents false clinical conversion and mandates human review. |

---

## 3. Deep Architectural Audit of Emergency Override Pre-emption

The existing codebase was inspected to verify the exact call sequence, line numbers, trigger rules, and test coverage of the emergency pre-emption mechanism.

### 3.1 Component Identification
* **Class Name:** `EmergencySafetyOverrideDetector`
* **File Location:** [experiments/action_policy.py](file:///d:/MedResolve/experiments/action_policy.py) (lines 152–320)
* **Primary Method:** `check_emergency(self, ledger: EvidenceLedger) -> Tuple[bool, List[str]]`

### 3.2 Endpoint Call Sites & Execution Sequence
The emergency detector is invoked at two critical operational entry points in [backend/main.py](file:///d:/MedResolve/backend/main.py):

#### Call Site 1: REST Assessment Endpoint (`/api/assess/{patient_id}`)
* **Location:** `backend/main.py` (lines 592–638)
* **Execution Flow:**
  ```python
  # Line 593: Step 1 Emergency Precedence Check
  is_emerg, red_flags = emergency_detector.check_emergency(ledger)
  if is_emerg:
      # Pre-emption payload built with emergency numbers (112/108)
      # Execution engine: "deterministic_emergency_preemption"
      # AI narrative generation is strictly suppressed
      return result.model_dump()
  # Step 2 (conflicts), Step 3 (policy), Step 4 (retrieval), Step 5 (LLM) only execute if NOT emergency!
  ```

#### Call Site 2: SSE Streaming Assessment Endpoint (`/api/assess-stream/{patient_id}`)
* **Location:** `backend/main.py` (lines 811–833)
* **Execution Flow:**
  ```python
  # Line 812: Step 4 Emergency Check
  is_emerg, red_flags = emergency_detector.check_emergency(ledger)
  if is_emerg:
      yield f"event: emergency_override\ndata: {emergency_payload}\n\n"
      yield f"event: completion\ndata: {comp_payload}\n\n"
      return  # Immediate return! Knowledge retrieval and LLM are NEVER reached
  ```

#### Call Site 3: Selective Action Policy (`SelectiveActionPolicy.select_action`)
* **Location:** `experiments/action_policy.py` (lines 541–555)
* **Execution Flow:** `is_emerg, red_flags = self.emergency_detector.check_emergency(ledger)` is evaluated as Step 1 before evaluating extraction confidence, conflicts, or predictive uncertainty.

### 3.3 Verification of Pre-emption Invariants
1. **Runs Before Retrieval:** Verified. In both REST and SSE endpoints, `check_emergency()` is executed before `kb.search_hybrid(...)`.
2. **Runs Before LLM Inference:** Verified. When `is_emerg = True`, execution halts and returns; Ollama / generator inference is completely bypassed (`llm_invoked = False`).
3. **Suppresses Unverified Narrative:** Verified. The response card contains deterministic emergency contact guidance, and zero AI-generated clinical text is emitted.
4. **Existing Regression Test Coverage:**
   - [tests/test_phase5_4_e2e.py::test_assessment_emergency_override_india](file:///d:/MedResolve/tests/test_phase5_4_e2e.py)
   - [tests/test_phase5_5_sse.py::test_sse_emergency_override_preemption](file:///d:/MedResolve/tests/test_phase5_5_sse.py)
   - [tests/test_rag_pipeline.py::test_preservation_of_emergency_override_precedence](file:///d:/MedResolve/tests/test_rag_pipeline.py)
   - [tests/test_action_policy.py::test_emergency_safety_override_detector](file:///d:/MedResolve/tests/test_action_policy.py)

### 3.4 Configured Trigger Rules
1. **Critical Airway:** Inspiratory stridor (`E_194`) or acute suffocation sensation (`E_128`).
2. **Syncope:** Documented acute loss of consciousness (`E_159`, `E_43`).
3. **Cardiopulmonary Syndrome:** Concurrent acute chest pain (`CHEST_PAIN_TOKENS`) and severe dyspnea (`E_66`, `E_64`, `E_67`).
4. **Active Hemorrhage:** Hematemesis / gross hemoptysis (`E_210`, `E_45`).
5. **Anaphylaxis Constellation:** Swelling (`E_151`, `E_152`) combined with respiratory compromise.
6. **Severe Hyperpyrexia:** Core temperature $\ge 104.0^\circ\text{F}$ ($40.0^\circ\text{C}$).
7. **Severe Hypoxemia:** SpO2 $< 90\%$.

*Crucial Experimental Rule:* Because the existing detector does not check lab analytes (e.g. potassium or creatinine), laboratory decimal errors are **not** expected to trigger emergency override. Emergency evaluation is conducted in a **separate deterministic 30-case suite** testing only actual configured rules.

---

## 4. Component Capability Matrix for Error Categories & Abstention Scenarios

| Error Category | Existing Implementation Support | Exact Class / Method | Existing Test Coverage | Phase 6 Adapter Required in Harness? | Realistic Expectation & Challenge Status |
| :--- | :---: | :--- | :--- | :---: | :--- |
| **1. Decimal-Point Corruption**<br>(e.g. Cr $1.2 \to 12.0$) | **Partial / Conditional** | `RuleBasedConflictDetector._check_concept_level_discrepancies()` | `test_conflict_detector.py` | **Yes:** If paired with a baseline lab within 24h, detected as `VALUE_OR_UNIT_DISCREPANCY` (diff $> 1.5$). If solitary, detector has no physiological ceiling rule. | **Challenge Scenario:** B0 blindly propagates. B2/B3 detect conflict when baseline exists. 2 scenarios have contradictory institutional labs triggering `EXPECTED_ABSTAIN`. |
| **2. Missing or Incorrect Unit**<br>(e.g. Glucose missing unit; Cr labeled `mmol/L`) | **Full (OCR)**<br>**Partial (Ledger)** | `MedicalDocumentProcessor._validate_and_classify_unit()` | `test_phase5_4_e2e.py` | **Yes:** Bridge OCR `requires_confirmation = True` into ledger unconfirmed status so `SelectiveActionPolicy` treats it as requiring clarification (`ASK`). | **Core Detection Scenario:** B0 asserts implicit unit. B1 tags unconfirmed. B3 selects `ASK`. 2 scenarios contain contradictory unit records across visits triggering `EXPECTED_ABSTAIN`. |
| **3. Medication Strength Misreading**<br>(e.g. Lisinopril $10 \to 100\text{ mg}$) | **Partial / Conditional** | `RuleBasedConflictDetector._check_concept_level_discrepancies()` | `test_conflict_detector.py` | **Yes:** Evaluated as source-to-extraction mismatch against prior prescription record. | **Challenge Scenario:** Evaluated strictly as mismatch against prior prescription in ledger. 2 scenarios contain conflicting discharge vs specialist Rx triggering `EXPECTED_ABSTAIN`. |
| **4. Analyte-Value Misassociation**<br>(e.g. Glucose $115$ and HbA1c $7.2$ swapped) | **Unsupported in Core** | *None in core* | *None* | **No core change (Strict Challenge):** No cross-analyte plausibility rules exist in core. | **Strict Challenge Scenario:** Directly tests whether B0–B3 hallucinate or propagate nonsensical inputs. 2 scenarios have irreconcilable contradictory panels triggering `EXPECTED_ABSTAIN`. |
| **5. Temporal Ordering Inversion**<br>(e.g. 2021 lab labeled 2026, inverting trend) | **Partial / Conditional** | `RuleBasedConflictDetector._check_temporal_discrepancies()` | `test_conflict_detector.py` | **Yes:** Core detector only checks $t_{\text{event}} > t_{\text{recorded}}$. Phase 6 scenario runner pairs records to evaluate longitudinal trend inversion in prompt context. | **Evaluation Scenario:** Tests whether longitudinal ledger in B2/B3 prevents naive chronological inversion compared to B0. |
| **6. Critical Field Omission**<br>(e.g. Potassium omitted from panel) | **Unsupported in Core** | *None in core* | *None* | **No core change (Strict Challenge):** Core extractor has no mandatory panel completeness checklist. | **Strict Challenge Scenario:** Evaluates whether B0 asserts a complete panel while omitting missing key markers. |
| **7. Clean Controls**<br>(Uncorrupted, consistent records) | **Full** | `SelectiveActionPolicy.select_action()` | `test_action_policy.py` | **No** | **Utility Baseline:** Evaluates whether B1, B2, B3 preserve high response coverage without over-abstention. |

---

## 5. Architectural Integrity Invariants

1. **Zero Modifications to Frozen Source:** `backend/ocr_service.py` and `experiments/` core files will not be touched.
2. **Phase 6 Evaluation Harness:** Any bridging logic (such as passing OCR `unit_status` into `EvidenceItem.notes` and ensuring `SelectiveActionPolicy` evaluates unconfirmed extractions) will be implemented strictly inside `experiments/phase6/`.
3. **Intellectual Honesty Guarantee:** Unsupported error categories are documented transparently as **challenge scenarios**, and system failures will be analyzed objectively.
