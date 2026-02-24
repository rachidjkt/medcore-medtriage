"""
storage/models.py

Pydantic v2 data models for the medtriage_app communication layer.

These models describe the shape of data flowing between the business logic
layer (case_manager.py) and the Streamlit UI.  They are NOT ORM models;
persistence is handled entirely by db.py.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class UserRole(str, Enum):
    """The two roles a registered identity can hold."""
    patient = "patient"
    professional = "professional"


class CaseStatus(str, Enum):
    """Lifecycle states of a triage case."""
    open = "open"
    shared = "shared"
    closed = "closed"


class ConsentScope(str, Enum):
    """Granularity of access granted to a provider."""
    read = "read"        # view payload only
    comment = "comment"  # read + post messages
    full = "full"        # read + message + export


class TriageLevel(str, Enum):
    critical = "critical"
    urgent = "urgent"
    routine = "routine"


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


class UserRecord(BaseModel):
    """A registered user identity as stored in the users table."""
    id: int
    role: UserRole
    display_name: str
    identifier_hash: str = Field(
        description="SHA-256 hex digest of the login identifier (username/email)."
    )
    created_at: str = Field(description="ISO-8601 UTC timestamp.")

    class Config:
        use_enum_values = True


class CasePayload(BaseModel):
    """
    The encrypted medical detail attached to a case.

    This is the only place PHI should appear.  The entire model is serialised
    to JSON and then encrypted before storage.
    """
    summary: str = Field(description="Free-text clinical summary.")
    triage_level: TriageLevel | str = Field(description="Urgency classification.")
    specialty_category: str | None = Field(
        default=None, description="Target specialty, e.g. 'cardiology'."
    )
    confidence_level: str | None = Field(
        default=None,
        description="Model confidence, e.g. 'high', 'medium', 'low'.",
    )
    context: str | None = Field(
        default=None,
        description="Optional clinical context supplied by the patient.",
    )
    raw_ai_output: str | None = Field(
        default=None,
        description="Truncated raw model output for audit purposes.",
    )
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary additional fields (forward-compatible).",
    )

    class Config:
        use_enum_values = True


class CaseRecord(BaseModel):
    """Case metadata row — does NOT include the encrypted payload."""
    id: int
    patient_user_id: int
    created_at: str
    status: CaseStatus | str
    triage_level: str | None = None
    specialty_category: str | None = None
    confidence_level: str | None = None

    class Config:
        use_enum_values = True


class ConsentRecord(BaseModel):
    """A share/consent link between a case and a provider."""
    id: int
    case_id: int
    patient_user_id: int
    provider_user_id: int
    consent_scope: ConsentScope | str = ConsentScope.read
    created_at: str

    class Config:
        use_enum_values = True


class AuditEntry(BaseModel):
    """One row of the append-only audit log."""
    id: int
    user_id: int
    action: str
    case_id: int | None = None
    timestamp: str
