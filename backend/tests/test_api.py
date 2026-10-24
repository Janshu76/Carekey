from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models import (
    AccessToken,
    ConsentRecord,
    Patient,
    PatientCondition,
    SourceRecord,
    TrustedContact,
    utcnow,
)
from backend.app.seed import DEMO_PATIENTS, seed_demo_data
from backend.app.services.security import hash_value

DEMO_SECRET = "carelink-1-demo-token"


@pytest.fixture
def client():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    db = TestingSessionLocal()
    patient = Patient(
        name="Ramesh Sharma",
        age=72,
        blood_group="B+",
        primary_condition="Type 2 diabetes",
        emergency_contact_name="Neha Sharma",
        emergency_contact_phone="+91 91000 00001",
        guardian_name="Neha Sharma",
        guardian_phone="+91 90000 00001",
        insurer_policy="DEMO-CARE-0001",
    )
    db.add(patient)
    db.flush()
    for field, value, tier in (
        ("blood_group", True, "emergency"),
        ("allergies", True, "emergency"),
        ("medications", True, "standard"),
        ("conditions", True, "standard"),
        ("contacts", True, "standard"),
        ("injuries", True, "standard"),
        ("insurer", False, "sensitive"),
    ):
        db.add(
            ConsentRecord(
                patient_id=patient.id,
                field_name=field,
                consent_value=value,
                tier=tier,
                expiry_minutes=180,
            )
        )
    db.add_all(
        [
            SourceRecord(
                patient_id=patient.id,
                source_name="Hospital A",
                record_type="allergies_and_medicines",
                payload='{"allergies":["Penicillin"],"medications":[{"name":"Metformin","dose":"500 mg twice daily"}]}',
            ),
            SourceRecord(
                patient_id=patient.id,
                source_name="Clinic B",
                record_type="conditions_blood_group_and_contacts",
                payload='{"conditions":["Type 2 diabetes"],"blood_group":"B+","medications":[{"name":"Metformin","dose":"850 mg twice daily"}]}',
            ),
            PatientCondition(
                patient_id=patient.id,
                name="Previous fall",
                body_region="left_knee",
                condition_type="injury",
                source_name="Hospital A",
                occurred_at=utcnow() - timedelta(days=30),
                is_active=False,
            ),
            TrustedContact(
                patient_id=patient.id,
                name="Neha Sharma",
                relationship="Daughter",
                phone="+91 91000 00001",
                is_primary=True,
            ),
            AccessToken(
                patient_id=patient.id,
                token_hash=hash_value(DEMO_SECRET),
                expires_at=utcnow() + timedelta(hours=4),
                is_active=True,
                revoked=False,
            ),
        ]
    )
    db.commit()
    db.close()

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    app.state.test_session_factory = TestingSessionLocal
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    del app.state.test_session_factory
    test_engine.dispose()


def responder_headers(client: TestClient, name: str = "Demo responder") -> dict[str, str]:
    response = client.post(
        "/auth/responder/login",
        json={"name": name, "organization": "Demo ambulance"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def guardian_headers(client: TestClient, phone: str = "+91 90000 00001") -> dict[str, str]:
    request = client.post("/auth/otp/request", json={"phone": phone})
    assert request.status_code == 200
    challenge = request.json()
    verified = client.post(
        "/auth/otp/verify",
        json={"challenge_id": challenge["challenge_id"], "code": challenge["demo_code"]},
    )
    assert verified.status_code == 200
    return {"Authorization": f"Bearer {verified.json()['access_token']}"}


def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_demo_seed_creates_ten_synthetic_patients_idempotently(client: TestClient):
    assert len(DEMO_PATIENTS) == 10
    db = app.state.test_session_factory()
    try:
        seed_demo_data(db)
        assert db.query(Patient).count() == 10
        seed_demo_data(db)
        assert db.query(Patient).count() == 10
        assert db.query(AccessToken).count() == 10
        assert db.query(TrustedContact).count() >= 30
    finally:
        db.close()


def test_guardian_otp_auth_and_patient_scope(client: TestClient):
    response = client.get("/patients")
    assert response.status_code == 401

    headers = guardian_headers(client)
    patients = client.get("/patients", headers=headers)
    assert patients.status_code == 200
    assert [patient["name"] for patient in patients.json()] == ["Ramesh Sharma"]

    other_guardian = guardian_headers(client, "+91 91000 00001")
    assert client.get("/patients/1", headers=other_guardian).status_code == 200


def test_invalid_otp_does_not_issue_a_session(client: TestClient):
    challenge = client.post("/auth/otp/request", json={"phone": "+91 90000 00001"}).json()
    wrong_code = "000000" if challenge["demo_code"] != "000000" else "000001"
    wrong = client.post(
        "/auth/otp/verify",
        json={"challenge_id": challenge["challenge_id"], "code": wrong_code},
    )
    assert wrong.status_code == 400


def test_scan_requires_responder_and_merges_both_sources(client: TestClient):
    assert client.post("/access/scan", json={"token": DEMO_SECRET}).status_code == 401
    headers = responder_headers(client)
    response = client.post(
        "/access/scan",
        json={"token": DEMO_SECRET},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["patient_id"] == 1
    assert result["blood_group"] == "B+"
    assert result["allergies"] == ["Penicillin"]
    assert result["conflict_flag"] is True
    assert result["fhir"]["resourceType"] == "Bundle"
    assert result["fhir"]["type"] == "collection"
    assert any(
        entry["resource"]["resourceType"] == "MedicationStatement"
        for entry in result["fhir"]["entry"]
    )
    assert {entry["source"] for entry in result["conflicts"][0]["values"]} == {
        "Hospital A",
        "Clinic B",
    }
    assert set(result["source_labels"]) == {"Clinic B", "Guardian profile", "Hospital A"}


def test_scan_redacts_fields_without_active_consent(client: TestClient):
    guardian = guardian_headers(client)
    update = client.post(
        "/patients/1/consents",
        headers=guardian,
        json={
            "consents": [
                {
                    "field_name": "medications",
                    "consent_value": False,
                    "tier": "standard",
                    "expiry_minutes": 120,
                }
            ]
        },
    )
    assert update.status_code == 200
    assert update.json()["receipt_id"]
    receipts = client.get("/patients/1/consent-receipts", headers=guardian).json()
    assert receipts[0]["consents"][0]["field_name"] == "medications"
    assert receipts[0]["consents"][0]["consent_value"] is False
    result = client.post(
        "/access/scan",
        json={"token": DEMO_SECRET},
        headers=responder_headers(client),
    ).json()
    assert result["medications"] == []
    assert result["blood_group"] == "B+"


def test_break_glass_is_reasoned_and_audited(client: TestClient):
    guardian = guardian_headers(client)
    assert client.post(
        "/patients/1/consents",
        headers=guardian,
        json={
            "consents": [
                {
                    "field_name": "allergies",
                    "consent_value": False,
                    "tier": "emergency",
                    "expiry_minutes": 120,
                }
            ]
        },
    ).status_code == 200

    headers = responder_headers(client, "Break-glass responder")
    no_reason = client.post(
        "/access/scan",
        json={"token": DEMO_SECRET, "break_glass": True},
        headers=headers,
    )
    assert no_reason.status_code == 422

    result = client.post(
        "/access/scan",
        json={
            "token": DEMO_SECRET,
            "break_glass": True,
            "reason": "Patient unable to communicate",
        },
        headers=headers,
    )
    assert result.status_code == 200
    assert result.json()["access_type"] == "break_glass"
    assert result.json()["allergies"] == ["Penicillin"]


def test_single_use_token_and_revocation_block_later_scans(client: TestClient):
    guardian = guardian_headers(client)
    token_response = client.post(
        "/patients/1/tokens",
        headers=guardian,
        json={"expiry_hours": 4, "single_use": True},
    )
    assert token_response.status_code == 201
    token = token_response.json()["token"]

    responder = responder_headers(client)
    assert client.post(
        "/access/scan", json={"token": token}, headers=responder
    ).status_code == 200
    assert client.post(
        "/access/scan", json={"token": token}, headers=responder
    ).status_code == 403

    listed_tokens = client.get("/patients/1/tokens", headers=guardian).json()
    assert token not in str(listed_tokens)

    assert client.post(
        "/patients/1/revoke-token",
        headers=guardian,
        json={"token": DEMO_SECRET},
    ).status_code == 200
    assert client.post(
        "/access/scan",
        json={"token": DEMO_SECRET},
        headers=responder,
    ).status_code == 403


def test_token_secret_is_only_stored_as_a_digest(client: TestClient):
    assert client.post(
        "/access/scan",
        json={"token": DEMO_SECRET},
        headers=responder_headers(client),
    ).status_code == 200
    # Access logs expose no QR secret, and token listings never return a secret.
    guardian = guardian_headers(client)
    assert DEMO_SECRET not in str(
        client.get("/patients/1/access-log", headers=guardian).json()
    )
    assert DEMO_SECRET not in str(client.get("/patients/1/tokens", headers=guardian).json())
    db = app.state.test_session_factory()
    try:
        saved = db.query(AccessToken).first()
        assert saved.token_hash == hash_value(DEMO_SECRET)
        assert saved.token_hash != DEMO_SECRET
    finally:
        db.close()


def test_audit_chain_and_family_alert_are_written_for_scans(client: TestClient):
    responder = responder_headers(client)
    for _ in range(2):
        assert client.post(
            "/access/scan",
            json={"token": DEMO_SECRET},
            headers=responder,
        ).status_code == 200
    guardian = guardian_headers(client)
    audit = client.get("/patients/1/access-log", headers=guardian).json()
    assert audit["verified"] is True
    entries = sorted(audit["entries"], key=lambda entry: entry["id"])
    assert entries[1]["previous_hash"] == entries[0]["current_hash"]
    notifications = client.get("/patients/1/notifications", headers=guardian).json()
    assert sum(item["channel"] == "family" for item in notifications) == 2


def test_admission_requires_insurer_consent_and_sends_minimal_notice(client: TestClient):
    headers = guardian_headers(client)
    admission_body = {
        "patient_id": 1,
        "hospital_name": "Sundaram General",
        "reason": "Medical review",
        "insurer_notice": True,
    }
    assert client.post("/admission", json=admission_body, headers=headers).status_code == 403

    updated = client.post(
        "/patients/1/consents",
        headers=headers,
        json={
            "consents": [
                {
                    "field_name": "insurer",
                    "consent_value": True,
                    "tier": "sensitive",
                    "expiry_minutes": 120,
                }
            ]
        },
    )
    assert updated.status_code == 200
    created = client.post("/admission", json=admission_body, headers=headers)
    assert created.status_code == 201
    assert created.json()["status"] == "admitted"
    assert set(created.json()["notifications_created"]) == {"family", "insurer"}
    admissions = client.get("/patients/1/admissions", headers=headers).json()
    assert admissions[0]["status"] == "admitted"
    notices = client.get("/patients/1/notifications", headers=headers).json()
    insurer_notice = next(item["message"] for item in notices if item["channel"] == "insurer")
    assert "Medical review" not in insurer_notice
    assert "DEMO-CARE-0001" in insurer_notice


def test_condition_endpoint_supports_body_regions(client: TestClient):
    guardian = guardian_headers(client)
    created = client.post(
        "/patients/1/conditions",
        headers=guardian,
        json={
            "name": "Previous fracture",
            "body_region": "left_wrist",
            "condition_type": "injury",
            "notes": "Healed; synthetic demo record",
            "source_name": "Guardian entry",
            "is_active": False,
        },
    )
    assert created.status_code == 201
    conditions = client.get("/patients/1/conditions", headers=guardian).json()
    assert any(
        item["body_region"] == "left_wrist" and item["condition_type"] == "injury"
        for item in conditions
    )


def test_admission_prefill_includes_only_consented_medical_fields(client: TestClient):
    headers = guardian_headers(client)
    prefill = client.get("/patients/1/admission-prefill", headers=headers)
    assert prefill.status_code == 200
    data = prefill.json()
    assert data["patient_name"] == "Ramesh Sharma"
    assert data["blood_group"] == "B+"
    assert data["allergies"] == ["Penicillin"]
    assert "insurer_policy" not in data

    assert client.post(
        "/patients/1/consents",
        headers=headers,
        json={
            "consents": [
                {
                    "field_name": "insurer",
                    "consent_value": True,
                    "tier": "sensitive",
                    "expiry_minutes": 120,
                }
            ]
        },
    ).status_code == 200
    prefill_with_insurer = client.get("/patients/1/admission-prefill", headers=headers)
    assert prefill_with_insurer.json()["insurer_policy"] == "DEMO-CARE-0001"


def test_consent_review_status_is_exposed_to_guardian(client: TestClient):
    response = client.get(
        "/patients/1/consent-review",
        headers=guardian_headers(client),
    )
    assert response.status_code == 200
    assert response.json()["review_due"] is False
    assert response.json()["review_interval_days"] == 183


def test_consent_review_is_due_when_any_field_is_stale(client: TestClient):
    db = app.state.test_session_factory()
    try:
        consent = db.query(ConsentRecord).filter(ConsentRecord.field_name == "blood_group").first()
        consent.updated_at = utcnow() - timedelta(days=184)
        db.commit()
    finally:
        db.close()
    response = client.get(
        "/patients/1/consent-review",
        headers=guardian_headers(client),
    )
    assert response.status_code == 200
    assert response.json()["review_due"] is True


def test_expired_access_token_is_rejected(client: TestClient):
    guardian = guardian_headers(client)
    created = client.post(
        "/patients/1/tokens",
        headers=guardian,
        json={"expiry_hours": 1, "single_use": False},
    )
    token = created.json()["token"]
    db = app.state.test_session_factory()
    try:
        saved = db.query(AccessToken).filter(AccessToken.token_hash == hash_value(token)).first()
        saved.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    finally:
        db.close()
    response = client.post(
        "/access/scan",
        json={"token": token},
        headers=responder_headers(client),
    )
    assert response.status_code == 403


def test_unsupported_consent_fields_are_rejected(client: TestClient):
    response = client.post(
        "/patients/1/consents",
        headers=guardian_headers(client),
        json={
            "consents": [
                {
                    "field_name": "everything",
                    "consent_value": True,
                    "tier": "standard",
                    "expiry_minutes": 120,
                }
            ]
        },
    )
    assert response.status_code == 422
