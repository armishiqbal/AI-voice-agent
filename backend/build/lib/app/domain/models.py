from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, EmailStr, Field, field_validator


class Intent(str, Enum):
    BUY = "buy"
    RENT = "rent"
    COMMERCIAL = "commercial"
    INVEST = "invest"
    SELL = "sell"
    BOOK = "book"
    RESCHEDULE = "reschedule"
    CANCEL = "cancel"
    UNKNOWN = "unknown"


class Property(BaseModel):
    id: str
    title: str
    city: str = Field(min_length=2, max_length=64)
    area: str
    purpose: Literal["sale", "rent", "commercial", "investment"]
    price_pkr: int = Field(gt=0)
    bedrooms: int = Field(ge=0, le=10)
    size_sqft: int = Field(gt=0)
    amenities: list[str] = Field(default_factory=list)
    investment_goals: list[str] = Field(default_factory=list)
    nearby_schools: list[str] = Field(default_factory=list)
    nearby_hospitals: list[str] = Field(default_factory=list)
    developer: str
    payment_plan: str
    available: bool
    assigned_employee: str
    source_version: str = "unspecified"
    source: str = "unverified"
    imported_at: datetime | None = None


class PropertyImport(BaseModel):
    properties: list[Property] = Field(min_length=1, max_length=5000)
    source: str = Field(min_length=3, max_length=200)


class PropertyQuery(BaseModel):
    city: str | None = None
    area: str | None = None
    purpose: str | None = None
    max_budget_pkr: int | None = Field(default=None, gt=0)
    bedrooms: int | None = Field(default=None, ge=0)
    amenities: list[str] = Field(default_factory=list, max_length=10)
    investment_goal: str | None = Field(default=None, max_length=100)
    target_size_sqft: int | None = Field(default=None, gt=0)


class ConversationTurn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    language: Literal["ur-Latn", "ur-Arab", "en", "hi", "ar", "pa", "bn"] = "ur-Latn"


class AgentDecision(BaseModel):
    kind: Literal[
        "answer", "ask_clarification", "recommend", "book", "reschedule", "cancel", "handoff"
    ]
    spoken_text: str = Field(min_length=1, max_length=2000)
    property_ids: list[str] = Field(default_factory=list, max_length=10)
    source_ids: list[str] = Field(default_factory=list, max_length=10)
    reason: str | None = None


class AppointmentRequest(BaseModel):
    property_id: str
    employee: str = Field(min_length=2, max_length=128)
    employee_email: EmailStr | None = None
    requirements: str = Field(default="", max_length=1000)
    meeting_notes: str = Field(default="", max_length=1000)
    starts_at: datetime
    client_name: str = Field(min_length=2, max_length=100)
    contact_email: EmailStr
    contact_phone: str | None = Field(default=None, min_length=7, max_length=32)
    idempotency_key: UUID = Field(default_factory=uuid4)
    consent: bool

    @field_validator("consent")
    @classmethod
    def require_consent(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Consent is required before a support request is stored")
        return value


class AppointmentContactContext(BaseModel):
    """Consent-bound contact details held only for the active voice session."""

    client_name: str = Field(min_length=2, max_length=100)
    contact_email: EmailStr
    contact_phone: str | None = Field(default=None, min_length=7, max_length=32)
    consent: bool

    @field_validator("consent")
    @classmethod
    def require_voice_booking_consent(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Consent is required before a voice booking")
        return value


class Appointment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    reference: str
    property_id: str
    employee: str
    employee_email: EmailStr | None = None
    starts_at: datetime
    client_name: str
    contact_email: EmailStr
    contact_phone: str | None = None
    status: Literal["booked", "cancelled", "rescheduled"] = "booked"


class AppointmentUpdate(BaseModel):
    reference: str
    contact_email: EmailStr
    starts_at: datetime | None = None
    idempotency_key: UUID


class LeadCreate(BaseModel):
    """Consent-bound seller or uncertain-intent handoff payload."""

    client_name: str = Field(min_length=2, max_length=100)
    contact_email: EmailStr
    intent: Literal["sell", "handoff"] = "handoff"
    city: str | None = Field(default=None, max_length=64)
    area: str | None = Field(default=None, max_length=128)
    budget_pkr: int | None = Field(default=None, gt=0)
    notes: str = Field(default="", max_length=500)
    follow_up_at: datetime | None = None
    consent: bool

    @field_validator("consent")
    @classmethod
    def require_consent(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Consent is required before a lead is stored")
        return value


class Lead(BaseModel):
    id: UUID
    client_name: str
    contact_email: EmailStr
    intent: Literal["sell", "handoff"]
    city: str | None = None
    area: str | None = None
    budget_pkr: int | None = None
    notes: str = ""
    follow_up_at: datetime | None = None
    status: Literal["new", "contacted", "closed"] = "new"


class TelephonyCallRequest(BaseModel):
    """Operator-approved outbound call request; carrier credentials stay server-side."""

    destination: str = Field(pattern=r"^\+[1-9]\d{6,14}$")
