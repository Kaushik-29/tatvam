# Limitations

## Clinical
- **Not clinically validated.** No clinician has reviewed the system's answers; a blinded review sheet is produced but has not been rated. Synthetic performance is not clinical validity.
- **Information, not care.** MedResolve does not diagnose, prescribe, triage definitively or change medications.
- **Rule-based safety components.** The emergency screen, reconciliation rules and claim verifier rely on lexicons and regular expressions. They can miss paraphrases (one anaphylaxis word-order miss was found and fixed during testing) and can accept lexically matching but semantically wrong claims.

## Data
- **Synthea is synthetic.** Its disease modules, symptom sets and note templates are simplified and repetitive (e.g. identical chief-complaint lists across visits), and only 10 years of history are exported. Retrieval is easier and more regular than on real records.
- **Medication exposure is estimated.** Synthea exports no supply duration. Exposure windows follow a documented rule (chronic until next request, ≤400 days; acute 30 days) and are flagged as estimated, so "medications during episode" gold labels inherit that assumption.
- **Gold labels use curated clinical maps** (symptom → related conditions, organ system → labs). Retrieval variants use the same lexicon for query expansion, so absolute scores are optimistic. Comparisons between variants are fairer than absolute numbers.
- **Prescriptions leaf** is empty for Synthea patients; it is populated only by uploads and entries.
- **MIMIC-IV not used** (pending PhysioNet authorization). Even once authorized, MIMIC is hospital/ED-centred and not a lifelong outpatient record.
- **SearchTome release ≠ paper benchmark** (one book per domain; three books differ from the paper). Paper numbers cannot be reproduced on it.
- **MedlinePlus summaries** are consumer-level overviews, not clinical guidelines. The KB v2 passages are a small, previously curated set.

## Modelling
- **STAIR-Clinical was not trained at the reference scale.** The machine is CPU-only (i7-13700H, 16 GB RAM, Intel Iris Xe, no CUDA). The local adapter is a reduced-scale run (Qwen2.5-0.5B-Instruct, a few hundred examples, one pass). The Mistral-7B-Instruct-v0.2 reference configuration is provided as a cloud-GPU notebook and **has not been run**.
- **No parametric corpus memorization by design** — STAIR-Clinical differs from STAIR, which also ingests content into weights.
- **Dense patient retrieval** embeds concept-level texts, not individual dated values (CPU cost). Records of the same concept tie on dense score and are ordered by recency.
- **Local LLM quality.** `llama3.2:3b` follows citation instructions imperfectly. Claim verification then withholds statements, which can make answers short. Generation on CPU takes minutes per answer under load.
- **Lexical verification** cannot judge clinical correctness. Factual correctness requires human raters.

## Engineering
- **PostgreSQL untested here.** The code is SQLAlchemy-portable and configured by `DATABASE_URL`, but it was only run on SQLite because Docker was not running and the user chose SQLite.
- **Prototype security.** No HTTPS, no rate limiting, no account lockout, and tokens are kept in sessionStorage.
- **Single-node, in-process services.** Embeddings and indexes load into the API process (about 2–3 GB RAM).
