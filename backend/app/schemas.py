from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


ConsentTier = Literal["emergency", "standard", "sensitive"]
CONSENT_FIELDS = {
    "blood_group",
    "allergies",
    "medications",
    "conditions",
    "contacts",
    "injuries",
    "insurer",
}


class OTPRequest(BaseModel):
    phone: str = Field(min_length=7, max_length=50)


class OTPVerify(BaseModel):
    challenge_id: int
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class ResponderLogin(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    organization: str = Field(min_length=1, max_length=160)


class ConsentItem(BaseModel):
    field_name: str
    consent_value: bool
    tier: ConsentTier = "standard"
    expiry_minutes: int = Field(default=120, ge=1, le=525600)

    @field_validator("field_name")
    @classmethod
    def validate_field_name(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in CONSENT_FIELDS:
            raise ValueError("Unsupported consent field")
        return normalized


class ConsentRequest(BaseModel):
    consents: list[ConsentItem] = Field(min_length=1, max_length=20)


class TokenCreate(BaseModel):
    expiry_hours: int = Field(default=8, ge=1, le=24)
    single_use: bool = False


class TokenRevoke(BaseModel):
    token: str = Field(min_length=16, max_length=200)


class TokenLookup(BaseModel):
    token: str = Field(min_length=16, max_length=200)


class EmergencyAccessRequest(TokenLookup):
    break_glass: bool = False
    reason: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def require_break_glass_reason(self):
        if self.break_glass and not (self.reason and self.reason.strip()):
            raise ValueError("A reason is required for break-glass access")
        return self


class AdmissionCreate(BaseModel):
    patient_id: int = Field(gt=0)
    hospital_name: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=255)
    insurer_notice: bool = False


class PatientConditionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    body_region: str = Field(min_length=1, max_length=80)
    condition_type: Literal["condition", "injury", "surgery", "device"] = "condition"
    notes: str | None = Field(default=None, max_length=1000)
    source_name: str = Field(default="Guardian entry", min_length=1, max_length=80)
    occurred_at: datetime | None = None
    is_active: bool = True
