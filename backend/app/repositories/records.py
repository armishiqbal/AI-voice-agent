from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.repositories.database import Base


class PropertyRecord(Base):
    __tablename__ = "properties"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(64), index=True)
    area: Mapped[str] = mapped_column(String(128), index=True)
    purpose: Mapped[str] = mapped_column(String(32), index=True)
    price_pkr: Mapped[int] = mapped_column(BigInteger, index=True)
    bedrooms: Mapped[int] = mapped_column(Integer)
    size_sqft: Mapped[int] = mapped_column(Integer)
    amenities: Mapped[list[str]] = mapped_column(JSON)
    investment_goals: Mapped[list[str]] = mapped_column(JSON, default=list)
    nearby_schools: Mapped[list[str]] = mapped_column(JSON, default=list)
    nearby_hospitals: Mapped[list[str]] = mapped_column(JSON, default=list)
    developer: Mapped[str] = mapped_column(String(128))
    payment_plan: Mapped[str] = mapped_column(Text)
    available: Mapped[bool] = mapped_column(Boolean, index=True)
    assigned_employee: Mapped[str] = mapped_column(String(128))
    assigned_staff_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    source_version: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(255), default="unverified")
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    slug: Mapped[str | None] = mapped_column(String(180), nullable=True, unique=True)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    transaction_type: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    property_type: Mapped[str | None] = mapped_column(String(24), nullable=True, index=True)
    bathrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    publication_status: Mapped[str] = mapped_column(
        String(16), default="draft", server_default="draft", index=True
    )
    availability_status: Mapped[str] = mapped_column(
        String(20), default="unconfirmed", server_default="unconfirmed", index=True
    )
    availability_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    content_permission_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    edit_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)


class PropertyMediaRecord(Base):
    __tablename__ = "property_media"
    __table_args__ = (Index("ix_property_media_public_order", "property_id", "is_public", "sort_order"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    property_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("properties.id", ondelete="RESTRICT"), index=True
    )
    original_object_path: Mapped[str] = mapped_column(Text)
    derivative_object_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    public_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    alt_text: Mapped[str] = mapped_column(String(300), default="", server_default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    processing_status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending", index=True
    )
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class ListingVerificationRecord(Base):
    """Staff review metadata; evidence references remain private to the application."""

    __tablename__ = "listing_verifications"
    __table_args__ = (Index("ix_listing_verifications_latest", "property_id", "reviewed_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    property_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("properties.id", ondelete="RESTRICT"), index=True
    )
    review_scope: Mapped[str] = mapped_column(String(160))
    reviewer_id: Mapped[str] = mapped_column(String(128))
    evidence_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str] = mapped_column(String(20), index=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    public_source_url: Mapped[str | None] = mapped_column(Text, nullable=True)


class StaffUserRecord(Base):
    __tablename__ = "staff_users"

    provider_subject: Mapped[str] = mapped_column(String(128), primary_key=True)
    email: Mapped[str] = mapped_column(String(320))
    display_name: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(20), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class WebsiteInquiryRecord(Base):
    __tablename__ = "website_inquiries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    property_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("properties.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    request_type: Mapped[str] = mapped_column(String(20), index=True)
    client_name_ciphertext: Mapped[str] = mapped_column(Text)
    contact_email_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_phone_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_preference: Mapped[str] = mapped_column(String(16))
    message_redacted: Mapped[str] = mapped_column(Text, default="", server_default="")
    consent_version: Mapped[str] = mapped_column(String(64))
    consent_purpose: Mapped[str] = mapped_column(String(64))
    consent_channel: Mapped[str] = mapped_column(String(32))
    consented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    workflow_status: Mapped[str] = mapped_column(
        String(32), default="new", server_default="new", index=True
    )
    delivery_status: Mapped[str] = mapped_column(
        String(24), default="not_configured", server_default="not_configured"
    )
    edit_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    assigned_staff_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closing_outcome: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class WebsiteInquiryActivityRecord(Base):
    __tablename__ = "website_inquiry_activity"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    inquiry_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("website_inquiries.id", ondelete="CASCADE"), index=True
    )
    actor_staff_id: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(32))
    details_redacted: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )


class PropertyImportBatchRecord(Base):
    __tablename__ = "property_import_batches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source: Mapped[str] = mapped_column(String(255))
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    record_count: Mapped[int] = mapped_column(Integer)
    validation_errors: Mapped[list[dict[str, object]]] = mapped_column(JSON)


class ToolAuditEventRecord(Base):
    __tablename__ = "tool_audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    reference: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )


class LeadRecord(Base):
    __tablename__ = "leads"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    client_name: Mapped[str] = mapped_column(String(100))
    contact_email_ciphertext: Mapped[str] = mapped_column(Text)
    intent: Mapped[str] = mapped_column(String(32), index=True)
    city: Mapped[str | None] = mapped_column(String(64), nullable=True)
    area: Mapped[str | None] = mapped_column(String(128), nullable=True)
    budget_pkr: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes_redacted: Mapped[str] = mapped_column(Text, default="")
    follow_up_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    follow_up_enqueued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="new", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )


class ConversationTranscriptRecord(Base):
    __tablename__ = "conversation_transcripts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(16))
    text_redacted: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ConversationStateRecord(Base):
    __tablename__ = "conversation_states"
    conversation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    history: Mapped[list[str]] = mapped_column(JSON, default=list)
    detected_language: Mapped[str] = mapped_column(String(16), default="en")
    lead_profile: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    budget: Mapped[int | None] = mapped_column(Integer, nullable=True)
    city: Mapped[str | None] = mapped_column(String(64), nullable=True)
    area: Mapped[str | None] = mapped_column(String(128), nullable=True)
    bedrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amenities: Mapped[list[str]] = mapped_column(JSON, default=list)
    investment_goal: Mapped[str | None] = mapped_column(String(100), nullable=True)
    intent: Mapped[str] = mapped_column(String(32), default="unknown")
    retrieved_sources: Mapped[list[str]] = mapped_column(JSON, default=list)
    selected_property_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    tool_results: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    appointment_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    escalation_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )


class AppointmentRecord(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        Index(
            "uq_appointments_active_employee_slot",
            "employee",
            "starts_at",
            unique=True,
            sqlite_where=text("status IN ('booked', 'rescheduled')"),
            postgresql_where=text("status IN ('booked', 'rescheduled')"),
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    reference: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    property_id: Mapped[str] = mapped_column(String(64), index=True)
    employee: Mapped[str] = mapped_column(String(128))
    employee_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    client_name: Mapped[str] = mapped_column(String(100), default="")
    contact_email_ciphertext: Mapped[str] = mapped_column(Text)
    contact_phone_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(36), unique=True)


class AppointmentActionRecord(Base):
    __tablename__ = "appointment_actions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    reference: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(32))
    result_status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class OutboxEventRecord(Base):
    __tablename__ = "outbox_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    claimed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)


class VoiceSessionTicketRecord(Base):
    __tablename__ = "voice_session_tickets"
    client_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    origin: Mapped[str] = mapped_column(String(512))
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class VoiceSessionRateLimitRecord(Base):
    __tablename__ = "voice_session_rate_limits"
    client_fingerprint: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    request_count: Mapped[int] = mapped_column(Integer)


class VoiceSessionQuotaLockRecord(Base):
    __tablename__ = "voice_session_quota_locks"
    scope: Mapped[str] = mapped_column(String(80), primary_key=True)
    touched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class VoiceSessionLeaseRecord(Base):
    __tablename__ = "voice_session_leases"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
