"""
pipelines/schemas.py

Pydantic models for demo-safe workflow objects:
- Users (patient / professional)
- Patient profile
- Referral requests
- Appointments

These are intentionally lightweight for MVP/demo.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


Role = Literal["patient", "professional"]


class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    role: Role
    email: str
    password: str  # DEMO ONLY — do not use plaintext passwords in real systems
    display_name: str = "Demo User"


class PatientProfile(BaseModel):
    patient_id: str
    phone: str = ""
    allergies: str = ""
    medications: str = ""
    conditions: str = ""
    notes: str = ""


class StoredTriageReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    payload: dict  # stores TriageOutput.model_dump()


class ReferralRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    patient_id: str
    requested_specialty: str = "general"
    message: str = ""
    triage_report_id: Optional[str] = None
    status: Literal["draft", "sent"] = "draft"


class Appointment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)

    patient_id: str
    professional_id: str

    # scheduling-lite
    proposed_slots: list[str] = Field(default_factory=list)  # ISO strings
    chosen_slot: Optional[str] = None  # ISO string
    location: str = ""
    status: Literal["proposed", "confirmed", "cancelled"] = "proposed"
