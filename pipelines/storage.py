"""
pipelines/storage.py

Tiny JSON storage layer for demo/MVP.

- Uses ./data/app_db.json by default
- Atomic writes to reduce corruption risk
- Provides helper methods for auth + patient workflow

NOT for real PHI usage.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pipelines.schemas import (
    Appointment,
    PatientProfile,
    ReferralRequest,
    StoredTriageReport,
    User,
)

DEFAULT_DB_PATH = Path("data") / "app_db.json"


def _atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


class JsonDB:
    def __init__(self, path: Path = DEFAULT_DB_PATH):
        self.path = path
        self._ensure_initialized()
        # Add more realistic demo patients without breaking existing installs
        self.seed_demo_data_if_needed()

    def _ensure_initialized(self) -> None:
        if self.path.exists():
            return

        demo_patient = User(
            role="patient",
            email="patient@demo.com",
            password="demo",
            display_name="Demo Patient",
        )
        demo_pro = User(
            role="professional",
            email="doctor@demo.com",
            password="demo",
            display_name="Demo Doctor",
        )

        initial = {
            "users": [demo_patient.model_dump(), demo_pro.model_dump()],
            "profiles": {},      # patient_id -> PatientProfile
            "reports": {},        # patient_id -> [StoredTriageReport...]
            "referrals": {},      # patient_id -> [ReferralRequest...]
            "appointments": {},   # patient_id -> [Appointment...]
        }
        _atomic_write_json(self.path, initial)

    def load(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, db: dict) -> None:
        _atomic_write_json(self.path, db)

    # -------------------------
    # Auth / users
    # -------------------------
    def authenticate(self, email: str, password: str) -> Optional[dict]:
        db = self.load()
        for u in db.get("users", []):
            if u.get("email", "").lower() == email.lower() and u.get("password") == password:
                return u
        return None

    def get_user(self, user_id: str) -> Optional[dict]:
        db = self.load()
        for u in db.get("users", []):
            if u.get("id") == user_id:
                return u
        return None

    def list_users(self) -> list[dict]:
        db = self.load()
        return list(db.get("users", []))

    def list_patients(self) -> list[dict]:
        return [u for u in self.list_users() if u.get("role") == "patient"]

    # -------------------------
    # Demo seeding (adds named patients if missing)
    # -------------------------
    def seed_demo_data_if_needed(self) -> None:
        """
        If DB only has the single demo patient, add a few more named demo patients
        + basic profiles, so the professional view looks realistic.
        """
        db = self.load()
        users = db.get("users", [])
        patients = [u for u in users if u.get("role") == "patient"]

        # already seeded with multiple patients => do nothing
        if len(patients) >= 3:
            return

        demo_patients = [
            User(role="patient", email="emma@demo.com", password="demo", display_name="Emma Johnson").model_dump(),
            User(role="patient", email="oliver@demo.com", password="demo", display_name="Oliver Smith").model_dump(),
            User(role="patient", email="sophia@demo.com", password="demo", display_name="Sophia Davis").model_dump(),
        ]

        existing_emails = {u.get("email") for u in users}
        for p in demo_patients:
            if p.get("email") not in existing_emails:
                users.append(p)

        db["users"] = users

        db.setdefault("profiles", {})
        for p in demo_patients:
            pid = p.get("id")
            if not pid:
                continue
            if pid not in db["profiles"]:
                db["profiles"][pid] = PatientProfile(
                    patient_id=pid,
                    phone="—",
                    allergies="—",
                    medications="—",
                    conditions="—",
                    notes="Demo profile (no real PHI).",
                ).model_dump()

        self.save(db)

    # -------------------------
    # Patient profile
    # -------------------------
    def get_profile(self, patient_id: str) -> PatientProfile:
        db = self.load()
        raw = db.get("profiles", {}).get(patient_id)
        if raw:
            return PatientProfile(**raw)
        return PatientProfile(patient_id=patient_id)

    def upsert_profile(self, profile: PatientProfile) -> None:
        db = self.load()
        db.setdefault("profiles", {})[profile.patient_id] = profile.model_dump()
        self.save(db)

    # -------------------------
    # Triage reports
    # -------------------------
    def list_reports(self, patient_id: str) -> list[StoredTriageReport]:
        db = self.load()
        raw = db.get("reports", {}).get(patient_id, [])
        return [StoredTriageReport(**r) for r in raw]

    def add_report(self, patient_id: str, triage_payload: dict) -> StoredTriageReport:
        db = self.load()
        report = StoredTriageReport(payload=triage_payload)
        db.setdefault("reports", {}).setdefault(patient_id, []).insert(0, report.model_dump())
        self.save(db)
        return report

    # -------------------------
    # Referrals
    # -------------------------
    def list_referrals(self, patient_id: str) -> list[ReferralRequest]:
        db = self.load()
        raw = db.get("referrals", {}).get(patient_id, [])
        return [ReferralRequest(**r) for r in raw]

    def add_referral(self, referral: ReferralRequest) -> None:
        db = self.load()
        db.setdefault("referrals", {}).setdefault(referral.patient_id, []).insert(0, referral.model_dump())
        self.save(db)

    def update_referral(self, referral: ReferralRequest) -> None:
        db = self.load()
        lst = db.get("referrals", {}).get(referral.patient_id, [])
        for i, r in enumerate(lst):
            if r.get("id") == referral.id:
                lst[i] = referral.model_dump()
                db.setdefault("referrals", {})[referral.patient_id] = lst
                self.save(db)
                return

    # -------------------------
    # Appointments (dedupe to fix looping UI)
    # -------------------------
    def _dedupe_appointments(self, appts: list[Appointment]) -> list[Appointment]:
        """
        Removes near-identical duplicates that cause the 'looping' display.
        Keyed by: status + patient_id + professional_id + chosen_slot + proposed_slots + location
        """
        seen = set()
        out: list[Appointment] = []
        for a in appts:
            key = (
                getattr(a, "status", ""),
                getattr(a, "patient_id", ""),
                getattr(a, "professional_id", ""),
                getattr(a, "chosen_slot", None) or "",
                tuple(getattr(a, "proposed_slots", None) or []),
                getattr(a, "location", "") or "",
            )
            if key in seen:
                continue
            seen.add(key)
            out.append(a)
        return out

    def list_appointments(self, patient_id: str) -> list[Appointment]:
        db = self.load()
        raw = db.get("appointments", {}).get(patient_id, [])
        appts = [Appointment(**a) for a in raw]
        return self._dedupe_appointments(appts)

    def upsert_appointment(self, appt: Appointment) -> None:
        db = self.load()
        lst = db.setdefault("appointments", {}).setdefault(appt.patient_id, [])
        for i, a in enumerate(lst):
            if a.get("id") == appt.id:
                lst[i] = appt.model_dump()
                self.save(db)
                return
        lst.insert(0, appt.model_dump())
        self.save(db)

    def create_appointment_request(
        self,
        patient_id: str,
        professional_id: str,
        proposed_slots: list[str],
        location: str = "Clinic / Hospital (demo)",
    ) -> Appointment:
        """
        Create a proposed appointment request (patient will confirm one slot later).
        Also avoids sending exact duplicates.
        """
        existing = self.list_appointments(patient_id)
        for a in existing:
            if getattr(a, "status", "") == "proposed":
                if getattr(a, "professional_id", "") == professional_id and (getattr(a, "proposed_slots", []) == proposed_slots):
                    return a

        appt = Appointment(
            patient_id=patient_id,
            professional_id=professional_id,
            proposed_slots=proposed_slots,
            chosen_slot=None,
            location=location,
            status="proposed",
        )
        self.upsert_appointment(appt)
        return appt


_DB_SINGLETON: Optional[JsonDB] = None


def get_db() -> JsonDB:
    global _DB_SINGLETON
    if _DB_SINGLETON is None:
        _DB_SINGLETON = JsonDB()
    return _DB_SINGLETON