from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import AccessToken, AuthChallenge, Patient, utcnow

bearer_scheme = HTTPBearer(auto_error=False)
TOKEN_TTL_MINUTES = 60
OTP_TTL_MINUTES = 5
OTP_MAX_ATTEMPTS = 5


def hash_value(value: str) -> str:
    return hmac.new(settings.secret_key.encode(), value.encode(), hashlib.sha256).hexdigest()


def token_is_expired(expires_at: datetime) -> bool:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= utcnow()


def create_access_token(claims: dict[str, Any], ttl: timedelta = timedelta(minutes=TOKEN_TTL_MINUTES)) -> str:
    now = utcnow()
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {**claims, "iat": int(now.timestamp()), "exp": int((now + ttl).timestamp())}

    def encode_json(value: dict[str, Any]) -> str:
        raw = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    signing_input = f"{encode_json(header)}.{encode_json(payload)}"
    signature = hmac.new(settings.secret_key.encode(), signing_input.encode(), hashlib.sha256).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
    return f"{signing_input}.{encoded_signature}"


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        header_segment, payload_segment, signature_segment = token.split(".")
        signing_input = f"{header_segment}.{payload_segment}"
        expected = hmac.new(settings.secret_key.encode(), signing_input.encode(), hashlib.sha256).digest()
        supplied = base64.urlsafe_b64decode(signature_segment + "=" * (-len(signature_segment) % 4))
        if not hmac.compare_digest(expected, supplied):
            raise ValueError("Invalid signature")

        header_bytes = base64.urlsafe_b64decode(header_segment + "=" * (-len(header_segment) % 4))
        header = json.loads(header_bytes)
        if not isinstance(header, dict) or header.get("alg") != "HS256" or header.get("typ") != "JWT":
            raise ValueError("Invalid token header")
        payload_bytes = base64.urlsafe_b64decode(payload_segment + "=" * (-len(payload_segment) % 4))
        payload = json.loads(payload_bytes)
        if not isinstance(payload, dict):
            raise ValueError("Invalid token payload")
        if payload.get("exp", 0) <= int(utcnow().timestamp()):
            raise ValueError("Expired token")
        if not isinstance(payload.get("sub"), str) or not isinstance(payload.get("role"), str):
            raise ValueError("Invalid claims")
        return payload
    except (ValueError, TypeError, AttributeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired access token") from exc


def authenticated_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Bearer authentication is required")
    return decode_access_token(credentials.credentials)


def require_role(role: str):
    def dependency(claims: dict[str, Any] = Depends(authenticated_claims)) -> dict[str, Any]:
        if claims.get("role") != role:
            raise HTTPException(status_code=403, detail=f"{role.capitalize()} access is required")
        return claims

    return dependency


def require_guardian_for_patient(
    patient_id: int,
    claims: dict[str, Any] = Depends(require_role("guardian")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    phone = claims["sub"]
    if phone not in {patient.guardian_phone, patient.emergency_contact_phone}:
        raise HTTPException(status_code=403, detail="You are not a trusted guardian for this patient")
    return claims


def issue_otp(db: Session, phone: str) -> tuple[AuthChallenge, str]:
    code = f"{secrets.randbelow(1_000_000):06d}"
    challenge = AuthChallenge(
        phone=phone.strip(),
        code_hash=hash_value(code),
        expires_at=utcnow() + timedelta(minutes=OTP_TTL_MINUTES),
    )
    db.add(challenge)
    db.commit()
    db.refresh(challenge)
    return challenge, code


def verify_otp(db: Session, challenge_id: int, code: str) -> str:
    challenge = db.query(AuthChallenge).filter(AuthChallenge.id == challenge_id).first()
    if challenge is None or challenge.consumed or token_is_expired(challenge.expires_at):
        raise HTTPException(status_code=400, detail="OTP challenge is invalid or expired")
    if challenge.attempts >= OTP_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="OTP attempt limit reached")

    challenge.attempts += 1
    if not hmac.compare_digest(challenge.code_hash, hash_value(code)):
        db.commit()
        raise HTTPException(status_code=400, detail="Incorrect OTP")

    challenge.consumed = True
    db.commit()
    return challenge.phone


def lookup_access_token(db: Session, raw_token: str) -> AccessToken | None:
    return db.query(AccessToken).filter(AccessToken.token_hash == hash_value(raw_token)).first()
