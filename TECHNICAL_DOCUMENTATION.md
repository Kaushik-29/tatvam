# MedResolve — Technical Documentation

This document describes how MedResolve was designed and built: the problem, the technologies, the models, the architecture, the main workflows and how they were evaluated. Installation is in [`README.md`](README.md). Working on the code is in [`DEVELOPER_GUIDE.md`](DEVELOPER_GUIDE.md). Deeper write-ups of single components are in `docs/` (listed in §12).

> Research prototype. Not a diagnostic or prescribing system, and not clinically validated.

---

## 1. Problem and approach

General medical chatbots answer every question the same way for everyone. A useful answer to *"Can I take ibuprofen for this headache?"* depends on the person's own record: kidney disease, a blood thinner, an aspirin allergy or a recent stomach bleed all change the answer.

MedResolve treats a patient's longitudinal record as a **structured document**, the way a book has a table of contents. It retrieves the parts relevant to the question and writes an answer that cites both the patient's records and trusted medical references. A set of deterministic safety layers decides *whether* to answer at all, and removes any patient-specific sentence the record doesn't support.

The core research idea is **STAIR-Clinical**. It adapts STAIR (structure-aware iterative retrieval over a book's table of contents) to patient records. A fine-tuned language model reads the question plus the patient's record outline and "routes" to the sections that should hold the evidence. Its routing is then fused with ordinary hybrid search.

---

## 2. Technology stack

| Layer | Technology | Why it was chosen |
|---|---|---|
| Backend API | **Python 3.11, FastAPI, Uvicorn** | Async, typed request models (Pydantic v2), server-sent events for streaming progress |
| Database | **SQLAlchemy 2 ORM**; SQLite by default, PostgreSQL supported | One file for development; same models work on PostgreSQL |
| Auth | **python-jose** (JWT HS256), **passlib + bcrypt** | Stateless tokens; salted password hashes |
| Lexical search | **rank-bm25** | Strong on exact clinical terms and drug names |
| Dense search | **sentence-transformers + BAAI/bge-m3**, **FAISS** (CPU, inner product) | Multilingual, strong medical retrieval, runs on CPU |
| Fusion | Reciprocal Rank Fusion (k = 60) | Combines rankings without score calibration |
| Router (CPU app) | **Qwen2.5-0.5B-Instruct + LoRA** (**transformers, PEFT**, torch CPU) | Small enough to run on a laptop |
| Router (research) | **Mistral-7B-Instruct-v0.2 + QLoRA** (4-bit), trained on Kaggle/Colab T4 GPUs | Best routing accuracy; GPU-only |
| Answer writer | **llama3.2:3b via Ollama** (local, not fine-tuned) | Runs offline; no patient data leaves the machine |
| OCR | **PyMuPDF** (digital PDFs), **RapidOCR ONNX** (scans/photos) | Open-source and CPU-only |
| Speech-to-text | **faster-whisper** (Whisper base, int8, CPU) + **ffmpeg** CLI | Offline transcription |
| Frontend | **React 19, TypeScript, Vite, Tailwind CSS 4**, lucide-react icons | Fast dev server, typed API layer |
| Tests | **pytest** (backend), `tsc -b` type-check (frontend) | — |
| Paper | docx-js (Node) → Word → PDF | Reproducible IEEE-format build |

---

## 3. System architecture

```
 Browser (React, :5173)
   │  /api/*  (Vite proxy)
   ▼
 FastAPI app  backend/main.py  (:8000)
   ├── /api/v2/auth/*        backend/api/auth.py           register · login · demo login · JWT
   ├── /api/v2/*             backend/api/patient_routes.py profile · records · timeline · documents
   │                                                        consult (+SSE stream) · consultations
   │                                                        record decisions · speech · test cases
   │                                                        export/delete · audit · system status
   └── /api/*  (legacy)      backend/main.py               Phase 1–6 research system (frozen)
           │
           ▼
   Answer pipeline  backend/rag/pipeline.py  (variants B0–B5; B5 = product)
     ├── emergency screen        backend/evidence_reconciliation/emergency.py
     ├── query understanding     backend/rag/query_understanding.py
     ├── patient retrieval       backend/structured_retrieval/patient_retriever.py
     │     └── STAIR router      backend/stair_retriever/selector.py (+ constrained.py)
     ├── reference retrieval     backend/rag/reference_index.py  (MedlinePlus + curated KB)
     ├── medicine options        backend/rag/medicine_options.py (+ medicine_options.json)
     ├── reconciliation          backend/evidence_reconciliation/reconcile.py
     ├── evidence assembly       backend/rag/evidence_assembly.py
     ├── action policy           pipeline._policy
     ├── generation              backend/llm/ollama_client.py → Ollama (llama3.2:3b)
     └── claim verification      backend/claim_verification/verifier.py
           │
           ▼
   Patient memory  backend/patient_memory/  (SQLAlchemy models, hierarchy, repository)
     └── data/medresolve.db  (+ data/uploads/ for documents)

 Ingestion:  backend/fhir_ingestion/  (Synthea, MIMIC-IV FHIR demo, eICU demo → ClinicalRecord rows)
 Documents:  backend/ocr_service.py (frozen) → backend/document_checks.py → patient review
 Speech:     backend/speech.py (ffmpeg → faster-whisper)
```

Shared heavy objects (embedder, reference index, router, LLM client) are created once, lazily, in `backend/api/services.py:get_deps()`.

---

## 4. Data model: longitudinal patient memory

### 4.1 Tables (`backend/patient_memory/models.py`)

| Table | Holds |
|---|---|
| `User` | Login account (email, bcrypt hash), linked to one patient |
| `Patient` | Demographics, birth date, onboarding status, source tag (Synthea / MIMIC / user) |
| `ClinicalRecord` | **One clinical fact per row.** It keeps the original FHIR type and ID, encounter, source document, effective and recorded dates, concept code, raw and normalized value and unit, verification status, leaf path in the hierarchy, and provenance JSON. |
| `Document` | Uploaded file metadata, OCR output and review state |
| `Consultation` | Each question and answer: action, evidence, verification report, record offer. `owner` keeps demo sessions apart. |
| `AuditEvent` | Security-relevant actions (login, export, delete, …) |

Facts are never flattened into anonymous text. Every answer can be traced back to exact rows.

### 4.2 The record hierarchy (`backend/patient_memory/hierarchy.py`)

Every patient gets the same **stable skeleton** (levels 1–2). Patient-specific **concept groups** sit under each leaf at level 3, for example *Hypertension* under Conditions.

```
1   demographics
2   medical_history/        2.1 conditions · 2.2 diagnoses · 2.3 procedures · 2.4 immunizations
                            2.5 care_plans · 2.6 social_history
3   medication_history/     3.1 current_medications · 3.2 previous_medications · 3.3 medication_changes
4   allergy_history
5   clinical_encounters/    5.1 previous_symptoms · 5.2 complaints · 5.3 consultations · 5.4 encounter_dates
6   laboratory_observations/6.1 laboratory_results · 6.2 vital_signs · 6.3 historical_trends
                            6.4 assessments_and_surveys
7   medical_documents/      7.1 prescriptions · 7.2 discharge_summaries · 7.3 diagnostic_reports
                            7.4 clinical_notes
```

This outline plays the role of a book's table of contents in STAIR. The router is trained to pick leaves from it, and it can only emit paths that exist (§5.3).

### 4.3 Patient isolation (`backend/patient_memory/repository.py`)

`PatientMemory` is the **only** way retrieval code reads clinical data. It is bound to one `patient_id`, and every query adds `patient_id == :pid`, so records of different patients can never mix. API routes take the patient ID from the JWT, never from the request body.

### 4.4 Ingestion and derived records

- **Ingestion.** `backend/fhir_ingestion/synthea_ingest.py` maps FHIR R4 bundles (Condition, MedicationRequest, AllergyIntolerance, Observation, Encounter, Procedure, Immunization, CarePlan, DiagnosticReport, DocumentReference) to `ClinicalRecord` rows. `mimic_fhir_demo.py` and `eicu_demo.py` do the same for the public demo releases.
- **Classification and units.** `classify.py` holds deterministic lexicons, never an LLM. It separates symptoms, findings and social factors, and normalizes units.
- **Derived records.** `derived.py` adds medication changes (start, dose change, stop) and lab trends (first, latest, min, max, direction). They are marked `source_system="derived"` and cite their source rows.

---

## 5. Models

### 5.1 Answer writer: llama3.2:3b (Ollama)

- **Used as is, not fine-tuned.** It runs locally through Ollama (`backend/llm/ollama_client.py`) with a fixed system prompt.
- **Grounding.** The prompt requires `[E#]` citations for patient facts and `[R#]` for references.
- **Buffered output.** The output is held until claim verification has run, so unverified text is never streamed to the user.

### 5.2 Embeddings: BAAI/bge-m3

- **What it embeds.** Record "concept text" (the patient side) and reference passages.
- **Normalization.** Vectors are L2-normalized, so cosine similarity equals the inner product.
- **Caching.** `backend/rag/embeddings.py` caches vectors by text SHA-1 under `models/embeddings`, so known texts are never re-encoded.

### 5.3 STAIR-Clinical router

**Two-stage routing** (`backend/stair_retriever/selector.py`):

- **Stage 1:** the question plus the patient's outline (levels 1–2) → ranked leaves.
- **Stage 2:** the question plus each selected leaf's concept groups (level 3) → ranked groups.

**Constrained scoring** (`constrained.py`):

- The model doesn't free-generate a path. It computes log P(candidate | prompt) for **every valid path** and reuses the prompt's KV cache.
- Ranking by that score is equivalent to decoding restricted to the set of valid outputs, so **invalid paths are impossible by construction**.

**Backends** (`build_selector`, chosen by `STAIR_BACKEND`):

| Backend | Model | Used for |
|---|---|---|
| `lora` | Qwen2.5-0.5B-Instruct + LoRA adapter | The CPU app's default when an adapter exists |
| `precomputed` | Mistral-7B QLoRA predictions exported from a GPU run | Research results R10/R11 |
| `ollama` | Zero-shot llama3.2:3b | Baseline |
| `structural` | No LLM: BM25 + dense scoring over outline titles | Fallback when no adapter exists |

**Training data** (`training_data.py`):

- Natural-language questions over **real Synthea records**, from templates.
- **Gold evidence is computed from the database.** An LLM never chooses or edits a gold target.
- **Split by patient** (train / validation / test), so test patients are never seen in training.

**Training** (`train_lora.py`, `sft.py`):

- **CPU run:** Qwen2.5-0.5B, 240 examples, 1 epoch. Validation section R@1 rose from 0.227 to 0.780.
- **Reference run:** Mistral-7B-Instruct-v0.2 QLoRA, 100 steps / 800 examples on a cloud T4 (4.4 h). Validation R@1 rose from 0.74 to 0.98.
- **Replication:** a second Mistral run with **seed 29** (`scripts/kaggle_seed2_training.py`) confirmed the result.
- **Where the scripts are:** cloud notebooks and bundles are in `models/stair_clinical/configs/` and `scripts/make_cloud_bundle.py`.

### 5.4 Whisper base (speech-to-text)

- **What runs:** faster-whisper, int8 on CPU (`backend/speech.py`).
- **Decoding:** audio is decoded by the ffmpeg CLI to 16 kHz mono. PyAV is stubbed, because Windows Application Control can block its DLL.
- **Privacy:** audio is never stored or sent anywhere.

---

## 6. The answer workflow (pipeline B5)

`backend/rag/pipeline.py:run_pipeline` runs these steps in order. Safety checks come first.

1. **Emergency screen** (`emergency.py:screen_text`). Deterministic regular expressions look for red flags, including:
   - chest pain with breathlessness, sweating or pain spreading to the arm or jaw;
   - stroke signs, fainting, anaphylaxis, severe bleeding and black stools;
   - severe-dengue warning signs;
   - overdose (by tablet count or a whole strip) and poisoning;
   - worst-ever headache, and confusion with fever;
   - pregnancy with bleeding, pain or severe headache;
   - a diabetic who is vomiting.

   A match **short-circuits everything**. The patient gets a fixed "call emergency services now" message, and no retrieval or generation runs.
2. **Query understanding** (`query_understanding.py`). Rule-based, with no LLM: it extracts symptoms, medicines, organ systems, time expressions (e.g. "last March", "since my surgery") and intent.
3. **Patient retrieval** (`patient_retriever.py`):
   - the STAIR router picks sections;
   - hybrid search (BM25 + BGE-M3 + structured filters for dates, episodes and status) ranks records;
   - the two are fused with RRF, keeping the top 20 records.
4. **Medicine-options check** (`medicine_options.detect`). It recognises requests for over-the-counter help, such as "medicine for fever / headache / cough". There are 15 symptom groups, from fever to dandruff.
5. **Reference retrieval** (`reference_index.py`). Hybrid search over MedlinePlus plus the curated guideline KB, keeping 4 diverse passages. It is skipped for medicine options, which cite their own sources.
6. **Reconciliation** (`reconcile.py`). It looks for conflicts in the gathered evidence:
   - an allergy against a medicine (including cross-allergy by drug class);
   - duplicate active medicines;
   - status disagreements between sources;
   - stale data;
   - a medicine the patient mentions that isn't in their record.
7. **Evidence assembly** (`evidence_assembly.py`):
   - de-duplicates and orders the evidence by date;
   - gives each fact an `[E#]` alias with its date, value, unit and **epistemic status** (confirmed, patient-reported, unconfirmed OCR, derived);
   - lays out the LLM context in labelled sections.
8. **Action policy** (`_policy`). It picks exactly one action:

   | Action | When |
   |---|---|
   | `EMERGENCY_OVERRIDE` | Red flags |
   | `ABSTAIN_AND_NAVIGATE` | High-severity conflict; asks for a diagnosis or prescription; medicine options for a child, another person, pregnancy, or symptoms lasting too long |
   | `GENERAL_OPTIONS` | An adult asks for OTC options and nothing blocks them |
   | `ASK` | No history and set-up never finished; an unknown medicine was mentioned; a new symptom is described too briefly |
   | `EXPLAIN` | Enough evidence to give information |

9. **Generation.** Ollama writes the draft from the assembled context. `GENERAL_OPTIONS` answers are built from the curated JSON (`build_answer`) instead. Each option shows:
   - the medicine's generic and brand names, dose and maximum daily dose;
   - why it was chosen or avoided, based on the patient's allergies and conditions;
   - when to see a doctor;
   - its source (MedlinePlus, WHO or an FDA DailyMed label).
10. **Claim verification** (`verifier.py`). The draft is split into sentences.

    **Patient-specific sentences** must:
    - cite an existing `[E#]`;
    - use only numbers and dates that appear in the cited evidence;
    - name only medicines and diagnoses that appear in the cited evidence;
    - not cite only a reference (`[R#]`) for a patient fact.

    **General sentences** must cite an existing `[R#]` that overlaps in content. Safety advice is always allowed. Unsupported sentences are **withheld** and reported, and only permitted sentences are released.
11. **Record offer.** After an answer about a new problem, the patient can choose **Add to my record** or **Don't add**. Nothing is saved automatically. A saved item becomes a patient-reported, dated entry under *previous symptoms*, linked to the consultation.
12. **Persist.** The consultation is stored with the answer, evidence, verification report and timings.

**Streaming.** `POST /api/v2/consult/stream` emits server-sent events for each stage (`emergency_check`, `retrieving_patient_context`, `retrieving_references`, `reconciling`, `generating`, `verifying`), then the final result. The UI shows live progress.

**Variants B0–B4** switch steps off for the evaluation baselines:

| Variant | What it is |
|---|---|
| B0 | LLM alone |
| B1 | References only |
| B2 | History via STAIR |
| B3 | History via hybrid search |
| B4 | STAIR + hybrid + references, without the safety layers |

---

## 7. Other workflows

### 7.0 Answer modes: memory, normal and both

The patient chooses how a question is answered (`mode` in `POST /api/v2/consult` and `/consult/stream`):

| Mode | What runs | What the patient sees |
|---|---|---|
| `memory` (default) | The full B5 pipeline (§6) | One answer that uses and cites the health record |
| `normal` | B5 with `PipelineConfig(use_memory=False)` | One general answer, labelled "Normal mode" |
| `both` | Normal first, then memory; both share a `pair_id` | Two panels side by side, plus "What your memory changed" |

**What normal mode skips:**
- patient retrieval, the router and reconciliation (no record is read);
- the record checks in medicine options, whose section becomes "Not checked against your records";
- the record offer.

**What normal mode keeps:**
- the emergency screen;
- the action policy, including the child, pregnancy, other-person and duration blocks (age comes from the profile);
- reference retrieval;
- claim verification.

**How normal answers are labelled:**
- they never ask the patient to add their history first;
- they start with a note saying the record was not used;
- their "What your records show" section says "Not used". The code fills this section in after verification, because the verifier would withhold an uncited line written by the model.

**The comparison summary** is computed in the browser (`ChatScreen.tsx`, `CompareSummary`) from the two results:
- the action, if the two answers chose different ones;
- medicine options the record removed;
- flags raised from the record;
- the records the memory answer cited, which can be clicked to open the exact record.

**Streaming.** Every event carries a `panel` field (`normal` / `memory`), so the page fills each panel separately.

**History.** Both answers are saved, and the history list shows a "Normal mode" label on normal answers.

**Evaluation.** This feature is not part of any result in Section VI of the paper.

### 7.1 Sign-up, onboarding and demo access (`backend/api/auth.py`)

- **Sign-up and passwords.** Register with email and password (bcrypt). Birth dates are validated as ISO dates.
- **Tokens.** Login returns a JWT that expires after 12 h.
- **Lockout.** **5 failed logins lock the account for 15 minutes** (HTTP 429).
- **Onboarding.** Collects profile, conditions, medicines and allergies. A user who finishes onboarding with nothing added is treated as "no known history", not as "missing data", and receives general answers labelled as such.
- **Demo patients.** Synthetic and read-only. Each demo login gets a unique token subject (`demo-<uuid>`), and its consultations are stored with that `owner`, so two people using the same demo patient never see each other's questions.

### 7.2 Document upload and OCR (`POST /api/v2/documents`)

1. **Save the upload.** The file is stored under `data/uploads/`. The size and type are checked.
2. **Extract** (`backend/ocr_service.py`). Digital PDFs use their embedded text through PyMuPDF; images and scans go through RapidOCR. Tests, values, units, reference ranges and report dates are then extracted. This file is **hash-frozen** with the OCR evaluation and must not be edited.
3. **Line check** (`backend/document_checks.py`). Each lab value's own line is located, and its unit and range are re-read from that line. Results are marked `verified`, `corrected` or `line_not_found`. This fixed, for example, a platelet count that had been given a neighbouring row's unit and range.
4. **Patient review** (OCR Review screen). Every extracted value stays **unconfirmed** until the patient checks and accepts it. Only then does it become a record.

### 7.3 Speech input (`POST /api/v2/speech/transcribe`)

The 🎤 button records in the browser and uploads the audio (login required, 10 MB maximum). The backend transcribes it locally, and the editable text is placed into the question box. The patient always sees the text before sending.

### 7.4 Diagnostic test cases (`GET /api/v2/test-cases`)

Research → **Test cases (40)** shows the 40 clinician-assessment vignettes. `scripts/build_test_cases.py` builds `evaluation/experiments/diagnostic_cases/test_cases.json` from:

- the question set;
- llama3.2:3b's choices;
- the emergency-screen result for each case;
- post-hoc reasoning (`scripts/generate_case_reasoning.py`, temperature 0, seed 7);
- one MBBS graduate's blind answers (`rater_1.json`). These are **not an answer key**.

### 7.5 Data rights

- **Export:** `GET /api/v2/data/export` downloads all of a patient's data.
- **Delete consultations:** `DELETE /api/v2/data/consultations`.
- **Delete account:** `DELETE /api/v2/data/account`.
- **Audit:** security-relevant actions are recorded in `AuditEvent` (`GET /api/v2/audit`).

---

## 8. Security and safety measures

| Area | Measure |
|---|---|
| Isolation | Patient ID comes only from the JWT; `PatientMemory` filters every query; demo sessions are separated by `owner` |
| Auth | bcrypt hashes, signed JWTs, failed-login lockout, generated secret in `data/.jwt_secret` |
| Input validation | Pydantic length limits (question ≤ 2000 characters), ISO date validators, upload size and type checks |
| CORS | Only the origins in `MEDRESOLVE_CORS_ORIGINS` (localhost by default) |
| Privacy | All models run locally; no external LLM APIs; audio isn't stored; restricted MIMIC data never leaves the machine |
| Clinical safety | Emergency pre-emption, abstention policy, claim verification, OTC blocks (children, pregnancy, other people, symptom duration limits, allergy and cross-allergy, conflicting conditions) |
| Research integrity | Frozen benchmarks and `ocr_service.py` are hash-checked by tests; the doctor-review blinding key is kept out of Git |

The full audit and its 14 fixes are in `docs/security_safety_audit_2026-11-25.md`.

---

## 9. Evaluation

Full protocol and tables: `docs/phase6_experimental_protocol.md`, `docs/phase6_metric_definitions.md`, `docs/results_tables.md`, and the paper in `docs/paper/`.

### 9.1 Retrieval: does it find the right records?

**Data:**
- Synthea test patients (unseen in training);
- MIMIC-IV FHIR demo;
- eICU-CRD demo;
- about 600 questions per source, plus paraphrased versions for robustness.

**Methods:** 11 methods, R1–R11:
- BM25, dense, hybrid (R4), structured operations;
- STAIR variants (structural, Qwen LoRA, Ollama);
- Mistral router alone (R10), and Mistral router fused with hybrid (R11).

**Metrics:**
- **Recall@5** (main metric; capped at min(|gold|, 5));
- Recall@1 and Recall@10, MRR;
- invalid path rate;
- section hit@1 of the router.

**Statistics:** 95% confidence intervals from a **patient-clustered bootstrap** (1,000 resamples), with paired, patient-clustered bootstrap tests between methods.

**Main finding:** the fine-tuned Mistral router fused with hybrid search (R11) beats hybrid alone on every source, with confidence intervals above zero. Non-learned and CPU-scale routers don't reliably beat hybrid.

| | Synthea | MIMIC | eICU |
|---|---|---|---|
| Section hit@1 (seed 13 / seed 29) | 0.958 / 0.965 | 0.723 / 0.735 | 0.830 / 0.855 |
| R11 Recall@5 (seed 13 / seed 29) | 0.908 / 0.891 | 0.924 / 0.925 | 0.954 / 0.958 |

### 9.2 Answer quality (B0–B5)

**Data:** 120 Synthea questions and 60 MIMIC questions.

**Metrics:**
- unsupported patient-claim rate (raw, and in the released text);
- evidence support rate;
- historical context coverage;
- patient-history consistency;
- safety probes handled correctly.

**Results:**
- B5 released **0** unsupported patient claims on Synthea and **2** on MIMIC.
- B5 handled **5/5** safety probes; every other variant handled 1/5.
- Retrieving history roughly doubles coverage of the expected facts.

### 9.3 Extra checks

- **Rater agreement:** llama3.2:3b alone agreed with one blinded MBBS-graduate rater on **34/40** vignettes. This is agreement, not accuracy: there's no answer key.
- **Emergency screen:** it flagged 6 of the 40 vignettes before the safety review and 13 after.
- **Unit tests:** about 250 pytest tests cover the components.

### 9.4 Not yet measured

- **Clinician rating** of answer correctness. The doctor-review packet is in `evaluation/experiments/doctor_review/`.
- **False-alarm rate** of the emergency screen.
- **Real-world accuracy** of OCR on photos, and of speech input.

---

## 10. Known limitations

- **The best router needs a GPU.** The CPU app uses the smaller Qwen router or the structural router.
- **Rule-based parsing is fragile.** Query understanding and time parsing are rule-based, and reworded questions still cost 0.03–0.07 Recall@5.
- **English only.** The emergency screen matches English keywords only, so other languages and misspellings are missed.
- **Medicine options aren't clinician-reviewed yet.** They come from a curated file.
- **Photo OCR can mis-pair values.** These are flagged but not fixed, because the extractor is frozen.
- **Synthetic and demo data only.** The system has not been tested on real patients or reviewed by an ethics board.

---

## 11. Development history (summary)

| Phase | Outcome |
|---|---|
| 1–4 | Baseline ML, curated knowledge base, conflict taxonomy and benchmark, evidence ledger |
| 5.x | RAG pipeline, claim verification, OCR pipeline (frozen), SSE streaming, security audits |
| 6 | Experimental protocol, metric definitions, statistical analysis plan |
| v2 | Longitudinal patient memory, STAIR-Clinical router, B0–B5 pipeline, 14-screen patient app |
| v2 follow-ups | Seed-29 replication, medicine options with doses (15 groups), safety audit (14 fixes), healthy-user answers, record offer, test-cases page, OCR line checks, offline speech input |

Per-phase result reports: `docs/phase*_results.md`.

---

## 12. Further reading in `docs/`

| Topic | File |
|---|---|
| Architecture | `system_architecture.md`, `rag_architecture.md`, `architecture.md` |
| STAIR-Clinical | `stair_clinical_methodology.md`, `training_methodology.md` |
| Data | `dataset_documentation.md`, `data_card.md`, `data_processing_pipeline.md`, `knowledge_corpus.md` |
| Safety | `action_policy.md`, `emergency_detection_vs_precedence.md`, `claim_verification_audit.md`, `privacy_and_safety.md`, `security_safety_audit_2026-11-25.md` |
| OCR | `ocr_architecture.md`, `document_processing_protocol.md`, `measurement_unit_safety.md` |
| Evaluation | `phase6_experimental_protocol.md`, `phase6_metric_definitions.md`, `retrieval_evaluation.md`, `results_tables.md` |
| API | `api_documentation.md` |
| UI design | `MEDRESOLVE_DESIGN_SYSTEM.md` |
