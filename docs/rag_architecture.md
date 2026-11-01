# MedResolve: Medical RAG Architecture & Verification Engine

## 1. Architectural Overview

MedResolve Phase 5 introduces a lightweight, CPU-friendly medical Retrieval-Augmented Generation (RAG) and claim-verification engine. The system retrieves peer-reviewed clinical guidelines, preserves document provenance down to atomic passages, generates evidence-grounded health assessments, and applies dual-axis claim-level verification before presenting explanations to the user.

```
+--------------------------------------------------------------------------------------------------+
|                                    MedResolve Pipeline Overview                                  |
+--------------------------------------------------------------------------------------------------+
                                                 |
                                     +-----------------------+
                                     | Patient Evidence      |
                                     | Ledger (Ledger Items) |
                                     +-----------------------+
                                                 |
                       +-------------------------+-------------------------+
                       |                                                   |
                       v                                                   v
           +-----------------------+                           +-----------------------+
           | Predictive Model      |                           | Conflict Detector     |
           | Entropy & Margin      |                           | Rule-Based Taxonomy   |
           +-----------------------+                           +-----------------------+
                       |                                                   |
                       +-------------------------+-------------------------+
                                                 |
                                                 v
                               +-----------------------------------+
                               | Selective Action Policy           |
                               | (EMERGENCY, ASK, ABSTAIN, EXPLAIN)|
                               +-----------------------------------+
                                                 |
                           +---------------------+---------------------+
                           |                                           |
             [EMERGENCY / ASK / ABSTAIN]                           [EXPLAIN]
                           |                                           |
                           v                                           v
               Immediate Action / Exit                    +-------------------------+
                                                          | Dual Knowledge Base     |
                                                          | Dense FAISS + BM25Okapi |
                                                          +-------------------------+
                                                                       |
                                                                       v
                                                          +-------------------------+
                                                          | Evidence-Grounded       |
                                                          | Generator               |
                                                          +-------------------------+
                                                                       |
                                                                       v
                                                          +-------------------------+
                                                          | ClaimVerifier Engine    |
                                                          | Dual-Axis Verification  |
                                                          | & Guardrail Filtering   |
                                                          +-------------------------+
                                                                       |
                                                                       v
                                                          +-------------------------+
                                                          | Verified Explanation    |
                                                          +-------------------------+
```

---

## 2. Document Ingestion and Chunking

All clinical reference literature resides in `data/knowledge_base/` isolated from patient records.

### Provenance Tracking Schema
Every ingested passage retains strict metadata:
- **`document_id`**: Canonical document identifier (e.g., `DOC_MOHFW_GERD_2019`).
- **`document_title`**: Formal publication title.
- **`document_organization`**: Issuing health authority (e.g., MoHFW India, WHO, NCBI StatPearls).
- **`section_heading`**: Sub-clinical context (e.g., "Alarm Features Requiring Endoscopy").
- **`source_url`**: Official government or repository publication URL.
- **`publication_date`**: Verified date or explicit uncertainty note.
- **`access_date`**: Date accessed/ingested.
- **`license_or_reuse_conditions`**: Open Government Data (OGD) License India, CC BY-NC-SA 3.0 IGO, or NCBI Public Domain.
- **`document_type`**: Clinical guideline, consensus report, or peer-reviewed clinical review.
- **`version`**: Document version or edition.

### Semantic Segmentation
Documents are segmented along clinical section boundaries into self-contained passages of 100–250 words. Each passage is assigned a permanent identifier (`{document_id}_P{passage_num:03d}`).

---

## 3. Retrieval Engine Design

MedResolve employs a dual-index architecture optimized for CPU execution without external API dependencies:

### 3.1 Dense Retrieval (FAISS FlatIP)
- **Embedding Model**: `BAAI/bge-m3` (1024-dimensional dense vectors) executed locally on CPU.
- **Normalization**: All passage and query vectors are L2-normalized so that inner product equals cosine similarity:
  $$\text{score}(q, p) = \mathbf{e}_q \cdot \mathbf{e}_p$$
- **Index**: FAISS `IndexFlatIP` cached to disk in `data/knowledge_base/index/dense_index.faiss`.

### 3.2 Lexical Retrieval Baseline (BM25Okapi)
- Tokenizes clinical text using regularized lowercase alphanumeric terms.
- Serves as a keyword-matching baseline and guard against dense semantic drift.

### 3.3 Hybrid Reciprocal Rank Fusion (RRF)
Combines dense semantic representations with lexical precision:
$$\text{RRF\_Score}(d) = \sum_{m \in \{\text{dense}, \text{lexical}\}} \frac{1}{k + \text{rank}_m(d)}$$
where $k=60$. Hybrid search ensures high recall for specialized clinical terminology while retaining semantic generalization.

### 3.4 Insufficient Evidence Detection
To prevent hallucinations on out-of-domain presentations, the retriever evaluates semantic relevance:
- If the top retrieved passage has dense similarity $< 0.50$ (or pure BM25 score $< 5.0$), retrieval is classified as **inadequate / out-of-domain**.
- The generator immediately emits an `INSUFFICIENT RETRIEVED EVIDENCE` safety notice.

---

## 4. Evidence-Grounded Response Generation

The generator operates under three comparative system configurations:
1. **System B0 (Plain Baseline)**: Generates ungrounded explanations without reference literature.
2. **System B1 (Medical RAG)**: Prompts with retrieved passages and requires citation markers `[DOC_..._P...]`.
3. **System B2 (RAG + Claim Verification Guardrail)**: Generates candidate explanation, decomposes assertions into atomic claims, verifies reference entailment and patient ledger consistency, and prunes or annotates unverified claims.

### Clinical Guardrails Enforced During Generation:
- **Separation of Observations vs. Guidelines**: Patient-reported observations are kept distinct from clinical reference citations.
- **Citation Preservation**: Every factual medical claim links to an explicit retrieved passage ID.
- **Unconfirmed Extraction Warnings**: Findings extracted with $< 0.70$ confidence that remain unconfirmed by the patient trigger explicit cautionary notices.
- **Non-Diagnostic Framing**: All outputs include standardized academic research disclaimers clarifying that MedResolve does not establish definitive diagnoses.

---

## 5. Claim-Level Verification Engine (`ClaimVerifier`)

The verification engine decomposes generated explanations into atomic claims and performs **dual-axis verification**:

### Axis 1: Reference Entailment Verification
Evaluates whether a claim is substantiated by retrieved clinical guidelines:
- **`SUPPORTED_BY_SOURCE`**: Supported by high clinical keyword overlap or semantic entailment.
- **`CONTRADICTED_BY_SOURCE`**: Directly contradicts retrieved guideline recommendations (e.g. prescribing routine antibiotics for viral bronchitis).
- **`INSUFFICIENT_EVIDENCE`**: Information cannot be substantiated from retrieved passages.
- **`OUT_OF_SCOPE`**: Non-medical administrative statement.

### Axis 2: Patient Evidence Ledger Consistency
Evaluates whether a patient-specific claim is faithful to the patient's documented evidence:
- **`NOT_APPLICABLE_GENERAL`**: General medical knowledge statement; does not assert specific patient findings.
- **`CONSISTENT`**: Matches documented evidence in the ledger.
- **`CONTRADICTED_BY_LEDGER`**: Asserts a finding that the ledger explicitly marks as `ABSENT`.
- **`UNCONFIRMED_EXTRACTION`**: Relies upon a low-confidence document extraction that has not been confirmed by the patient.
- **`FINDING_NOT_IN_LEDGER`**: Asserts a patient observation not recorded in the ledger.

### Citation Integrity Guardrail
- Checks every cited `[DOC_..._P...]` identifier against the retrieved passages.
- Identifies and flags fabricated / hallucinated citations (`has_hallucinated_citation = True`).
- In System B2, lines containing hallucinated citations or contradicted guidance are automatically pruned.

---

## 6. Integration with Selective Action Policy

RAG integration strictly obeys the safety hierarchy established in Phases 3 and 4:
1. **`EMERGENCY_OVERRIDE` Strictly Preempts RAG**: If acute red flags (syncope, stridor, anaphylaxis constellation) are present, the system immediately emits an urgent warning. RAG explanations are **never** attached to emergency overrides.
2. **Material Conflicts Preempt RAG**: If contradictory clinician opinions or conflicting lab values exist, the system triggers `ABSTAIN_AND_NAVIGATE`. RAG passages are never used to arbitrate or override patient conflicts.
3. **Diagnostic Uncertainty Preempts RAG**: If predictive entropy is elevated and a discriminating question is available, the policy triggers `ASK`.
4. **Conditional RAG on `EXPLAIN`**: Only when evidence is adequate, consistent, and low-uncertainty does the policy invoke `execute_policy_with_rag` to ground the explanation in verified literature.

---

## 7. Clinical Safety and Research Scope Disclaimer

> [!WARNING]
> MedResolve is an academic research prototype. Algorithmic retrieval precision, citation fidelity, and natural language inference verification measure compliance under synthetic and retrospective benchmarks. They do **not** constitute clinical validation, medical diagnosis, or real-world safety certification.
