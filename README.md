# MedResolve

**STAIR-enabled, longitudinal, patient-context-aware medical information assistant (research prototype).**

MedResolve answers a patient's new health question in light of their **own history**: earlier conditions, current and previous medications, allergies, earlier symptoms, encounters and lab results. Every patient-specific statement must cite the record it comes from, and the app shows which records and which medical references shaped each answer.

> ⚠️ Academic research prototype. **Not** a diagnostic or prescribing system and **not** clinically validated. All bundled data is synthetic (Synthea).

## What is in this repository
| Area | Where |
|---|---|
| Longitudinal patient memory (FHIR R4 → normalized records, provenance, ToC) | `backend/patient_memory/`, `backend/fhir_ingestion/` |
| STAIR-Clinical (hierarchy, prompts, constrained scoring, selectors, data generator, LoRA trainer) | `backend/stair_retriever/` |
| Hybrid retrieval (BM25, BGE-M3, RRF, structured ops) + reference corpus | `backend/structured_retrieval/`, `backend/rag/` |
| Safety: emergency pre-emption, reconciliation, claim verification | `backend/evidence_reconciliation/`, `backend/claim_verification/` |
| API (FastAPI, JWT, patient isolation, SSE) | `backend/api/`, mounted in `backend/main.py` |
| Web app (React + TypeScript + Vite + Tailwind) — 14 patient screens | `frontend/src/v2/` (default route) |
| Phase 1–6 research system (unchanged, incl. frozen benchmarks) | `experiments/`, `/api/*`, frontend `#/research` |
| Evaluation (retrieval, SearchTome, B0–B5 responses) | `evaluation/` |
| Documentation | `docs/` (start with `system_architecture.md`) |

## Quick start (Windows / Linux, Python 3.11, Node 20+)
```bash
pip install -r requirements.txt
```
```bash
python scripts/download_datasets.py
```
```bash
bash scripts/generate_synthea.sh
```
```bash
python -m backend.fhir_ingestion.synthea_ingest --input data/datasets/synthea/raw/generated_p600_seed20261101/fhir --tag generated_p600_seed20261101 --reset
```
```bash
python -m backend.rag.reference_corpus
```
```bash
python -m backend.stair_retriever.training_data
```
Local LLM: install [Ollama](https://ollama.com) and pull the default model (configurable with `OLLAMA_MODEL`).
```bash
ollama pull llama3.2:3b
```
Run the API and the web app:
```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```
```bash
cd frontend && npm install && npm run dev
```
Open http://localhost:5173. Create an account, or open a **synthetic demo patient** (read-only) from the sign-in page.

### Configuration (environment variables)
| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///data/medresolve.db` | PostgreSQL: `postgresql+psycopg2://user:pass@host:5432/medresolve` |
| `OLLAMA_MODEL` / `OLLAMA_URL` | `llama3.2:3b` / `http://localhost:11434` | local LLM (localhost only) |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | dense retrieval |
| `STAIR_BACKEND` | `auto` | `lora` (adapter in `models/stair_clinical/adapters/current`), `ollama`, `structural` |
| `JWT_SECRET` | generated into `data/.jwt_secret` | token signing |

## Training and evaluation
```bash
python -m backend.stair_retriever.train_lora --task clinical --stage 1 --base-model Qwen/Qwen2.5-0.5B-Instruct --max-train-queries 500 --epochs 1 --output-dir models/stair_clinical/checkpoints/run
```
```bash
python -m evaluation.experiments.patient_context_retrieval.run_retrieval_eval --split test --sample 600
```
```bash
python -m evaluation.experiments.stair.run_searchtome --zero-shot-n 100 --ollama-n 50
```
```bash
python -m evaluation.experiments.response_evaluation.run_response_eval --n-queries 12
```
The reference Mistral-7B LoRA configuration needs a GPU; use `models/stair_clinical/configs/stair_cloud_gpu_training.ipynb` together with `python scripts/make_cloud_bundle.py`.

## Tests
```bash
python -m pytest
```
```bash
cd frontend && npm run build
```

## Results (synthetic data; see `docs/retrieval_evaluation.md`, `docs/results_tables.md`)
- **Patient-context retrieval, 599 test queries / 108 unseen patients.** Hybrid BM25 + BGE-M3 + structured operations is the strongest single method (R@5 0.758). STAIR+hybrid fusion reaches the best R@10 (0.873, structural selector) and R@1/MRR (0.716/0.770, LoRA selector), but **no STAIR variant significantly beats hybrid on R@5 or MRR**. 0 invalid evidence paths.
- **STAIR-Clinical LoRA** (reduced scale: Qwen2.5-0.5B, 240 examples, CPU): validation section R@1 0.227 → 0.780; free-generation invalid paths 0/30. The Mistral-7B reference configuration is **not run** (no GPU; notebook provided).
- **Responses (B0–B5, n=8 + 5 probes).** History raises gold-concept coverage from 0.38 to 0.79. The B5 gate released **0** unsupported patient-specific claims, and the action policy was correct on 5/5 safety probes. Factual correctness is **not yet rated** by clinicians.
- **SearchTome (official reduced release).** BM25 medicine R@1 0.678; zero-shot free-generation LLM produced invalid leaves 20/30 times. Paper numbers are not reproduced (the release differs from the paper).

## Data status
Synthea: generated and ingested. SearchTome: official reduced HF release, validated. MedlinePlus: indexed. **MIMIC-IV: pending PhysioNet authorization; not downloaded or used.** See `docs/dataset_documentation.md`.
