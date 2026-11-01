# MedResolve — Document Security & File-Processing Audit

**Phase Identifier:** Phase 5.5  
**Document Purpose:** Independent audit of file-processing security, magic-byte validation, path traversal prevention, and cross-patient isolation.

---

## 1. Security Threat Model & Defense In Depth

Clinical document processing systems represent high-risk attack surfaces due to complex document parsers (PDF engines, image decoders) and multi-tenant patient confidentiality requirements.

MedResolve enforces four defensive layers:

```
[ Client Request ]
       |
1. Size & Format Validation (15 MB Max, Allowed Extensions)
       |
2. File Signature Magic Bytes Verification (%PDF, \x89PNG, \xff\xd8)
       |
3. Path Traversal & Filename Sanitization (re.sub regex + UUID sandbox)
       |
4. Memory-Safe CPU Extraction Sandbox (PyMuPDF / ONNX with Exception Isolation)
       |
5. Cross-Patient Document Identity Binding (Patient ID Equality Checks)
```

---

## 2. Invariant Verification Results

The test suite in `tests/test_phase5_5_e2e_security.py` and `experiments/run_e2e_and_security_audit.py` verified the following security properties:

### 1. 15 MB Upload Limit Enforced
- **Policy:** Files exceeding $15 \times 1024 \times 1024$ bytes (15,728,640 bytes) are rejected immediately at the route level prior to disk writes.
- **Empirical Test:** Uploading an oversized 16 MB payload resulted in `HTTP 400 Bad Request` with message: `"File size (16777316 bytes) exceeds 15 MB limit."`.

### 2. File Signature Magic Bytes (Anti-Spoofing)
- **Policy:** Extension-based MIME spoofing (e.g. executable or HTML files renamed with `.pdf` or `.png` extensions) is strictly rejected by examining leading file bytes.
- **Header Magic Bytes Checked:**
  - PDF: `%PDF` (`b"%PDF"`)
  - PNG: `\x89PNG\r\n\x1a\n` (`b"\x89PNG\r\n\x1a\n"`)
  - JPEG: `\xff\xd8\xff` / `\xff\xd8` (`b"\xff\xd8"`)
- **Empirical Test:** Renaming raw text as `fake_lab.pdf` returned `HTTP 400 Bad Request` with message: `"Invalid PDF file: Missing %PDF header magic bytes."`.

### 3. Filename Sanitization and Path Traversal Protection
- **Policy:** Client-provided filenames are stripped of relative path components (`../`, `..\`) and special characters using:
  $$\text{safe\_name} = \text{re.sub}(r'[^a-zA-Z0-9\_\-\.]', '\_', \text{Path}(filename).\text{name})$$
- **Empirical Test:** Uploading `../../../../etc/passwd.pdf` resulted in file storage strictly confined to `data/uploads/DOC_SYNTH_PATIENT_01_<timestamp>_passwd.pdf` inside the designated upload sandbox.

### 4. Cross-Patient Document Isolation
- **Policy:** A document uploaded under patient $A$ cannot be viewed, summarized, or downloaded under patient $B$.
- **Implementation in `backend/main.py`:**
  ```python
  @app.get("/api/documents/{patient_id}/{document_id}")
  def api_get_document_details(patient_id: str, document_id: str):
      doc = UPLOADED_DOCS_STORE.get(document_id)
      if not doc or doc["patient_id"] != patient_id:
          raise HTTPException(status_code=404, detail="Document not found")
      return doc
  ```
- **Empirical Test:** Requesting `DOC_SYNTH_PATIENT_01_1793429559638` under `SYNTH_PATIENT_02` returned `HTTP 404 Not Found` for both metadata review and raw file download endpoints.

### 5. Secret and Environment Variable Leakage Prevention
- **Policy:** API error handlers and metrics dashboards do not expose environment variables, tokens, or system paths.
- **Empirical Test:** Scanned metrics and error responses for `SECRET_KEY`, `TOKEN`, `PASSWORD`, and `AWS_SECRET`; zero leakage detected.

---

## 3. Prototype Limitations & Production Deployment Requirements

MedResolve is an investigational academic research prototype evaluated on synthetic patient records in a local CPU environment. Before deployment in real clinical EHR workflows, the following controls are required:

1. **At-Rest & In-Transit Encryption:** AES-256-GCM encryption for stored PDF/image artifacts; TLS 1.3 for all client communication.
2. **Role-Based Access Control (RBAC):** Authenticated JWT sessions with clinician/patient role separation.
3. **Malware Pipeline Scanning:** Integration of ClamAV or equivalent container scanning prior to PyMuPDF parsing.
4. **Audit Logging & Retention:** Immutable HIPAA-compliant audit logs for every document view, correction, and access attempt.
