"""
app/pages/patients.py

Professional portal: My Patients (MedCore style)
- List patients on the left
- Select patient to view details on the right
- Schedule-lite: propose 3 time slots to selected patient (date + time inputs)
- Uses JsonDB.create_appointment_request() (robust, consistent)
- No raw JSON shown
"""

from __future__ import annotations

from datetime import datetime, date
from typing import Any, Dict, List

import streamlit as st
from pipelines.storage import get_db

try:
    from app.ui import inject_theme, card_open, card_close, risk_badge
except ModuleNotFoundError:
    from ui import inject_theme, card_open, card_close, risk_badge  # type: ignore


def _normalize_risk(level: str) -> str:
    lvl = (level or "").lower()
    if "high" in lvl or "critical" in lvl:
        return "high"
    if "mod" in lvl or "urgent" in lvl:
        return "moderate"
    return "low"


def _latest_report_summary(db: Any, patient_id: str) -> Dict[str, str]:
    """
    Returns: {label, date, risk}
    """
    out = {"label": "—", "date": "—", "risk": "low"}
    if not hasattr(db, "list_reports"):
        return out

    reps = db.list_reports(patient_id) or []
    if not reps:
        return out

    r0 = reps[0]
    payload = getattr(r0, "payload", {}) or {}
    out["label"] = str(payload.get("specialty_category", "Scan review"))
    out["risk"] = _normalize_risk(str(payload.get("triage_level", "low")))
    try:
        out["date"] = r0.created_at.strftime("%d %b %Y")
    except Exception:
        pass
    return out


def render() -> None:
    inject_theme()
    st.title("My Patients")
    st.caption("Select a patient to view their profile and propose appointment times.")

    if not st.session_state.get("auth_ok") or st.session_state.get("auth_role") != "professional":
        st.warning("Please log in as a medical professional.")
        st.session_state["current_page"] = "auth"
        st.rerun()
        return

    db = get_db()
    demo_mode = st.session_state.get("demo_mode", True)

    pro_user = st.session_state.get("auth_user") or {}
    professional_id = str(pro_user.get("id", "professional"))
    professional_name = pro_user.get("display_name", "Clinician")

    # Get patients from DB (supports both list_patients() or list_users())
    patients: List[Dict[str, Any]] = []
    if hasattr(db, "list_patients"):
        patients = db.list_patients() or []
    elif hasattr(db, "list_users"):
        patients = [u for u in (db.list_users() or []) if u.get("role") == "patient"]

    if not patients and demo_mode:
        # Demo list only (names only; no real PHI)
        patients = [
            {"id": "p1", "display_name": "Emma Johnson", "age": 45, "reason": "Cerebral vascular assessment"},
            {"id": "p2", "display_name": "Oliver Smith", "age": 62, "reason": "Post-operative monitoring"},
            {"id": "p3", "display_name": "Sophia Davis", "age": 34, "reason": "Routine neurological check"},
            {"id": "p4", "display_name": "Liam Wilson", "age": 58, "reason": "Spinal stenosis follow-up"},
        ]

    if "selected_patient_id" not in st.session_state:
        st.session_state["selected_patient_id"] = str(patients[0]["id"]) if patients else None

    left, right = st.columns([1.05, 1.6], gap="large")

    # -------------------------------------------------------------------------
    # LEFT: Patient list + selector
    # -------------------------------------------------------------------------
    with left:
        card_open("Patients")
        if not patients:
            st.caption("No patients available.")
            card_close()
        else:
            # Build a stable selector label map
            label_map: Dict[str, Dict[str, Any]] = {}
            for p in patients:
                pid = str(p.get("id"))
                name = p.get("display_name", f"Patient {pid}")
                age = p.get("age", "—")
                reason = p.get("reason", "")
                summ = _latest_report_summary(db, pid) if hasattr(db, "list_reports") else {"label": "—", "date": "—", "risk": "low"}
                label = f"{name} · Age {age} · Last {summ['date']}"
                label_map[label] = p

            labels = list(label_map.keys())

            # Preselect current patient in selectbox
            current_pid = str(st.session_state.get("selected_patient_id") or "")
            current_label = None
            for lbl, p in label_map.items():
                if str(p.get("id")) == current_pid:
                    current_label = lbl
                    break
            if current_label is None:
                current_label = labels[0]

            picked_label = st.selectbox("Select patient", options=labels, index=labels.index(current_label))
            picked = label_map[picked_label]
            st.session_state["selected_patient_id"] = str(picked.get("id"))

            # Show a compact “cards” list underneath (nice UX, no buttons spam)
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            for p in patients[:12]:
                pid = str(p.get("id"))
                name = p.get("display_name", f"Patient {pid}")
                age = p.get("age", "—")
                reason = p.get("reason", "")
                summ = _latest_report_summary(db, pid) if hasattr(db, "list_reports") else {"label": "—", "date": "—", "risk": "low"}

                is_selected = pid == str(st.session_state.get("selected_patient_id"))
                border = "2px solid hsla(177,60%,38%,0.55)" if is_selected else "1px solid rgba(15,23,42,0.10)"

                st.markdown(
                    f"""
<div style="border:{border}; border-radius:16px; padding:14px; margin-bottom:12px; background:#fff;">
  <div style="display:flex; justify-content:space-between; gap:10px; align-items:flex-start;">
    <div>
      <div style="font-weight:900; font-size:16px; color:rgba(15,23,42,0.92);">{name}</div>
      <div class="mc-sub">{reason}</div>
      <div class="mc-sub">Age {age} · Last scan {summ["date"]}</div>
    </div>
    <div>{risk_badge(summ["risk"])}</div>
  </div>
</div>
                    """,
                    unsafe_allow_html=True,
                )

            card_close()

    # -------------------------------------------------------------------------
    # RIGHT: Patient details + scheduling
    # -------------------------------------------------------------------------
    with right:
        card_open("Patient details")

        pid = st.session_state.get("selected_patient_id")
        if not pid:
            st.caption("Select a patient to view details.")
            card_close()
            return

        selected = next((x for x in patients if str(x.get("id")) == str(pid)), {"display_name": f"Patient {pid}"})

        st.markdown(
            f"<div style='font-weight:1000; font-size:18px;'>{selected.get('display_name')}</div>",
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # Profile (NO JSON)
        profile = db.get_profile(pid) if hasattr(db, "get_profile") else None
        if profile is None:
            st.caption("No saved profile for this patient yet.")
        else:
            st.markdown("<div class='mc-sub'>Allergies</div>", unsafe_allow_html=True)
            st.write(getattr(profile, "allergies", None) or "—")
            st.markdown("<div class='mc-sub'>Medications</div>", unsafe_allow_html=True)
            st.write(getattr(profile, "medications", None) or "—")
            st.markdown("<div class='mc-sub'>Conditions</div>", unsafe_allow_html=True)
            st.write(getattr(profile, "conditions", None) or "—")
            st.markdown("<div class='mc-sub'>Notes</div>", unsafe_allow_html=True)
            st.write(getattr(profile, "notes", None) or "—")

        # Latest scan summary
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        summ = _latest_report_summary(db, pid)
        st.markdown(
            f"""
<div class="mc-card" style="padding:14px;">
  <div style="display:flex; justify-content:space-between; gap:10px; align-items:flex-start;">
    <div>
      <div class="mc-title">Latest scan</div>
      <div class="mc-sub">{summ["label"]} · {summ["date"]}</div>
    </div>
    <div>{risk_badge(summ["risk"])}</div>
  </div>
</div>
            """,
            unsafe_allow_html=True,
        )

        # Scheduling
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        st.markdown("<div class='mc-title'>Schedule appointment</div>", unsafe_allow_html=True)
        st.caption("Propose 3 time slots. The patient can confirm one in their portal.")

        with st.form("propose_slots"):
            colA, colB = st.columns([1.1, 1], gap="small")
            with colA:
                appt_date = st.date_input("Date", value=date.today())
                location = st.text_input("Location", value="Video consultation")
            with colB:
                t1 = st.time_input("Time option 1", value=datetime.now().replace(minute=0, second=0, microsecond=0).time())
                t2 = st.time_input("Time option 2", value=datetime.now().replace(minute=0, second=0, microsecond=0).time())
                t3 = st.time_input("Time option 3", value=datetime.now().replace(minute=0, second=0, microsecond=0).time())

            submitted = st.form_submit_button("Send proposal", type="primary")

            if submitted:
                slots = [
                    datetime.combine(appt_date, t1).strftime("%Y-%m-%dT%H:%M"),
                    datetime.combine(appt_date, t2).strftime("%Y-%m-%dT%H:%M"),
                    datetime.combine(appt_date, t3).strftime("%Y-%m-%dT%H:%M"),
                ]
                # de-dup exact duplicates (if same time used)
                slots = list(dict.fromkeys(slots))

                if hasattr(db, "create_appointment_request"):
                    db.create_appointment_request(
                        patient_id=str(pid),
                        professional_id=professional_id,
                        proposed_slots=slots,
                        location=location or "Video consultation",
                    )
                    st.success("Proposal sent.")
                    st.rerun()
                else:
                    st.error("DB missing create_appointment_request(). Please update pipelines/storage.py.")
                    st.stop()

        # Show existing appointments for this patient
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        st.markdown("<div class='mc-title'>Appointments</div>", unsafe_allow_html=True)

        appts = db.list_appointments(pid) if hasattr(db, "list_appointments") else []
        if not appts:
            st.caption("No appointments yet.")
        else:
            for a in appts[:8]:
                status = getattr(a, "status", "—")
                chosen = getattr(a, "chosen_slot", None)
                proposed = getattr(a, "proposed_slots", None) or []
                who = getattr(a, "professional_id", None) or professional_name

                if status == "confirmed" and chosen:
                    line = f"✅ Confirmed · {_fmt_dt(chosen)}"
                else:
                    # proposed/pending
                    preview = ", ".join(_fmt_dt(s) for s in proposed[:2])
                    more = f" (+{len(proposed)-2} more)" if len(proposed) > 2 else ""
                    line = f"🕒 Pending · {preview}{more}"

                st.markdown(
                    f"""
<div style="padding:12px 0; border-top:1px solid rgba(15,23,42,0.06);">
  <div style="font-weight:850;">{line}</div>
  <div class="mc-sub">Location: {getattr(a, "location", "—")}</div>
</div>
                    """,
                    unsafe_allow_html=True,
                )

        card_close()


def _fmt_dt(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%a %b %d · %H:%M")
    except Exception:
        return iso_str