# MedResolve — Server-Sent Events (SSE) Streaming Integration Validation

**Phase Identifier:** Phase 5.5  
**Document Purpose:** Architectural verification of genuine SSE streaming behavior on `GET /api/assess-stream/{patient_id}`.

---

## 1. Architectural Principles of MedResolve SSE Streaming

The streaming endpoint `GET /api/assess-stream/{patient_id}` serves two safety objectives:
1. **Interactive Real-Time Progress Transparency:** Long CPU generation pipelines (~16s on local hardware) are broken into human-comprehensible processing stages so clinicians and patients understand what the system is doing.
2. **Strict In-Memory Buffering of Unverified Narrative:** To guarantee patient safety, partial tokens of clinical narrative are **never** streamed directly to the user as they are generated. The narrative remains buffered in memory until the dual-axis claim verifier validates reference citations and patient ledger consistency. The final response is delivered exclusively via `event: final_result`.

---

## 2. Event Channel Specification

| Event Name | Stage Code | Payload Contents | Emitted When |
| :--- | :--- | :--- | :--- |
| `intake` | `STAGE_1_INTAKE` | `patient_id`, timestamp, progress message | Stream connection opened; patient profile validated |
| `evidence_ledger` | `STAGE_2_LEDGER` | `items_count`, observations summarized | Structured evidence ledger synthesized |
| `conflict_detection`| `STAGE_3_CONFLICTS` | `conflicts_count`, discrepancies detected | 6-category conflict detector evaluates discrepancies |
| `emergency_override`| `STAGE_4_EMERGENCY_OVERRIDE`| `red_flags`, `safety_dispatch`, emergency details | **Only in Emergency:** Preempts all generation |
| `knowledge_retrieval`| `STAGE_5_RETRIEVAL` | Formulated query, retrieval method (BGE-M3 + BM25) | Only when no emergency override |
| `generation_buffered`| `STAGE_6_SYNTHESIS` | Notice that generation is underway and buffered | Only when permitted by policy |
| `claim_verification`| `STAGE_7_VERIFICATION` | Dual-axis verification notice | Generated claims evaluated against guidelines & ledger |
| `final_result` | `STAGE_8_DELIVERY` | Complete verified `AssessmentResultDTO` JSON | After verification and policy approvals |
| `completion` | `COMPLETED` / `EMERGENCY_PREEMPTED` | Final lifecycle status, action code | Connection termination |
| `error` | `ERROR` | Error description, detail | Unexpected server error or network cancellation |

---

## 3. Comparative Scenario Execution

### Scenario A: In-Domain Verified Assessment (`SYNTH_PATIENT_01`)
- **Connection Header:** `Content-Type: text/event-stream; charset=utf-8`
- **Stream Lifecycle:**
  ```
  event: intake
  data: {"stage": "STAGE_1_INTAKE", "message": "Parsing clinical intake and patient observations...", "patient_id": "SYNTH_PATIENT_01"}

  event: evidence_ledger
  data: {"stage": "STAGE_2_LEDGER", "message": "Synthesized structured evidence ledger with 9 observations.", "items_count": 9}

  event: conflict_detection
  data: {"stage": "STAGE_3_CONFLICTS", "message": "Evaluated 6-category conflict taxonomy (0 discrepancies detected).", "conflicts_count": 0}

  event: knowledge_retrieval
  data: {"stage": "STAGE_5_RETRIEVAL", "message": "Executing hybrid retrieval (BGE-M3 Dense FAISS + BM25 Lexical with RRF)..."}

  event: generation_buffered
  data: {"stage": "STAGE_6_SYNTHESIS", "message": "Generating clinical evidence summary. Content is buffered pending claim verification..."}

  event: claim_verification
  data: {"stage": "STAGE_7_VERIFICATION", "message": "Executing dual-axis claim verification (reference entailment & patient consistency)..."}

  event: final_result
  data: {"assessment_id": "asmt_1793429560123", "workflow_stage": "COMPLETED", ...}

  event: completion
  data: {"status": "COMPLETED", "action": "EXPLAIN"}
  ```

### Scenario B: Emergency Override Preemption (`SYNTH_PATIENT_07`)
- **Clinical Trigger:** Acute stridor and suspected anaphylaxis.
- **Stream Lifecycle:**
  ```
  event: intake
  data: {"stage": "STAGE_1_INTAKE", ...}

  event: evidence_ledger
  data: {"stage": "STAGE_2_LEDGER", ...}

  event: conflict_detection
  data: {"stage": "STAGE_3_CONFLICTS", ...}

  event: emergency_override
  data: {
    "stage": "STAGE_4_EMERGENCY_OVERRIDE",
    "message": "CRITICAL EMERGENCY OVERRIDE TRIGGERED. Ordinary LLM generation preempted.",
    "red_flags": [
      "Critical acute upper airway compromise: patient presents with inspiratory stridor or acute suffocation sensation.",
      "Suspected acute anaphylaxis: acute swelling combined with respiratory compromise."
    ],
    "safety_dispatch": "Dial 112 / 108 immediately (Emergency Services)"
  }

  event: completion
  data: {"status": "EMERGENCY_PREEMPTED", "action": "EMERGENCY_OVERRIDE", "llm_invoked": false}
  ```
- **Preemption Verification:** Neither `knowledge_retrieval` nor `generation_buffered` were emitted. Ollama was not called.
