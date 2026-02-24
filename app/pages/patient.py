"""
app/pages/patient.py

Patient portal: Overview (MedCore style)
- Metrics + scan history
- Action required for proposed appointment(s) (deduped)
- Next appointment uses earliest confirmed future slot (fixes not updating)
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Tuple

import streamlit as st
from pipelines.storage import get_db

try:
    from app.ui import inject_theme, metric_card, risk_badge, card_open, card_close
except ModuleNotFoundError:
    from ui import inject_theme, metric_card, risk_badge, card_open, card_close  # type: ignore


def _normalize_risk(level: str) -> str:
    lvl = (level or "").lower()
    if "high" in lvl or "critical" in lvl:
        return "high"
    if "mod" in lvl or "urgent" in lvl:
        return "moderate"
    return "low"


def _fmt_slot(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%a %b %d · %H:%M")
    except Exception:
        return iso_str


def render() -> None:
    inject_theme()
    st.title("My Health Overview")
    st.caption(datetime.now().strftime("%A, %d %B %Y"))

    if not st.session_state.get("auth_ok") or st.session_state.get("auth_role") != "patient":
        st.warning("Please log in as a patient.")
        st.session_state["current_page"] = "auth"
        st.rerun()
        return

    db = get_db()
    demo_mode = st.session_state.get("demo_mode", True)

    user = st.session_state.get("auth_user") or {}
    patient_id = str(user.get("id", "patient"))

    # Pull reports + appointments (DB already dedupes appointments now)
    reports = db.list_reports(patient_id) if hasattr(db, "list_reports") else []
    appts = db.list_appointments(patient_id) if hasattr(db, "list_appointments") else []

    # -------------------------
    # Recent scans (UI)
    # -------------------------
    recent_scans: List[Tuple[str, str, str, dict]] = []  # label, date, risk, payload
    last_risk = None
    last_risk_date = None

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
    # Appointments: compute next appointment robustly
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
                    dt = datetime.fromisoformat(s)
                    proposed_times.append(dt)
                except Exception:
                    continue

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

    # Upcoming list for sidebar card
    upcoming: List[Tuple[str, str, str]] = []  # time, label, date
    for a in appts[:10]:
        status = getattr(a, "status", "")
        chosen = getattr(a, "chosen_slot", None)
        proposed = getattr(a, "proposed_slots", None) or []

        if status == "confirmed" and chosen:
            try:
                dt = datetime.fromisoformat(chosen)
                upcoming.append((dt.strftime("%H:%M"), "Consultation (confirmed)", dt.strftime("%d %b")))
            except Exception:
                pass
        elif status == "proposed" and proposed:
            # show earliest proposed slot for context
            earliest = None
            for s in proposed:
                try:
                    dt = datetime.fromisoformat(s)
                    earliest = dt if (earliest is None or dt < earliest) else earliest
                except Exception:
                    continue
            if earliest:
                upcoming.append((earliest.strftime("%H:%M"), "Consultation (choose a time)", earliest.strftime("%d %b")))
            else:
                upcoming.append(("—", "Consultation (choose a time)", "—"))

    # -------------------------
    # Action required (dedupe proposed requests)
    # -------------------------
    proposed_requests = [
        a for a in appts
        if getattr(a, "status", "") == "proposed" and (getattr(a, "proposed_slots", None) or [])
    ]

    # Deduplicate by (professional_id + proposed_slots)
    uniq = []
    seen = set()
    for a in proposed_requests:
        key = (getattr(a, "professional_id", ""), tuple(getattr(a, "proposed_slots", []) or []))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(a)
    proposed_requests = uniq

    if proposed_requests:
        card_open("Action required", "A clinician proposed times — pick one to confirm.")
        for a in proposed_requests[:2]:
            appt_id = getattr(a, "id", "appt")
            slots = list(getattr(a, "proposed_slots", None) or [])
            slot_labels = [_fmt_slot(s) for s in slots]
            label_to_slot = dict(zip(slot_labels, slots))

            st.markdown(
                f"<div class='mc-sub' style='margin-top:6px;'>Request ID: <b>{appt_id}</b></div>",
                unsafe_allow_html=True,
            )

            chosen_label = st.selectbox(
                "Select a time",
                options=slot_labels,
                key=f"pick_slot_{appt_id}",
            )

            cA, cB = st.columns([1, 1], gap="small")
            with cA:
                if st.button("Confirm selected time", type="primary", use_container_width=True, key=f"confirm_{appt_id}"):
                    chosen_slot = label_to_slot.get(chosen_label, slots[0])

                    # Update appointment
                    try:
                        updated = a.model_copy(update={"chosen_slot": chosen_slot, "status": "confirmed"})
                    except Exception:
                        setattr(a, "chosen_slot", chosen_slot)
                        setattr(a, "status", "confirmed")
                        updated = a

                    db.upsert_appointment(updated)
                    st.success("Appointment confirmed.")
                    st.rerun()

            with cB:
                st.caption("This is a demo scheduling flow (no email/calendar integration).")

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        card_close()
        st.markdown("<br>", unsafe_allow_html=True)

    # -------------------------
    # Metrics
    # -------------------------
    c1, c2, c3 = st.columns(3, gap="large")
    with c1:
        metric_card("Scans uploaded", str(len(reports)), foot="Total")
    with c2:
        metric_card("Next appointment", next_appt_value, foot=next_appt_foot)
    with c3:
        metric_card(
            "Last risk level",
            ("—" if not last_risk else last_risk.title()),
            foot=last_risk_date or "",
            pill_html=risk_badge(last_risk or "low"),
        )

    st.markdown("<br>", unsafe_allow_html=True)

    left, right = st.columns([2, 1], gap="large")

    # -------------------------
    # Recent scans: with "View" buttons -> opens Results
    # -------------------------
    with left:
        card_open("Scan history", "View what the model extracted from your scans.")
        if not recent_scans:
            st.caption("No scans yet. Upload an image in Scan Analysis.")
        else:
            for i, (label, when, risk, payload) in enumerate(recent_scans[:8]):
                cA, cB = st.columns([4, 1], gap="small")
                with cA:
                    st.markdown(
                        f"""
<div style="display:flex; justify-content:space-between; gap:10px; padding:12px 0; border-top:1px solid rgba(15,23,42,0.06);">
  <div>
    <div style="font-weight:800;">{label}</div>
    <div class="mc-sub">{when}</div>
  </div>
  <div>{risk_badge(risk)}</div>
</div>
                        """,
                        unsafe_allow_html=True,
                    )
                with cB:
                    if st.button("View", key=f"view_report_{i}", use_container_width=True):
                        # Store payload as the active triage_result for results page
                        st.session_state["triage_result"] = payload
                        st.session_state["current_page"] = "results"
                        st.rerun()
        card_close()

    # -------------------------
    # Upcoming
    # -------------------------
    with right:
        card_open("Upcoming")
        if not upcoming:
            st.caption("No upcoming appointments.")
        else:
            for time, label, date_str in upcoming[:8]:
                st.markdown(
                    f"""
<div style="display:flex; gap:12px; padding:12px 0; border-top:1px solid rgba(15,23,42,0.06); align-items:flex-start;">
  <div style="min-width:64px;">
    <div style="font-weight:900;">{time}</div>
    <div class="mc-sub">{date_str}</div>
  </div>
  <div style="flex:1;">
    <div style="font-weight:800;">{label}</div>
  </div>
</div>
                    """,
                    unsafe_allow_html=True,
                )
        card_close()

    st.markdown("<br>", unsafe_allow_html=True)
    cols = st.columns([1, 1, 1], gap="small")
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