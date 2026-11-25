# MedResolve: security and patient-safety audit (25 Nov 2026)

Scope: the v2 patient app (API, authentication, data isolation, uploads), the answer pipeline
(emergency screen, medicine options, LLM answers) and the legacy v1 research API.
Every fixed item has a regression test in `tests/test_security_audit.py` (31 tests). Full suite: 218 passed.

## Fixed

| # | Severity | Loophole | Fix |
|---|---|---|---|
| 1 | Critical | Child questions ("my 5 year old son has fever") got **adult** doses | Options are blocked for children; answer says to ask a doctor or pharmacist for the child's dose |
| 2 | Critical | Paracetamol overdose by count ("I took 20 dolo tablets") was not an emergency | Emergency screen catches tablet / pill counts and "a whole strip/bottle" |
| 3 | Critical | "Chest burning and left arm pain" (possible heart attack) was not an emergency | Chest burning / discomfort and "arm pain" now count; "heart attack" itself too |
| 4 | High | Pregnancy / breastfeeding (in the question or the record) still got options | Options blocked; advises asking a doctor or pharmacist |
| 5 | High | "My mother has fever" was checked against the **user's** record | Options blocked for other people |
| 6 | High | Dengue warning signs (fever with bleeding gums / nose, repeated vomiting, severe stomach pain) not urgent | New red flag based on the WHO dengue fact sheet |
| 7 | High | "Difficulty breathing", "black stools" not emergencies | Added to the breathing and bleeding red flags |
| 8 | High | Demo patients are shared: every visitor could read and delete other visitors' questions | Each demo login gets its own session id; questions are stored and listed per session (`consultations.owner`, added automatically to existing databases) |
| 9 | Medium | Symptom lasting longer than the sources allow ("fever for 5 days") still got self-care options | Per-group day limits (e.g. fever 2, diarrhoea 2, cough 7); longer → see a doctor |
| 10 | Medium | A free-text date ("last year", "29/08/2005") made every later answer for that patient crash | API rejects non-ISO dates (profile, records, uploads, sign-up); stored bad dates are skipped instead of crashing |
| 11 | Medium | No limit on failed logins (password guessing) | 5 failures per email → 15-minute lockout (HTTP 429) |
| 12 | Medium | CORS allowed any website (`"*"` with credentials) to call the local API | Only the local frontend origins (configurable with `MEDRESOLVE_CORS_ORIGINS`) |
| 13 | Low | No length limits on text inputs (very long questions sent to the LLM) | Question ≤ 2,000 characters; names, values and units bounded |
| 14 | Low | "Which syrup / cream / shampoo / spray?" not recognised as a medicine request | Added these product forms |

## Checked and found safe
- Patient isolation in the v2 API: every route takes the patient id from the signed token; record, document and consultation routes check ownership.
- Demo patients' records, profile and documents are read-only.
- Passwords are bcrypt-hashed; the JWT secret is random and stored outside git.
- Legacy v1 upload: the patient id is checked against the fixed synthetic list **before** anything is written, so the unsanitised id in the file path is not exploitable. `backend/ocr_service.py` was left unchanged because it is hash-frozen with the OCR evaluation.
- Your own data: the 12 consultations in your account were kept by the database change.

## Open (needs a decision, not fixed)
1. **Legacy v1 research API has no login.** It only serves the fixed synthetic demo patients and is used by the `#/research` dashboard and older tests. Recommendation: disable it when the app is ever hosted for others.
2. **Data at rest is not encrypted.** `data/medresolve.db` holds real health data in plain SQLite. Fine for a local prototype; use disk encryption or an encrypted database before any shared deployment.
3. **Sign-in lasts 12 hours and cannot be revoked** (no sign-out on the server). Acceptable locally; add token revocation for deployment.
4. **Prompt injection through the user's own records/uploads** can only affect that user's own answers, and the claim verifier blocks unsupported patient statements. Low risk; noted.
5. **The emergency screen is English keyword matching.** Tamil / Hindi or misspelled red flags are not caught. A clinician-reviewed multilingual list is future work.
6. **Medicine options are not clinician-reviewed** (already stated in the paper).
