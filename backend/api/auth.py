"""
Authentication and patient-level isolation.

Passwords: bcrypt (passlib). Sessions: signed JWT (HS256) whose `sub` is the
user and whose `pid` claim is the ONLY patient_id any request can touch.
Patient IDs are never accepted from the client for data access.
"""

import re
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend import config
from backend.patient_memory.db import get_session
from backend.patient_memory.models import AuditEvent, Patient, User

router = APIRouter(prefix="/api/v2/auth", tags=["auth"])
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer(auto_error=False)


class RegisterIn(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    given_name: str = Field(min_length=1, max_length=128)
    family_name: Optional[str] = None
    birth_date: Optional[str] = None
    gender: Optional[str] = None


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    patient_id: str
    onboarding_complete: bool
    is_demo: bool = False


def _token(user_id: str, patient_id: str, demo: bool = False) -> str:
    exp = datetime.utcnow() + timedelta(minutes=config.JWT_EXPIRE_MINUTES)
    return jwt.encode({"sub": user_id, "pid": patient_id, "demo": demo, "exp": exp},
                      config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def current_patient_id(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer)) -> str:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = jwt.decode(creds.credentials, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    pid = payload.get("pid")
    if not pid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token has no patient scope")
    return pid


def audit(s: Session, pid: str, event: str, detail: str = "", actor: str = "patient"):
    s.add(AuditEvent(patient_id=pid, actor=actor, event=event, detail=detail[:2000]))


@router.post("/register", response_model=TokenOut)
def register(body: RegisterIn, s: Session = Depends(get_session)):
    email = body.email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(400, "Invalid email address")
    if s.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists")
    pid = f"user-{uuid.uuid4().hex[:16]}"
    s.add(Patient(patient_id=pid, source="registered_user", given_name=body.given_name.strip(),
                  family_name=(body.family_name or "").strip() or None, birth_date=body.birth_date,
                  gender=body.gender, onboarding_complete=False))
    s.flush()
    uid = f"u-{uuid.uuid4().hex[:16]}"
    s.add(User(user_id=uid, email=email, password_hash=pwd.hash(body.password), patient_id=pid))
    audit(s, pid, "register")
    return TokenOut(access_token=_token(uid, pid), patient_id=pid, onboarding_complete=False)


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, s: Session = Depends(get_session)):
    u = s.scalar(select(User).where(User.email == body.email.strip().lower()))
    if u is None or not pwd.verify(body.password, u.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    p = s.get(Patient, u.patient_id)
    audit(s, u.patient_id, "login")
    return TokenOut(access_token=_token(u.user_id, u.patient_id), patient_id=u.patient_id,
                    onboarding_complete=bool(p and p.onboarding_complete))


@router.get("/demo-patients")
def demo_patients(s: Session = Depends(get_session), limit: int = 25):
    """Synthetic (Synthea) TEST-split patients that can be opened read-only for demonstration.
    Only synthetic records are exposed; registered users' data is never listed."""
    rows = s.scalars(select(Patient).where(Patient.source == "synthea_fhir_r4", Patient.split == "test",
                                           Patient.deceased_date.is_(None)).order_by(Patient.patient_id).limit(limit))
    return [{"patient_id": p.patient_id, "label": f"{p.given_name.split()[0]} {p.family_name}",
             "gender": p.gender, "birth_date": p.birth_date, "city": p.city} for p in rows]


@router.post("/demo-login/{patient_id}", response_model=TokenOut)
def demo_login(patient_id: str, s: Session = Depends(get_session)):
    p = s.get(Patient, patient_id)
    if p is None or p.source != "synthea_fhir_r4":
        raise HTTPException(404, "Synthetic demo patient not found")
    audit(s, patient_id, "demo_login", actor="demo")
    return TokenOut(access_token=_token("demo", patient_id, demo=True), patient_id=patient_id,
                    onboarding_complete=True, is_demo=True)
