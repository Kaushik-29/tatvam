# MedResolve — Developer Guide

This guide is for a developer who is joining the project: how the codebase is organised, where to make common changes, how to debug and test, and which rules must not be broken.

Before reading it:
- **Setup:** [`README.md`](README.md) covers installing and running the app.
- **Design:** [`TECHNICAL_DOCUMENTATION.md`](TECHNICAL_DOCUMENTATION.md) explains why the system is built this way.

---

## 1. Ground rules (read first)

These rules protect the research results, the patients' privacy and the users' safety. Break one and you can invalidate the paper or leak data.

1. **Never edit frozen files.** `backend/ocr_service.py`, the frozen Phase 5/6 benchmarks under `experiments/` and their manifests are hash-checked by tests (`tests/test_phase5_5_2_1_freeze.py`, `tests/test_phase5_5_ocr.py` and others).
   - To change OCR behaviour, add a layer after it, the way `backend/document_checks.py` does.
   - On Windows, `git` may show `ocr_service.py` as modified only because of line endings. **Don't stage it.** If it was ever edited, restore it with:

     ```powershell
     git show HEAD:backend/ocr_service.py | Set-Content -NoNewline -Encoding utf8 backend/ocr_service.py
     ```

     Then run the freeze tests.
2. **Never commit data or secrets.** `data/medresolve.db*`, `data/uploads/`, `data/.jwt_secret`, `models/` and raw datasets are gitignored, and must stay that way. The repository on GitHub is **public**.
3. **Never commit the doctor-review key.** `evaluation/experiments/doctor_review/key/` holds the blinding key. It would unblind the clinician review.
4. **Never send patient data off the machine.** No external LLM APIs, especially not with MIMIC data (PhysioNet terms). The LLM must stay on `localhost` (Ollama).
5. **Never fabricate results or datasets.** Every number in the paper and in `docs/` must come from a script in this repository and its output files. Don't describe a model as fine-tuned unless it was.
6. **Keep patient isolation.** Read clinical data only through `PatientMemory(session, patient_id)`. API routes take the patient from the JWT (`current_patient_id`), never from the request body or URL.
7. **Safety comes before the LLM.** Any new safety check must run before generation, and must be deterministic and unit-tested.
8. **Commit only finished, tested work.** Run `python -m pytest` and `npm --prefix frontend run build` before committing.

---

## 2. Repository map

```
MedResolve/
├── backend/                     Python package (FastAPI app + all logic)
│   ├── main.py                  App entry point: CORS, legacy /api routes, mounts the v2 routers
│   ├── config.py                All settings (env variables) and paths
│   ├── api/
│   │   ├── auth.py              /api/v2/auth: register, login, demo login, JWT, lockout
│   │   ├── patient_routes.py    /api/v2: every patient-facing endpoint
│   │   └── services.py          get_deps(): lazily builds embedder, indexes, router, LLM (once)
│   ├── patient_memory/          Data layer
│   │   ├── models.py            SQLAlchemy tables (User, Patient, ClinicalRecord, Document, Consultation, AuditEvent)
│   │   ├── db.py                Engine, session, lightweight migrations (_migrate)
│   │   ├── hierarchy.py         The fixed record outline (leaves 1 – 7.4) = STAIR "table of contents"
│   │   ├── repository.py        PatientMemory: patient-scoped reads + ToC building
│   │   ├── classify.py          Deterministic lexicons and unit normalization
│   │   └── derived.py           Medication-change and lab-trend records
│   ├── fhir_ingestion/          Synthea / MIMIC-IV demo / eICU demo → ClinicalRecord rows
│   ├── rag/
│   │   ├── pipeline.py          ★ run_pipeline (B0–B5) and _policy: start here
│   │   ├── query_understanding.py  Rule-based parsing of the question
│   │   ├── evidence_assembly.py    [E#]/[R#] context for the LLM
│   │   ├── medicine_options.py/.json  Curated OTC options, doses, blocks
│   │   ├── reference_corpus.py  Builds the MedlinePlus + KB corpus
│   │   ├── reference_index.py   BM25/dense/hybrid reference search
│   │   ├── embeddings.py        Cached BGE-M3 embedder
│   │   └── fusion.py            Tokenizer + RRF
│   ├── structured_retrieval/patient_retriever.py  BM25, dense, hybrid, structured, STAIR
│   ├── stair_retriever/         Router: selector, constrained scoring, prompts, training data, LoRA training
│   ├── evidence_reconciliation/ emergency.py (red flags) · reconcile.py (conflicts)
│   ├── claim_verification/verifier.py  Sentence-level checks, release gate
│   ├── llm/ollama_client.py     Local Ollama client
│   ├── ocr_service.py           🔒 FROZEN OCR extractor
│   ├── document_checks.py       Line-level unit/range correction after OCR
│   └── speech.py                ffmpeg + faster-whisper transcription
├── frontend/                    React + TypeScript + Vite + Tailwind
│   └── src/
│       ├── App.tsx              Router: v2 patient app (default) and legacy research screens
│       └── v2/
│           ├── PatientApp.tsx   Shell, sidebar NAV, screen switching
│           ├── api.ts           ★ Every backend call (fetch wrapper, SSE stream)
│           ├── types.ts         TypeScript shapes of API responses
│           ├── ui.tsx / components.tsx  Shared UI pieces (badges, banners, MicButton…)
│           └── screens/         One file per screen (Chat, Concern, Timeline, Documents, OcrReview, TestCases…)
├── tests/                       pytest suite (~250 tests)
├── scripts/                     Data download, Synthea, Kaggle/cloud training, test-case builders
├── evaluation/                  Metrics and experiment runners (retrieval, responses, paraphrase, doctor review)
├── experiments/                 Phase 1–6 research system (frozen benchmarks)
├── models/                      (gitignored) embeddings cache, router adapters, Whisper
├── data/                        (mostly gitignored) DB, uploads, datasets, knowledge bases
├── docs/                        Component write-ups; docs/paper/ = IEEE paper build
└── doctor_assessment_app/       Separate app for the 40-case doctor assessment
```

---

## 3. How a request flows (read this code first)

To understand the system, read these files in this order:

1. **`frontend/src/v2/screens/ChatScreen.tsx`** (or `ConcernScreen.tsx`): the user types or speaks a question.
2. **`frontend/src/v2/api.ts`**: `consultStream()` posts to `/api/v2/consult/stream` with the JWT.
3. **`backend/api/patient_routes.py`**: the `/consult/stream` handler checks the token, gets `get_deps()`, and runs the pipeline in a thread that emits SSE events.
4. **`backend/rag/pipeline.py`**: `run_pipeline` runs the steps listed in its header (emergency → … → verification). The comments are numbered `# 1.` to `# 9.`.
5. **`backend/rag/pipeline.py`**: `_policy()` is the single place where the action is decided.
6. **`backend/claim_verification/verifier.py`**: decides which sentences are released.
7. **Back in the UI**, `ui.tsx` draws the action banner, and the "Why this answer" screens show the evidence, references and conflicts stored with the consultation.

---

## 4. Daily workflow

**Terminal 1, backend.** Restart it after every backend change, because it runs without reload:

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

`--reload` works too, but each reload re-loads BGE-M3 and the router, which is slow.

**Terminal 2, frontend.** It hot-reloads on save:

```powershell
npm --prefix frontend run dev
```

**Before committing:**

```powershell
python -m pytest
```

```powershell
npm --prefix frontend run build
```

**A faster loop.** Run one test file, or one test by name:

```powershell
python -m pytest tests/test_medicine_options.py -q
```

```powershell
python -m pytest tests/test_security_audit.py -q -k emergency
```

**Run the pipeline without the web app.** This is useful while debugging. Save the following as a scratch file outside the repository (for example `try_pipeline.py`), put a real patient ID in it, and run it from the project folder with `python try_pipeline.py`:

```python
import sys; sys.path.insert(0, ".")
from backend.patient_memory.db import session_scope
from backend.api.services import get_deps
from backend.rag.pipeline import run_pipeline, PipelineConfig

with session_scope() as s:
    r = run_pipeline(s, "<patient_id>", "I have had a fever since yesterday. Which medicine can I take?",
                     cfg=PipelineConfig(persist=False), deps=get_deps())
    print(r["action"], "-", r["action_reason"])
    print(r["final_text"])
```

`persist=False` keeps the test question out of the patient's consultation history.

**Branches and commits:**

- **Branch:** work happens on `medresolve-v2`, which is pushed to `main` on GitHub (`Kaushik-29/tatvam`).
- **Messages:** write commit messages that say what changed and why.
- **What to stage:** check `git status` first, and never stage `backend/ocr_service.py` or anything in `data/`.

---

## 5. Common changes: where and how

### 5.1 Add or change a medicine-options group

**Files:**
- `backend/rag/medicine_options.json` (data)
- `backend/rag/medicine_options.py` (logic)
- `tests/test_medicine_options.py`

**Steps:**

1. **Add a source** under `"sources"` (for example `"S27": {title, url}`). Use MedlinePlus, WHO or an FDA DailyMed label. **Every option, dose, caution and warning must cite a source.**
2. **Add a group** under `"groups"` with these fields:

   | Field | What it holds |
   |---|---|
   | `label` | The group's display name |
   | `symptoms` | Trigger words |
   | `options` | Each option has `generic`, `names` (also used for allergy matching), `brands`, `use` (dose), `limit` (maximum per day), `sources`, `cautions` (record words that turn on a caution), and optionally `allergy_names` and `skip_if_query` |
   | `avoid` | Medicines to avoid |
   | `see_doctor` | Warning signs |
   | `max_days` | How long self-care is acceptable; after that the answer becomes "see a doctor" |

3. **Check detection.** If the new symptom words overlap with an existing group, check `detect()`.
4. **Add tests:** detection, the generated answer, an allergy block, and the child, pregnancy and long-duration blocks.
5. **Run the safety tests:**

   ```powershell
   python -m pytest tests/test_medicine_options.py tests/test_security_audit.py -q
   ```

### 5.2 Add an emergency red flag

**Files:**
- `backend/evidence_reconciliation/emergency.py` (`RED_FLAGS`)
- `tests/test_security_audit.py`

**Steps:**

1. **Add an entry** `(label, [trigger regexes], [required co-symptom regexes])`. An empty second list means the trigger alone is enough.
2. **Write tests in both directions:** phrases that **must** fire, and everyday phrases that must **not** fire. False alarms train users to ignore the screen.
3. **Rebuild the test-case snapshot.** The 40 test cases store each case's emergency result, and a test checks it is still in sync:

   ```powershell
   python scripts/build_test_cases.py
   ```

### 5.3 Change when the app answers, asks or abstains

**File:** `_policy()` in `backend/rag/pipeline.py`.

- **Order matters:** emergency → high conflict → medicine options → decision request → no history → unknown medicine → too-short question → explain.
- **Tests:** add a case to `tests/test_action_policy.py` or `tests/test_security_audit.py`.
- **Paper:** changing the policy changes B5 results in the paper, so re-run the response evaluation if the change affects evaluated behaviour.

### 5.4 Add an API endpoint

1. **Add the route** in `backend/api/patient_routes.py` (prefix `/api/v2`).
   - Use `pid: str = Depends(current_patient_id)` to get the patient from the token, and `s: Session = Depends(get_session)` for the database.
   - Use a Pydantic model with `Field(max_length=…)` for every input string, and validate dates with the existing `iso_date` validators.
2. **Read data** through `PatientMemory`. Filter consultations with `_owned(owner)`, where `owner` comes from `Depends(consultation_owner)`, so demo sessions stay separate.
3. **Block writes for demo users** (return 403), like `record-decision` does.
4. **Record an `AuditEvent`** for anything security-relevant.
5. **Add the client function** in `frontend/src/v2/api.ts` and its type in `types.ts`.
6. **Add tests**, including one showing that another patient's data cannot be reached.

### 5.5 Add a database column

1. **Add the column** to the model in `backend/patient_memory/models.py`.
2. **Add an `ALTER TABLE … ADD COLUMN`** in `db.py:_migrate()`, guarded by a check that the column is missing. Existing SQLite databases are upgraded at start-up this way; there is no Alembic.
3. **If it should be exported**, update `record_to_dict` and the export endpoint.

### 5.6 Add a frontend screen

1. **Create** `frontend/src/v2/screens/MyScreen.tsx`.
2. **Register it** in `PatientApp.tsx`: add its ID to `V2Screen`, an entry to `NAV`, and a render case.
3. **Use the shared parts:** styles from `ui.tsx` and `components.tsx`, and the colours and spacing in `docs/MEDRESOLVE_DESIGN_SYSTEM.md`.
4. **Hide writes for demo users** (`readOnly={isDemo}` pattern).
5. **Type-check:**

   ```powershell
   npm --prefix frontend run build
   ```

### 5.7 Change OCR results

**Don't touch `ocr_service.py`.** Add the logic to `backend/document_checks.py`, which runs after extraction on the v2 upload path. Show any new flags in `frontend/src/v2/screens/OcrReviewScreen.tsx`. Values must stay unconfirmed until the patient reviews them.

### 5.8 Change the answer modes (memory / normal / both)

**Backend:**
- **The switch:** `PipelineConfig.use_memory` in `backend/rag/pipeline.py`. Every place that reads the record checks `use_mem`.
- **Where the modes are expanded:** `_mode_runs()` in `patient_routes.py` turns a mode into one or two pipeline runs.
- **Rule:** anything new that reads the patient's record must be skipped when `use_mem` is false. Add a test in `tests/test_answer_modes.py` proving normal mode doesn't read it.

**Frontend:**
- **The switch:** `AnswerModeSwitch` and `useAnswerMode` (remembered in `localStorage`) in `frontend/src/v2/components.tsx`.
- **The panels and the comparison summary:** `ChatScreen.tsx` (`AnswerCard`, `CompareSummary`).

### 5.9 Change the LLM or the prompt

- **Model:** set `OLLAMA_MODEL`. No code change is needed.
- **Prompt:** the system prompt and prompt building are in `pipeline.py`.
- **Citation format:** keep the `[E#]` / `[R#]` rules, because the verifier depends on them.
- **After any prompt change**, re-check the unsupported-claim rate with the response evaluation (§8).

---

## 6. Testing

| Test file | Covers |
|---|---|
| `test_security_audit.py` | The 14 audit fixes: emergency patterns, isolation, lockout, validation, CORS, test-case snapshot, rater data |
| `test_medicine_options.py` | Group detection, doses, allergy and cross-allergy, child, pregnancy and duration blocks |
| `test_record_offer.py` | "Add to record / Don't add" flow, 409 on a second decision, demo 403 |
| `test_answer_modes.py` | Memory / normal / both modes: normal never reads the record, safety still applies, panels in the stream |
| `test_ocr_and_speech.py` | `document_checks` line correction, speech endpoint limits |
| `test_rag_pipeline.py`, `test_action_policy.py` | Pipeline variants and the action policy |
| `test_longitudinal_*.py`, `test_temporal_windows.py` | Patient memory, API, safety, time windows |
| `test_leakage_prevention.py`, `test_subset_selection.py` | No train/test patient leakage |
| `test_phase5_*`, `test_phase6_*` | Frozen research system, OCR freeze hashes, protocol checks |
| `fixtures/fhir_fixture.py` | Small synthetic FHIR patients used by tests |

**Testing rules:**
- **Every safety rule needs tests in both directions:** cases that must trigger it and cases that must not.
- **No real LLM or network calls in tests.** Use `use_llm=False` or a stub. Tests must pass with Ollama turned off.
- **If a freeze test fails**, you changed a frozen file. Revert it; don't update the hash.

---

## 7. Debugging

### Where to look

| Symptom | Look at |
|---|---|
| Backend errors | The Uvicorn terminal (logging level INFO; loggers are named `MedResolve.*`) |
| Which router or LLM is active | Start-up log line `Services ready: STAIR backend=…, LLM=…`, or `GET /api/v2/system/status` |
| Why an answer was ASK / ABSTAIN | The consultation's `action_reason`; "Previous consultations" in the UI; `_policy()` |
| A sentence disappeared from the answer | `verification` in the consultation: each claim's status and why it was withheld (missing citation, number not in evidence, unknown entity…) |
| Wrong records retrieved | `retrieval_trace` in the consultation (router leaves, scores, invalid paths) and the "Retrieved patient context" screen |
| Slow answers | `timings` in the result (`emergency_check_s`, `patient_retrieval_s`, `reference_retrieval_s`, generation, verification) |
| Frontend issues | The browser dev tools Console and Network tabs. SSE events appear under `/api/v2/consult/stream`. |
| Database contents | Open `data/medresolve.db` with any SQLite viewer. **Stop the backend first** (WAL mode), or open it read-only. |

### Known problems and fixes

| Problem | Cause and fix |
|---|---|
| Code change has no effect | The backend runs without reload. Restart it. |
| `ImportError` / DLL blocked for `av` | Windows Application Control blocks PyAV. `speech.py` installs a stub and uses ffmpeg instead. Don't try to bypass the policy. |
| Speech: "ffmpeg not found" | Install it with WinGet, or set `FFMPEG_PATH`. |
| Freeze tests fail on a clean checkout | Line endings changed on `ocr_service.py`. Restore it from `HEAD` (§1). |
| `401` in the UI | The token expired, or `JWT_SECRET` changed (for example `data/.jwt_secret` was deleted). Sign in again. |
| Reference list empty | Corpus not built. Run `python -m backend.rag.reference_corpus`. |
| `LoraSelector` slow on first question | The Qwen model loads lazily on first use; later questions are faster. |
| Demo patient shows another user's questions | Must never happen. Check that the route filters by `owner`, and add a test. |

---

## 8. Training and evaluation

### Train the router

**CPU (Qwen2.5-0.5B, small scale):**

```powershell
python -m backend.stair_retriever.train_lora --task clinical --stage 1 --base-model Qwen/Qwen2.5-0.5B-Instruct --max-train-queries 500 --epochs 1 --output-dir models/stair_clinical/checkpoints/run
```

To use the result in the app, copy it to `models/stair_clinical/adapters/current`. It must contain `stair_clinical_meta.json`.

**GPU (Mistral-7B QLoRA, as in the paper):**
- **Notebook:** `models/stair_clinical/configs/stair_cloud_gpu_training.ipynb`, with the bundle from `python scripts/make_cloud_bundle.py`.
- **Kaggle:** `scripts/kaggle_seed2_training.py` reproduces the second (seed 29) run with the same settings as seed 13. It needs an `HF_TOKEN` Kaggle secret for the gated Mistral weights.
- **Scoring:** score the test questions on the GPU (`python -m backend.stair_retriever.predict_stage1 predict …`), then evaluate locally with `--methods R10_stair_precomputed,R11_stair_precomputed_hybrid --stage1-predictions <file>`.

### Run the evaluations

Retrieval:

```powershell
python -m evaluation.experiments.patient_context_retrieval.run_retrieval_eval --split test --sample 600
```

Answer quality (B0–B5):

```powershell
python -m evaluation.experiments.response_evaluation.run_response_eval --n-queries 12
```

Robustness to reworded questions:

```powershell
python -m evaluation.experiments.paraphrase_robustness.run_paraphrase --help
```

**Rules for evaluations:**
- Set `MEDRESOLVE_TODAY` when a run has to be repeated exactly.
- Results go under `evaluation/experiments/*/results`. Never overwrite frozen result files: write new ones.

### Diagnostic test cases

Regenerate the AI's reasoning. This needs Ollama:

```powershell
python scripts/generate_case_reasoning.py
```

Rebuild the test-case file the app reads:

```powershell
python scripts/build_test_cases.py
```

**About the rater file.** Rater answers live in `evaluation/experiments/diagnostic_cases/rater_1.json`. Refer to the rater only as "MBBS graduate", never by name. Her answers are **not** an answer key.

---

## 9. The paper

**Where it is:** `docs/paper/build_ieee_docx.js` builds `MedResolve_IEEE.docx` (with the clinician review). Setting `NO_CLINICIAN_REVIEW=1` builds `MedResolve_IEEE_no_clinician_review.docx` instead.

**How the two versions differ:** text that differs between them uses `rv(withReview, noReview)`.

**Before committing paper changes:**

1. **Rebuild both versions.**
2. **Export them to PDF.**
3. **Check that both are still 8 pages.**
4. **Check that every new number matches a result file** in the repository.

---

## 10. Open work (good next steps)

**Needs a clinician:**
- Clinician review of answers. The packet is in `evaluation/experiments/doctor_review/`, and the analysis is `analyze_ratings.py`.
- A second clinician to adjudicate the 6 vignette disagreements.

**Needs testing:**
- Measure the false-alarm rate of the emergency screen on ordinary questions.
- Test the real microphone and real photo OCR on several devices.

**Needs development:**
- Non-English and misspelling support for the emergency screen.
- A learned query parser to replace the rule-based time and episode parsing.
- Make the Mistral router usable without a GPU (quantised CPU inference), or distil it into the Qwen model.
