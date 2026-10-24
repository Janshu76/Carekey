from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    age = Column(Integer, nullable=False)
    blood_group = Column(String(20))
    primary_condition = Column(String(255))
    emergency_contact_name = Column(String(255))
    emergency_contact_phone = Column(String(50))
    guardian_name = Column(String(255))
    guardian_phone = Column(String(50))
    insurer_policy = Column(String(255))
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    source_records = relationship("SourceRecord", back_populates="patient", cascade="all, delete-orphan")
    consent_records = relationship("ConsentRecord", back_populates="patient", cascade="all, delete-orphan")
    consent_receipts = relationship("ConsentReceipt", cascade="all, delete-orphan")
    access_logs = relationship("AccessLog", back_populates="patient", cascade="all, delete-orphan")
    trusted_contacts = relationship("TrustedContact", cascade="all, delete-orphan")
    admissions = relationship("AdmissionRecord", cascade="all, delete-orphan")
    notifications = relationship("Notification", cascade="all, delete-orphan")
    conditions = relationship("PatientCondition", cascade="all, delete-orphan")


class SourceRecord(Base):
    __tablename__ = "source_records"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    source_name = Column(String(80), nullable=False)
    record_type = Column(String(80), nullable=False)
    payload = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    patient = relationship("Patient", back_populates="source_records")


class ConsentRecord(Base):
    __tablename__ = "consent_records"
    __table_args__ = (UniqueConstraint("patient_id", "field_name", name="uq_patient_consent_field"),)

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    field_name = Column(String(120), nullable=False)
    consent_value = Column(Boolean, nullable=False)
    tier = Column(String(50), default="standard", nullable=False)
    expiry_minutes = Column(Integer, default=60, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    patient = relationship("Patient", back_populates="consent_records")


class ConsentReceipt(Base):
    __tablename__ = "consent_receipts"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    receipt = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class AccessToken(Base):
    __tablename__ = "access_tokens"

    id = Column(Integer, primary_key=True, index=True)
    # The legacy "token" column stores a SHA-256 digest, never the QR secret itself.
    token_hash = Column("token", String(255), unique=True, index=True, nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), default=lambda: utcnow() + timedelta(hours=8), nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    single_use = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class AccessLog(Base):
    __tablename__ = "access_logs"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    token = Column(String(64), nullable=False)
    responder_name = Column(String(120), default="Unknown responder", nullable=False)
    access_type = Column(String(50), default="standard", nullable=False)
    fields_shared = Column(Text, default="[]", nullable=False)
    previous_hash = Column(String(64))
    current_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    patient = relationship("Patient", back_populates="access_logs")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    channel = Column(String(50), default="family", nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class TrustedContact(Base):
    __tablename__ = "trusted_contacts"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    relationship = Column(String(80), nullable=False)
    phone = Column(String(50), nullable=False)
    is_primary = Column(Boolean, default=False, nullable=False)


class AdmissionRecord(Base):
    __tablename__ = "admission_records"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    hospital_name = Column(String(120), nullable=False)
    reason = Column(String(255), nullable=False)
    status = Column(String(50), default="pending", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class PatientCondition(Base):
    __tablename__ = "patient_conditions"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    name = Column(String(160), nullable=False)
    body_region = Column(String(80), nullable=False)
    condition_type = Column(String(40), default="condition", nullable=False)
    notes = Column(Text)
    source_name = Column(String(80), nullable=False)
    occurred_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True, nullable=False)


class AuthChallenge(Base):
    __tablename__ = "auth_challenges"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(50), nullable=False, index=True)
    code_hash = Column(String(64), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    consumed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
