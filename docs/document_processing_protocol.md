# MedResolve — Clinical Document Processing Protocol

**Protocol Identifier:** PROT-DOC-PROC-5.4  
**Effective Date:** October 31, 2026  
**Scope:** Document Ingestion, Security Boundaries, OCR Processing & Ledger Lifecycle  

---

## 1. Supported Document Specifications

MedResolve accepts clinical documents across the following formats:

| Format Code | File Extension | Permitted MIME Types | Processing Path | Target Clinical Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **PDF** | `.pdf` | `application/pdf` | Direct text stream via PyMuPDF; fallback to 200 DPI RapidOCR | Digital pathology reports, hospital discharge summaries, clinical lab sheets |
| **PNG** | `.png` | `image/png` | RapidOCR (ONNX CPU) | High-contrast scanned prescriptions, laboratory panel screenshots |
| **JPEG** | `.jpg`, `.jpeg` | `image/jpeg` | RapidOCR (ONNX CPU) | Paper prescription photos, mobile document scans |
| **Plain Text** | `.txt` | `text/plain` | Direct line streaming | Legacy EHR notes, raw consultation transcripts |

---

## 2. Ingestion Security & Boundary Validation

To protect system integrity in research environments and prevent arbitrary file injection or file traversal exploits, the ingestion protocol applies four mandatory gates:

### Gate 1: Extension Whitelist & Path Traversal Neutralization
- Only extensions in `{".pdf", ".png", ".jpg", ".jpeg", ".txt"}` are accepted.
- Filenames are sanitized using `Path(filename).name` stripped of directory separators (`/`, `\`, `..`).
- Filenames are normalized with regex replacement: `re.sub(r"[^a-zA-Z0-9_\-\.]", "_", name)`.

### Gate 2: Content Size & Empty File Detection
- Maximum permitted file size: **15,728,640 bytes (15 MB)**. Files exceeding this limit are rejected with HTTP 400.
- Empty files (0 bytes) are rejected immediately with HTTP 400.

### Gate 3: Header Magic Byte Verification (Anti-Spoofing)
File extensions must match genuine content signatures. Extension spoofing triggers an immediate HTTP 400 rejection:
- **PDF:** Must begin with bytes `b"%PDF"` (`0x25 0x50 0x44 0x46`).
- **PNG:** Must begin with the 8-byte PNG signature `b"\x89PNG\r\n\x1a\n"` (`0x89 0x50 0x4E 0x47 0x0D 0x0A 0x1A 0x0A`).
- **JPEG:** Must begin with SOI (Start of Image) marker `b"\xff\xd8"` (`0xFF 0xD8`).

### Gate 4: Patient Cohort Boundary Validation
- Upload requests require a valid `patient_id`.
- The `patient_id` must match a recognized synthetic patient in the research cohort (`get_all_synthetic_patients()`).
- Ingestion requests for unregistered patient IDs are rejected with HTTP 404.

---

## 3. Storage Hierarchy & Isolation

All ingested artifacts are saved to a controlled local directory:
`d:\MedResolve\data\uploads\`

Each document receives an immutable, globally unique system identifier:
`DOC_{patient_id}_{timestamp_ms}_{safe_filename}`

Example: `DOC_SYNTH_PATIENT_01_1793425590498_test_digital_lab.pdf`

The directory is isolated from source code, version control (`.gitignore`), and web root paths. Files are served exclusively through the controlled endpoint `GET /api/documents/{patient_id}/{document_id}/file` with explicit MIME headers and patient ownership verification.

---

## 4. End-to-End Processing Workflow

```
[User Action: Document Upload]
             |
             v
   [Gate 1-4 Security Validation]
             |
             +---> Fails Gate: Return HTTP 400 / 404 with explicit detail
             |
             v
   [Save Upload to Controlled Storage]
             |
             v
   [Run Text Extraction: PyMuPDF or RapidOCR]
             |
             v
   [Clinical Entity Parser: Tests, Vitals, Meds]
             |
             v
   [Unit Safety Classifier: 5-Way Provenance]
             |
             v
   [Evidence Ledger Ingestion: UNCONFIRMED Items]
             |
             v
   [Interactive OCR Review: Confirm / Correct / Reject]
             |
             v
   [Conflict Detection & Guideline RAG Assessment]
```

---

## 5. Review Interface Operations

The interactive OCR review interface provides four discrete clinical governance actions:

1. **Confirm Extraction (`action = "CONFIRM"`):**
   - Clinician or patient inspects the raw text and normalized value.
   - Sets `user_confirmation_status = CONFIRMED_BY_PATIENT`.
   - The observation is now eligible for inclusion in verified clinical summaries.
2. **Correct Value / Unit (`action = "CORRECT"`):**
   - Used when OCR misreads a character (e.g., blurring in tenth digits) or unit abbreviation.
   - Applies `corrected_value` and `corrected_unit`.
   - Automatically preserves the original raw text and previous value in audit notes.
   - Sets `user_confirmation_status = CONFIRMED_BY_PATIENT`.
3. **Reject Extraction (`action = "REJECT"`):**
   - Used when text corresponds to boilerplate headers, laboratory disclaimers, or noise.
   - Sets `evidence_status = ABSENT` and `user_confirmation_status = REJECTED_BY_PATIENT`.
   - Completely excluded from clinical assessment assembly.
4. **Mark Unreadable (`action = "MARK_UNREADABLE"`):**
   - Used when ink smudge or blur renders reading ambiguous.
   - Sets `evidence_status = UNKNOWN` and `user_confirmation_status = UNCONFIRMED`.
   - Prevents ungrounded clinical inferences.

---

## 6. Demonstration Boundaries & Academic Disclaimer

- **Synthetic Cohort Only:** This protocol is validated strictly on synthetic patient cases and synthetic clinical documentation.
- **No Clinical Deployment:** This software is an investigational academic prototype. It is not approved for real-world electronic health record (EHR) ingestion, medical triage, or patient diagnosis.
