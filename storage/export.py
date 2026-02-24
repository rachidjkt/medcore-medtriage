"""
storage/export.py

Handoff export helpers — produce a JSON string or PDF bytes for a triage case.

Both exporters enforce the same access control used by get_case_payload:
the requester must be the case owner or a consented provider.

Dependencies
------------
- reportlab  (PDF generation)
- storage.db / storage.case_manager  (data access)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from storage import db as _db
from storage.case_manager import get_shares_for_case
from storage.models import UserRecord

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared data fetch
# ---------------------------------------------------------------------------


def _build_export_bundle(case_id: int, requester: UserRecord) -> dict[str, Any] | None:
    """
    Assemble all exportable data for a case.

    Returns ``None`` if the requester is not authorised.
    """
    # Metadata
    with _db._connect() as conn:
        case_row = conn.execute(
            "SELECT * FROM cases WHERE id = ?", (case_id,)
        ).fetchone()

    if case_row is None:
        return None

    # Consent-gated payload decrypt
    payload_dict = _db.get_case_payload(case_id, requester.model_dump())
    if payload_dict is None:
        return None  # access denied or missing

    # Shares (non-PHI)
    shares = get_shares_for_case(case_id)

    return {
        "export_generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "case": {
            "id": case_row["id"],
            "status": case_row["status"],
            "triage_level": case_row["triage_level"],
            "specialty_category": case_row["specialty_category"],
            "confidence_level": case_row["confidence_level"],
            "created_at": case_row["created_at"],
            "patient_user_id": case_row["patient_user_id"],
        },
        "payload": payload_dict,
        "shares": [
            {
                "provider_display_name": s.get("provider_display_name"),
                "consent_scope": s["consent_scope"],
                "shared_at": s["created_at"],
            }
            for s in shares
        ],
        "disclaimer": (
            "This document is generated for local demo purposes only. "
            "It is NOT a legally valid health record and must NOT be used "
            "as a substitute for professional medical advice."
        ),
    }


# ---------------------------------------------------------------------------
# JSON export
# ---------------------------------------------------------------------------


def export_json(case_id: int, requester: UserRecord) -> str | None:
    """
    Produce a pretty-printed JSON string for the case handoff.

    Args:
        case_id:   The case to export.
        requester: Logged-in user (access control enforced).

    Returns:
        JSON string, or ``None`` if access is denied / case not found.
    """
    bundle = _build_export_bundle(case_id, requester)
    if bundle is None:
        return None
    _db.append_audit(requester.id, "export_json", case_id=case_id)
    return json.dumps(bundle, indent=2, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# PDF export
# ---------------------------------------------------------------------------


def export_pdf(case_id: int, requester: UserRecord) -> bytes | None:
    """
    Produce a PDF bytes object for the case handoff using reportlab.

    Args:
        case_id:   The case to export.
        requester: Logged-in user (access control enforced).

    Returns:
        PDF as ``bytes``, or ``None`` if access is denied / case not found.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import LETTER
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as exc:
        logger.error("reportlab is not installed: %s", exc)
        raise ImportError(
            "PDF export requires reportlab. Install it with: pip install reportlab"
        ) from exc

    bundle = _build_export_bundle(case_id, requester)
    if bundle is None:
        return None

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=LETTER,
        leftMargin=inch,
        rightMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        fontSize=18,
        textColor=colors.HexColor("#1a3a5c"),
        spaceAfter=6,
    )
    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=12,
        textColor=colors.HexColor("#1a3a5c"),
        spaceBefore=12,
        spaceAfter=4,
    )
    normal = styles["Normal"]
    small = ParagraphStyle("Small", parent=normal, fontSize=8, textColor=colors.grey)

    case = bundle["case"]
    payload = bundle["payload"]
    shares = bundle["shares"]
    generated_at = bundle["export_generated_at"]

    story = []

    # ---- Header ----
    story.append(Paragraph("MedTriage AI — Case Handoff Report", title_style))
    story.append(Paragraph(f"Generated: {generated_at}", small))
    story.append(Spacer(1, 0.15 * inch))

    # ---- Case metadata table ----
    story.append(Paragraph("Case Metadata", heading_style))
    meta_data = [
        ["Field", "Value"],
        ["Case ID", str(case["id"])],
        ["Status", case.get("status", "—")],
        ["Triage Level", case.get("triage_level") or "—"],
        ["Specialty", case.get("specialty_category") or "—"],
        ["Confidence", case.get("confidence_level") or "—"],
        ["Created", case.get("created_at", "—")],
    ]
    meta_table = Table(meta_data, colWidths=[2 * inch, 4.5 * inch])
    meta_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a5c")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4f8")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    story.append(meta_table)
    story.append(Spacer(1, 0.1 * inch))

    # ---- Payload ----
    story.append(Paragraph("Clinical Summary", heading_style))
    story.append(Paragraph(payload.get("summary", "No summary provided."), normal))

    if payload.get("context"):
        story.append(Spacer(1, 0.05 * inch))
        story.append(Paragraph("<b>Clinical Context:</b>", normal))
        story.append(Paragraph(payload["context"], normal))

    if payload.get("raw_ai_output"):
        story.append(Spacer(1, 0.05 * inch))
        story.append(Paragraph("<b>AI Model Output (excerpt):</b>", normal))
        excerpt = payload["raw_ai_output"][:800]
        story.append(Paragraph(excerpt.replace("\n", "<br/>"), small))

    # ---- Shares ----
    if shares:
        story.append(Paragraph("Consent Records", heading_style))
        share_data = [["Provider", "Scope", "Shared At"]] + [
            [s.get("provider_display_name", "—"), s["consent_scope"], s["shared_at"]]
            for s in shares
        ]
        share_table = Table(share_data, colWidths=[2.5 * inch, 1.5 * inch, 2.5 * inch])
        share_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2d6a4f")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f8f4")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        story.append(share_table)

    # ---- Disclaimer ----
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(bundle["disclaimer"], small))

    doc.build(story)
    _db.append_audit(requester.id, "export_pdf", case_id=case_id)
    return buf.getvalue()
