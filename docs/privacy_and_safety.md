# Privacy and Safety

MedResolve is an **academic medical information assistant**. It is not a diagnostic or prescribing system and has not been clinically validated. All development and evaluation data are synthetic (Synthea).

## Patient-level isolation
- Each data endpoint derives `patient_id` from the signed JWT (`backend/api/auth.py::current_patient_id`). No endpoint accepts a patient ID from the client for data access.
- All reads go through `PatientMemory(session, patient_id)`, which adds `patient_id = :pid` to every query and returns `None` for another patient's record ID, even when the ID is guessed (`tests/test_longitudinal_memory.py::test_patient_isolation`, `tests/test_longitudinal_api.py::test_patient_isolation_between_users`).
- The evaluation harness asserts that every retrieved record belongs to the queried patient.
- Synthetic demo patients can be opened read-only (test split, living patients only). Registered users' data is never listed.

## Authentication
- Passwords are hashed with bcrypt (passlib). JWTs are HS256 with a 12 h default expiry. The secret comes from `JWT_SECRET` or a generated `data/.jwt_secret` (gitignored).
- The frontend keeps the token in `sessionStorage`, which is cleared when the tab closes. For a production deployment, use HttpOnly cookies, CSRF protection, HTTPS, rate limiting and account lockout. These are not implemented in this prototype.
- An audit log records registration, login, record changes, uploads, consultations, exports and deletions.

## Data minimization and control
- Patients can export all of their data as JSON, delete their consultation history, or delete the account along with all records, documents and uploaded files.
- Uploaded files stay local (`data/uploads`, gitignored). OCR runs locally.
- **No external AI services.** The LLM client only accepts a localhost Ollama URL (`OllamaClient.__init__`). Restricted data (MIMIC) must never be sent to third-party APIs, and the cloud-training bundle script refuses any MIMIC path.

## Safety architecture (order of execution)
1. **Emergency pre-emption** (`evidence_reconciliation/emergency.py`) runs before retrieval and generation. A deterministic, negation-aware screen covers ACS-like chest pain with associated features, severe dyspnoea, stroke signs, syncope, anaphylaxis, severe bleeding, suicidality/self-harm, seizure, thunderclap headache, meningism and overdose. A trigger returns a fixed emergency message; no LLM text is produced.
2. **Evidence reconciliation** covers allergy–medication class conflicts (including drugs named in the question), duplicate active medications, cross-source status disagreement, unit discrepancies, temporal inconsistencies, unconfirmed OCR values, estimated exposure windows, missing information (unrecorded medications the patient mentions, empty sections) and stale measurements.
3. **Selective action policy:** EMERGENCY_OVERRIDE → ABSTAIN_AND_NAVIGATE (high-severity conflict, or a diagnostic/prescribing decision request) → ASK (empty record, unrecorded medication, vague new concern without duration) → EXPLAIN.
4. **Buffered generation + claim verification.** Raw LLM tokens are never streamed. Each sentence is classified as patient-specific, general, safety, or structural.
   - Patient-specific claims must cite existing `[E#]` evidence, and all numbers, dates and clinical entities in the claim must appear in that evidence. Otherwise they are withheld, which blocks invented diagnoses, values and medication changes.
   - Patient claims supported only by references are rejected, so a guideline never silently becomes a patient fact.
   - General claims need lexical support from the cited `[R#]` passages.
   - Only permitted claims are released, and the user is told how many were withheld.
5. **Epistemic labelling.** Each fact shown to the LLM and the user carries CONFIRMED / PATIENT-REPORTED / EXTRACTED-UNCONFIRMED / DERIVED. Estimated medication end dates are marked as estimated.
6. **No invented history.** With an empty profile the system asks the user to add history (`test_empty_profile_asks_instead_of_inventing`).

## Known limits of the safety layer
The emergency screen and claim verifier are lexical and rule-based. They can miss paraphrased red flags or accept a claim that matches the evidence's words but not its meaning. Similarity scores are never treated as clinical truth. These components reduce risk but cannot certify safety. See `limitations.md`.
