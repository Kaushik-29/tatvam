"""
Normalized longitudinal patient memory (SQLAlchemy ORM).

Every clinical fact is one `ClinicalRecord` row that keeps its original FHIR
resource type / ID, patient, encounter, source document, effective and recorded
dates, concept code, raw value + unit, normalized value + unit, provenance and
confirmation status. Rows are never flattened into anonymous text.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    user_id = Column(String(64), primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    patient_id = Column(String(64), ForeignKey("patients.patient_id"), nullable=False, unique=True)
    role = Column(String(32), default="patient", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Patient(Base):
    __tablename__ = "patients"
    patient_id = Column(String(64), primary_key=True)
    source = Column(String(32), nullable=False)          # synthea_fhir_r4 | registered_user | mimic_iv
    fhir_resource_id = Column(String(64), nullable=True)
    given_name = Column(String(128))
    family_name = Column(String(128))
    birth_date = Column(String(10))
    gender = Column(String(16))
    deceased_date = Column(String(32), nullable=True)
    city = Column(String(128))
    state = Column(String(64))
    race = Column(String(64))
    ethnicity = Column(String(64))
    source_document = Column(String(255))
    onboarding_complete = Column(Boolean, default=False)
    split = Column(String(16), nullable=True)            # train | validation | test (Synthea only)
    created_at = Column(DateTime, default=datetime.utcnow)


class ClinicalRecord(Base):
    __tablename__ = "clinical_records"
    record_id = Column(String(160), primary_key=True)
    patient_id = Column(String(64), ForeignKey("patients.patient_id"), nullable=False)
    leaf_path = Column(String(96), nullable=False)        # STAIR-Clinical level-2 leaf
    group_path = Column(String(200), nullable=False)      # level-3 concept-group path
    resource_type = Column(String(48), nullable=False)    # original FHIR type or Derived/UserEntry/OCR
    fhir_resource_id = Column(String(96))
    encounter_id = Column(String(96))
    source_document = Column(String(255))
    source_system = Column(String(32), nullable=False)    # synthea_fhir_r4 | patient_entered | ocr_extracted | derived
    concept_system = Column(String(96))
    concept_code = Column(String(64))
    concept_display = Column(String(400), nullable=False)
    concept_key = Column(String(200), nullable=False)     # grouping key (display-normalized)
    effective_start = Column(String(32))
    effective_end = Column(String(32))
    recorded_date = Column(String(32))
    value_num = Column(Float)
    value_text = Column(Text)
    unit = Column(String(64))                             # original unit string
    normalized_value = Column(Float)
    normalized_unit = Column(String(64))
    clinical_status = Column(String(32))                  # active | resolved | completed | stopped | ...
    verification_status = Column(String(32), nullable=False)  # confirmed | unconfirmed | patient_reported | refuted
    confidence = Column(Float, default=1.0)
    provenance = Column(Text)                             # JSON: source refs, derivation, extraction method
    text = Column(Text, nullable=False)                   # rendered evidence sentence (BM25 / display)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_records_patient_leaf", "patient_id", "leaf_path"),
        Index("ix_records_patient_group", "patient_id", "group_path"),
        Index("ix_records_patient_date", "patient_id", "effective_start"),
        Index("ix_records_patient_encounter", "patient_id", "encounter_id"),
    )


class Document(Base):
    __tablename__ = "documents"
    document_id = Column(String(128), primary_key=True)
    patient_id = Column(String(64), ForeignKey("patients.patient_id"), nullable=False, index=True)
    leaf_path = Column(String(96), nullable=False)
    title = Column(String(255))
    doc_date = Column(String(32))
    encounter_id = Column(String(96))
    fhir_resource_id = Column(String(96))
    source_system = Column(String(32), nullable=False)
    file_path = Column(String(400))
    text = Column(Text)
    ocr_status = Column(String(32))                       # n/a | pending_review | reviewed
    extraction_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class Consultation(Base):
    __tablename__ = "consultations"
    consultation_id = Column(String(64), primary_key=True)
    patient_id = Column(String(64), ForeignKey("patients.patient_id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    query = Column(Text, nullable=False)
    intake_json = Column(Text)
    action = Column(String(32))
    response_text = Column(Text)
    result_json = Column(Text)                            # full evidence / verification payload
    system_variant = Column(String(16))
    latency_s = Column(Float)
    owner = Column(String(64), index=True)                # demo browser session that asked it (None for own account)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(String(64), index=True)
    actor = Column(String(64))
    event = Column(String(64))
    detail = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
