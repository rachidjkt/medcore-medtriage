"""
pipelines/referral_logic.py

Loads Ottawa/Gatineau hospital data and ranks hospitals based on triage level,
specialty category, and optional user location string.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DATA_PATH = Path(__file__).parent.parent / "data" / "hospitals_ottawa.json"

_TRIAGE_TRAUMA_REQUIREMENT: dict[str, int] = {
    "critical": 1,
    "urgent": 2,
    "routine": 3,
}


def _normalize_triage(triage_level: str) -> str:
    lvl = (triage_level or "").strip().lower()
    # Accept both “model schema” and “UI schema”
    if lvl in ("critical",):
        return "critical"
    if lvl in ("urgent",):
        return "urgent"
    if lvl in ("routine",):
        return "routine"

    # UI/demo variants
    if "high" in lvl:
        return "critical"
    if "mod" in lvl:
        return "urgent"
    if "low" in lvl:
        return "routine"

    return "routine"


def _load_hospitals() -> list[dict[str, Any]]:
    if not _DATA_PATH.exists():
        logger.error("Hospital data file not found: %s", _DATA_PATH)
        return []
    with _DATA_PATH.open("r", encoding="utf-8") as f:
        hospitals: list[dict[str, Any]] = json.load(f)
    return hospitals


def rank_hospitals(
    triage_level: str,
    specialty_category: str,
    user_location: str | None = None,
) -> list[dict[str, Any]]:
    hospitals = _load_hospitals()
    if not hospitals:
        return []

    triage_level_norm = _normalize_triage(triage_level)
    required_trauma = _TRIAGE_TRAUMA_REQUIREMENT.get(triage_level_norm, 3)

    scored: list[dict[str, Any]] = []

    for hospital in hospitals:
        score = 0
        reasons: list[str] = []

        if specialty_category in hospital.get("specialties", []):
            score += 3
            reasons.append(f"specializes in {specialty_category}")

        if hospital.get("trauma_level", 99) <= required_trauma:
            score += 2
            reasons.append(f"trauma level {hospital['trauma_level']} meets requirement")

        if hospital.get("has_icu", False):
            score += 1
            reasons.append("has ICU")

        entry = {
            **hospital,
            "score": score,
            "reason": "; ".join(reasons) or "general community care",
        }
        scored.append(entry)

    scored.sort(key=lambda h: (-h["score"], h.get("trauma_level", 99)))

    top3 = scored[:3]

    if triage_level_norm == "critical" and top3:
        top3[0]["emergency_note"] = "⚠️ Seek immediate emergency care at this facility."

    if user_location:
        logger.info(
            "Ranked hospitals for triage=%s(norm=%s), specialty=%s, location=%s",
            triage_level,
            triage_level_norm,
            specialty_category,
            user_location,
        )

    return top3