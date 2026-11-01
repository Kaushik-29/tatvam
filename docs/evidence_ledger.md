# MedResolve: Source-Aware Evidence Ledger Specification

## 1. Motivation & Architectural Purpose
In naive AI diagnostic systems and standard LLM symptom checkers, clinical findings are treated as flat, ungrounded bags of tokens (e.g. `['fever', 'cough']`). This design fundamentally obscures critical clinical context:
1. **Provenance Blindness:** Failing to distinguish between a patient's unverified self-report, an objective laboratory finding, a discharge summary observation, or an external physician's opinion.
2. **Extraction Opacity:** Conflating high-confidence structured entries with noisy, low-confidence OCR or document-parsing extractions.
3. **Temporal Inversion:** Overlooking the chronology between when a symptom occurred (`event_timestamp`) and when it was recorded or ingested into the system (`recorded_timestamp`).
4. **Data Destruction via Imputation:** Fabricating units or observation dates when none exist, creating dangerous diagnostic assumptions.

The **MedResolve Evidence Ledger** (`EvidenceLedger`) resolves these flaws by tracking every clinical observation as an independent, typed, source-aware container (`EvidenceItem`).

---

## 2. Evidence Item Data Schema

Each entry in a patient's evidence ledger adheres to the following typed schema (implemented in [`experiments/evidence_ledger.py`](file:///d:/MedResolve/experiments/evidence_ledger.py) via Pydantic):

| Field | Data Type | Nullable? | Description | Example |
|---|---|---|---|---|
| `evidence_id` | `str` | No | Unique identifier for this observation instance | `"case_0102_ev_003"` |
| `patient_case_id` | `str` | No | Identifier for the patient encounter | `"case_eval_0042_row91402"` |
| `concept` | `str` | No | Canonical concept or ontology code | `"E_53"`, `"E_LAB_01"` |
| `concept_name_en` | `str` | Yes | Human-readable English descriptor | `"Do you have a fever?"` |
| `normalized_value` | `Any` | No | Canonical typed value (`bool`, `str`, `float`) | `101.4`, `True`, `"V_180"` |
| `original_value` | `str` | Yes | Raw text extracted from source before normalization | `"101.4 F orally"` |
| `unit` | `str` | Yes | Standardized unit or `None` if dimensionless/missing | `"degF"`, `"mg/dL"`, `None` |
| `source_type` | `SourceType` | No | Categorical provenance source | `SourceType.PATIENT_REPORTED` |
| `source_document_id` | `str` | Yes | Identifier of source clinical report or letter | `"doc_ed_discharge_09"` |
| `source_page` | `int` | Yes | Page number in multi-page document | `2` |
| `event_timestamp` | `str` | Yes | ISO 8601 timestamp when finding occurred | `"2026-10-15T08:00:00Z"` |
| `recorded_timestamp` | `str` | No | ISO 8601 timestamp when observation was ingested | `"2026-10-15T10:00:00Z"` |
| `extraction_method` | `ExtractionMethod` | No | Method utilized to extract the record | `ExtractionMethod.OCR_EXTRACTION` |
| `extraction_confidence`| `float` | No | Confidence score $\in [0.0, 1.0]$ | `0.48` |
| `user_confirmation_status` | `UserConfirmationStatus` | No | Verification state | `UserConfirmationStatus.UNCONFIRMED` |
| `evidence_status` | `EvidenceStatus` | No | Clinical finding state | `EvidenceStatus.PRESENT` |
| `is_simulated` | `bool` | No | Flag indicating simulated / benchmark data | `True` |

---

## 3. Enumerated Provenance & Status Types

### 3.1 Source Types (`SourceType`)
- **`PATIENT_REPORTED`:** Direct patient statement obtained via triage questionnaire or interactive query.
- **`EHR_EXTRACTED_NOTE`:** Clinical documentation (progress notes, consultation letters, nursing flowsheets).
- **`LABORATORY_REPORT`:** Tabular or semi-structured pathology/biochemistry test outputs.
- **`PRIOR_PRESCRIPTION`:** Pharmacy medication dispensation or prescription history.
- **`ENTERED_CLINICIAN_OPINION`:** Formally stated diagnostic impression from a reviewing medical professional.

### 3.2 Evidence Assertion Status (`EvidenceStatus`)
- **`PRESENT`:** Positive clinical observation (symptom active / sign confirmed).
- **`ABSENT`:** Negative clinical observation (symptom explicitly denied / sign ruled out).
- **`UNCERTAIN`:** Equivocal or border-line finding.
- **`UNKNOWN`:** Unobserved or unqueried finding.

### 3.3 User Confirmation Status (`UserConfirmationStatus`)
- **`UNCONFIRMED`:** Ingested from automated document parser without human verification.
- **`CONFIRMED_BY_PATIENT`:** Verified as accurate by the patient.
- **`REJECTED_BY_PATIENT`:** Denied by the patient upon verification request.
- **`CONFIRMED_BY_CLINICIAN`:** Validated by a licensed medical practitioner.

---

## 4. Clinician Opinion Container (`ClinicianOpinionItem`)

External diagnostic opinions are captured in a dedicated structure separate from raw findings:
- `opinion_id`: Unique opinion ID.
- `clinician_id`: Clinician pseudonym or ID.
- `clinician_specialty`: Clinical discipline (e.g. *Pulmonology*, *Emergency Medicine*).
- `diagnostic_impression`: Condition diagnosed.
- `confidence_assessment`: Stated clinician certainty level (`PROBABLE`, `DEFINITIVE`, `DIFFERENTIAL_CONSIDERATION`).
- `recorded_timestamp`: ISO 8601 documentation timestamp.

> [!IMPORTANT]
> **Non-Arbitration Policy:** Clinician opinions are stored to track clinical disagreement. The Evidence Ledger and MedResolve conflict detector do **NOT** determine which clinician is correct or arbitrate clinical truth.
