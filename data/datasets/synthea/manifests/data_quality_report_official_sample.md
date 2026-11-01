# Synthea ingestion data-quality report — `official_sample`

- Source: `data\datasets\synthea\raw\official_sample\extracted`
- Generated: 2026-11-01T04:45:08
- Patients: **112**, records: **98537**, duplicate IDs skipped: 0

## Records per STAIR-Clinical leaf

| Leaf | Records | Patients with ≥1 |
|---|---:|---:|
| `allergy_history` | 101 | 19 |
| `clinical_encounters/complaints` | 7821 | 109 |
| `clinical_encounters/consultations` | 5087 | 112 |
| `clinical_encounters/previous_symptoms` | 130 | 43 |
| `demographics` | 112 | 112 |
| `laboratory_observations/assessments_and_surveys` | 18458 | 103 |
| `laboratory_observations/historical_trends` | 2000 | 111 |
| `laboratory_observations/laboratory_results` | 19903 | 112 |
| `laboratory_observations/vital_signs` | 10992 | 112 |
| `medical_documents/clinical_notes` | 4993 | 112 |
| `medical_documents/diagnostic_reports` | 4571 | 112 |
| `medical_documents/discharge_summaries` | 94 | 48 |
| `medical_history/care_plans` | 327 | 99 |
| `medical_history/conditions` | 940 | 112 |
| `medical_history/diagnoses` | 1140 | 108 |
| `medical_history/immunizations` | 1521 | 112 |
| `medical_history/procedures` | 13737 | 111 |
| `medical_history/social_history` | 2421 | 112 |
| `medication_history/current_medications` | 246 | 69 |
| `medication_history/medication_changes` | 968 | 108 |
| `medication_history/previous_medications` | 2975 | 106 |

Leaves with no Synthea records (expected — populated by uploads / patient entry): `medical_documents/prescriptions`

## FHIR resources

| Resource | Seen | Mapped |
|---|---:|---:|
| AllergyIntolerance | 101 | 101 |
| CarePlan | 327 | 327 |
| CareTeam | 327 | 0 |
| Claim | 8308 | 0 |
| Condition | 3418 | 3418 |
| Device | 507 | 0 |
| DiagnosticReport | 9281 | 4194 |
| DocumentReference | 5087 | 5087 |
| Encounter | 5087 | 5087 |
| ExplanationOfBenefit | 8308 | 0 |
| ImagingStudy | 377 | 377 |
| Immunization | 1521 | 1521 |
| Medication | 571 | 0 |
| MedicationAdministration | 571 | 0 |
| MedicationRequest | 3221 | 3221 |
| Observation | 34024 | 34024 |
| Patient | 112 | 0 |
| Procedure | 13737 | 13737 |
| Provenance | 112 | 0 |
| SupplyDelivery | 2507 | 0 |

## Not mapped (by design)

- **CareTeam** (327): care-team roster
- **Claim** (8308): billing, not clinical evidence
- **Device** (507): device inventory (not in the requested hierarchy)
- **ExplanationOfBenefit** (8308): billing, not clinical evidence
- **Medication** (571): referenced medication definition (display copied onto MedicationRequest)
- **MedicationAdministration** (571): in-clinic administrations (MedicationRequest is the prescribing record)
- **Provenance** (112): bundle-level provenance (kept as source_document reference)
- **SupplyDelivery** (2507): supply logistics

## Data-quality issues

- `numeric_value_without_unit`: 3
