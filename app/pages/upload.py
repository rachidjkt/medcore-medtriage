"""
app/pages/upload.py

Scan Analysis page
- Patient: upload -> run analysis -> saved to their record
- Professional: select patient -> upload -> run analysis -> saved to selected patient
"""

from __future__ import annotations

import streamlit as st
from PIL import Image

from pipelines.storage import get_db

try:
    from app.ui import inject_theme, card_open, card_close
except ModuleNotFoundError:
    from ui import inject_theme, card_open, card_close  # type: ignore


def _profile_to_context(profile) -> str:
    if profile is None:
        return ""
    chunks = []
    if getattr(profile, "conditions", ""):
        chunks.append(f"Conditions: {profile.conditions}")
    if getattr(profile, "medications", ""):
        chunks.append(f"Medications: {profile.medications}")
    if getattr(profile, "allergies", ""):
        chunks.append(f"Allergies: {profile.allergies}")
    if getattr(profile, "notes", ""):
        chunks.append(f"Notes: {profile.notes}")
    return "\n\n".join([c.strip() for c in chunks if c.strip()])


def render() -> None:
    inject_theme()
    st.title("Scan Analysis")
    st.caption("Upload a medical image and optional context to generate a structured triage summary.")

    if not st.session_state.get("auth_ok"):
        st.warning("Please sign in.")
        st.session_state["current_page"] = "auth"
        st.rerun()
        return

    db = get_db()
    demo_mode = st.session_state.get("demo_mode", True)
    role = st.session_state.get("auth_role")
    user = st.session_state.get("auth_user") or {}

    # ---------------------------------------------------------
    # Determine which patient this report belongs to
    # ---------------------------------------------------------
    patient_id = None

    if role == "patient":
        patient_id = str(user.get("id"))
    elif role == "professional":
        patients = db.list_patients() if hasattr(db, "list_patients") else []
        if not patients:
            st.error("No patients found in DB.")
            return

        # If clinician selected a patient in My Patients page, prefer that
        preferred = st.session_state.get("selected_patient_id")
        label_map = {f"{p.get('display_name','Patient')} · {p.get('email','')}": p for p in patients}

        labels = list(label_map.keys())
        default_idx = 0
        if preferred:
            for i, lab in enumerate(labels):
                if str(label_map[lab].get("id")) == str(preferred):
                    default_idx = i
                    break

        picked_label = st.selectbox("Attach report to patient", options=labels, index=default_idx)
        patient_id = str(label_map[picked_label].get("id"))
        st.session_state["selected_patient_id"] = patient_id  # keep it synced
    else:
        st.error("Unknown role.")
        return

    # ---------------------------------------------------------
    # Load profile context (safer than trusting manual entry)
    # ---------------------------------------------------------
    profile = db.get_profile(patient_id) if hasattr(db, "get_profile") else None
    base_context = _profile_to_context(profile)

    st.divider()

    col1, col2 = st.columns([1.15, 1], gap="large")

    with col1:
        uploaded = st.file_uploader(
            "Upload image (PNG/JPG)",
            type=["png", "jpg", "jpeg"],
            help="Demo app: do not upload real PHI to public deployments.",
        )

        use_profile = st.checkbox(
            "Use saved patient profile as context",
            value=True,
            help="Auto-loads conditions/meds/allergies/notes to reduce missing details.",
        )

        extra = st.text_area(
            "Additional context (optional)",
            placeholder="Symptoms, reason for scan, what changed since last visit…",
            height=120,
        )

        context = ""
        if use_profile and base_context.strip():
            context = base_context.strip()
        if extra.strip():
            context = (context + "\n\n" + extra.strip()).strip()

    with col2:
        card_open("Run analysis")
        st.write("This produces a structured triage output (risk level, findings, red flags, next steps).")
        run = st.button("Run MedGemma analysis", type="primary", use_container_width=True)
        card_close()

    if not uploaded:
        st.info("Upload an image to continue.")
        return

    # Keep a preview image in session for Results page
    try:
        pil_img = Image.open(uploaded).convert("RGB")
        st.session_state["uploaded_image"] = pil_img
    except Exception:
        st.session_state["uploaded_image"] = None
        st.error("Could not read the uploaded file as an image.")
        return

    if run:
        with st.spinner("Processing..."):
            if demo_mode:
                triage_payload = {
                    "triage_level": "routine",
                    "specialty_category": "general",
                    "confidence_level": "low",
                    "patient_summary": "Demo output: clinician review recommended.",
                    "suspected_findings": ["Demo only (no model loaded)."],
                    "red_flags": [],
                    "recommended_next_steps": ["Schedule clinician review"],
                    "disclaimer": "Demo only — not medical advice.",
                }
            else:
                from pipelines.preprocess import preprocess_image
                from models.medgemma_runner import get_runner
                from pipelines.postprocess import parse_model_output

                img = preprocess_image(pil_img)
                raw_json_text = get_runner().analyze_image(img, context=context)
                triage_obj = parse_model_output(raw_json_text)
                triage_payload = triage_obj.model_dump()

            if hasattr(db, "add_report"):
                db.add_report(patient_id, triage_payload)

            st.session_state["triage_result"] = triage_payload
            st.session_state["current_page"] = "results"
            st.success("Analysis complete. Opening Results…")
            st.rerun()