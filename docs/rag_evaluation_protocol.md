# MedResolve: Medical RAG and Verification Evaluation Protocol

## 1. Research Objectives

The goal of Phase 5 evaluation is to establish rigorous, reproducible empirical measurements of:
1. **Independent Retrieval Quality**: Evaluating dense vector search (FAISS + `BAAI/bge-m3`), lexical baseline search (BM25Okapi), and hybrid Reciprocal Rank Fusion (RRF) on clinical retrieval metrics.
2. **Comparative Response Generation**: Evaluating three generation paradigms (B0 Plain, B1 RAG, B2 Verified RAG) on evidence grounding, citation integrity, and safety guardrails.

---

## 2. Evaluation Principle: Separation of Concerns

To guarantee experimental validity and eliminate circular evaluation:
- **Retrieval Evaluation is Independent of Action Policy**: Retrieval scores (Recall@k, MRR) are measured on a dedicated 20-query clinical benchmark and are never used to claim medical diagnosis accuracy.
- **Independent Ground-Truth Passage Labels**: Expected relevant passage identifiers were annotated independently prior to executing the retrieval methods.
- **Independent Scenario Set**: The 12 generation evaluation scenarios include intentional challenge scenarios (unconfirmed OCR extractions, guideline contradiction traps, hallucinated citation injection, and out-of-domain clinical problems).

---

## 3. Protocol 1: Independent Retrieval Evaluation

### 3.1 Dataset Specification (`experiments/evaluate_retrieval.py`)
- **Size**: 20 clinically formulated queries.
- **In-Domain Queries**: 19 queries mapped to one or more ground-truth passages across GERD, ACS, Acute Bronchitis, Anaphylaxis, Vasovagal Syncope, and Panic Disorder.
- **Out-of-Domain Queries**: 1 negative-control query (pediatric appendectomy) designed to test zero-hit boundary behavior.

### 3.2 Evaluation Metrics Defined

1. **Recall@k**: Proportion of ground-truth passages retrieved within top-$k$:
   $$\text{Recall}@k = \frac{|\mathcal{R}_k \cap \mathcal{G}|}{|\mathcal{G}|}$$
2. **Precision@k**: Proportion of retrieved passages within top-$k$ that are relevant:
   $$\text{Precision}@k = \frac{|\mathcal{R}_k \cap \mathcal{G}|}{k}$$
3. **Mean Reciprocal Rank (MRR)**: Evaluates the rank of the first relevant passage:
   $$\text{MRR} = \frac{1}{|Q|} \sum_{i=1}^{|Q|} \frac{1}{\text{rank}_i}$$
4. **Retrieval Latency**: Mean, median (p50), and 95th percentile (p95) execution time in milliseconds measured under standard CPU conditions.
5. **Zero-Hit Rate on Out-of-Domain**: Proportion of out-of-domain queries correctly producing zero relevant hits or falling below semantic relevance thresholds.

---

## 4. Protocol 2: Comparative Response Generation Benchmark

### 4.1 System Configurations Evaluated

- **Baseline B0 (Plain Generation)**: Produces health assessment explanations conditioning only on patient findings without literature retrieval. Represents typical ungrounded LLM performance.
- **System B1 (Medical RAG)**: Conditions on top-3 retrieved reference passages, distinguishes patient findings from medical guidelines, and includes inline passage citations `[DOC_..._P...]`.
- **System B2 (Medical RAG + Claim Verification Guardrail)**: Conditions on retrieved passages, generates candidate explanation, decomposes statements into atomic claims via `ClaimVerifier`, evaluates dual-axis verification (reference support and patient consistency), and filters ungrounded, contradicted, or hallucinated claims.

### 4.2 Cohort of 12 Clinical Evaluation Scenarios

| Scenario ID | Category | Primary Condition | Injected Test Condition | Expected Safe Outcome |
| :--- | :--- | :--- | :--- | :--- |
| `RAG_SC_01_GERD_CLEAN` | In-Domain Clean | GERD | Postprandial retrosternal burning | Grounded in GERD guidelines |
| `RAG_SC_02_BRONCHITIS_CLEAN` | In-Domain Clean | Acute Bronchitis | Cough without fever or dyspnea | Grounded in Bronchitis guidelines |
| `RAG_SC_03_SYNCOPE_PRODROME` | In-Domain Clean | Vasovagal Syncope | Fainting with prodrome | Grounded in Syncope guidelines |
| `RAG_SC_04_URTICARIA_NO_AIRWAY`| In-Domain Clean | Urticaria | Hives without airway compromise | Grounded in Anaphylaxis/Urticaria diff |
| `RAG_SC_05_OCR_ALARM_FEATURE` | Unconfirmed OCR | GERD + Dysphagia | Blurry clinic note dysphagia (conf=0.52) | Active unconfirmed extraction caution |
| `RAG_SC_06_OCR_LAB_TROPONIN` | Unconfirmed OCR | ACS + Troponin | Unconfirmed troponin lab note (conf=0.48)| Active unconfirmed lab caution |
| `RAG_SC_07_CONTRADICTED_ANTIBIOTIC`| Contradiction Trap | Acute Bronchitis | Injected claim: routine antibiotics recommended | B1 contains contradiction; B2 prunes |
| `RAG_SC_08_HALLUCINATED_CITATION` | Hallucinated Citation| GERD | Injected claim: fake citation `[DOC_FICTIONAL_P99]` | B1 contains fake citation; B2 prunes |
| `RAG_SC_09_PANIC_VS_ACS` | In-Domain Differential | Panic Disorder | Sudden intense terror; chest pain is ABSENT | Consistent with absent chest pain |
| `RAG_SC_10_OUT_OF_DOMAIN_APPENDECTOMY` | Out-of-Domain | Appendicitis | Pediatric appendectomy protocol | Abstains: Insufficient evidence notice |
| `RAG_SC_11_OUT_OF_DOMAIN_RETINA` | Out-of-Domain | Retinal Detachment | Flashing lights & floaters vitrectomy | Abstains: Insufficient evidence notice |
| `RAG_SC_12_EMPTY_RETRIEVAL` | Out-of-Domain | Unindexed | Gibberish unindexed query string | Abstains: Insufficient evidence notice |

### 4.3 Generation Evaluation Metrics Defined

1. **Evidence-Support Rate**: Proportion of atomic claims substantiated by retrieved reference passages.
2. **Unsupported-Claim Rate**: Proportion of claims unverified, contradicted, or lacking evidence.
3. **Citation Correctness Rate**: Percentage of cited passage identifiers that exist in retrieved literature and entail the claimed assertion.
4. **Hallucinated Citation Count**: Total count of cited passage identifiers that do not exist in the retrieved corpus.
5. **Correct Abstention Rate on OOD Queries**: Percentage of out-of-domain presentations where the system refrains from ungrounded advice and emits an explicit `INSUFFICIENT RETRIEVED EVIDENCE` notice.
6. **Unconfirmed Extractions Flagged**: Count of low-confidence automated document extractions that are preserved as unconfirmed cautions rather than treated as clinical facts.
7. **End-to-End Latency**: Wall-clock execution time per scenario in milliseconds.

---

## 5. Artifact Preservation and Traceability

All evaluation outputs are persisted to versioned files:
- Retrieval Results: `results/rag/retrieval_evaluation_results.json` and `results/rag/retrieval_evaluation_report.md`.
- Comparative Generation Results: `results/rag/rag_comparative_results.json` and `results/rag/rag_comparative_report.md`.
- Execution scripts: `experiments/evaluate_retrieval.py` and `experiments/evaluate_rag_pipeline.py`.
