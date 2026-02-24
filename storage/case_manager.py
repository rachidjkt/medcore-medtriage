"""
storage/case_manager.py

Higher-level business logic for the medtriage_app communication layer.

Responsibilities
----------------
- Password-based registration and authentication (PBKDF2-HMAC-SHA256).
- Wrapping db.py functions with validation and typed return values.
- Providing the Streamlit pages with a clean, framework-agnostic API.

Password storage
----------------
Passwords are hashed with ``hashlib.pbkdf2_hmac`` (SHA-256, 260 000
iterations, 16-byte random salt) and stored as a single colon-delimited
string ``"<hex_salt>:<hex_hash>"`` inside the ``identifier_hash`` column
alongside a separate lookup key.

Because the users table uses identifier_hash as a UNIQUE lookup key, we
store the login identifier (username) hashed with SHA-256 as the lookup
key, and store the password material in a separate column would require a
schema change.  Instead we use a two-row-per-user approach:

  identifier_hash = sha256(username)   ← lookup key
  display_name    = username            ← plain display value
  role            = patient | professional

The password hash is kept in a *separate* sqlite table ``credentials``:

  CREATE TABLE IF NOT EXISTS credentials (
      user_id       INTEGER PRIMARY KEY REFERENCES users(id),
      password_blob TEXT NOT NULL        -- "<hex_salt>:<hex_hash>"
  );

``init_db()`` in db.py already creates all base tables; this module calls
``_ensure_credentials_table()`` on first import to add the credentials
table without modifying db.py.
"""

import hashlib
import hmac
import logging
import os
import sqlite3
from pathlib import Path
from typing import Any

from storage import db as _db
from storage.models import CasePayload, CaseRecord, ConsentRecord, UserRecord

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Credentials table (extension of the base schema)
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DB_PATH = _PROJECT_ROOT / "data" / "medtriage_comm.db"


def _get_conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def _ensure_credentials_table() -> None:
    """Create the credentials table if it doesn't exist yet."""
    with _get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS credentials (
                user_id       INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                password_blob TEXT NOT NULL
            );
            """
        )


_ensure_credentials_table()

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

_ITERATIONS = 260_000
_HASH_ALG = "sha256"


def _hash_password(password: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
    """
    Hash *password* with PBKDF2-HMAC-SHA256.

    Returns:
        ``(salt, dk)`` where both are raw bytes.
    """
    if salt is None:
        salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac(_HASH_ALG, password.encode("utf-8"), salt, _ITERATIONS)
    return salt, dk


def _verify_password(password: str, blob: str) -> bool:
    """
    Verify *password* against a stored ``"<hex_salt>:<hex_hash>"`` blob.
    Uses ``hmac.compare_digest`` to prevent timing attacks.
    """
    try:
        hex_salt, hex_hash = blob.split(":", 1)
    except ValueError:
        return False
    salt = bytes.fromhex(hex_salt)
    _, dk = _hash_password(password, salt)
    return hmac.compare_digest(dk.hex(), hex_hash)


def _username_to_lookup_hash(username: str) -> str:
    """Return SHA-256 hex of the lower-cased username for use as lookup key."""
    return hashlib.sha256(username.strip().lower().encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Public auth API
# ---------------------------------------------------------------------------


def register_user(username: str, password: str, role: str, display_name: str | None = None) -> UserRecord:
    """
    Register a new user and return their ``UserRecord``.

    Args:
        username:     Login identifier (case-insensitive).
        password:     Plaintext password (hashed before storage).
        role:         ``'patient'`` or ``'professional'``.
        display_name: Optional human name; defaults to *username*.

    Returns:
        ``UserRecord`` for the newly created user.

    Raises:
        ValueError:                 If the username already exists or role is invalid.
        sqlite3.IntegrityError:     On unexpected DB constraint violations.
    """
    if role not in ("patient", "professional"):
        raise ValueError(f"Invalid role '{role}'.")

    lookup_hash = _username_to_lookup_hash(username)

    if _db.get_user_by_identifier(lookup_hash) is not None:
        raise ValueError(f"Username '{username}' is already registered.")

    salt, dk = _hash_password(password)
    password_blob = f"{salt.hex()}:{dk.hex()}"

    row = _db.create_user(
        role=role,
        display_name=display_name or username,
        identifier_hash=lookup_hash,
    )

    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO credentials (user_id, password_blob) VALUES (?, ?)",
            (row["id"], password_blob),
        )

    logger.info("Registered user '%s' (role=%s, id=%d)", username, role, row["id"])
    return UserRecord(**row)


def authenticate_user(username: str, password: str) -> UserRecord | None:
    """
    Verify credentials and return the ``UserRecord`` on success, or ``None``.

    Args:
        username: Login identifier.
        password: Plaintext password to verify.

    Returns:
        ``UserRecord`` if credentials match, ``None`` otherwise.
    """
    lookup_hash = _username_to_lookup_hash(username)
    user_row = _db.get_user_by_identifier(lookup_hash)
    if user_row is None:
        logger.debug("authenticate_user: unknown username '%s'", username)
        return None

    with _get_conn() as conn:
        cred = conn.execute(
            "SELECT password_blob FROM credentials WHERE user_id = ?",
            (user_row["id"],),
        ).fetchone()

    if cred is None or not _verify_password(password, cred["password_blob"]):
        logger.debug("authenticate_user: wrong password for '%s'", username)
        _db.append_audit(user_row["id"], "login_failure")
        return None

    _db.append_audit(user_row["id"], "login_success")
    logger.info("Authenticated user '%s' (id=%d)", username, user_row["id"])
    return UserRecord(**user_row)


def get_user_by_username(username: str) -> UserRecord | None:
    """Lookup a user by username (no password check)."""
    lookup_hash = _username_to_lookup_hash(username)
    row = _db.get_user_by_identifier(lookup_hash)
    return UserRecord(**row) if row else None


# ---------------------------------------------------------------------------
# Case management
# ---------------------------------------------------------------------------


def create_case_for_patient(
    patient: UserRecord,
    payload: CasePayload,
) -> CaseRecord:
    """
    Create a new triage case owned by *patient*, encrypting *payload*.

    Args:
        patient: The logged-in patient ``UserRecord``.
        payload: ``CasePayload`` containing clinical detail.

    Returns:
        ``CaseRecord`` metadata (payload excluded).
    """
    row = _db.create_case(
        patient_user_id=patient.id,
        triage_level=payload.triage_level,
        specialty_category=payload.specialty_category,
        confidence_level=payload.confidence_level,
        payload=payload.model_dump(mode="json"),
    )
    return CaseRecord(**row)


def get_patient_cases(patient: UserRecord) -> list[CaseRecord]:
    """Return all ``CaseRecord`` objects owned by *patient*."""
    rows = _db.get_cases_for_patient(patient.id)
    return [CaseRecord(**r) for r in rows]


def get_provider_cases(provider: UserRecord) -> list[dict[str, Any]]:
    """
    Return case metadata dicts for cases shared with *provider*.
    Includes ``consent_scope`` field from the shares table.
    """
    return _db.get_shared_cases_for_provider(provider.id)


def read_case_payload(case_id: int, requester: UserRecord) -> CasePayload | None:
    """
    Decrypt and return the ``CasePayload`` for *case_id*, enforcing consent.

    Returns ``None`` if the requester does not have access.
    """
    raw = _db.get_case_payload(case_id, requester.model_dump())
    if raw is None:
        return None
    return CasePayload(**raw)


def share_case_with_provider(
    case_id: int,
    patient: UserRecord,
    provider_username: str,
    consent_scope: str = "read",
) -> ConsentRecord | None:
    """
    Grant a professional access to *case_id*.

    Args:
        case_id:           The case to share.
        patient:           The owning patient (must match case owner).
        provider_username: Login username of the professional.
        consent_scope:     ``'read'``, ``'comment'``, or ``'full'``.

    Returns:
        ``ConsentRecord`` on success, or ``None`` if the provider is not found.

    Raises:
        PermissionError:       If *patient* does not own *case_id*.
        ValueError:            If *consent_scope* is invalid.
        sqlite3.IntegrityError: If the share already exists.
    """
    provider = get_user_by_username(provider_username)
    if provider is None:
        logger.warning("share_case_with_provider: unknown provider '%s'", provider_username)
        return None

    if provider.role != "professional":
        raise ValueError(f"User '{provider_username}' is not a professional.")

    # Verify ownership
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT patient_user_id FROM cases WHERE id = ?", (case_id,)
        ).fetchone()

    if row is None or row["patient_user_id"] != patient.id:
        raise PermissionError("Patient does not own this case.")

    share_row = _db.share_case(
        case_id=case_id,
        patient_user_id=patient.id,
        provider_user_id=provider.id,
        consent_scope=consent_scope,
    )
    return ConsentRecord(**share_row)


def get_shares_for_case(case_id: int) -> list[dict[str, Any]]:
    """Return all active share records for a given case, joined with provider display_name."""
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT s.*, u.display_name AS provider_display_name
            FROM shares s
            JOIN users u ON u.id = s.provider_user_id
            WHERE s.case_id = ?
            ORDER BY s.created_at DESC
            """,
            (case_id,),
        ).fetchall()
    return [dict(r) for r in rows]
