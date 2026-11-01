# Data Processing Pipeline

All steps are reproducible from the repository root. Each one writes a manifest or report.

```bash
python scripts/download_datasets.py                       # Synthea sample, Synthea jar, JDK, SearchTome, MedlinePlus
bash scripts/generate_synthea.sh                           # 600 living patients, seed 20261101
python -m backend.fhir_ingestion.synthea_ingest --input data/datasets/synthea/raw/generated_p600_seed20261101/fhir --tag generated_p600_seed20261101 --reset
python -m backend.rag.reference_corpus                     # MedlinePlus + KB v2 hierarchical corpus
python -m backend.stair_retriever.training_data            # patient-split STAIR-Clinical queries + gold
python -m backend.stair_retriever.sft --stage 1            # pre-rendered SFT JSONL for GPU training
```

## 1. FHIR R4 → normalized longitudinal records
`BundleMapper` (`backend/fhir_ingestion/synthea_ingest.py`) handles one patient bundle at a time.

| FHIR resource | Leaf (STAIR-Clinical hierarchy) | Notes |
|---|---|---|
| Patient | `demographics` | birth date, sex, deceased date, city/state, race/ethnicity |
| Condition | `medical_history/diagnoses` (SNOMED tag *disorder*), `/conditions` (other), `clinical_encounters/previous_symptoms` (symptom lexicon), `medical_history/social_history` (SDOH lexicon) | clinical + verification status kept; `refuted` / `entered-in-error` → `refuted` |
| MedicationRequest | `current_medications` (active/on-hold), `previous_medications` (completed/stopped) | ingredient extracted for grouping; reasons, dosing, requester kept |
| AllergyIntolerance | `allergy_history` | category, criticality, reactions + severity |
| Encounter | `clinical_encounters/consultations`; each `reasonCode` → `complaints` | class, provider, location, period |
| DocumentReference | `medical_documents/clinical_notes` or `/discharge_summaries` (inpatient encounter); full text in `documents` | `# Chief Complaint` bullets → `complaints` (status *patient_reported*, rule-based parser) |
| Observation | `laboratory_results` / `vital_signs` / `social_history` / `assessments_and_surveys` by category | components (e.g. systolic/diastolic BP) become separate records `Observation/<id>#<loinc>` |
| Procedure, Immunization, CarePlan | `procedures`, `immunizations`, `care_plans` | |
| DiagnosticReport, ImagingStudy | `medical_documents/diagnostic_reports` | note-type DiagnosticReports that duplicate a DocumentReference are de-duplicated and counted |
| Claim, EOB, SupplyDelivery, CareTeam, Device, Provenance, Medication, MedicationAdministration | not mapped | counted with reasons in the quality report |

Every record keeps: original resource type and ID, patient ID, encounter ID, source document (bundle file), effective start/end, recorded date, concept system/code/display, raw value + unit, normalized value + unit, clinical status, verification status, confidence, provenance JSON and a rendered evidence sentence. Record IDs are stable: `<ResourceType>/<fhir id>[#suffix]`.

**Unit normalization** (`classify.normalize_quantity`) converts only unambiguous cases (°F→°C, lb→kg, in→cm, g/L→g/dL) and harmonizes aliases (`pH`→`[pH]`). The original value and unit are always stored alongside the normalized pair.

## 2. Derived records (`backend/patient_memory/derived.py`)
- **Medication changes:** per ingredient, a *started* event at the first request; a *dose changed* event when the strength differs from the previous request; and a *no longer active* event when no active request remains. Each cites its source request IDs.
- **Historical trends:** for each (concept, normalized unit) with ≥3 numeric values: first, latest, min, max, count, and a direction (mean of first w vs last w values, w = min(3, n//2), 5% threshold). The source record IDs are cited (up to 60, plus a count).
- Derived rows are labelled `source_system=derived`, `verification_status=derived`, so they never pass as primary facts.

## 3. Medication exposure intervals (`PatientMemory.medication_intervals`)
Synthea MedicationRequests have **no supply duration**, so the exposure end is an assumption. Chronic pattern (≥3 requests or any active request): the request is in effect until the next request, capped at 400 days, and the latest active request is open-ended. Otherwise (acute pattern): 30 days. Every assumed end is flagged `end_uncertain` and shown to the LLM and the user ("end date ESTIMATED"). The same rule produces the gold labels for "medications during episode" questions.

## 4. Quality checks
The ingestion report (`data/datasets/synthea/manifests/*.md|json`) covers per-leaf record counts, the number of patients with each leaf populated, mapped and unmapped resource counts, de-duplication, duplicate record IDs, missing effective dates, numeric values without units, unresolved encounter references, subject mismatches, and concepts recorded with several unit strings. Two defects found during development were fixed and re-ingested:
- urine-pH unit alias collision (`pH`/`[pH]`), which had caused 13 duplicate trend IDs;
- overlapping head/tail windows in trend direction for series with <6 points.

## 5. Patient-entered and uploaded data
- UI entries become `UserEntry/<uuid>` records with `verification_status=patient_reported`.
- Uploads go through the existing `MedicalDocumentProcessor` (RapidOCR / PDF text): file validation, magic bytes, a 15 MB cap, and unit-provenance classification. Extracted values become `OCRExtraction/<uuid>` records with `verification_status=unconfirmed`, the extraction confidence, and provenance (document, page, raw text, unit status). The patient confirms, corrects or rejects each one in OCR Review.
- New records are queryable at once. The patient ToC is rebuilt from the database on every query, so no index or model retraining is needed. Dense vectors for new concept texts are computed on demand and cached.
