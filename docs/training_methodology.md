# Training Methodology — STAIR and STAIR-Clinical

## Hardware actually available
| Item | Value |
|---|---|
| CPU | Intel Core i7-13700H, 14 cores / 20 threads |
| RAM | 15.7 GB |
| GPU | Intel Iris Xe (integrated, 2 GB shared) — **no CUDA** |
| Disk free | D: 122 GB |
| Software | Python 3.11.0, torch 2.13 (CPU), transformers 4.57.6, peft 0.17.1 |

On this hardware, Mistral-7B LoRA training was not attempted locally. The reference configuration was trained on a free cloud GPU instead (Tesla T4, 15.6 GB; see the Mistral run below).

## Stage 1 — original STAIR (SearchTome)
- Prompt format: `backend/stair_retriever/prompts.py::original_stair_prompt` (paper Table 2). The ToC is rebuilt from the numbered leaf titles of the release.
- Reference configuration: Mistral-7B-Instruct-v0.2, 4-bit QLoRA, r=16, α=32, dev Recall@1 early stopping. Notebook: `models/stair_clinical/configs/stair_cloud_gpu_training.ipynb`. **Status on SearchTome: not run.** The GPU budget went to the STAIR-Clinical task (below).
- Run locally on CPU: flat BM25 / BGE-M3 / hybrid baselines and an out-of-the-box constrained baseline with the untrained base LM (see `retrieval_evaluation.md`, SearchTome section).

## Stage 2 — STAIR-Clinical training data
See `stair_clinical_methodology.md §4`: 16,198 / 3,074 / 3,736 queries, split by patient, with programmatic gold. Each example records patient ID, query, category, expected leaf paths, expected evidence paths, gold evidence IDs, temporal constraint, source FHIR resource IDs and split.

## Stage 3 — fine-tuning
`python -m backend.stair_retriever.train_lora` (one script for both tasks):
- One SFT example per (query, gold path). Loss is computed on target tokens only (prompt tokens masked to -100). Examples longer than `--max-len` are skipped and counted.
- LoRA r=16, α=32, dropout 0.05 on `q,k,v,o`; AdamW, lr 2e-4, 3% linear warm-up then linear decay; gradient accumulation 8; gradient clipping 1.0.
- Evaluation: constrained scoring of **all valid candidates** gives Recall@1/3/5, MRR and exact path match@1. Free greedy generation on a sample gives the invalid-path (hallucination) rate. Validation runs before training (base model + zero-initialized adapter, i.e. the base model) and after training.
- Recorded in `train_metrics.json`: model, tokenizer, LoRA settings, loss history per step, validation metrics, train time, hardware, seed, and SHA-256 of every adapter file. `training_status` is set to `smoke_test_only` (<10 optimizer steps; the v1 rule used `max_steps<50` and mislabelled run2, which was corrected with a note), `completed_reduced_scale` (non-reference model) or `completed` (reference model).

### Runs performed
| Run | Base model | Data | Steps | Status |
|---|---|---|---|---|
| `smoke_stage1` | Qwen2.5-0.5B-Instruct | 40 queries → 49 examples | 5 | **smoke_test_only** — pipeline check; 20-query validation R@1 0.35 → 0.55 (too small to interpret) |
| `qwen05b_stage1_cpu_run1` | Qwen2.5-0.5B-Instruct | 500-query pool | 12 of 79 | **crashed** (segmentation fault under memory pressure, 16 GB shared with Ollama + API). No checkpoint existed; checkpoint/resume (`--save-every`, `--resume`) was added afterwards. Log kept. |
| `qwen05b_stage1_cpu_run2` | Qwen2.5-0.5B-Instruct | 500-query pool (628 tokenized examples); **30 steps × 8 = 240 examples, 1 pass** | 30 | **completed_reduced_scale**; 3,977 s on CPU (8 threads); installed as `models/stair_clinical/adapters/current` |
| `mistral7b_clinical_stage1` | Mistral-7B-Instruct-v0.2, 4-bit NF4 QLoRA, fp16 compute | 4,000-example pool; **100 steps × 8 = 800 examples** (0.2 of one pass) | 100 | **completed** (reference configuration, reduced number of steps); 15,779 s on a Tesla T4. The run started on Colab, which disconnected, and resumed on Kaggle from the step-75 checkpoint (`--resume`). |

## Results
Validation (150 queries from unseen validation patients, stage-1 section routing, constrained scoring over the patient's valid sections):

| | R@1 | R@3 | R@5 | MRR | Free-generation invalid-path rate |
|---|---|---|---|---|---|
| Base Qwen2.5-0.5B-Instruct (no fine-tuning) | 0.227 (34/150) | 0.373 | 0.467 | 0.358 | — |
| + STAIR-Clinical LoRA (run2) | **0.780 (117/150)** | 0.913 | 0.980 | 0.860 | **0/30** (exact match 23/30) |

Mistral-7B reference configuration (300 validation queries, same protocol):

| | R@1 | R@3 | R@5 | MRR | Free-generation invalid-path rate |
|---|---|---|---|---|---|
| Base Mistral-7B-Instruct-v0.2 (no fine-tuning) | 0.740 (222/300) | 0.920 | 0.960 | 0.834 | — |
| + STAIR-Clinical QLoRA (100 steps) | **0.980 (294/300)** | 1.000 | 1.000 | 0.990 | **0/100** (exact match 0.99) |

On the 599-query **test** sample (108 unseen patients; scored on Kaggle with `backend.stair_retriever.predict_stage1`), the trained Mistral router puts a gold section first for **574/599 (0.958)** and in the top 3 for 599/599. Metrics are in `models/stair_clinical/checkpoints/mistral7b_clinical_stage1/train_metrics.json`, transcribed from the Kaggle output; the loss history and adapter SHA-256 were not copied back, and the adapter weights are not in the repository. The base 7B model is already a strong zero-shot router (0.74, against 0.23 for Qwen-0.5B), so the 7B gain is smaller in absolute terms but closes most of the remaining gap.

The run was deterministic: run1 and run2 had identical step-0 validation and step-1 loss. Training loss went from 3.35 at step 1 to about 0.2 by step 8 and 0.14 at step 30. Full loss history, hardware, seed and adapter SHA-256 are in `models/stair_clinical/checkpoints/qwen05b_stage1_cpu_run2/train_metrics.json` (adapter weights `be3f48586075587de06fed5d0da3da1413a8538da9a09be660b136cb5644b5e8`).

**Interpretation limits:** this is section-level (stage-1) routing on synthetic Synthea questions generated from templates, so validation questions share templates with training questions (patients are disjoint, templates are not). Results show the routing skill is learnable from the hierarchy. They do not show generalization to free-form real patient language. Test-split record-level results are in `retrieval_evaluation.md`.
