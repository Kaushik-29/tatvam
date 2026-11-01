# MedResolve: Problem Statement & Clinical Scope

## 1. Project Background
In modern clinical care navigation and outpatient assessment, patients increasingly present with disparate, multimodal, and asynchronous information. This includes patient-reported symptoms, prior medical histories, medication lists, unstructured laboratory/imaging reports, and previous physician opinions.

Current AI health assistants and LLM-based symptom checkers typically suffer from critical failure modes:
1. **Uncalibrated Certainty:** Over-reliance on surface-level text generation without grounding claims in verifiable evidence.
2. **Inability to Track Evidence Provenance:** Conflating unverified patient self-reports with clinician-verified laboratory findings and discharge summaries.
3. **Fragility Under Conflict & Incompleteness:** Either ignoring contradictory evidence (e.g., patient claims no cough, but a chest X-ray report notes bilateral infiltrates) or prematurely predicting high-stakes diagnoses without seeking critical missing observations.
4. **Lack of Selective Abstention:** Forcing diagnostic categorizations when clinical evidence is insufficient or equivocal, rather than requesting targeted clinical clarification or initiating safe care escalation.

## 2. Research Objective & Central Hypothesis
**MedResolve** is an academic research prototype (B.Tech Major Project) investigating evidence-grounded health assessment and care navigation.

### Core Research Question
*Does integrating source-aware evidence tracking, uncertain document extraction, explicit clinical conflict detection, and an uncertainty-aware action selection policy measurably improve the reliability and safety of automated diagnostic assistance compared to standard scaffolded baselines under incomplete and conflicting evidence?*

### Foundational Anchor
- **Base Paper:** *EviDx — Evidence-Aware Active Diagnosis with Scaffolded LLM Agents*, Findings of EMNLP 2026 ([ACL Anthology](https://aclanthology.org/2026.findings-emnlp.1557/)).
- **Primary Diagnostic Benchmark:** **DDXPlus** ([Mila / IQIA](https://mila-iqia.github.io/ddxplus/)), a benchmark containing over 1.29 million synthetic patient cases across 49 acute pathologies, 223 binary/categorical evidences, and expert differential diagnoses.

## 3. Epistemic Rigor & Scope Boundaries
To maintain research integrity, the project strictly distinguishes:
- **Established Facts:** Verified empirical findings in existing literature and verified properties of the benchmark dataset.
- **Design Decisions:** Explicit engineering and modeling choices made in MedResolve (e.g., sparse vectorization, modular decomposition).
- **Hypotheses for Verification:** Proposed algorithmic improvements (e.g., conflict-aware policy, abstain mechanism) that must remain unproven until rigorous comparative experiments are conducted against appropriate baselines.

> [!WARNING]
> **Synthetic Dataset Limitation:** DDXPlus consists entirely of synthesized patient profiles generated via a rule-based expert system and medical knowledge graph. Findings on DDXPlus cannot by themselves establish real-world clinical effectiveness or safety in live human clinical workflows. MedResolve is strictly a diagnostic research prototype and is not a clinical decision support device.

---

## 4. Phase 7 (v2) Extension — Longitudinal, Patient-Context-Aware Medical Assistance

*Added 2026-11-01. Sections 1–3 above describe the original DDXPlus/EviDx scope (Phases 1–6), which remains unchanged, including its frozen benchmarks.*

### 4.1 Problem
Existing AI medical question-answering systems mostly respond to the **current** symptom or query. They overlook previously recorded conditions, ongoing medications, allergies, earlier symptoms, diagnoses and reports. Without longitudinal context, answers are generic and miss medication-related considerations and links between old and new problems.

Patient information is spread across many documents, records and encounters, so the evidence relevant to a new concern is hard to find. Conventional RAG splits that information into flat, fixed-size chunks. Flat chunking discards hierarchy (record type → section → concept), chronology, and the relationships between parts of a history.

### 4.2 Approach
MedResolve v2 combines three components:
1. a **structured longitudinal patient memory**: normalized FHIR-derived records with full provenance, stored in a database and never in model weights;
2. **STAIR-Clinical**: a clinical adaptation of STAIR (STructure Aware Information Retriever, arXiv:2609.03874) that routes a question over the patient's record hierarchy (its "table of contents"), and over the hierarchy of medical references, to valid evidence paths;
3. **hybrid medical RAG**: structured filters, BM25, BGE-M3 dense retrieval and Reciprocal Rank Fusion, followed by a local LLM. Emergency pre-emption, evidence reconciliation, a selective action policy and claim-level verification run before anything reaches the user.

### 4.3 Research questions
- **RQ1.** Does structure-aware routing (STAIR-Clinical) retrieve the relevant longitudinal evidence better than flat BM25, dense (BGE-M3) and hybrid retrieval over the same records? *Not assumed; measured against these baselines on a patient-separated split.*
- **RQ2.** Does combining patient history with general medical RAG (B4/B5) increase historical-context coverage and reduce unsupported patient-specific claims compared with a generic LLM (B0), reference-only RAG (B1) and history-only retrieval (B2)?
- **RQ3.** Does claim-level verification with buffered release stop unverified patient-specific statements from reaching the user?

### 4.4 Scope boundaries
This is an academic **medical information** assistant. It does not diagnose, prescribe or change medications, and it has not been clinically validated. All development data is synthetic (Synthea). MIMIC-IV evaluation is pending PhysioNet authorization.
