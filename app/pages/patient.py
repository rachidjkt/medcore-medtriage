"""
app/pages/patient.py (DEMO SAFE — no HTML helpers)

Patient portal: Overview
- Uses pure Streamlit components (st.metric, st.container)
- Avoids any HTML rendering issues (prevents stray </div>)
- Demo-clean appointments:
    - If a confirmed future appointment exists: show confirmed only
    - Else: show proposed + action required
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Tuple

import streamlit as st
from pipelines.storage import get_db


def _normalize_risk(level: str) -> str:
    lvl = (level or "").lower()
    if "high" in lvl or "critical" in lvl:
        return "high"
    if "mod" in lvl or "urgent" in lvl:
        return "moderate"
    return "low"


def _risk_text(risk: str) -> str:
    r = (risk or "").lower()
    if r == "high":
        return "High Risk"
    if r == "moderate":
        return "Moderate Risk"
    return "Low Risk"


def _fmt_slot(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%a %b %d · %H:%M")
    except Exception:
        return iso_str


def render() -> None:
    st.title("My Health Overview")
    st.caption(datetime.now().strftime("%A, %d %B %Y"))

    if not st.session_state.get("auth_ok") or st.session_state.get("auth_role") != "patient":
        st.warning("Please log in as a patient.")
        st.session_state["current_page"] = "auth"
        st.rerun()
        return

    db = get_db()
    user = st.session_state.get("auth_user") or {}
    patient_id = str(user.get("id", "patient"))

    reports = db.list_reports(patient_id) if hasattr(db, "list_reports") else []
    appts = db.list_appointments(patient_id) if hasattr(db, "list_appointments") else []

    # -------------------------
    # Recent scans
    # -------------------------
    recent_scans: List[Tuple[str, str, str, dict]] = []  # label, date, risk, payload
    last_risk: str | None = None
    last_risk_date: str | None = None

    if reports:
        for r in reports[:8]:
            payload = getattr(r, "payload", {}) or {}
            label = str(payload.get("specialty_category", "Scan"))
            risk = _normalize_risk(str(payload.get("triage_level", "low")))
            when = "—"
            try:
                when = r.created_at.strftime("%d %b %Y")
            except Exception:
                pass
            recent_scans.append((label, when, risk, payload))

        payload0 = getattr(reports[0], "payload", {}) or {}
        last_risk = _normalize_risk(str(payload0.get("triage_level", "low")))
        try:
            last_risk_date = reports[0].created_at.strftime("%d %b %Y")
        except Exception:
            last_risk_date = None

    # -------------------------
    # Appointments: choose one "state" for demo
    # -------------------------
    now = datetime.now()
    confirmed_future: List[datetime] = []
    proposed_times: List[datetime] = []

    for a in appts:
        status = getattr(a, "status", "")
        chosen = getattr(a, "chosen_slot", None)
        proposed = getattr(a, "proposed_slots", None) or []

        if status == "confirmed" and chosen:
            try:
                dt = datetime.fromisoformat(chosen)
                if dt >= now:
                    confirmed_future.append(dt)
            except Exception:
                pass

        if status == "proposed":
            for s in proposed:
                try:
                    proposed_times.append(datetime.fromisoformat(s))
                except Exception:
                    continue

    any_confirmed_future = len(confirmed_future) > 0

    # Next appointment metric
    next_appt_value = "—"
    next_appt_foot = ""

    if confirmed_future:
        dt = min(confirmed_future)
        next_appt_value = dt.strftime("%b %d")
        next_appt_foot = dt.strftime("%H:%M")
    elif proposed_times:
        dt = min(proposed_times)
        next_appt_value = dt.strftime("%b %d")
        next_appt_foot = "Pending (select time below)"

    # -------------------------
    # Metrics row (PURE Streamlit)
    # -------------------------
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Scans uploaded", str(len(reports)))
        st.caption("Total")
    with c2:
        st.metric("Next appointment", next_appt_value)
        if next_appt_foot:
            st.caption(next_appt_foot)
    with c3:
        st.metric("Last risk level", "—" if not last_risk else _risk_text(last_risk))
        st.caption(last_risk_date or "")

    st.divider()

    # -------------------------
    # Action required (ONLY if no confirmed future)
    # -------------------------
    proposed_requests = [
        a
        for a in appts
        if getattr(a, "status", "") == "proposed" and (getattr(a, "proposed_slots", None) or [])
    ]

    # Deduplicate proposed requests
    uniq = []
    seen = set()
    for a in proposed_requests:
        key = (getattr(a, "professional_id", ""), tuple(getattr(a, "proposed_slots", []) or []))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(a)
    proposed_requests = uniq

    if proposed_requests and not any_confirmed_future:
        st.subheader("Action required")
        st.caption("A clinician proposed times — pick one to confirm.")

        for a in proposed_requests[:2]:
            appt_id = getattr(a, "id", "appt")
            slots = list(getattr(a, "proposed_slots", None) or [])
            slot_labels = [_fmt_slot(s) for s in slots]
            label_to_slot = dict(zip(slot_labels, slots))

            st.info(f"Request ID: {appt_id}")

            chosen_label = st.selectbox("Select a time", options=slot_labels, key=f"pick_slot_{appt_id}")

            colA, colB = st.columns([1, 1])
            with colA:
                if st.button("Confirm selected time", type="primary", use_container_width=True, key=f"confirm_{appt_id}"):
                    chosen_slot = label_to_slot.get(chosen_label, slots[0])

                    try:
                        updated = a.model_copy(update={"chosen_slot": chosen_slot, "status": "confirmed"})
                    except Exception:
                        setattr(a, "chosen_slot", chosen_slot)
                        setattr(a, "status", "confirmed")
                        updated = a

                    db.upsert_appointment(updated)
                    st.success("Appointment confirmed.")
                    st.rerun()

            with colB:
                st.caption("Demo scheduling (no email/calendar integration).")

        st.divider()

    # -------------------------
    # Two panels: Scan history + Upcoming
    # -------------------------
    left, right = st.columns([2, 1])

    with left:
        st.subheader("Scan history")
        st.caption("View what the model extracted from your scans.")
        if not recent_scans:
            st.caption("No scans yet. Upload an image in Scan Analysis.")
        else:
            for i, (label, when, risk, payload) in enumerate(recent_scans[:8]):
                with st.container():
                    st.write(f"**{label}**")
                    st.caption(f"{when} • {_risk_text(risk)}")
                    if st.button("View", key=f"view_report_{i}", use_container_width=True):
                        st.session_state["triage_result"] = payload
                        st.session_state["current_page"] = "results"
                        st.rerun()
                st.write("")

    with right:
        st.subheader("Upcoming")
        upcoming_rows: List[Tuple[str, str, str]] = []  # time, label, date

        for a in appts[:20]:
            status = getattr(a, "status", "")
            chosen = getattr(a, "chosen_slot", None)
            proposed = getattr(a, "proposed_slots", None) or []

            if any_confirmed_future:
                if status == "confirmed" and chosen:
                    try:
                        dt = datetime.fromisoformat(chosen)
                        if dt >= now:
                            upcoming_rows.append((dt.strftime("%H:%M"), "Consultation (confirmed)", dt.strftime("%d %b")))
                    except Exception:
                        pass
            else:
                if status == "proposed" and proposed:
                    earliest = None
                    for s in proposed:
                        try:
                            dt = datetime.fromisoformat(s)
                            earliest = dt if (earliest is None or dt < earliest) else earliest
                        except Exception:
                            continue
                    if earliest:
                        upcoming_rows.append((earliest.strftime("%H:%M"), "Consultation (choose a time)", earliest.strftime("%d %b")))
                    else:
                        upcoming_rows.append(("—", "Consultation (choose a time)", "—"))

        if not upcoming_rows:
            st.caption("No upcoming appointments.")
        else:
            for time, label, date_str in upcoming_rows[:8]:
                st.write(f"**{time}**  — {label}")
                st.caption(date_str)
                st.write("")

    st.divider()

    cols = st.columns(3)
    with cols[0]:
        if st.button("Scan analysis →", type="primary", use_container_width=True):
            st.session_state["current_page"] = "upload"
            st.rerun()
    with cols[1]:
        if st.button("Results →", use_container_width=True):
            st.session_state["current_page"] = "results"
            st.rerun()
    with cols[2]:
        if st.button("Find hospitals →", use_container_width=True):
            st.session_state["current_page"] = "referral"
            st.rerun()