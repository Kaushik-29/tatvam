"""
Patient-scoped API (v2). Every route derives patient_id from the JWT via
`current_patient_id`; no route accepts a patient_id from the client.
"""

import asyncio
import json
import queue
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend import config
from backend.api.auth import DEMO_SOURCES, audit, consultation_owner, current_patient_id
from backend.api.services import get_deps
from backend.patient_memory.db import get_session, session_scope
from backend.patient_memory.hierarchy import LEAF_BY_PATH, LEAVES
from backend.patient_memory.models import (
    AuditEvent, ClinicalRecord, Consultation, Document, Patient, User,
)
from backend.patient_memory.repository import PatientMemory
from backend.rag.pipeline import PipelineConfig, run_pipeline

router = APIRouter(prefix="/api/v2", tags=["patient"])

EDITABLE_LEAVES = [l.path for l in LEAVES if not l.virtual and l.path not in (
    "demographics", "laboratory_observations/historical_trends", "medication_history/medication_changes")]


# ------------------------------------------------------------------ profile
def iso_date(v: Optional[str]) -> Optional[str]:
    """Dates must be ISO (YYYY-MM-DD, optionally with a time): a free-text date stored once would make every
    later answer for this patient fail when the timeline and medication windows are computed."""
    if v is None or v == "":
        return None
    try:
        datetime.fromisoformat(v.strip()[:19].replace("Z", ""))
    except ValueError:
        raise ValueError("Use a date like 2024-05-31")
    return v.strip()


class ProfileIn(BaseModel):
    given_name: Optional[str] = Field(None, max_length=128)
    family_name: Optional[str] = Field(None, max_length=128)
    birth_date: Optional[str] = None
    gender: Optional[str] = Field(None, max_length=32)
    city: Optional[str] = Field(None, max_length=128)
    onboarding_complete: Optional[bool] = None

    _d = field_validator("birth_date")(lambda cls, v: iso_date(v))


def _profile(p: Patient, mem: PatientMemory) -> Dict[str, Any]:
    return {"patient_id": p.patient_id, "source": p.source, "given_name": p.given_name, "family_name": p.family_name,
            "birth_date": p.birth_date, "gender": p.gender, "city": p.city, "state": p.state,
            "deceased_date": p.deceased_date, "onboarding_complete": bool(p.onboarding_complete),
            "is_synthetic": p.source == "synthea_fhir_r4", "is_demo": p.source in DEMO_SOURCES, "record_count": mem.count()}


@router.get("/profile")
def get_profile(pid: str = Depends(current_patient_id), s: Session = Depends(get_session)):
    mem = PatientMemory(s, pid)
    p = mem.patient()
    if p is None:
        raise HTTPException(404, "Patient not found")
    return _profile(p, mem)


@router.put("/profile")
def update_profile(body: ProfileIn, pid: str = Depends(current_patient_id), s: Session = Depends(get_session)):
    p = s.get(Patient, pid)
    if p is None:
        raise HTTPException(404, "Patient not found")
    if p.source in DEMO_SOURCES:
        raise HTTPException(403, "Demo patients are read-only")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(p, k, v)
    audit(s, pid, "profile_update")
    return _profile(p, PatientMemory(s, pid))


# ---------------------------------------------------------- hierarchy / toc
@router.get("/hierarchy")
def hierarchy():
    return [{"path": l.path, "number": l.number, "title": l.title, "description": l.description,
             "in_spec": l.in_spec, "virtual": l.virtual, "editable": l.path in EDITABLE_LEAVES} for l in LEAVES]


@router.get("/toc")
def toc(pid: str = Depends(current_patient_id), s: Session = Depends(get_session)):
    def ser(n):
        return {"path": n.path, "number": n.number, "title": n.title, "count": n.count,
                "date_range": n.date_range, "children": [ser(c) for c in n.children]}
    return [ser(n) for n in PatientMemory(s, pid).toc()]


# ------------------------------------------------------------------ records
class RecordIn(BaseModel):
    leaf_path: str = Field(max_length=128)
    display: str = Field(min_length=1, max_length=200)
    start: Optional[str] = None
    end: Optional[str] = None
    value_num: Optional[float] = None
    value_text: Optional[str] = Field(None, max_length=1000)
    unit: Optional[str] = Field(None, max_length=32)
    status: Optional[str] = Field(None, max_length=32)

    _d = field_validator("start", "end")(lambda cls, v: iso_date(v))


class RecordPatch(BaseModel):
    concept_display: Optional[str] = Field(None, max_length=200)
    effective_start: Optional[str] = None
    effective_end: Optional[str] = None
    value_num: Optional[float] = None
    value_text: Optional[str] = Field(None, max_length=1000)
    unit: Optional[str] = Field(None, max_length=32)
    clinical_status: Optional[str] = Field(None, max_length=32)
    verification_status: Optional[str] = None

    _d = field_validator("effective_start", "effective_end")(lambda cls, v: iso_date(v))


@router.get("/records")
def list_records(leaf: Optional[str] = None, group: Optional[str] = None, start: Optional[str] = None,
                 end: Optional[str] = None, limit: int = 200, pid: str = Depends(current_patient_id),
                 s: Session = Depends(get_session)):
    if leaf and leaf not in LEAF_BY_PATH:
        raise HTTPException(400, "Unknown hierarchy leaf")
    return PatientMemory(s, pid).records(leaves=[leaf] if leaf else None, groups=[group] if group else None,
                                         start=start, end=end, limit=min(limit, 2000))


@router.get("/records/{record_id:path}")
def get_record(record_id: str, pid: str = Depends(current_patient_id), s: Session = Depends(get_session)):
    r = PatientMemory(s, pid).get(record_id)
    if r is None:
        raise HTTPException(404, "Record not found")
    return r


def _require_writable(s: Session, pid: str):
    p = s.get(Patient, pid)
    if p is None or p.source in DEMO_SOURCES:
        raise HTTPException(403, "Demo patients are read-only")


@router.post("/records")
def add_record(body: RecordIn, pid: str = Depends(current_patient_id), s: Session = Depends(get_session)):
    _require_writable(s, pid)
    if body.leaf_path not in EDITABLE_LEAVES:
        raise HTTPException(400, f"Records cannot be added to '{body.leaf_path}'")
    rec = PatientMemory(s, pid).add_patient_entry(body.leaf_path, body.display.strip(), start=body.start,
                                                  end=body.end, value_num=body.value_num, value_text=body.value_text,
                                                  unit=body.unit, status=body.status)
    audit(s, pid, "record_add", rec["record_id"])
    return rec


@router.patch("/records/{record_id:path}")
def patch_record(record_id: str, body: RecordPatch, pid: str = Depends(current_patient_id),
                 s: Session = Depends(get_session)):
    _require_writable(s, pid)
    fields = body.model_dump(exclude_none=True)
    if fields.get("verification_status") not in (None, "confirmed", "patient_reported", "refuted", "unconfirmed"):
        raise HTTPException(400, "Invalid verification status")
    if fields.get("verification_status") == "confirmed":
        fields["verification_status"] = "confirmed"   # patient confirmation of an extracted value
    r = PatientMemory(s, pid).update_record(record_id, **fields)
    if r is None:
        raise HTTPException(404, "Record not found")
    audit(s, pid, "record_update", record_id)
    return r


@router.delete("/records/{record_id:path}")
def delete_record(record_id: str, pid: str = Depends(current_patient_id), s: Session = Depends(get_session)):
    _require_writable(s, pid)
    if not PatientMemory(s, pid).delete_record(record_id):
        raise HTTPException(404, "Record not found")
    audit(s, pid, "record_delete", record_id)
    return {"deleted": record_id}


# ----------------------------------------------------------------- timeline
@router.get("/timeline")
def timeline(start: Optional[str] = None, end: Optional[str] = None, leaves: Optional[str] = None,
             limit: int = 300, pid: str = Depends(current_patient_id), s: Session = Depends(get_session)):
    """Chronological events. Raw vital/lab/survey values are summarized per encounter to stay readable."""
    mem = PatientMemory(s, pid)
    sel = [l for l in (leaves.split(",") if leaves else []) if l in LEAF_BY_PATH] or [
        "medical_history/diagnoses", "medical_history/conditions", "medical_history/procedures",
        "medication_history/medication_changes", "allergy_history", "clinical_encounters/previous_symptoms",
        "clinical_encounters/consultations", "medical_history/immunizations", "medical_documents/prescriptions",
        "laboratory_observations/laboratory_results"]
    recs = [r for r in mem.records(leaves=sel, start=start, end=end, limit=4000) if r.get("effective_start")]
    events, lab_by_day = [], {}
    for r in recs:
        if r["leaf_path"] == "laboratory_observations/laboratory_results":
            lab_by_day.setdefault(r["effective_start"][:10], []).append(r)
            continue
        events.append({"date": r["effective_start"][:10], "end": (r.get("effective_end") or "")[:10] or None,
                       "leaf_path": r["leaf_path"], "title": r["concept_display"], "text": r["text"],
                       "record_ids": [r["record_id"]], "status": r.get("clinical_status"),
                       "source_system": r["source_system"], "verification_status": r["verification_status"]})
    for day, rs in lab_by_day.items():
        events.append({"date": day, "end": None, "leaf_path": "laboratory_observations/laboratory_results",
                       "title": f"{len(rs)} laboratory result(s)", "text": "; ".join(sorted({x['concept_display'] for x in rs})[:6]),
                       "record_ids": [x["record_id"] for x in rs], "status": None,
                       "source_system": rs[0]["source_system"], "verification_status": rs[0]["verification_status"]})
    events.sort(key=lambda e: e["date"], reverse=True)
    return events[:limit]


# ---------------------------------------------------------------- documents
@router.post("/documents")
async def upload_document(document_type: str = Form("MEDICAL_REPORT"), document_date: Optional[str] = Form(None),
                          file: UploadFile = File(...), pid: str = Depends(current_patient_id),
                          s: Session = Depends(get_session)):
    _require_writable(s, pid)
    try:
        document_date = iso_date(document_date)
    except ValueError as e:
        raise HTTPException(400, str(e))
    from backend.ocr_service import MedicalDocumentProcessor
    proc = MedicalDocumentProcessor()
    content = await file.read()
    ok, err = proc.validate_file(file.filename or "upload", content)
    if not ok:
        raise HTTPException(400, err)
    doc_id, path = proc.save_upload(pid, file.filename or "upload", content)
    try:
        res = await asyncio.to_thread(proc.process_document, path, document_type)
    except Exception:
        path.unlink(missing_ok=True)
        raise HTTPException(400, "The document could not be read (corrupted or unsupported).")
    leaf = {"PRESCRIPTION": "medical_documents/prescriptions", "DISCHARGE_SUMMARY": "medical_documents/discharge_summaries",
            "LAB_REPORT": "medical_documents/diagnostic_reports"}.get(document_type.upper(), "medical_documents/diagnostic_reports")
    s.add(Document(document_id=doc_id, patient_id=pid, leaf_path=leaf, title=file.filename, doc_date=document_date,
                   source_system="ocr_extracted", file_path=str(path), text=res["full_text"][:200000],
                   ocr_status="pending_review", extraction_json=json.dumps(res["structured_items"])))
    s.flush()
    mem = PatientMemory(s, pid)
    created = []
    # check each lab value against its own line (the frozen OCR extractor can attach a neighbouring row's unit)
    from backend.document_checks import check_items
    res["structured_items"] = check_items(res["structured_items"], res["full_text"])
    for i, it in enumerate(res["structured_items"]):
        is_med = bool(it.get("medication_name"))
        target = "medication_history/current_medications" if is_med else "laboratory_observations/laboratory_results"
        try:
            val = float(it["normalized_value"]) if not is_med else None
        except (TypeError, ValueError):
            val = None
        disp = (f"{it['medication_name']} {it.get('dosage_strength') or ''}{it.get('dosage_unit') or ''}".strip()
                if is_med else it.get("concept_name_en") or it["concept"])
        rec = mem.add_patient_entry(
            target, disp, start=it.get("document_date") or document_date, value_num=val,
            value_text=None if val is not None else (it.get("frequency") or it.get("normalized_value")),
            unit=it.get("unit"), source_system="ocr_extracted", verification="unconfirmed",
            confidence=float(it.get("confidence") or 0.0), source_document=doc_id,
            provenance={"document_id": doc_id, "page": it.get("page_number"), "raw_text": it.get("raw_text"),
                        "unit_status": it.get("unit_status"), "extraction_method": it.get("extraction_method"),
                        "reference_range": it.get("reference_range"), "item_index": i,
                        "line_check": it.get("line_check"), "check_note": it.get("confirmation_reason")})
        created.append(rec)
    audit(s, pid, "document_upload", f"{doc_id} items={len(created)}")
    return {"document_id": doc_id, "leaf_path": leaf, "pages": res["total_pages"], "extracted_records": created,
            "processing_latency_ms": res["processing_latency_ms"]}


@router.get("/documents")
def list_documents(leaf: Optional[str] = None, limit: int = 100, pid: str = Depends(current_patient_id),
                   s: Session = Depends(get_session)):
    docs = PatientMemory(s, pid).documents(leaf)[:limit]
    return [{"document_id": d.document_id, "title": d.title, "leaf_path": d.leaf_path, "doc_date": d.doc_date,
             "source_system": d.source_system, "ocr_status": d.ocr_status, "has_file": bool(d.file_path),
             "preview": (d.text or "")[:300]} for d in docs]


@router.get("/documents/{document_id:path}/review")
def document_review(document_id: str, pid: str = Depends(current_patient_id), s: Session = Depends(get_session)):
    d = s.get(Document, document_id)
    if d is None or d.patient_id != pid:
        raise HTTPException(404, "Document not found")
    recs = PatientMemory(s, pid).records()
    extracted = [r for r in recs if r.get("source_document") == document_id]
    return {"document_id": d.document_id, "title": d.title, "text": d.text, "ocr_status": d.ocr_status,
            "doc_date": d.doc_date, "extracted_records": extracted}


@router.post("/documents/{document_id:path}/complete-review")
def complete_review(document_id: str, pid: str = Depends(current_patient_id), s: Session = Depends(get_session)):
    d = s.get(Document, document_id)
    if d is None or d.patient_id != pid:
        raise HTTPException(404, "Document not found")
    d.ocr_status = "reviewed"
    audit(s, pid, "document_review_complete", document_id)
    return {"document_id": document_id, "ocr_status": "reviewed"}


@router.get("/documents/{document_id:path}/file")
def document_file(document_id: str, pid: str = Depends(current_patient_id), s: Session = Depends(get_session)):
    d = s.get(Document, document_id)
    if d is None or d.patient_id != pid or not d.file_path or not Path(d.file_path).exists():
        raise HTTPException(404, "File not found")
    return FileResponse(d.file_path)


# ------------------------------------------------------------- consultation
class ConsultIn(BaseModel):
    query: str = Field(max_length=2000)          # bounds the text sent to the local LLM
    symptoms: Optional[List[str]] = None
    onset: Optional[str] = None
    duration: Optional[str] = None
    severity: Optional[str] = None
    temperature_c: Optional[float] = None
    notes: Optional[str] = None
    variant: str = "B5"


def _intake(body: ConsultIn) -> Dict[str, Any]:
    return {k: v for k, v in body.model_dump().items() if k not in ("query", "variant") and v not in (None, "", [])}


@router.post("/consult")
def consult(body: ConsultIn, pid: str = Depends(current_patient_id), owner: Optional[str] = Depends(consultation_owner),
            s: Session = Depends(get_session)):
    if not body.query.strip():
        raise HTTPException(400, "Question is empty")
    variant = body.variant if body.variant in ("B0", "B1", "B2", "B3", "B4", "B5") else "B5"
    res = run_pipeline(s, pid, body.query.strip(), _intake(body), PipelineConfig(variant=variant, owner=owner), get_deps())
    audit(s, pid, "consult", res["consultation_id"])
    return res


@router.post("/consult/stream")
async def consult_stream(body: ConsultIn, pid: str = Depends(current_patient_id),
                         owner: Optional[str] = Depends(consultation_owner)):
    """Server-sent events. Stage/evidence events stream live; the answer text is released
    ONLY after claim verification (never raw LLM tokens)."""
    if not body.query.strip():
        raise HTTPException(400, "Question is empty")
    q: "queue.Queue" = queue.Queue()

    def worker():
        try:
            with session_scope() as s:
                res = run_pipeline(s, pid, body.query.strip(), _intake(body), PipelineConfig(variant="B5", owner=owner),
                                   get_deps(), on_event=lambda ev, data: q.put((ev, data)))
                audit(s, pid, "consult", res["consultation_id"])
            q.put(("verified_result", res))
        except Exception as e:      # never leak internals
            q.put(("error", {"message": "The assistant could not complete this request.", "type": type(e).__name__}))
        q.put(None)

    threading.Thread(target=worker, daemon=True).start()

    async def gen():
        while True:
            item = await asyncio.to_thread(q.get)
            if item is None:
                break
            ev, data = item
            if ev == "verified_result":
                text = data.get("final_text") or ""
                for i in range(0, len(text), 120):            # release verified text in chunks
                    yield f"event: answer_chunk\ndata: {json.dumps({'text': text[i:i + 120]})}\n\n"
                    await asyncio.sleep(0.01)
                yield f"event: done\ndata: {json.dumps(data, default=str)}\n\n"
            else:
                yield f"event: {ev}\ndata: {json.dumps(data, default=str)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _owned(owner: Optional[str]):
    """Own account: its questions (owner NULL). Demo session: only that session's questions."""
    return Consultation.owner.is_(None) if owner is None else Consultation.owner == owner


@router.get("/consultations")
def consultations(limit: int = 50, pid: str = Depends(current_patient_id),
                  owner: Optional[str] = Depends(consultation_owner), s: Session = Depends(get_session)):
    rows = s.scalars(select(Consultation).where(Consultation.patient_id == pid, _owned(owner))
                     .order_by(Consultation.created_at.desc()).limit(limit))
    return [{"consultation_id": c.consultation_id, "created_at": c.created_at.isoformat(), "query": c.query,
             "action": c.action, "latency_s": c.latency_s, "preview": (c.response_text or "")[:220]} for c in rows]


@router.get("/consultations/{cid}")
def consultation(cid: str, pid: str = Depends(current_patient_id),
                 owner: Optional[str] = Depends(consultation_owner), s: Session = Depends(get_session)):
    c = s.get(Consultation, cid)
    if c is None or c.patient_id != pid or c.owner != owner:
        raise HTTPException(404, "Consultation not found")
    return json.loads(c.result_json)


class RecordDecisionIn(BaseModel):
    save: bool
    display: Optional[str] = Field(None, max_length=200)      # the patient may rename the problem before saving
    details: Optional[str] = Field(None, max_length=1000)


@router.post("/consultations/{cid}/record-decision")
def record_decision(cid: str, body: RecordDecisionIn, pid: str = Depends(current_patient_id),
                    s: Session = Depends(get_session)):
    """After an answer about a new problem, the patient chooses whether it goes into their record.
    Saved as a patient-reported symptom dated the day of the question, linked to the consultation."""
    _require_writable(s, pid)
    c = s.get(Consultation, cid)
    if c is None or c.patient_id != pid:
        raise HTTPException(404, "Consultation not found")
    res = json.loads(c.result_json)
    offer = res.get("record_offer")
    if not offer:
        raise HTTPException(400, "This answer has nothing to add to your record")
    if offer.get("status") != "pending":
        raise HTTPException(409, f"Already {offer['status']}")
    if body.save:
        name = (body.display or offer.get("suggested") or "").strip()
        if not name:
            raise HTTPException(400, "Please give the problem a name")
        rec = PatientMemory(s, pid).add_patient_entry(
            "clinical_encounters/previous_symptoms", name, start=c.created_at.date().isoformat(),
            value_text=(body.details or c.query).strip()[:1000], status="ongoing",
            provenance={"entered_via": "MedResolve answer", "consultation_id": cid})
        offer.update(status="saved", record_id=rec["record_id"], display=name)
        audit(s, pid, "record_add_from_consultation", rec["record_id"])
    else:
        offer.update(status="declined")
        audit(s, pid, "record_offer_declined", cid)
    res["record_offer"] = offer
    c.result_json = json.dumps(res, default=str)
    return offer


# ---------------------------------------------------------- data management
@router.get("/data/export")
def export_data(pid: str = Depends(current_patient_id), owner: Optional[str] = Depends(consultation_owner),
                s: Session = Depends(get_session)):
    mem = PatientMemory(s, pid)
    p = mem.patient()
    cons = s.scalars(select(Consultation).where(Consultation.patient_id == pid, _owned(owner)))
    audit(s, pid, "data_export")
    return {"exported_at": datetime.utcnow().isoformat(), "profile": _profile(p, mem), "records": mem.records(),
            "documents": [{"document_id": d.document_id, "title": d.title, "doc_date": d.doc_date,
                           "leaf_path": d.leaf_path, "text": d.text} for d in mem.documents()],
            "consultations": [json.loads(c.result_json) for c in cons]}


@router.delete("/data/account")
def delete_account(pid: str = Depends(current_patient_id), s: Session = Depends(get_session)):
    p = s.get(Patient, pid)
    if p is None:
        raise HTTPException(404, "Patient not found")
    if p.source in DEMO_SOURCES:
        raise HTTPException(403, "Demo patients cannot be deleted from the app")
    for d in PatientMemory(s, pid).documents():
        if d.file_path:
            Path(d.file_path).unlink(missing_ok=True)
    for model in (ClinicalRecord, Document, Consultation, AuditEvent, User):
        s.execute(delete(model).where(model.patient_id == pid))
    s.delete(p)
    return {"deleted": True}


@router.delete("/data/consultations")
def delete_consultations(pid: str = Depends(current_patient_id), owner: Optional[str] = Depends(consultation_owner),
                         s: Session = Depends(get_session)):
    n = s.execute(delete(Consultation).where(Consultation.patient_id == pid, _owned(owner))).rowcount
    audit(s, pid, "consultations_deleted", str(n))
    return {"deleted": n}


@router.get("/audit")
def audit_log(pid: str = Depends(current_patient_id), s: Session = Depends(get_session)):
    rows = s.scalars(select(AuditEvent).where(AuditEvent.patient_id == pid).order_by(AuditEvent.id.desc()).limit(100))
    return [{"event": a.event, "actor": a.actor, "detail": a.detail, "at": a.created_at.isoformat()} for a in rows]


# ---------------------------------------------------------------- speech to text
MAX_AUDIO_BYTES = 10 * 1024 * 1024


@router.post("/speech/transcribe")
async def speech_transcribe(audio: UploadFile = File(...), language: Optional[str] = Form(None),
                            pid: str = Depends(current_patient_id)):
    """Local Whisper transcription of a spoken question. The audio is processed in memory on this
    machine and never stored or sent anywhere; the text goes back to the question box for the user to edit."""
    data = await audio.read()
    if not data:
        raise HTTPException(400, "The recording is empty")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "The recording is too long (up to about one minute)")
    from backend import speech
    try:
        return await asyncio.to_thread(speech.transcribe, data, (language or None) and language[:5])
    except speech.SpeechUnavailable as e:
        raise HTTPException(503, f"Speech to text is not available: {e}")
    except ValueError as e:
        raise HTTPException(400, str(e))


# ---------------------------------------------------------- research: test cases
TEST_CASES_FILE = config.PROJECT_ROOT / "evaluation" / "experiments" / "diagnostic_cases" / "test_cases.json"


@router.get("/test-cases")
def test_cases(pid: str = Depends(current_patient_id)):
    """The 40 doctor-assessment cases with the AI model's chosen diagnosis and what the patient app would do
    (built by scripts/build_test_cases.py). Read-only research material, the same for every user."""
    if not TEST_CASES_FILE.exists():
        raise HTTPException(404, "Test cases have not been built (run scripts/build_test_cases.py)")
    return json.loads(TEST_CASES_FILE.read_text(encoding="utf-8"))


# ------------------------------------------------------------------- system
@router.get("/system/status")
def system_status():
    from backend.llm.ollama_client import OllamaClient
    adapter_meta = config.STAIR_ADAPTER_DIR / "stair_clinical_meta.json"
    def _j(p):
        return json.loads(Path(p).read_text(encoding="utf-8")) if Path(p).exists() else None
    return {
        "llm": {"model": config.OLLAMA_MODEL, "available": OllamaClient().available() if config.USE_OLLAMA else False},
        "embedding_model": config.EMBEDDING_MODEL,
        "stair": {"configured_backend": config.STAIR_BACKEND, "adapter": _j(adapter_meta)},
        "datasets": {
            "synthea": _j(config.DATA_DIR / "datasets/synthea/manifests/data_quality_report_generated_p600_seed20261101.json") and "ingested",
            "patient_retrieval": _j(config.DATA_DIR / "patient_retrieval/manifest.json"),
            "medical_reference": _j(config.REFERENCE_INDEX_DIR / "reference_manifest.json"),
            "mimic_iv": "PENDING_AUTHORIZATION — credentialed PhysioNet access not configured; no MIMIC data present.",
        },
        "disclaimer": "Research prototype. Not clinically validated. Not for diagnosis or treatment.",
    }
