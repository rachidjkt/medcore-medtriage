"""
app/pages/results.py

Results page (MedCore style):
- No raw JSON shown to user
- Clean risk badge + findings + next steps
- Export button available (JSON download) without displaying it
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List

import streamlit as st

try:
    from app.ui import inject_theme, card_open, card_close, risk_badge
except ModuleNotFoundError:
    from ui import inject_theme, card_open, card_close, risk_badge  # type: ignore


def _as_text_list(x: Any) -> List[str]:
    if x is None:
        return []
    if isinstance(x, list):
        return [str(i) for i in x if str(i).strip()]
    if isinstance(x, str):
        parts = [p.strip("•- \t") for p in x.split("\n")]
        return [p for p in parts if p]
    return [str(x)]


def _safe_get(obj: Any, key: str, default: Any = "") -> Any:
    if obj is None:
        return default
    if hasattr(obj, key):
        return getattr(obj, key)
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default


def _triage_payload(triage_result: Any) -> Dict[str, Any]:
    """
    Ensure we always end up with a JSON-serializable dict for export.
    """
    if triage_result is None:
        return {}
    if hasattr(triage_result, "model_dump"):
        return triage_result.model_dump()  # Pydantic v2
    if isinstance(triage_result, dict):
        return triage_result
    return {"raw": str(triage_result)}


def render() -> None:
    inject_theme()
    st.title("Results")
    st.caption(datetime.now().strftime("%A, %d %B %Y"))

    if not st.session_state.get("auth_ok"):
        st.warning("Please log in to view results.")
        st.session_state["current_page"] = "auth"
        st.rerun()
        return

    triage = st.session_state.get("triage_result")
    img = st.session_state.get("uploaded_image")

    if triage is None and not st.session_state.get("demo_mode", True):
        st.info("No results yet. Go to **Scan Analysis** to generate a report.")
        return

    payload = _triage_payload(triage)

    # Demo mode + no triage => minimal screen (don’t invent medical facts)
    if triage is None and st.session_state.get("demo_mode", True):
        card_open("No report yet", "Upload a scan to generate a triage summary (demo mode is enabled).")
        st.caption("Tip: In demo mode, the app can run without loading the model.")
        card_close()
        return

    triage_level = str(_safe_get(triage, "triage_level", payload.get("triage_level", "Unknown")))
    specialty = str(_safe_get(triage, "specialty_category", payload.get("specialty_category", "General")))
    confidence = str(_safe_get(triage, "confidence_level", payload.get("confidence_level", "")))
    disclaimer = str(_safe_get(triage, "disclaimer", payload.get("disclaimer", "")))

    findings = _as_text_list(_safe_get(triage, "suspected_findings", payload.get("suspected_findings")))
    red_flags = _as_text_list(_safe_get(triage, "red_flags", payload.get("red_flags")))
    next_steps = _as_text_list(_safe_get(triage, "recommended_next_steps", payload.get("recommended_next_steps")))
    summary = str(_safe_get(triage, "patient_summary", payload.get("patient_summary", "")))

    # Top row: image preview + summary card
    left, right = st.columns([1, 1.25], gap="large")

    with left:
        card_open("Scan preview")
        if img is not None:
            st.image(img, use_container_width=True)
        else:
            st.caption("No scan image in session.")
        card_close()

    with right:
        card_open("Triage summary")
        st.markdown(
            f"""
<div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px;">
  <div>
    <div class="mc-sub">Specialty</div>
    <div style="font-weight:900; font-size:22px; color: rgba(15,23,42,0.92); margin-top:2px;">{specialty}</div>
    <div class="mc-sub" style="margin-top:6px;">{("Confidence: " + confidence) if confidence else ""}</div>
  </div>
  <div>{risk_badge(triage_level)}</div>
</div>
            """,
            unsafe_allow_html=True,
        )

        if summary.strip():
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            st.markdown("<div class='mc-sub'>Patient-friendly summary</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:15px; line-height:1.5;'>{summary}</div>", unsafe_allow_html=True)

        card_close()

    st.markdown("<br>", unsafe_allow_html=True)

    # Two cards: findings + next steps
    c1, c2 = st.columns([1, 1], gap="large")

    with c1:
        card_open("Findings")
        if findings:
            for f in findings[:8]:
                st.markdown(f"• {f}")
        else:
            st.caption("No findings listed.")
        if red_flags:
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            st.markdown("<div class='mc-title' style='font-size:14px;'>Red flags</div>", unsafe_allow_html=True)
            for r in red_flags[:8]:
                st.markdown(f"• {r}")
        card_close()

    with c2:
        card_open("Recommended next steps")
        if next_steps:
            for s in next_steps[:10]:
                st.markdown(f"• {s}")
        else:
            st.caption("No next steps listed.")
        card_close()

    st.markdown("<br>", unsafe_allow_html=True)

    if disclaimer.strip():
        st.caption(f"⚠️ {disclaimer}")

    # Export without displaying JSON
    export_bytes = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
    st.download_button(
        "Download report (JSON)",
        data=export_bytes,
        file_name="medcore_triage_report.json",
        mime="application/json",
        use_container_width=False,
    )

    # Role-based actions (clinicians don't need referral)
    role = st.session_state.get("auth_role")
    cols = st.columns([1, 1, 1], gap="small")

    with cols[0]:
        if role == "patient":
            if st.button("Find care →", type="primary", use_container_width=True):
                st.session_state["current_page"] = "referral"
                st.rerun()
        else:
            if st.button("Back to My Patients →", type="primary", use_container_width=True):
                st.session_state["current_page"] = "patients"
                st.rerun()

    with cols[1]:
        if st.button("Run another analysis", use_container_width=True):
            st.session_state["current_page"] = "upload"
            st.rerun()