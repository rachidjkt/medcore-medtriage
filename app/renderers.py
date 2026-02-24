# app/renderers.py
from __future__ import annotations
import streamlit as st

from app.ui import card_open, card_close, risk_badge

def render_triage_report(result) -> None:
    """
    Render TriageOutput (Pydantic) in a friendly way.
    Never shows raw JSON.
    """
    # result fields expected:
    # triage_level, suspected_findings, red_flags, recommended_next_steps,
    # specialty_category, patient_summary, confidence_level, disclaimer

    triage_level = getattr(result, "triage_level", "unknown")
    specialty = getattr(result, "specialty_category", "general")
    confidence = getattr(result, "confidence_level", "unknown")
    summary = getattr(result, "patient_summary", "")

    card_open("Triage Summary", "A structured summary of the scan analysis (demo / AI-assisted).")
    st.markdown(
        f"""
<div style="display:flex; gap:10px; flex-wrap:wrap; margin-top:6px;">
  {risk_badge(triage_level)}
  <span class="risk-badge risk-low" style="background:#EEF2F7;color:rgba(15,23,42,0.75);">Specialty: {specialty}</span>
  <span class="risk-badge risk-low" style="background:#EEF2F7;color:rgba(15,23,42,0.75);">Confidence: {confidence}</span>
</div>
        """,
        unsafe_allow_html=True,
    )
    if summary:
        st.markdown(f"**Summary:** {summary}")
    card_close()

    # Findings
    findings = getattr(result, "suspected_findings", []) or []
    card_open("Findings")
    if findings:
        for f in findings:
            st.markdown(f"- {f}")
    else:
        st.caption("No findings listed.")
    card_close()

    # Red flags
    red_flags = getattr(result, "red_flags", []) or []
    card_open("Red flags")
    if red_flags:
        for r in red_flags:
            st.markdown(f"- {r}")
    else:
        st.caption("No red flags listed.")
    card_close()

    # Next steps
    steps = getattr(result, "recommended_next_steps", []) or []
    card_open("Recommended next steps")
    if steps:
        for s in steps:
            st.markdown(f"- {s}")
    else:
        st.caption("No next steps listed.")
    card_close()

    disclaimer = getattr(result, "disclaimer", "")
    if disclaimer:
        st.info(disclaimer)
