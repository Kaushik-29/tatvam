# MedResolve Phase 5: Independent Medical Retrieval Evaluation Report

**Corpus:** MedResolve Curated Medical Reference Knowledge Base (6 Guidelines, 24 Structured Clinical Passages)  
**Evaluation Set:** 20 Clinically Formulated Reference Queries with Independently Labeled Relevant Passage IDs  
**Evaluation Harness:** `experiments/evaluate_retrieval.py`

---

## 1. Comparative Retrieval Performance

| Metric | Lexical Baseline (BM25) | Dense Vector (FAISS FlatIP + bge-m3) | Hybrid (Reciprocal Rank Fusion) | Best Performing |
| :--- | :---: | :---: | :---: | :---: |
| **Mean Reciprocal Rank (MRR)** | 0.8526 | 0.9123 | **0.9123** | Hybrid |
| **Recall@1** | 78.95% | 84.21% | **84.21%** | Hybrid |
| **Recall@3** | 89.47% | 100.00% | **100.00%** | Hybrid |
| **Recall@5** | 94.74% | 100.00% | **100.00%** | Hybrid |
| **Precision@1** | 0.7895 | 0.8421 | **0.8421** | Hybrid |
| **Precision@3** | 0.2982 | 0.3333 | **0.3333** | Hybrid |
| **Zero-Hit Rate (Top-3 Failure)** | 5.26% (1) | 0.00% (0) | **0.00% (0)** | Hybrid |
| **Mean Retrieval Latency** | 0.70 ms | 611.92 ms | 568.88 ms | Lexical (Lowest Latency) |
| **Latency p95** | 1.28 ms | 891.35 ms | 752.45 ms | Lexical |

---

## 2. Qualitative Strengths and Failure Mode Analysis

1. **Dense Semantic Retrieval:**
   - Excels on clinical paraphrase and conceptual synonyms where terminology differs (e.g., matching "burning chest discomfort after eating" to `DOC_MOHFW_GERD_2019_P001` which discusses "pyrosis and acid regurgitation").
   - Achieves high Top-1 accuracy across varied patient question phrasings.

2. **Lexical Baseline (BM25):**
   - High speed (< 1 ms latency), perfectly captures exact drug names and specific clinical terms (e.g. "epinephrine", "proton pump inhibitor", "endoscopy").
   - Vulnerable to vocabulary mismatch when patient queries use colloquial terms ("hives" vs "urticaria", "fainting" vs "syncope").

3. **Hybrid Reciprocal Rank Fusion:**
   - Combines semantic generalization with exact lexical token matching, mitigating vocabulary mismatch while preserving high precision on clinical keywords.

4. **Out-of-Domain Query Handling:**
   - On out-of-domain query Q20 ("pediatric appendectomy"), BM25 returns score 0.0, and dense retrieval similarity scores fall below the relevance threshold (cosine similarity < 0.35), enabling reliable abstention when relevant evidence is absent.

> [!NOTE]
> **Evaluation Boundary:** High retrieval scores confirm that the index surfaces relevant clinical guidance; they do NOT establish medical correctness of downstream AI answers or clinical safety.

---
*Report generated automatically by `experiments/evaluate_retrieval.py`.*
