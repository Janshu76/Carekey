from __future__ import annotations

import json
from datetime import timedelta

from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import (
    AccessToken,
    AdmissionRecord,
    ConsentRecord,
    Patient,
    PatientCondition,
    SourceRecord,
    TrustedContact,
    utcnow,
)
from .services.security import hash_value

DEMO_PATIENTS = [
    ("Ramesh Sharma", 72, "B+", "Type 2 diabetes", "Neha Sharma", "Daughter", "Hypertension"),
    ("Kamala Nair", 68, "A+", "Hypertension", "Arun Nair", "Son", "Osteoarthritis"),
    ("Vijay Patel", 81, "O-", "Coronary artery disease", "Mira Patel", "Daughter", "Type 2 diabetes"),
    ("Savitri Iyer", 76, "AB+", "Chronic kidney disease", "Karthik Iyer", "Son", "Osteoporosis"),
    ("Harish Mehta", 70, "A-", "Atrial fibrillation", "Nisha Mehta", "Daughter", "Hypertension"),
    ("Leela Reddy", 84, "B-", "Heart failure", "Anand Reddy", "Son", "Type 2 diabetes"),
    ("Mohammed Khan", 65, "O+", "Type 2 diabetes", "Sana Khan", "Daughter", "Asthma"),
    ("Anjali Das", 79, "AB-", "Hypertension", "Rahul Das", "Son", "Osteoarthritis"),
    ("Gopal Singh", 88, "A+", "Chronic kidney disease", "Simran Singh", "Daughter", "Coronary artery disease"),
    ("Mary Thomas", 62, "B+", "Hypothyroidism", "Joseph Thomas", "Son", "Type 2 diabetes"),
]


def _add_patient(db: Session, index: int, data: tuple[str, int, str, str, str, str, str]) -> None:
    name, age, blood_group, condition, contact_name, contact_relation, second_condition = data
    guardian_phone = {
        1: "+91 98990 11223",
        2: "+91 98111 24567",
    }.get(index, f"+91 90000 {index:05d}")
    contact_phone = {
        1: "+91 98765 43210",
        2: "+91 98450 22333",
    }.get(index, f"+91 91000 {index:05d}")
    patient = Patient(
        name=name,
        age=age,
        blood_group=blood_group,
        primary_condition=condition,
        emergency_contact_name=contact_name,
        emergency_contact_phone=contact_phone,
        guardian_name=contact_name,
        guardian_phone=guardian_phone,
        insurer_policy=f"DEMO-CARE-{index:04d}",
    )
    db.add(patient)
    db.flush()

    contacts = [
        (contact_name, contact_relation, contact_phone, True),
        (f"Guardian {index}", "Guardian", guardian_phone, False),
        (f"Family contact {index}", "Relative", f"+91 92000 {index:05d}", False),
    ]
    db.add_all(
        TrustedContact(
            patient_id=patient.id,
            name=contact_name_value,
            relationship=relation,
            phone=phone,
            is_primary=is_primary,
        )
        for contact_name_value, relation, phone, is_primary in contacts
    )

    for field, tier in (
        ("blood_group", "emergency"),
        ("allergies", "emergency"),
        ("medications", "standard"),
        ("conditions", "standard"),
        ("contacts", "standard"),
        ("injuries", "standard"),
        ("insurer", "sensitive"),
    ):
        db.add(
            ConsentRecord(
                patient_id=patient.id,
                field_name=field,
                consent_value=field != "insurer",
                tier=tier,
                expiry_minutes=180,
            )
        )

    medication_name = "Metformin" if "diabetes" in condition.lower() else "Amlodipine"
    first_dose = "500 mg twice daily" if index == 1 else "500 mg once daily"
    hospital_payload = {
        "allergies": ["Penicillin"] if index % 2 else ["Sulfonamide antibiotics"],
        "medications": [
            {"name": medication_name, "dose": first_dose},
            {"name": "Aspirin", "dose": "75 mg once daily"},
        ],
        "source_date": utcnow().isoformat(),
    }
    clinic_payload = {
        "conditions": [condition, second_condition],
        "blood_group": blood_group,
        "contacts": [contact_name, patient.guardian_name],
        "source_date": utcnow().isoformat(),
    }
    if index == 1:
        clinic_payload["medications"] = [
            {"name": "Metformin", "dose": "850 mg twice daily"}
        ]

    db.add_all(
        [
            SourceRecord(
                patient_id=patient.id,
                source_name="Hospital A",
                record_type="allergies_and_medicines",
                payload=json.dumps(hospital_payload),
            ),
            SourceRecord(
                patient_id=patient.id,
                source_name="Clinic B",
                record_type="conditions_blood_group_and_contacts",
                payload=json.dumps(clinic_payload),
            ),
            PatientCondition(
                patient_id=patient.id,
                name=condition,
                body_region="whole_body",
                condition_type="condition",
                notes="Synthetic demo record; confirm with the patient or clinician.",
                source_name="Clinic B",
                is_active=True,
            ),
            PatientCondition(
                patient_id=patient.id,
                name="Previous fall injury" if index % 2 else "Knee replacement",
                body_region="left_knee",
                condition_type="injury" if index % 2 else "surgery",
                notes="Synthetic demo history.",
                source_name="Hospital A",
                occurred_at=utcnow() - timedelta(days=365),
                is_active=False,
            ),
            AccessToken(
                patient_id=patient.id,
                token_hash=hash_value(f"carelink-{patient.id}-demo-token"),
                expires_at=utcnow() + timedelta(hours=8),
                is_active=True,
                revoked=False,
                single_use=False,
            ),
            AdmissionRecord(
                patient_id=patient.id,
                hospital_name="Sundaram General",
                reason="Emergency assessment",
                status="pending",
            ),
        ]
    )


def _complete_existing_patient(
    db: Session,
    patient: Patient,
    index: int,
    data: tuple[str, int, str, str, str, str, str],
) -> None:
    _, _, _, condition, contact_name, contact_relation, second_condition = data
    present_consents = {
        row.field_name
        for row in db.query(ConsentRecord).filter(ConsentRecord.patient_id == patient.id).all()
    }
    for field, tier in (
        ("blood_group", "emergency"),
        ("allergies", "emergency"),
        ("medications", "standard"),
        ("conditions", "standard"),
        ("contacts", "standard"),
        ("injuries", "standard"),
        ("insurer", "sensitive"),
    ):
        if field not in present_consents:
            db.add(
                ConsentRecord(
                    patient_id=patient.id,
                    field_name=field,
                    consent_value=field != "insurer",
                    tier=tier,
                    expiry_minutes=180,
                )
            )

    existing_contacts = db.query(TrustedContact).filter(TrustedContact.patient_id == patient.id).all()
    contact_phones = {contact.phone for contact in existing_contacts}
    if patient.emergency_contact_phone and patient.emergency_contact_phone not in contact_phones:
        db.add(
            TrustedContact(
                patient_id=patient.id,
                name=contact_name,
                relationship=contact_relation,
                phone=patient.emergency_contact_phone,
                is_primary=True,
            )
        )
        contact_phones.add(patient.emergency_contact_phone)
    if patient.guardian_phone and patient.guardian_phone not in contact_phones:
        db.add(
            TrustedContact(
                patient_id=patient.id,
                name=patient.guardian_name or f"Guardian {index}",
                relationship="Guardian",
                phone=patient.guardian_phone,
                is_primary=False,
            )
        )
        contact_phones.add(patient.guardian_phone)
    if len(contact_phones) < 3:
        db.add(
            TrustedContact(
                patient_id=patient.id,
                name=f"Family contact {index}",
                relationship="Relative",
                phone=f"+91 92000 {index:05d}",
                is_primary=False,
            )
        )

    clinic_record = (
        db.query(SourceRecord)
        .filter(SourceRecord.patient_id == patient.id, SourceRecord.source_name == "Clinic B")
        .first()
    )
    if clinic_record and index == 1:
        clinic_payload = json.loads(clinic_record.payload)
        if not clinic_payload.get("medications"):
            clinic_payload["medications"] = [
                {"name": "Metformin", "dose": "850 mg twice daily"}
            ]
            clinic_record.payload = json.dumps(clinic_payload)

    existing_condition = (
        db.query(PatientCondition)
        .filter(
            PatientCondition.patient_id == patient.id,
            PatientCondition.condition_type == "condition",
        )
        .first()
    )
    if existing_condition is None:
        db.add(
            PatientCondition(
                patient_id=patient.id,
                name=condition,
                body_region="whole_body",
                condition_type="condition",
                source_name="Clinic B",
                is_active=True,
            )
        )
    existing_injury = (
        db.query(PatientCondition)
        .filter(
            PatientCondition.patient_id == patient.id,
            PatientCondition.condition_type.in_({"injury", "surgery"}),
        )
        .first()
    )
    if existing_injury is None:
        db.add(
            PatientCondition(
                patient_id=patient.id,
                name="Previous fall injury" if index % 2 else "Knee replacement",
                body_region="left_knee",
                condition_type="injury" if index % 2 else "surgery",
                notes="Synthetic demo history.",
                source_name="Hospital A",
                occurred_at=utcnow() - timedelta(days=365),
                is_active=False,
            )
        )


def seed_demo_data(db: Session | None = None) -> None:
    owns_session = db is None
    if db is None:
        db = SessionLocal()
    try:
        for index, patient_data in enumerate(DEMO_PATIENTS, start=1):
            existing_patient = (
                db.query(Patient)
                .filter(Patient.name == patient_data[0])
                .first()
            )
            if existing_patient is None:
                _add_patient(db, index, patient_data)
            else:
                _complete_existing_patient(db, existing_patient, index, patient_data)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        if owns_session:
            db.close()
