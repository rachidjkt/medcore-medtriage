"""
app/pages/auth.py

MedCore-style auth landing page:
- Left hero panel (raw HTML via components.html)
- Right portal selector (Patient / Professional)
"""

from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components
from pipelines.storage import get_db

try:
    from app.ui import inject_theme, portal_choice
except ModuleNotFoundError:
    from ui import inject_theme, portal_choice  # type: ignore


def render() -> None:
    inject_theme()
    db = get_db()

    colL, colR = st.columns([1.15, 1], gap="large")

    with colL:
        hero_html = """
<div style="
  border-radius: 18px;
  height: 640px;
  padding: 26px 26px;
  background:
    radial-gradient(1200px 600px at 10% 20%, rgba(255,255,255,0.08), rgba(255,255,255,0.00) 60%),
    linear-gradient(145deg, hsl(212 72% 18%), hsl(212 72% 12%));
  border: 1px solid rgba(255,255,255,0.10);
  position: relative;
  overflow: hidden;
  font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
">
  <div style="
    position:absolute; left:-40px; top:40px; width:120%;
    height:120px; transform: rotate(-2deg);
    background: linear-gradient(90deg, rgba(255,255,255,0.10), rgba(255,255,255,0.02), rgba(255,255,255,0.00));
    opacity:0.45;
  "></div>

  <div style="display:flex; align-items:center; gap:12px; margin-bottom:22px; position:relative;">
    <div style="
      width:46px; height:46px; border-radius:14px;
      background: hsla(177,60%,38%,0.18);
      display:flex; align-items:center; justify-content:center;
      font-weight:900; color: hsl(177 60% 55%);
      border: 1px solid rgba(255,255,255,0.08);
    ">🩺</div>
    <div style="color: rgba(255,255,255,0.95); font-weight:900; font-size:20px;">MedCore</div>
  </div>

  <div style="position:absolute; left:26px; bottom:22px; right:26px;">
    <div style="color:white; font-weight:1000; font-size:52px; line-height:1.02; margin-bottom:14px;">
      Integrated<br>clinical platform.
    </div>

    <div style="color: rgba(255,255,255,0.75); font-size:15px; max-width:520px; margin-bottom:22px;">
      AI-assisted scan analysis, hospital locator, patient management and scheduling —
      in one unified workspace.
    </div>

    <div style="display:flex; gap:24px; flex-wrap:wrap; margin-top:12px;">
      <div>
        <div style="color: hsl(177 60% 55%); font-weight:900; font-size:12px; letter-spacing:0.06em;">AI ANALYSIS</div>
        <div style="color: rgba(255,255,255,0.80); font-size:13px;">CT · MRI</div>
      </div>
      <div>
        <div style="color: hsl(177 60% 55%); font-weight:900; font-size:12px; letter-spacing:0.06em;">HOSPITALS</div>
        <div style="color: rgba(255,255,255,0.80); font-size:13px;">Live wait times</div>
      </div>
      <div>
        <div style="color: hsl(177 60% 55%); font-weight:900; font-size:12px; letter-spacing:0.06em;">SCHEDULING</div>
        <div style="color: rgba(255,255,255,0.80); font-size:13px;">Real-time</div>
      </div>
    </div>
  </div>
</div>
        """
        # IMPORTANT: components.html renders raw HTML, no Markdown parsing
        components.html(hero_html, height=660)

    with colR:
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        st.markdown(
            """
<div style="padding: 10px 4px;">
  <div style="font-weight:1000; font-size:36px; color: rgba(15,23,42,0.92);">Sign in as</div>
  <div style="margin-top:6px; color: rgba(15,23,42,0.55); font-size:15px;">Choose your portal to continue</div>
</div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

        portal_choice("Patient", "Upload scans, find hospitals and manage your appointments", icon_text="👤")
        if st.button("Continue as Patient", type="primary", use_container_width=True):
            user = db.authenticate("patient@demo.com", "demo")
            st.session_state["auth_ok"] = True
            st.session_state["auth_role"] = user["role"]
            st.session_state["auth_user"] = user
            st.session_state["current_page"] = "patient"
            st.rerun()

        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

        portal_choice("Medical Professional", "Manage patients, review scans and schedule consultations", icon_text="🩺")
        if st.button("Continue as Professional", use_container_width=True):
            user = db.authenticate("doctor@demo.com", "demo")
            st.session_state["auth_ok"] = True
            st.session_state["auth_role"] = user["role"]
            st.session_state["auth_user"] = user
            st.session_state["current_page"] = "professional"
            st.rerun()

        st.markdown(
            """
<p style="color: rgba(15,23,42,0.55); font-size:12px; margin-top:16px;">
By continuing you agree to our Terms and Privacy Policy (demo).
</p>
            """,
            unsafe_allow_html=True,
        )
