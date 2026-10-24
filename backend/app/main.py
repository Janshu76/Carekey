from __future__ import annotations

import json
import re
import secrets
from datetime import timedelta

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .config import settings
from .database import Base, SessionLocal, engine, get_db
from .models import (
    AccessLog,
    AccessToken,
    AdmissionRecord,
    ConsentReceipt,
    ConsentRecord,
    Notification,
    Patient,
    PatientCondition,
    SourceRecord,
    TrustedContact,
    utcnow,
)
from .schemas import (
    AdmissionCreate,
    ConsentRequest,
    EmergencyAccessRequest,
    OTPRequest,
    OTPVerify,
    PatientConditionCreate,
    ResponderLogin,
    TokenCreate,
    TokenLookup,
    TokenRevoke,
)
from .services.bridge import get_patient_record_view, verify_audit_chain
from .services.security import (
    authenticated_claims,
    create_access_token,
    hash_value,
    issue_otp,
    lookup_access_token,
    require_guardian_for_patient,
    require_role,
    token_is_expired,
    verify_otp,
)

app = FastAPI(
    title="CareLink Emergency Bridge API",
    description=(
        "Synthetic-data demo API for consent-based emergency record access. "
        "This is not a production medical-record system."
    ),
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Convert secrets written by the early demo backend into digests.
        for row in db.query(AccessToken).all():
            if not re.fullmatch(r"[0-9a-f]{64}", row.token_hash):
                row.token_hash = hash_value(row.token_hash)
        for row in db.query(AccessLog).all():
            if not re.fullmatch(r"[0-9a-f]{64}", row.token):
                row.token = hash_value(row.token)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    if settings.environment != "production":
        from .seed import seed_demo_data

        seed_demo_data()


initialize_database()


def _patient_or_404(db: Session, patient_id: int) -> Patient:
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


def _active_consent(db: Session, patient_id: int, field_name: str) -> bool:
    consent = (
        db.query(ConsentRecord)
        .filter(
            ConsentRecord.patient_id == patient_id,
            ConsentRecord.field_name == field_name,
        )
        .first()
    )
    if consent is None or not consent.consent_value:
        return False
    updated_at = consent.updated_at
    if updated_at.tzinfo is None:
        from datetime import timezone

        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return updated_at + timedelta(minutes=consent.expiry_minutes) > utcnow()


@app.get("/health")
def health_check():
    return {"status": "ok", "service": settings.app_name, "environment": settings.environment}


@app.post("/auth/otp/request")
def request_guardian_otp(payload: OTPRequest, db: Session = Depends(get_db)):
    if settings.environment == "production":
        raise HTTPException(status_code=503, detail="Mock OTP delivery is disabled in production")
    challenge, code = issue_otp(db, payload.phone)
    response = {
        "challenge_id": challenge.id,
        "expires_in_seconds": 300,
        "delivery": "mock",
        "message": "Demo OTP generated; no SMS was sent.",
    }
    if settings.environment != "production":
        response["demo_code"] = code
    return response


@app.post("/auth/otp/verify")
def verify_guardian_otp(payload: OTPVerify, db: Session = Depends(get_db)):
    phone = verify_otp(db, payload.challenge_id, payload.code)
    patient = (
        db.query(Patient)
        .filter((Patient.guardian_phone == phone) | (Patient.emergency_contact_phone == phone))
        .first()
    )
    if patient is None:
        raise HTTPException(status_code=403, detail="This phone is not linked to a trusted guardian")
    access_token = create_access_token({"sub": phone, "role": "guardian"})
    return {"access_token": access_token, "token_type": "bearer", "role": "guardian"}


@app.post("/auth/responder/login")
def responder_login(payload: ResponderLogin):
    if settings.environment == "production":
        raise HTTPException(status_code=503, detail="Mock responder login is disabled in production")
    access_token = create_access_token(
        {
            "sub": payload.name.strip(),
            "role": "responder",
            "organization": payload.organization.strip(),
        }
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": "responder",
        "demo": True,
    }


@app.get("/patients")
def list_patients(
    claims: dict = Depends(require_role("guardian")),
    db: Session = Depends(get_db),
):
    patients = (
        db.query(Patient)
        .filter(
            (Patient.guardian_phone == claims["sub"])
            | (Patient.emergency_contact_phone == claims["sub"])
        )
        .order_by(Patient.name)
        .all()
    )
    return [
        {
            "id": patient.id,
            "name": patient.name,
            "age": patient.age,
            "primary_condition": patient.primary_condition,
        }
        for patient in patients
    ]


@app.get("/patients/{patient_id}")
def get_patient(
    patient_id: int,
    _: dict = Depends(require_guardian_for_patient),
    db: Session = Depends(get_db),
):
    patient = _patient_or_404(db, patient_id)
    return {
        "id": patient.id,
        "name": patient.name,
        "age": patient.age,
        "blood_group": patient.blood_group,
        "primary_condition": patient.primary_condition,
        "emergency_contact_name": patient.emergency_contact_name,
        "emergency_contact_phone": patient.emergency_contact_phone,
        "guardian_name": patient.guardian_name,
        "guardian_phone": patient.guardian_phone,
        "insurer_policy": patient.insurer_policy,
    }


@app.get("/patients/{patient_id}/consents")
def get_patient_consents(
    patient_id: int,
    _: dict = Depends(require_guardian_for_patient),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(ConsentRecord)
        .filter(ConsentRecord.patient_id == patient_id)
        .order_by(ConsentRecord.field_name)
        .all()
    )
    return [
        {
            "id": row.id,
            "field_name": row.field_name,
            "consent_value": row.consent_value,
            "tier": row.tier,
            "expiry_minutes": row.expiry_minutes,
            "updated_at": row.updated_at.isoformat(),
            "expires_at": (row.updated_at + timedelta(minutes=row.expiry_minutes)).isoformat(),
            "expired": token_is_expired(row.updated_at + timedelta(minutes=row.expiry_minutes)),
        }
        for row in rows
    ]


@app.post("/patients/{patient_id}/consents")
def save_patient_consents(
    patient_id: int,
    payload: ConsentRequest,
    _: dict = Depends(require_guardian_for_patient),
    db: Session = Depends(get_db),
):
    if len({item.field_name for item in payload.consents}) != len(payload.consents):
        raise HTTPException(status_code=422, detail="A consent field may only be included once")
    receipt_items = []
    for item in payload.consents:
        existing = (
            db.query(ConsentRecord)
            .filter(
                ConsentRecord.patient_id == patient_id,
                ConsentRecord.field_name == item.field_name,
            )
            .first()
        )
        if existing is None:
            existing = ConsentRecord(patient_id=patient_id, field_name=item.field_name)
            db.add(existing)
        existing.consent_value = item.consent_value
        existing.tier = item.tier
        existing.expiry_minutes = item.expiry_minutes
        existing.updated_at = utcnow()
        receipt_items.append(
            {
                "field_name": item.field_name,
                "consent_value": item.consent_value,
                "tier": item.tier,
                "expiry_minutes": item.expiry_minutes,
            }
        )
    receipt_time = utcnow()
    receipt = ConsentReceipt(
        patient_id=patient_id,
        receipt=json.dumps(receipt_items, sort_keys=True),
        created_at=receipt_time,
    )
    db.add(receipt)
    db.commit()
    db.refresh(receipt)
    return {
        "patient_id": patient_id,
        "updated": len(payload.consents),
        "receipt_id": receipt.id,
        "receipt_created_at": receipt.created_at.isoformat(),
        "consents": receipt_items,
    }


@app.get("/patients/{patient_id}/consent-receipts")
def get_consent_receipts(
    patient_id: int,
    _: dict = Depends(require_guardian_for_patient),
    db: Session = Depends(get_db),
):
    receipts = (
        db.query(ConsentReceipt)
        .filter(ConsentReceipt.patient_id == patient_id)
        .order_by(ConsentReceipt.id.desc())
        .all()
    )
    return [
        {
            "id": receipt.id,
            "consents": json.loads(receipt.receipt),
            "created_at": receipt.created_at.isoformat(),
        }
        for receipt in receipts
    ]


@app.post("/patients/{patient_id}/tokens", status_code=201)
def create_patient_token(
    patient_id: int,
    payload: TokenCreate,
    _: dict = Depends(require_guardian_for_patient),
    db: Session = Depends(get_db),
):
    raw_token = secrets.token_urlsafe(32)
    row = AccessToken(
        patient_id=patient_id,
        token_hash=hash_value(raw_token),
        expires_at=utcnow() + timedelta(hours=payload.expiry_hours),
        single_use=payload.single_use,
        is_active=True,
        revoked=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "patient_id": patient_id,
        "token": raw_token,
        "expires_at": row.expires_at.isoformat(),
        "single_use": row.single_use,
        "note": "The QR secret is shown only once. Store it securely.",
    }


@app.get("/patients/{patient_id}/tokens")
def get_patient_tokens(
    patient_id: int,
    _: dict = Depends(require_guardian_for_patient),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(AccessToken)
        .filter(AccessToken.patient_id == patient_id)
        .order_by(AccessToken.id.desc())
        .all()
    )
    return [
        {
            "id": row.id,
            "is_active": row.is_active and not row.revoked and not token_is_expired(row.expires_at),
            "expires_at": row.expires_at.isoformat(),
            "revoked": row.revoked,
            "single_use": row.single_use,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@app.delete("/patients/{patient_id}/tokens/{token_id}")
def revoke_patient_token(
    patient_id: int,
    token_id: int,
    _: dict = Depends(require_guardian_for_patient),
    db: Session = Depends(get_db),
):
    row = (
        db.query(AccessToken)
        .filter(AccessToken.patient_id == patient_id, AccessToken.id == token_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Token not found")
    row.revoked = True
    row.is_active = False
    db.commit()
    return {"patient_id": patient_id, "token_id": token_id, "revoked": True}


@app.post("/patients/{patient_id}/revoke-token")
def revoke_patient_token_by_secret(
    patient_id: int,
    payload: TokenRevoke,
    _: dict = Depends(require_guardian_for_patient),
    db: Session = Depends(get_db),
):
    row = (
        db.query(AccessToken)
        .filter(
            AccessToken.patient_id == patient_id,
            AccessToken.token_hash == hash_value(payload.token),
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Token not found")
    row.revoked = True
    row.is_active = False
    db.commit()
    return {"patient_id": patient_id, "revoked": True}


@app.post("/tokens/validate")
def validate_token(
    payload: TokenLookup,
    _: dict = Depends(require_role("responder")),
    db: Session = Depends(get_db),
):
    row = lookup_access_token(db, payload.token)
    if row is None:
        raise HTTPException(status_code=404, detail="Token not found")
    if not row.is_active or row.revoked or token_is_expired(row.expires_at):
        raise HTTPException(status_code=403, detail="Token is expired or revoked")
    return {"valid": True, "expires_at": row.expires_at.isoformat()}


@app.post("/access/scan")
def access_scan(
    payload: EmergencyAccessRequest,
    claims: dict = Depends(require_role("responder")),
    db: Session = Depends(get_db),
):
    row = lookup_access_token(db, payload.token)
    if row is None:
        raise HTTPException(status_code=404, detail="Token not found")
    if not row.is_active or row.revoked or token_is_expired(row.expires_at):
        raise HTTPException(status_code=403, detail="Token is expired or revoked")
    patient = _patient_or_404(db, row.patient_id)
    return get_patient_record_view(
        db=db,
        patient=patient,
        access_token=row,
        responder_name=claims["sub"],
        responder_organization=claims.get("organization", "Responder"),
        break_glass=payload.break_glass,
        reason=payload.reason,
    )


@app.get("/patients/{patient_id}/access-log")
def access_log(
    patient_id: int,
    _: dict = Depends(require_guardian_for_patient),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(AccessLog)
        .filter(AccessLog.patient_id == patient_id)
        .order_by(AccessLog.id.desc())
        .all()
    )
    return {
        "verified": verify_audit_chain(rows),
        "entries": [
            {
                "id": row.id,
                "responder_name": row.responder_name,
                "access_type": row.access_type,
                "fields_shared": row.fields_shared,
                "previous_hash": row.previous_hash,
                "current_hash": row.current_hash,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ],
    }


@app.get("/patients/{patient_id}/notifications")
def get_notifications(
    patient_id: int,
    _: dict = Depends(require_guardian_for_patient),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Notification)
        .filter(Notification.patient_id == patient_id)
        .order_by(Notification.id.desc())
        .all()
    )
    return [
        {
            "id": row.id,
            "channel": row.channel,
            "message": row.message,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@app.get("/patients/{patient_id}/trusted-contacts")
def get_trusted_contacts(
    patient_id: int,
    _: dict = Depends(require_guardian_for_patient),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(TrustedContact)
        .filter(TrustedContact.patient_id == patient_id)
        .order_by(TrustedContact.is_primary.desc(), TrustedContact.id)
        .all()
    )
    return [
        {
            "id": row.id,
            "name": row.name,
            "relationship": row.relationship,
            "phone": row.phone,
            "is_primary": row.is_primary,
        }
        for row in rows
    ]


@app.get("/patients/{patient_id}/conditions")
def get_patient_conditions(
    patient_id: int,
    _: dict = Depends(require_guardian_for_patient),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(PatientCondition)
        .filter(PatientCondition.patient_id == patient_id)
        .order_by(PatientCondition.occurred_at.desc(), PatientCondition.id.desc())
        .all()
    )
    return [
        {
            "id": row.id,
            "name": row.name,
            "body_region": row.body_region,
            "condition_type": row.condition_type,
            "notes": row.notes,
            "source_name": row.source_name,
            "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
            "is_active": row.is_active,
        }
        for row in rows
    ]


@app.get("/patients/{patient_id}/admission-prefill")
def get_admission_prefill(
    patient_id: int,
    _: dict = Depends(require_guardian_for_patient),
    db: Session = Depends(get_db),
):
    patient = _patient_or_404(db, patient_id)
    consented = {
        field
        for field in ("blood_group", "allergies", "medications", "conditions", "contacts", "insurer")
        if _active_consent(db, patient_id, field)
    }
    result = {
        "patient_id": patient.id,
        "patient_name": patient.name,
        "age": patient.age,
        "prefilled_fields": ["patient_name", "age"],
    }
    source_records = (
        db.query(SourceRecord)
        .filter(SourceRecord.patient_id == patient_id)
        .all()
    )
    if "blood_group" in consented:
        result["blood_group"] = patient.blood_group
        result["prefilled_fields"].append("blood_group")
    if "allergies" in consented:
        result["allergies"] = list(
            dict.fromkeys(
                allergy
                for source in source_records
                for allergy in json.loads(source.payload).get("allergies", [])
            )
        )
        result["prefilled_fields"].append("allergies")
    if "medications" in consented:
        result["medications"] = [
            medication
            for source in source_records
            for medication in json.loads(source.payload).get("medications", [])
        ]
        result["prefilled_fields"].append("medications")
    if "conditions" in consented:
        result["conditions"] = [
            condition
            for source in source_records
            for condition in json.loads(source.payload).get("conditions", [])
        ]
        result["prefilled_fields"].append("conditions")
    if "contacts" in consented:
        result["emergency_contacts"] = [
            {
                "name": contact.name,
                "relationship": contact.relationship,
                "phone": contact.phone,
            }
            for contact in db.query(TrustedContact)
            .filter(TrustedContact.patient_id == patient_id)
            .all()
        ]
        result["prefilled_fields"].append("emergency_contacts")
    if "insurer" in consented:
        result["insurer_policy"] = patient.insurer_policy
        result["prefilled_fields"].append("insurer_policy")
    return result


@app.get("/patients/{patient_id}/consent-review")
def get_consent_review_status(
    patient_id: int,
    _: dict = Depends(require_guardian_for_patient),
    db: Session = Depends(get_db),
):
    _patient_or_404(db, patient_id)
    records = db.query(ConsentRecord).filter(ConsentRecord.patient_id == patient_id).all()
    review_dates = [row.updated_at for row in records]
    if review_dates:
        from datetime import timezone

        review_dates = [
            value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
            for value in review_dates
        ]
        last_reviewed_at = min(review_dates)
        review_due = any(value + timedelta(days=183) <= utcnow() for value in review_dates)
    else:
        last_reviewed_at = None
        review_due = True
    return {
        "patient_id": patient_id,
        "review_due": review_due,
        "last_reviewed_at": last_reviewed_at.isoformat() if last_reviewed_at else None,
        "review_interval_days": 183,
    }


@app.get("/patients/{patient_id}/admissions")
def get_patient_admissions(
    patient_id: int,
    _: dict = Depends(require_guardian_for_patient),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(AdmissionRecord)
        .filter(AdmissionRecord.patient_id == patient_id)
        .order_by(AdmissionRecord.created_at.desc(), AdmissionRecord.id.desc())
        .all()
    )
    return [
        {
            "id": row.id,
            "hospital_name": row.hospital_name,
            "reason": row.reason,
            "status": row.status,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@app.post("/patients/{patient_id}/conditions", status_code=201)
def add_patient_condition(
    patient_id: int,
    payload: PatientConditionCreate,
    _: dict = Depends(require_guardian_for_patient),
    db: Session = Depends(get_db),
):
    row = PatientCondition(patient_id=patient_id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "name": row.name,
        "body_region": row.body_region,
        "condition_type": row.condition_type,
        "source_name": row.source_name,
    }


@app.post("/admission", status_code=201)
def create_admission(
    payload: AdmissionCreate,
    claims: dict = Depends(authenticated_claims),
    db: Session = Depends(get_db),
):
    patient = _patient_or_404(db, payload.patient_id)
    if claims.get("role") == "guardian":
        if claims.get("sub") not in {patient.guardian_phone, patient.emergency_contact_phone}:
            raise HTTPException(status_code=403, detail="You are not a trusted guardian for this patient")
    elif claims.get("role") != "responder":
        raise HTTPException(status_code=403, detail="Guardian or responder access is required")
    if payload.insurer_notice and not _active_consent(db, patient.id, "insurer"):
        raise HTTPException(status_code=403, detail="Current insurer-notice consent is required")

    admission = AdmissionRecord(
        patient_id=patient.id,
        hospital_name=payload.hospital_name.strip(),
        reason=payload.reason.strip(),
        status="admitted",
    )
    db.add(admission)
    db.flush()
    db.add(
        Notification(
            patient_id=patient.id,
            channel="family",
            message=f"Admission recorded at {admission.hospital_name}.",
        )
    )
    channels = ["family"]
    if payload.insurer_notice:
        db.add(
            Notification(
                patient_id=patient.id,
                channel="insurer",
                message=(
                    f"Simulated policy {patient.insurer_policy}: admission event at "
                    f"{admission.hospital_name}, {utcnow().isoformat()}. No medical details included."
                ),
            )
        )
        channels.append("insurer")
    db.commit()
    db.refresh(admission)
    return {
        "id": admission.id,
        "status": admission.status,
        "patient_id": patient.id,
        "notifications_created": channels,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
