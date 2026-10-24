from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import (
    AccessLog,
    AccessToken,
    ConsentRecord,
    Notification,
    Patient,
    PatientCondition,
    SourceRecord,
    TrustedContact,
    utcnow,
)
from .security import token_is_expired

BREAK_GLASS_FIELDS = {"blood_group", "allergies"}


def _record_is_current(record: ConsentRecord) -> bool:
    updated_at = record.updated_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return updated_at + timedelta(minutes=record.expiry_minutes) > utcnow()


def get_consent_map(db: Session, patient_id: int) -> dict[str, ConsentRecord]:
    records = db.query(ConsentRecord).filter(ConsentRecord.patient_id == patient_id).all()
    return {record.field_name: record for record in records}


def _medications(sources: list[SourceRecord]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_name: dict[str, list[dict[str, str]]] = {}
    for source in sources:
        payload = json.loads(source.payload)
        for item in payload.get("medications", []):
            if isinstance(item, str):
                medication = {"name": item, "dose": "Not specified"}
            else:
                medication = {
                    "name": str(item.get("name", "Unknown medication")),
                    "dose": str(item.get("dose", "Not specified")),
                }
            by_name.setdefault(medication["name"].casefold(), []).append(
                {**medication, "source": source.source_name}
            )

    merged: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for entries in by_name.values():
        doses = {entry["dose"].casefold() for entry in entries}
        item = {
            "name": entries[0]["name"],
            "dose": entries[0]["dose"],
            "source": entries[0]["source"],
            "conflict": len(doses) > 1,
            "source_records": entries,
        }
        merged.append(item)
        if item["conflict"]:
            conflicts.append(
                {
                    "field": item["name"],
                    "values": [{"value": entry["dose"], "source": entry["source"]} for entry in entries],
                }
            )
    return merged, conflicts


def _fhir_bundle(patient: Patient, view: dict[str, Any]) -> dict[str, Any]:
    patient_id = str(patient.id)
    entries: list[dict[str, Any]] = [
        {
            "resource": {
                "resourceType": "Patient",
                "id": patient_id,
                "name": [{"text": patient.name}],
            }
        }
    ]
    if "blood_group" in view:
        entries.append(
            {
                "resource": {
                    "resourceType": "Observation",
                    "status": "final",
                    "code": {"text": "Blood group"},
                    "subject": {"reference": f"Patient/{patient_id}"},
                    "valueString": view["blood_group"],
                    "performer": [{"display": "Clinic B"}],
                }
            }
        )
    for allergy in view.get("allergies", []):
        entries.append(
            {
                "resource": {
                    "resourceType": "AllergyIntolerance",
                    "clinicalStatus": {"text": "active"},
                    "code": {"text": allergy},
                    "patient": {"reference": f"Patient/{patient_id}"},
                    "recorder": {"display": "Hospital A"},
                }
            }
        )
    for medication in view.get("medications", []):
        for source_record in medication["source_records"]:
            entries.append(
                {
                    "resource": {
                        "resourceType": "MedicationStatement",
                        "status": "active",
                        "medicationCodeableConcept": {"text": medication["name"]},
                        "subject": {"reference": f"Patient/{patient_id}"},
                        "dosage": [{"text": source_record["dose"]}],
                        "informationSource": {"display": source_record["source"]},
                    }
                }
            )
    for condition in view.get("conditions", []):
        entries.append(
            {
                "resource": {
                    "resourceType": "Condition",
                    "clinicalStatus": {"text": "active"},
                    "code": {"text": condition["name"]},
                    "subject": {"reference": f"Patient/{patient_id}"},
                    "bodySite": [{"text": condition.get("body_region", "unspecified")}],
                    "asserter": {"display": condition["source"]},
                }
            }
        )
    for injury in view.get("injuries", []):
        entries.append(
            {
                "resource": {
                    "resourceType": "Condition",
                    "clinicalStatus": {"text": "inactive"},
                    "code": {"text": injury["name"]},
                    "subject": {"reference": f"Patient/{patient_id}"},
                    "bodySite": [{"text": injury["body_region"]}],
                    "asserter": {"display": injury["source"]},
                }
            }
        )
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "timestamp": utcnow().isoformat(),
        "entry": entries,
    }


def get_patient_record_view(
    db: Session,
    patient: Patient,
    access_token: AccessToken,
    responder_name: str,
    responder_organization: str,
    break_glass: bool = False,
    reason: str | None = None,
) -> dict[str, Any]:
    if not access_token.is_active or access_token.revoked or token_is_expired(access_token.expires_at):
        raise HTTPException(status_code=403, detail="Access token is expired or revoked")

    consent_map = get_consent_map(db, patient.id)
    granted = {
        field
        for field, record in consent_map.items()
        if record.consent_value and _record_is_current(record) and record.tier != "sensitive"
    }
    if break_glass:
        granted.update(
            field
            for field, record in consent_map.items()
            if field in BREAK_GLASS_FIELDS and record.tier == "emergency"
        )

    sources = db.query(SourceRecord).filter(SourceRecord.patient_id == patient.id).all()
    record: dict[str, Any] = {
        "patient_id": patient.id,
        "patient_name": patient.name,
        "access_type": "break_glass" if break_glass else "standard",
        "medications": [],
        "allergies": [],
        "conditions": [],
        "injuries": [],
        "source_labels": [],
        "conflicts": [],
        "conflict_flag": False,
    }
    exposed_sources: set[str] = set()

    if "blood_group" in granted:
        record["blood_group"] = patient.blood_group
        exposed_sources.add("Clinic B")

    if "medications" in granted:
        medications, medication_conflicts = _medications(sources)
        record["medications"] = medications
        record["conflicts"].extend(medication_conflicts)
        if medications:
            exposed_sources.update(
                item["source"]
                for medication in medications
                for item in medication["source_records"]
            )

    if "allergies" in granted:
        for source in sources:
            payload = json.loads(source.payload)
            allergies = payload.get("allergies", [])
            if allergies:
                record["allergies"].extend(allergies)
                exposed_sources.add(source.source_name)
        record["allergies"] = list(dict.fromkeys(record["allergies"]))

    if "conditions" in granted:
        for source in sources:
            payload = json.loads(source.payload)
            if payload.get("conditions"):
                record["conditions"].extend(
                    {"name": condition, "source": source.source_name}
                    for condition in payload["conditions"]
                )
                exposed_sources.add(source.source_name)
        condition_rows = (
            db.query(PatientCondition)
            .filter(PatientCondition.patient_id == patient.id, PatientCondition.is_active.is_(True))
            .all()
        )
        record["conditions"].extend(
            {
                "name": condition.name,
                "source": condition.source_name,
                "body_region": condition.body_region,
                "condition_type": condition.condition_type,
            }
            for condition in condition_rows
        )
        exposed_sources.update(condition.source_name for condition in condition_rows)

    if "injuries" in granted:
        injury_rows = (
            db.query(PatientCondition)
            .filter(
                PatientCondition.patient_id == patient.id,
                PatientCondition.condition_type.in_({"injury", "surgery"}),
            )
            .all()
        )
        record["injuries"] = [
            {
                "name": injury.name,
                "body_region": injury.body_region,
                "condition_type": injury.condition_type,
                "occurred_at": injury.occurred_at.isoformat() if injury.occurred_at else None,
                "source": injury.source_name,
            }
            for injury in injury_rows
        ]
        exposed_sources.update(injury.source_name for injury in injury_rows)

    if "contacts" in granted:
        record["emergency_contacts"] = [
            {"name": contact.name, "relationship": contact.relationship, "phone": contact.phone}
            for contact in db.query(TrustedContact)
            .filter(TrustedContact.patient_id == patient.id)
            .all()
        ]
        if not record["emergency_contacts"] and patient.emergency_contact_name:
            record["emergency_contacts"] = [
                {
                    "name": patient.emergency_contact_name,
                    "relationship": "Emergency contact",
                    "phone": patient.emergency_contact_phone,
                }
            ]
        if record["emergency_contacts"]:
            exposed_sources.add("Guardian profile")

    record["source_labels"] = sorted(exposed_sources)
    record["conflict_flag"] = bool(record["conflicts"])
    previous = (
        db.query(AccessLog)
        .filter(AccessLog.patient_id == patient.id)
        .order_by(AccessLog.id.desc())
        .first()
    )
    fields_shared = sorted(
        field for field in granted if field in {"blood_group", "allergies", "medications", "conditions", "injuries", "contacts"}
    )
    log_time = utcnow()
    log_payload = json.dumps(
        {
            "patient_id": patient.id,
            "token_hash": access_token.token_hash,
            "responder": responder_name,
            "organization": responder_organization,
            "access_type": record["access_type"],
            "fields_shared": fields_shared,
            "reason": reason if break_glass else None,
            "created_at": log_time.isoformat(),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    previous_hash = previous.current_hash if previous else None
    current_hash = hashlib.sha256(f"{previous_hash or ''}{log_payload}".encode()).hexdigest()
    access_log = AccessLog(
        patient_id=patient.id,
        token=access_token.token_hash,
        responder_name=responder_name,
        access_type=record["access_type"],
        fields_shared=json.dumps(fields_shared),
        previous_hash=previous_hash,
        current_hash=current_hash,
        created_at=log_time,
    )
    db.add(access_log)
    db.add(
        Notification(
            patient_id=patient.id,
            channel="family",
            message=f"{'Break-glass ' if break_glass else ''}emergency record accessed by {responder_name} ({responder_organization}).",
            created_at=log_time,
        )
    )
    if access_token.single_use:
        access_token.is_active = False
    db.commit()
    db.refresh(access_log)

    record["access_expires_at"] = access_token.expires_at.isoformat()
    record["audit"] = {
        "id": access_log.id,
        "created_at": access_log.created_at.isoformat(),
        "previous_hash": access_log.previous_hash,
        "current_hash": access_log.current_hash,
    }
    record["fhir"] = _fhir_bundle(patient, record)
    return record


def verify_audit_chain(logs: list[AccessLog]) -> bool:
    expected_previous: str | None = None
    for log in sorted(logs, key=lambda entry: entry.id):
        if log.previous_hash != expected_previous or not log.current_hash:
            return False
        expected_previous = log.current_hash
    return True
