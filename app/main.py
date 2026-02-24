"""
app/main.py

MedTriage / MedCore — Streamlit entry point.
- Demo Mode toggle
- Simple role-based login gate (Patient / Professional)
- Role dashboards + core pages
- Global theme injection
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]  # .../medtriage_app
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="MedCore",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Session defaults
# ---------------------------------------------------------------------------
if "triage_result" not in st.session_state:
    st.session_state["triage_result"] = None  # dict | Pydantic | None
if "uploaded_image" not in st.session_state:
    st.session_state["uploaded_image"] = None  # PIL.Image | None

if "demo_mode" not in st.session_state:
    st.session_state["demo_mode"] = True

if "auth_ok" not in st.session_state:
    st.session_state["auth_ok"] = False
if "auth_role" not in st.session_state:
    st.session_state["auth_role"] = None  # "patient" | "professional" | None
if "auth_user" not in st.session_state:
    st.session_state["auth_user"] = None

if "current_page" not in st.session_state:
    st.session_state["current_page"] = "auth"

# If professional selects a patient in Patients tab, store here
if "selected_patient_id" not in st.session_state:
    st.session_state["selected_patient_id"] = None

# ---------------------------------------------------------------------------
# Import helper (package vs script-root)
# ---------------------------------------------------------------------------
def _import_render(module_name: str):
    """
    Import `render` from a page module, handling both:
    - package-style imports: app.pages.<module>
    - script-root imports: pages.<module>
    """
    try:
        mod = __import__(f"app.pages.{module_name}", fromlist=["render"])
        return mod.render
    except ModuleNotFoundError:
        mod = __import__(f"pages.{module_name}", fromlist=["render"])
        return mod.render


def _logout() -> None:
    st.session_state["auth_ok"] = False
    st.session_state["auth_role"] = None
    st.session_state["auth_user"] = None
    st.session_state["current_page"] = "auth"
    st.session_state["selected_patient_id"] = None
    st.rerun()


# ---------------------------------------------------------------------------
# Global theme injection
# ---------------------------------------------------------------------------
try:
    from app.ui import inject_theme
except ModuleNotFoundError:
    from ui import inject_theme  # type: ignore

inject_theme()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.title("🩺 MedCore")
st.sidebar.markdown("AI-assisted scan analysis, hospital locator, scheduling — one workspace.")
st.sidebar.divider()

st.sidebar.toggle(
    "🎬 Demo Mode (no model, hosting-friendly)",
    key="demo_mode",
    help="When enabled, the app can run without loading a model. Best for free hosting.",
)

if st.session_state["auth_ok"]:
    role = st.session_state.get("auth_role") or "unknown"
    user = st.session_state.get("auth_user") or {}
    display = user.get("display_name") or user.get("email") or "User"
    st.sidebar.success(f"**{display}**\n\nRole: **{role}**")
    if st.sidebar.button("↩️ Sign out"):
        _logout()
else:
    st.sidebar.info("Not logged in")

st.sidebar.divider()

# ---------------------------------------------------------------------------
# Navigation options (role-based)
# ---------------------------------------------------------------------------
nav_options = [("Sign in", "auth")]

if st.session_state["auth_ok"]:
    role = st.session_state["auth_role"]

    if role == "patient":
        nav_options.append(("Overview", "patient"))
        nav_options.extend(
            [
                ("Scan Analysis", "upload"),
                ("Results", "results"),
                ("Find Hospitals", "referral"),
            ]
        )

    elif role == "professional":
        nav_options.append(("Overview", "professional"))
        nav_options.append(("My Patients", "patients"))
        nav_options.extend(
            [
                ("Scan Analysis", "upload"),
                ("Results", "results"),
                # NO referral for clinicians
            ]
        )

# Force auth if not logged in
if not st.session_state["auth_ok"]:
    st.session_state["current_page"] = "auth"

labels = [x[0] for x in nav_options]
keys = [x[1] for x in nav_options]

try:
    current_idx = keys.index(st.session_state["current_page"])
except ValueError:
    current_idx = 0
    st.session_state["current_page"] = keys[0]

page_label = st.sidebar.radio("Navigate", options=labels, index=current_idx)
page_key = dict(nav_options)[page_label]
st.session_state["current_page"] = page_key

st.sidebar.divider()
st.sidebar.caption(
    "⚠️ Demo warning: Do not enter real personal health information on a public demo.\n\n"
    "Not a substitute for professional medical advice."
)

# ---------------------------------------------------------------------------
# Page routing
# ---------------------------------------------------------------------------
if page_key == "auth":
    _import_render("auth")()

elif page_key == "patient":
    _import_render("patient")()

elif page_key == "professional":
    _import_render("professional")()

elif page_key == "patients":
    _import_render("patients")()

elif page_key == "upload":
    _import_render("upload")()

elif page_key == "results":
    _import_render("results")()

elif page_key == "referral":
    # Patients only should ever reach this page via nav, but keep it safe:
    if st.session_state.get("auth_role") != "patient":
        st.warning("Referral tools are available in the patient portal only.")
        st.session_state["current_page"] = "professional"
        st.rerun()
    _import_render("referral")()