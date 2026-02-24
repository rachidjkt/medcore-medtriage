"""
app/pages/referral.py

Referral page: accepts city/postal code input and displays top ranked hospitals
based on the current triage result stored in session state.
"""

from __future__ import annotations

import logging
import streamlit as st

logger = logging.getLogger(__name__)


def _safe_get(obj, key: str, default=None):
    if obj is None:
        return default
    if hasattr(obj, key):
        return getattr(obj, key)
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default


def render() -> None:
    """Render the Find Care / Referral page."""
    st.title("🏥 Find Care Near You")

    result = st.session_state.get("triage_result")

    # We allow browsing even without a triage result
    if result is None:
        st.info("No triage result yet. You can still browse hospitals near you.")
        st.caption("Tip: Run a scan analysis to get triage-based ranking.")
        triage_level = "routine"
        specialty_category = "general"
    else:
        triage_level = str(_safe_get(result, "triage_level", "routine") or "routine")
        specialty_category = str(_safe_get(result, "specialty_category", "general") or "general")

        st.markdown(
            f"Based on your triage level **`{triage_level.upper()}`** "
            f"and specialty **`{specialty_category.capitalize()}`**, "
            f"here are recommended facilities."
        )

    st.divider()

    # ---------------------------------------------------------------------------
    # Location input
    # ---------------------------------------------------------------------------
    user_location = st.text_input(
        "Your city or postal code (optional)",
        placeholder="e.g. Ottawa, ON  or  K1Y 4E9  or  Gatineau, QC",
        help="Used for display context only. No geocoding is performed.",
    )

    if st.button("🔍 Find Hospitals", type="primary"):
        from pipelines.referral_logic import rank_hospitals

        with st.spinner("Ranking hospitals..."):
            hospitals = rank_hospitals(
                triage_level=triage_level,
                specialty_category=specialty_category,
                user_location=user_location or None,
            )

        if not hospitals:
            st.error("Could not load hospital data. Please check `data/hospitals_ottawa.json`.")
            return

        st.divider()
        st.subheader("Top Recommended Facilities")

        for rank, hospital in enumerate(hospitals, start=1):
            emergency_note = hospital.get("emergency_note")

            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"### #{rank} — {hospital['name']}")
                    if emergency_note:
                        st.error(emergency_note)
                    st.markdown(f"**Type:** {hospital.get('type', 'N/A')}")
                    st.markdown(f"**Address:** {hospital.get('address', 'N/A')}")
                    st.markdown(f"**Phone:** {hospital.get('phone', 'N/A')}")
                    st.markdown(f"**Notes:** {hospital.get('notes', '')}")
                    if hospital.get("lat") is not None and hospital.get("lon") is not None:
                        st.caption(f"Coords: {hospital['lat']}, {hospital['lon']}")
                    st.markdown(f"**Why recommended:** _{hospital.get('reason', 'N/A')}_")
                with col2:
                    trauma = hospital.get("trauma_level", "N/A")
                    icu = "✅ Yes" if hospital.get("has_icu") else "❌ No"
                    st.metric("Trauma Level", trauma)
                    st.markdown(f"**ICU:** {icu}")
                    specialties = ", ".join(hospital.get("specialties", []))
                    st.caption(f"Specialties: {specialties}")

        st.divider()
        st.caption(
            "⚠️ Hospital rankings are rule-based suggestions based on specialty and trauma level. "
            "Always call ahead or contact emergency services (911) in a life-threatening situation."
        )