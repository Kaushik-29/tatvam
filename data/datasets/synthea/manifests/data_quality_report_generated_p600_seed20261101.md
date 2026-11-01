# Synthea ingestion data-quality report — `generated_p600_seed20261101`

- Source: `data\datasets\synthea\raw\generated_p600_seed20261101\fhir`
- Generated: 2026-11-01T05:22:13
- Patients: **671**, records: **750156**, duplicate IDs skipped: 0

## Records per STAIR-Clinical leaf

| Leaf | Records | Patients with ≥1 |
|---|---:|---:|
| `allergy_history` | 589 | 107 |
| `clinical_encounters/complaints` | 72181 | 664 |
| `clinical_encounters/consultations` | 35459 | 671 |
| `clinical_encounters/previous_symptoms` | 685 | 262 |
| `demographics` | 671 | 671 |
| `laboratory_observations/assessments_and_surveys` | 132289 | 587 |
| `laboratory_observations/historical_trends` | 13336 | 671 |
| `laboratory_observations/laboratory_results` | 172364 | 671 |
| `laboratory_observations/vital_signs` | 83488 | 671 |
| `medical_documents/clinical_notes` | 34817 | 671 |
| `medical_documents/diagnostic_reports` | 34826 | 671 |
| `medical_documents/discharge_summaries` | 642 | 269 |
| `medical_history/care_plans` | 2150 | 612 |
| `medical_history/conditions` | 6069 | 671 |
| `medical_history/diagnoses` | 7216 | 663 |
| `medical_history/immunizations` | 10053 | 670 |
| `medical_history/procedures` | 96026 | 671 |
| `medical_history/social_history` | 16174 | 671 |
| `medication_history/current_medications` | 1598 | 442 |
| `medication_history/medication_changes` | 5585 | 650 |
| `medication_history/previous_medications` | 23938 | 648 |

Leaves with no Synthea records (expected — populated by uploads / patient entry): `medical_documents/prescriptions`

## FHIR resources

| Resource | Seen | Mapped |
|---|---:|---:|
| AllergyIntolerance | 589 | 589 |
| CarePlan | 2150 | 2150 |
| CareTeam | 2150 | 0 |
| Claim | 60995 | 0 |
| Condition | 21872 | 21872 |
| Device | 3423 | 0 |
| DiagnosticReport | 67515 | 32056 |
| DocumentReference | 35459 | 35459 |
| Encounter | 35459 | 35459 |
| ExplanationOfBenefit | 60995 | 0 |
| ImagingStudy | 2770 | 2770 |
| Immunization | 10053 | 10053 |
| Medication | 9948 | 0 |
| MedicationAdministration | 9948 | 0 |
| MedicationRequest | 25536 | 25536 |
| Observation | 280282 | 280282 |
| Patient | 671 | 0 |
| Procedure | 96026 | 96026 |
| Provenance | 671 | 0 |
| SupplyDelivery | 14959 | 0 |

## Not mapped (by design)

- **CareTeam** (2150): care-team roster
- **Claim** (60995): billing, not clinical evidence
- **Device** (3423): device inventory (not in the requested hierarchy)
- **ExplanationOfBenefit** (60995): billing, not clinical evidence
- **Medication** (9948): referenced medication definition (display copied onto MedicationRequest)
- **MedicationAdministration** (9948): in-clinic administrations (MedicationRequest is the prescribing record)
- **Provenance** (671): bundle-level provenance (kept as source_document reference)
- **SupplyDelivery** (14959): supply logistics

## Data-quality issues

- `multiple_unit_strings_same_concept:erythrocyte [distwidth] in blood by automated count:%|fL`: 55
- `multiple_unit_strings_same_concept:glomerular filtration rate [volume rate/area] in serum or plasma by creatinine-based formula (mdrd)/1.73 sq m:mL/min|mL/min/{1.73_m2}`: 40
- `multiple_unit_strings_same_concept:ph of urine by test strip:[pH]|pH`: 16
- `multiple_unit_strings_same_concept:specific gravity of urine by test strip:{SG}|{nominal}`: 16
- `multiple_unit_strings_same_concept:troponin i.cardiac [mass/volume] in serum or plasma by high sensitivity method:ng/L|pg/mL`: 2
