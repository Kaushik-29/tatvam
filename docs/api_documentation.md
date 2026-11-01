# API Documentation (v2)

Base URL: `http://127.0.0.1:8000`. Interactive OpenAPI: `/docs`. Every `/api/v2/*` endpoint except `auth/*` and `system/status` requires `Authorization: Bearer <JWT>`, and the patient scope comes from the token. The Phase 5 `/api/*` endpoints are unchanged (see `docs/api_integration_test_report.md`).

## Auth
| Method | Path | Body / notes |
|---|---|---|
| POST | `/api/v2/auth/register` | `{email, password (≥8), given_name, family_name?, birth_date?, gender?}` → `{access_token, patient_id, onboarding_complete}` |
| POST | `/api/v2/auth/login` | `{email, password}` → token |
| GET | `/api/v2/auth/demo-patients` | synthetic test-split patients for read-only demo |
| POST | `/api/v2/auth/demo-login/{patient_id}` | read-only token for a **synthetic** patient |

## Profile & hierarchy
| GET/PUT | `/api/v2/profile` | profile + record count; PUT updates demographics / `onboarding_complete` (403 for synthetic) |
|---|---|---|
| GET | `/api/v2/hierarchy` | the 23 STAIR-Clinical leaves (path, number, title, description, in_spec, virtual, editable) |
| GET | `/api/v2/toc` | the patient's ToC: branches → leaves → concept groups with counts and date ranges |

## Records & timeline
| GET | `/api/v2/records?leaf=&group=&start=&end=&limit=` | patient-scoped records (newest first) |
|---|---|---|
| GET | `/api/v2/records/{record_id}` | one record (404 if not this patient's) |
| POST | `/api/v2/records` | `{leaf_path, display, start?, end?, value_num?, value_text?, unit?, status?}` → stored as `patient_reported` |
| PATCH | `/api/v2/records/{record_id}` | edit value/unit/dates/status; `verification_status` ∈ confirmed/patient_reported/refuted/unconfirmed |
| DELETE | `/api/v2/records/{record_id}` | delete own entry |
| GET | `/api/v2/timeline?start=&end=&leaves=` | chronological events; labs grouped per day |

## Documents
| POST | `/api/v2/documents` (multipart) | `file`, `document_type` (LAB_REPORT/PRESCRIPTION/DISCHARGE_SUMMARY), `document_date?` → extracted records (unconfirmed) |
|---|---|---|
| GET | `/api/v2/documents` | list |
| GET | `/api/v2/documents/{id}/review` | extracted text + extracted records |
| POST | `/api/v2/documents/{id}/complete-review` | mark reviewed |
| GET | `/api/v2/documents/{id}/file` | original file |

## Consultation
| POST | `/api/v2/consult` | `{query, symptoms?, onset?, duration?, severity?, temperature_c?, notes?, variant? (B0–B5, default B5)}` → full result |
|---|---|---|
| POST | `/api/v2/consult/stream` | Server-Sent Events: `stage` (emergency_check, retrieving_patient_context, retrieving_references, reconciling, generating, verifying), `evidence`, `answer_chunk` (**verified text only**), `done` (full result), `error` |
| GET | `/api/v2/consultations` | history list |
| GET | `/api/v2/consultations/{id}` | stored full result |

Result fields: `action` (ASK/EXPLAIN/ABSTAIN_AND_NAVIGATE/EMERGENCY_OVERRIDE), `action_reason`, `final_text`, `raw_generation` (pre-verification; for research views), `engine`, `evidence[]` (records + `alias`, `epistemic_status`), `references[]` (passage, path, licence, URL, score), `findings[]`, `verification` (`claims[]`, `withheld[]`, `stats`), `retrieval_trace` (selected leaves/groups with scores, invalid paths, structured ops, selector backend), `query_understanding`, `timings`, `model_config`.

## Data management & system
| GET | `/api/v2/data/export` | all of the patient's data (JSON) |
|---|---|---|
| DELETE | `/api/v2/data/consultations` | delete consultation history |
| DELETE | `/api/v2/data/account` | delete account, records, documents, uploads |
| GET | `/api/v2/audit` | last 100 audit events |
| GET | `/api/v2/system/status` | LLM availability, embedding model, STAIR adapter metadata, dataset status (MIMIC: pending) |
