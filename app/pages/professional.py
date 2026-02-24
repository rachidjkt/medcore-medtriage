"""
app/pages/professional.py

Professional dashboard (Overview) — MedCore style
- Metrics: active patients, scans reviewed, upcoming appointments
- Recent scans + Upcoming sections
- Meeting request creator:
    clinician selects patient + proposes 3 slots (date + time inputs)
- No raw JSON
- IMPORTANT: Force import from app.ui (prevents accidentally importing stale root ui.py)
- Hardening: HTML-escape user/DB strings inside unsafe HTML blocks
"""

from __future__ import annotations

from datetime import datetime, date
import html
import streamlit as st
from pipelines.storage import get_db

# IMPORTANT: Force the correct module (do NOT fall back to `ui.py`)
from app.ui import inject_theme, metric_card, risk_badge, card_open, card_close


def _esc(x: str) -> str:
    return html.escape(str(x or ""), quote=True)


def _normalize_risk(level: str) -> str:
    lvl = (level or "").lower()
    if "high" in lvl or "critical" in lvl:
        return "high"
    if "mod" in lvl or "urgent" in lvl:
        return "moderate"
    return "low"


def _fmt_dt(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%a %b %d · %H:%M")
    except Exception:
        return iso_str


def render() -> None:
    inject_theme()
    st.title("Clinical Dashboard")
    st.caption(datetime.now().strftime("%A, %d %B %Y"))

    if not st.session_state.get("auth_ok") or st.session_state.get("auth_role") != "professional":
        st.warning("Please log in as a medical professional.")
        st.session_state["current_page"] = "auth"
        st.rerun()
        return

    db = get_db()
    demo_mode = st.session_state.get("demo_mode", True)

    pro_user = st.session_state.get("auth_user") or {}
    professional_id = str(pro_user.get("id", "professional"))

    # -------------------------------------------------------------------------
    # Patients list
    # -------------------------------------------------------------------------
    patients = []
    if hasattr(db, "list_patients"):
        patients = db.list_patients() or []
    elif hasattr(db, "list_users"):
        patients = [u for u in (db.list_users() or []) if u.get("role") == "patient"]

    # -------------------------------------------------------------------------
    # Meeting request creator (date + time pickers)
    # -------------------------------------------------------------------------
    with st.expander("➕ Create meeting request", expanded=True):
        if not patients:
            st.info("No patients found in DB (demo mode may still show dashboard metrics).")
        else:
            patient_options = {
                f"{p.get('display_name','Patient')} · {p.get('email','')}".strip(" ·"): p
                for p in patients
            }
            patient_label = st.selectbox("Select patient", options=list(patient_options.keys()))
            patient = patient_options[patient_label]
            patient_id = str(patient.get("id"))

            colA, colB, colC = st.columns([1.2, 1, 1], gap="small")

            with colA:
                appt_date = st.date_input("Date", value=date.today())
                location = st.text_input("Location (optional)", value="Clinic / Hospital (demo)")

            with colB:
                t1 = st.time_input("Time option 1", value=datetime.now().replace(minute=0, second=0, microsecond=0).time())
                t2 = st.time_input("Time option 2", value=datetime.now().replace(minute=0, second=0, microsecond=0).time())
                t3 = st.time_input("Time option 3", value=datetime.now().replace(minute=0, second=0, microsecond=0).time())

            with colC:
                st.caption("These will be sent as **3 proposed slots**.\n\nPatient confirms one on their dashboard.")

                if st.button("Send meeting request", type="primary", use_container_width=True):
                    slots = [
                        datetime.combine(appt_date, t1).strftime("%Y-%m-%dT%H:%M"),
                        datetime.combine(appt_date, t2).strftime("%Y-%m-%dT%H:%M"),
                        datetime.combine(appt_date, t3).strftime("%Y-%m-%dT%H:%M"),
                    ]

                    # remove exact duplicates (if times are same)
                    slots = list(dict.fromkeys(slots))

                    if hasattr(db, "create_appointment_request"):
                        db.create_appointment_request(
                            patient_id=patient_id,
                            professional_id=professional_id,
                            proposed_slots=slots,
                            location=location or "Clinic / Hospital (demo)",
                        )
                        st.success("Meeting request sent.")
                        st.rerun()
                    else:
                        st.error("DB missing create_appointment_request(). Update pipelines/storage.py.")
                        st.stop()

    st.divider()

    # -------------------------------------------------------------------------
    # Compute scans + upcoming appointments
    # -------------------------------------------------------------------------
    scans_reviewed = 0
    upcoming_appts = 0
    recent_scans = []   # list of (patient_name, scan_label, when, risk)
    upcoming = []       # list of (time, patient_name, label, date, status, detail)

    now = datetime.now()

    for p in patients:
        pid = p.get("id")
        pname = p.get("display_name", f"Patient {pid}")

        # reports
        if hasattr(db, "list_reports") and pid:
            reps = db.list_reports(pid) or []
            scans_reviewed += len(reps)

            for r in reps[:1]:
                payload = getattr(r, "payload", {}) or {}
                risk = _normalize_risk(str(payload.get("triage_level", "low")))
                spec = str(payload.get("specialty_category", "Scan review"))
                when = "—"
                try:
                    when = r.created_at.strftime("%d %b %Y")
                except Exception:
                    pass
                recent_scans.append((pname, spec, when, risk))

        # appointments
        if hasattr(db, "list_appointments") and pid:
            appts = db.list_appointments(pid) or []
            for a in appts:
                status = getattr(a, "status", "")
                chosen = getattr(a, "chosen_slot", None)
                proposed = getattr(a, "proposed_slots", None) or []

                if status == "confirmed" and chosen:
                    try:
                        dt = datetime.fromisoformat(chosen)
                        if dt >= now:
                            upcoming_appts += 1
                            upcoming.append(
                                (dt.strftime("%H:%M"), pname, "Consultation", dt.strftime("%d %b"), "confirmed", _fmt_dt(chosen))
                            )
                    except Exception:
                        pass

                elif status == "proposed" and proposed:
                    # show earliest proposed time as a hint (and show the correct detail)
                    earliest = None
                    earliest_str = None
                    for s in proposed:
                        try:
                            dt = datetime.fromisoformat(s)
                            if earliest is None or dt < earliest:
                                earliest = dt
                                earliest_str = s
                        except Exception:
                            continue

                    upcoming_appts += 1
                    if earliest and earliest_str:
                        upcoming.append(
                            (earliest.strftime("%H:%M"), pname, "Consultation", earliest.strftime("%d %b"), "pending", _fmt_dt(earliest_str))
                        )
                    else:
                        upcoming.append(("—", pname, "Consultation", "—", "pending", "Select a time"))

    # Demo fallback ONLY if empty and demo_mode
    if demo_mode and len(patients) == 0 and scans_reviewed == 0 and upcoming_appts == 0:
        patients = [{"id": "p1", "display_name": "Emma Johnson"}, {"id": "p2", "display_name": "Oliver Smith"}]
        scans_reviewed = 138
        upcoming_appts = 7
        recent_scans = [
            ("Emma Johnson", "MRI – Brain", "12 Feb 2026", "moderate"),
            ("Oliver Smith", "CT – Spine", "15 Feb 2026", "high"),
            ("Sophia Davis", "MRI – Lumbar", "10 Feb 2026", "low"),
        ]
        upcoming = [
            ("09:30", "Emma Johnson", "Consultation", "20 Feb", "confirmed", "Thu Feb 20 · 09:30"),
            ("—", "Oliver Smith", "Consultation", "—", "pending", "Pending selection"),
        ]

    # Metrics row (SAFE: plain strings)
    c1, c2, c3 = st.columns(3, gap="large")
    with c1:
        metric_card("Active patients", str(len(patients)), foot="In database")
    with c2:
        metric_card("Scans reviewed", str(scans_reviewed), foot="Total")
    with c3:
        metric_card("Appointments", str(upcoming_appts), foot="Upcoming / pending")

    st.markdown("<br>", unsafe_allow_html=True)

    # Two panels: Recent scans + Upcoming
    left, right = st.columns([2, 1], gap="large")

    with left:
        card_open("Recent Scans")
        if not recent_scans:
            st.caption("No recent scans.")
        else:
            for (pname, label, when, risk) in recent_scans[:6]:
                st.markdown(
                    f"""
<div style="display:flex; justify-content:space-between; gap:10px; padding:12px 0; border-top:1px solid rgba(15,23,42,0.06);">
  <div>
    <div style="font-weight:750;">{_esc(pname)}</div>
    <div style="font-size:14px;">{_esc(label)}</div>
    <div class="mc-sub">{_esc(when)}</div>
  </div>
  <div>{risk_badge(risk)}</div>
</div>
                    """,
                    unsafe_allow_html=True,
                )
        card_close()

    with right:
        card_open("Upcoming")
        if not upcoming:
            st.caption("No upcoming appointments.")
        else:
            for (time, who, label, date_str, status, detail) in upcoming[:6]:
                badge = (
                    '<span class="risk-badge risk-low">Confirmed</span>'
                    if status == "confirmed"
                    else '<span class="risk-badge risk-moderate">Pending</span>'
                )
                st.markdown(
                    f"""
<div style="display:flex; justify-content:space-between; gap:10px; padding:12px 0; border-top:1px solid rgba(15,23,42,0.06);">
  <div style="min-width:64px;">
    <div style="font-weight:800;">{_esc(time)}</div>
    <div class="mc-sub">{_esc(date_str)}</div>
  </div>
  <div style="flex:1;">
    <div style="font-weight:750;">{_esc(who)}</div>
    <div class="mc-sub">{_esc(label)}</div>
    <div class="mc-sub">{_esc(detail)}</div>
  </div>
  <div style="display:flex; align-items:center; gap:8px;">
    {badge}
  </div>
</div>
                    """,
                    unsafe_allow_html=True,
                )
        card_close()

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Go to My Patients →", type="primary"):
        st.session_state["current_page"] = "patients"
        st.rerun()