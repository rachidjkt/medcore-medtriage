"""
storage/db.py

SQLite backend for medtriage_app secure case communication.

Schema
------
users          — registered identities (patient or professional)
cases          — triage case metadata (non-PHI fields in the clear)
case_payloads  — encrypted medical payload blob per case
shares         — consent records linking a case to a provider
audit_log      — append-only action log

All medical/PHI content is stored only inside case_payloads.encrypted_blob,
which is encrypted by storage.crypto before being persisted.

Usage
-----
    from storage.db import init_db, create_user, create_case, ...
    init_db()                  # call once at app startup
"""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from storage.crypto import decrypt_json, encrypt_json

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Database location
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DB_PATH: Path = _PROJECT_ROOT / "data" / "medtriage_comm.db"


def _connect() -> sqlite3.Connection:
    """
    Open (or create) the SQLite database and return a connection.

    :func:`sqlite3.Row` is set as the row_factory so rows behave like dicts.
    ``check_same_thread=False`` allows Streamlit's multi-thread model to
    share a connection safely when wrapped with a lock — callers are
    responsible for their own serialisation if needed.
    """
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    role            TEXT    NOT NULL CHECK(role IN ('patient', 'professional')),
    display_name    TEXT    NOT NULL,
    identifier_hash TEXT    NOT NULL UNIQUE,   -- SHA-256 of username/email
    created_at      TEXT    NOT NULL           -- ISO-8601 UTC
);

CREATE TABLE IF NOT EXISTS cases (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_user_id     INTEGER NOT NULL REFERENCES users(id),
    created_at          TEXT    NOT NULL,      -- ISO-8601 UTC
    status              TEXT    NOT NULL DEFAULT 'open'
                            CHECK(status IN ('open', 'shared', 'closed')),
    triage_level        TEXT,                  -- critical / urgent / routine
    specialty_category  TEXT,
    confidence_level    TEXT
);

CREATE TABLE IF NOT EXISTS case_payloads (
    case_id        INTEGER PRIMARY KEY REFERENCES cases(id) ON DELETE CASCADE,
    encrypted_blob TEXT    NOT NULL            -- Fernet token from crypto.py
);

CREATE TABLE IF NOT EXISTS shares (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id          INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    patient_user_id  INTEGER NOT NULL REFERENCES users(id),
    provider_user_id INTEGER NOT NULL REFERENCES users(id),
    consent_scope    TEXT    NOT NULL DEFAULT 'read',  -- read | comment | full
    created_at       TEXT    NOT NULL,
    UNIQUE(case_id, provider_user_id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id   INTEGER NOT NULL REFERENCES users(id),
    action    TEXT    NOT NULL,
    case_id   INTEGER REFERENCES cases(id),
    timestamp TEXT    NOT NULL                -- ISO-8601 UTC
);
"""


def init_db() -> None:
    """
    Create all tables if they do not already exist.

    Safe to call multiple times (idempotent).  Should be called once at
    application startup before any other storage functions are used.
    """
    with _connect() as conn:
        conn.executescript(_DDL)
    logger.info("Database initialised at %s", _DB_PATH)


# ---------------------------------------------------------------------------
# Timestamp helper
# ---------------------------------------------------------------------------

def _now() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# User operations
# ---------------------------------------------------------------------------

def create_user(
    role: str,
    display_name: str,
    identifier_hash: str,
) -> dict[str, Any]:
    """
    Insert a new user record and return the created row as a dict.

    Args:
        role:             ``'patient'`` or ``'professional'``.
        display_name:     Human-readable name shown in the UI.
        identifier_hash:  Hex-encoded SHA-256 of the user's login identifier
                          (e.g. username or email).  Must be unique.

    Returns:
        Dict with keys: id, role, display_name, identifier_hash, created_at.

    Raises:
        sqlite3.IntegrityError: If identifier_hash already exists.
        ValueError: If role is not a recognised value.
    """
    if role not in ("patient", "professional"):
        raise ValueError(f"Invalid role '{role}'. Must be 'patient' or 'professional'.")

    now = _now()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO users (role, display_name, identifier_hash, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (role, display_name, identifier_hash, now),
        )
        user_id = cur.lastrowid
        logger.info("Created user id=%d role=%s", user_id, role)
        append_audit(user_id, "user_created", case_id=None, _conn=conn)

    return {
        "id": user_id,
        "role": role,
        "display_name": display_name,
        "identifier_hash": identifier_hash,
        "created_at": now,
    }


def get_user_by_identifier(identifier_hash: str) -> dict[str, Any] | None:
    """
    Retrieve a user row by their identifier hash.

    Args:
        identifier_hash: Hex-encoded SHA-256 of the login identifier.

    Returns:
        Dict with user fields, or ``None`` if not found.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE identifier_hash = ?",
            (identifier_hash,),
        ).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Case operations
# ---------------------------------------------------------------------------

def create_case(
    patient_user_id: int,
    triage_level: str | None,
    specialty_category: str | None,
    confidence_level: str | None,
    payload: dict,
) -> dict[str, Any]:
    """
    Create a new case record plus its encrypted payload.

    All medical detail belongs in *payload*; the top-level columns hold only
    non-sensitive metadata used for filtering/display.

    Args:
        patient_user_id:    ID of the patient who owns this case.
        triage_level:       e.g. ``'critical'``, ``'urgent'``, ``'routine'``.
        specialty_category: e.g. ``'cardiology'``.
        confidence_level:   e.g. ``'high'``, ``'medium'``, ``'low'``.
        payload:            Arbitrary dict of medical details — will be
                            encrypted before storage.

    Returns:
        Dict with the new case's metadata (does not include the payload).
    """
    now = _now()
    encrypted = encrypt_json(payload)

    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO cases
                (patient_user_id, created_at, status,
                 triage_level, specialty_category, confidence_level)
            VALUES (?, ?, 'open', ?, ?, ?)
            """,
            (patient_user_id, now, triage_level, specialty_category, confidence_level),
        )
        case_id = cur.lastrowid

        conn.execute(
            "INSERT INTO case_payloads (case_id, encrypted_blob) VALUES (?, ?)",
            (case_id, encrypted),
        )
        append_audit(patient_user_id, "case_created", case_id=case_id, _conn=conn)
        logger.info("Created case id=%d for patient_user_id=%d", case_id, patient_user_id)

    return {
        "id": case_id,
        "patient_user_id": patient_user_id,
        "created_at": now,
        "status": "open",
        "triage_level": triage_level,
        "specialty_category": specialty_category,
        "confidence_level": confidence_level,
    }


def get_cases_for_patient(patient_user_id: int) -> list[dict[str, Any]]:
    """
    Return all case metadata rows owned by *patient_user_id*.

    Payloads are NOT included — call :func:`get_case_payload` separately.

    Args:
        patient_user_id: The patient's user ID.

    Returns:
        List of case metadata dicts, newest first.
    """
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM cases
            WHERE patient_user_id = ?
            ORDER BY created_at DESC
            """,
            (patient_user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_shared_cases_for_provider(provider_user_id: int) -> list[dict[str, Any]]:
    """
    Return all case metadata rows that a provider has been granted access to
    via the *shares* table.

    Payloads are NOT included.

    Args:
        provider_user_id: The professional's user ID.

    Returns:
        List of case metadata dicts with an additional ``'consent_scope'``
        field, newest-shared first.
    """
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT c.*, s.consent_scope
            FROM cases c
            JOIN shares s ON s.case_id = c.id
            WHERE s.provider_user_id = ?
            ORDER BY s.created_at DESC
            """,
            (provider_user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_case_payload(case_id: int, requesting_user: dict[str, Any]) -> dict | None:
    """
    Decrypt and return the medical payload for a case, enforcing access control.

    Access rules:
    - The patient who owns the case may always read it.
    - A professional may read it only if a matching row exists in *shares*.

    Args:
        case_id:          The case to retrieve.
        requesting_user:  Dict with at minimum ``'id'`` and ``'role'`` keys
                          (as returned by :func:`create_user` /
                          :func:`get_user_by_identifier`).

    Returns:
        Decrypted payload dict, or ``None`` if access is denied or the case
        does not exist.
    """
    user_id: int = requesting_user["id"]
    user_role: str = requesting_user["role"]

    with _connect() as conn:
        # Fetch the case
        case_row = conn.execute(
            "SELECT * FROM cases WHERE id = ?", (case_id,)
        ).fetchone()
        if case_row is None:
            logger.warning("get_case_payload: case %d not found", case_id)
            return None

        # Access control
        is_owner = (case_row["patient_user_id"] == user_id)
        is_consented_provider = False

        if user_role == "professional":
            share_row = conn.execute(
                "SELECT 1 FROM shares WHERE case_id = ? AND provider_user_id = ?",
                (case_id, user_id),
            ).fetchone()
            is_consented_provider = share_row is not None

        if not (is_owner or is_consented_provider):
            logger.warning(
                "Access denied: user %d attempted to read case %d", user_id, case_id
            )
            append_audit(user_id, "unauthorized_payload_access", case_id=case_id, _conn=conn)
            return None

        payload_row = conn.execute(
            "SELECT encrypted_blob FROM case_payloads WHERE case_id = ?", (case_id,)
        ).fetchone()
        if payload_row is None:
            logger.error("case_payloads row missing for case_id=%d", case_id)
            return None

        append_audit(user_id, "payload_read", case_id=case_id, _conn=conn)

    return decrypt_json(payload_row["encrypted_blob"])


# ---------------------------------------------------------------------------
# Sharing / consent
# ---------------------------------------------------------------------------

def share_case(
    case_id: int,
    patient_user_id: int,
    provider_user_id: int,
    consent_scope: str = "read",
) -> dict[str, Any]:
    """
    Grant a professional access to a case by inserting a share record.

    The case *status* is updated to ``'shared'`` if it was ``'open'``.

    Args:
        case_id:          Case to share.
        patient_user_id:  Must match the owning patient (enforced via FK).
        provider_user_id: The professional receiving access.
        consent_scope:    ``'read'``, ``'comment'``, or ``'full'``.

    Returns:
        Dict of the created share record.

    Raises:
        ValueError: If *consent_scope* is not recognised.
        sqlite3.IntegrityError: If the share already exists.
    """
    valid_scopes = ("read", "comment", "full")
    if consent_scope not in valid_scopes:
        raise ValueError(f"consent_scope must be one of {valid_scopes}")

    now = _now()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO shares
                (case_id, patient_user_id, provider_user_id, consent_scope, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (case_id, patient_user_id, provider_user_id, consent_scope, now),
        )
        share_id = cur.lastrowid

        # Promote status so the patient can see the case is now shared
        conn.execute(
            "UPDATE cases SET status = 'shared' WHERE id = ? AND status = 'open'",
            (case_id,),
        )
        append_audit(
            patient_user_id, "case_shared",
            case_id=case_id, _conn=conn,
        )
        logger.info(
            "Shared case %d with provider_user_id=%d (scope=%s)",
            case_id, provider_user_id, consent_scope,
        )

    return {
        "id": share_id,
        "case_id": case_id,
        "patient_user_id": patient_user_id,
        "provider_user_id": provider_user_id,
        "consent_scope": consent_scope,
        "created_at": now,
    }


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

def append_audit(
    user_id: int,
    action: str,
    case_id: int | None = None,
    *,
    _conn: sqlite3.Connection | None = None,
) -> None:
    """
    Append an entry to the append-only audit log.

    Can be called with an existing connection (*_conn*) to participate in the
    caller's transaction, or without one to open its own connection.

    Args:
        user_id:  Actor performing the action.
        action:   Short snake_case label, e.g. ``'case_created'``.
        case_id:  Associated case, or ``None`` for user-level actions.
        _conn:    Optional existing SQLite connection to reuse.
    """
    timestamp = _now()
    sql = """
        INSERT INTO audit_log (user_id, action, case_id, timestamp)
        VALUES (?, ?, ?, ?)
    """
    params = (user_id, action, case_id, timestamp)

    if _conn is not None:
        _conn.execute(sql, params)
    else:
        with _connect() as conn:
            conn.execute(sql, params)

    logger.debug("Audit: user=%d action=%s case=%s", user_id, action, case_id)
