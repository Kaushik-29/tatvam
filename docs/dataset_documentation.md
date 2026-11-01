# Dataset Documentation (v2 longitudinal stack)

Each dataset has one job; they are never used interchangeably. All downloads go through `scripts/download_datasets.py`, which writes a `download_manifest.json` (URL, access date, size, SHA-256, licence, citation) next to each artifact. Access date for everything below: **2026-11-01**.

| ID | Dataset | Role | Status | Licence |
|---|---|---|---|---|
| A | Synthea FHIR R4 | Primary patient memory, STAIR-Clinical training/eval data | **Generated + ingested** | Apache-2.0; synthetic |
| B | SearchTome | STAIR method benchmark | **Official HF release downloaded and validated (reduced release; see below)** | CC-BY-SA-4.0 |
| C | MIMIC-IV / -Note / -ED | Research validation | **PENDING AUTHORIZATION — not downloaded** | PhysioNet Credentialed Health Data License + DUA |
| D | MedlinePlus Health Topics XML | General medical knowledge RAG | **Downloaded + indexed** | Public domain (summaries) |
| — | Existing KB v2 (10 curated guideline documents) | Kept from Phase 5 | Re-used | Per-document records in `data/knowledge_base_v2` |

## A. Synthea (primary)
- **Generator:** `synthea-with-dependencies.jar`, GitHub release tag `master-branch-latest` (published 2026-10-21), commit `bd8a52b`. Jar SHA-256 `20098ec70c24c715ea874b19140983634711cc4986196105b5b0a9ca72a4b644`. Run on portable Eclipse Temurin JDK 21.0.13+9 (zip SHA-256 `a4dbaa05…04f9`, checked against the publisher's checksum).
- **Command:** `scripts/generate_synthea.sh`. `-p 600 -s 20261101 -cs 20261101 -r 20261101`, Massachusetts, FHIR R4 transaction bundles only, `exporter.years_of_history=10`.
- **Output:** 671 patients (600 alive, 71 deceased) plus hospital and practitioner bundles, 2.3 GB, `data/datasets/synthea/raw/generated_p600_seed20261101/fhir/`. The aggregate SHA-256 over sorted per-file hashes is `19b3c829ccd18751679a68546361c7f2c9a6a5c21f9ea4051a117fdd0d55967e`; per-file hashes are in `data/datasets/synthea/manifests/generated_p600_seed20261101_manifest.json`.
- **Official sample (pipeline validation):** `synthea_sample_data_fhir_latest.zip` (SHA-256 `66141b77…b315`, 114 files) was ingested into a separate scratch DB: 112 patients, 98,537 records, 0 duplicate IDs. Report: `data/datasets/synthea/manifests/data_quality_report_official_sample.md`.
- **Ingested cohort:** 671 patients, **750,156 records**, 35,459 documents. Report: `data_quality_report_generated_p600_seed20261101.md`. Findings include two concepts recorded under multiple unit strings (RDW `%`/`fL`; eGFR `mL/min`/`mL/min/{1.73_m2}`). These are kept as separate series and flagged; they are never merged silently.
- **Citation:** Walonoski J, et al. *Synthea: An approach, method, and software mechanism for generating synthetic patients and the synthetic electronic health care record.* JAMIA 2018;25(3):230–238.

## B. SearchTome
- **Paper link:** arXiv:2609.03874v2 links `https://huggingface.co/datasets/meghanadh/SearchTome` (also an `anonymous.4open.science` link that returns **HTTP 410 Gone**).
- **Release checked:** HF dataset `meghanadh/SearchTome`, last modified 2026-10-11, not gated, CC-BY-SA-4.0. It contains 6 domains with corpus/train/dev/test files; per-file SHA-256 values are in `data/datasets/searchtome/raw/official_hf_meghanadh/download_manifest.json` and `processed/validation_report.json`.
- **Discrepancy with the paper (important):** the release has **one textbook per domain** (Action Research, Principles of Financial Accounting, Introduction to Intellectual Property, Nursing Assistant, Introduction to Soil Science, Foundations of Aural Skills). Paper Table 1 lists **18 books** (3 per domain), and several released books do not appear there. Sizes also differ (e.g. medicine: 121 leaves / 1,996 test queries vs the paper's Nursing Assistant 118 leaves / 4,586 test). We therefore treat it as the **official but reduced public release** and **do not claim to reproduce the paper's reported numbers**.
- **Community subset** `SGK86/searchtome-subset` was inspected (file listing only) and **not used**, because the official release is available.
- **Validation:** every query's `gold_doc_title` is checked against the corpus titles; unanswerable items are excluded and counted (see `evaluation/experiments/stair/results/searchtome_results.json`).

## C. MIMIC-IV v3.1, MIMIC-IV-Note v2.2, MIMIC-IV-ED v2.2
- **Not downloaded, not used, not fabricated.** Access needs PhysioNet credentialing, CITI human-subjects training and signed DUAs, which the user must complete.
- `backend/fhir_ingestion/mimic_pipeline.py` documents the linkage (`subject_id`, `hadm_id`, `stay_id`, `note_id`) and mapping. It refuses to run without an explicit authorization flag and locally present files, and it ships no untested ingestion code. Status file: `data/datasets/mimic/manifests/access_status.json` (`PENDING_AUTHORIZATION`).
- DUA safeguards: localhost-only LLM client, MIMIC paths excluded from the cloud bundle, gitignored data directories.

## D. MedlinePlus
- `mplus_topics_compressed_2026-10-31.zip` (SHA-256 `8d95315a…f5f6f1`) → `mplus_topics_2026-10-31.xml` (SHA-256 `261f04c1…1572`), generated by NLM 10/31/2026.
- **Usage terms:** health-topic summaries are U.S. government works in the public domain (https://medlineplus.gov/about/using/usingcontent/). Only `<full-summary>` text is indexed. Third-party `<site>` links are kept as titles and URLs only and are not indexed or reproduced.
- **Processed:** 1,017 English topics → 14,835 passages, plus 42 KB v2 passages = **14,877 passages in 1,058 sections and 52 chapters** (`data/datasets/medical_knowledge/processed/reference_manifest.json`).
- **Citation:** MedlinePlus [Internet]. Bethesda (MD): National Library of Medicine (US). Health Topics XML, 31 Oct 2026.

## Derived dataset: STAIR-Clinical patient retrieval
`data/patient_retrieval/{train,validation,test}/queries.jsonl` and `manifest.json` (per-split SHA-256). **16,198 / 3,074 / 3,736** queries over **473 / 89 / 109** patients. Patient overlap between splits: **0** (asserted at generation time). Pre-rendered SFT files for cloud training are in `data/patient_retrieval/sft/` (20,346 stage-1 training examples, 400 validation).
