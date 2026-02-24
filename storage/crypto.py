"""
storage/crypto.py

Fernet-based encryption helpers for medtriage_app case payloads.

Key lifecycle
-------------
The Fernet key is read from the environment variable APP_DATA_KEY.
APP_DATA_KEY must be a URL-safe base64-encoded 32-byte key as produced by
``Fernet.generate_key()``.

If APP_DATA_KEY is not set, a fresh key is generated at process start and
stored in memory only (suitable for local demo / testing). A warning is
emitted so the operator knows data will not survive a process restart.

Public API
----------
encrypt_json(data: dict) -> str
decrypt_json(token: str) -> dict
"""

import json
import logging
import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Key management
# ---------------------------------------------------------------------------

_ENV_KEY_NAME = "APP_DATA_KEY"


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    """
    Return a cached Fernet instance.

    Reads APP_DATA_KEY from the environment.  If absent, generates a
    one-time in-memory key and logs a warning.
    """
    raw_key = os.environ.get(_ENV_KEY_NAME)

    if raw_key:
        key = raw_key.encode() if isinstance(raw_key, str) else raw_key
        logger.debug("Fernet key loaded from environment variable '%s'.", _ENV_KEY_NAME)
    else:
        key = Fernet.generate_key()
        logger.warning(
            "APP_DATA_KEY environment variable is not set. "
            "A temporary in-memory Fernet key has been generated. "
            "Encrypted data will NOT be recoverable after process restart. "
            "Set APP_DATA_KEY to a stable key for persistent storage."
        )

    return Fernet(key)


# ---------------------------------------------------------------------------
# Public encryption helpers
# ---------------------------------------------------------------------------


def encrypt_json(data: dict) -> str:
    """
    Serialize *data* to JSON, encrypt with Fernet, and return a
    URL-safe base64 token string.

    Args:
        data: Any JSON-serialisable dictionary.

    Returns:
        Fernet token as a UTF-8 string, suitable for TEXT storage in SQLite.

    Raises:
        TypeError: If *data* contains non-serialisable types.
    """
    plaintext: bytes = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    token: bytes = _get_fernet().encrypt(plaintext)
    return token.decode("utf-8")


def decrypt_json(token: str) -> dict:
    """
    Decrypt a Fernet token produced by :func:`encrypt_json` and return
    the original dictionary.

    Args:
        token: A Fernet token string as returned by :func:`encrypt_json`.

    Returns:
        The decrypted dictionary.

    Raises:
        cryptography.fernet.InvalidToken: If *token* is invalid, expired,
            or was encrypted with a different key.
        json.JSONDecodeError: If the decrypted bytes are not valid JSON
            (should never happen for data written by this module).
    """
    try:
        plaintext: bytes = _get_fernet().decrypt(token.encode("utf-8"))
    except InvalidToken as exc:
        logger.error("Fernet decryption failed — wrong key or corrupted token.")
        raise exc

    return json.loads(plaintext.decode("utf-8"))
