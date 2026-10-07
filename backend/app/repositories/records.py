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
    organization_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    classification: Mapped[str | None] = mapped_column(String(16), nullable=True)
    rental_period: Mapped[str | None] = mapped_column(String(16), nullable=True)
    coordinates_approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
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
    __table_args__ = (
        Index("ix_property_media_public_order", "property_id", "is_public", "sort_order"),
    )

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
    is_public: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", index=True
    )
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
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class WebsiteInquiryRecord(Base):
    __tablename__ = "website_inquiries"
    organization_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    agent_subject: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

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
    organization_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    agent_subject: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
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
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
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


class AreaGuideRecord(Base):
    __tablename__ = "area_guides"
    __table_args__ = (Index("uq_area_guides_city_area", "city_slug", "area_slug", unique=True),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    city_slug: Mapped[str] = mapped_column(String(64), index=True)
    area_slug: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(255))
    overview_markdown: Mapped[str] = mapped_column(Text, default="")
    amenities_summary: Mapped[str] = mapped_column(Text, default="")
    transport_info: Mapped[str] = mapped_column(Text, default="")
    investment_outlook: Mapped[str] = mapped_column(Text, default="")
    publication_status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewer_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sources_json: Mapped[list[dict]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class OrganizationRecord(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    contact_email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    coverage: Mapped[list[str]] = mapped_column(JSON, default=list)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    edit_version: Mapped[int] = mapped_column(Integer, default=1)


class MembershipRecord(Base):
    __tablename__ = "organization_memberships"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    subject: Mapped[str] = mapped_column(String(128), index=True)
    email: Mapped[str] = mapped_column(String(254))
    role: Mapped[str] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    display_name: Mapped[str] = mapped_column(String(128))
    slug: Mapped[str | None] = mapped_column(String(160), nullable=True, unique=True)
    profile_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    languages: Mapped[list[str]] = mapped_column(JSON, default=list)
    __table_args__ = (
        Index("uq_membership_org_subject", "organization_id", "subject", unique=True),
    )


class LocationRecord(Base):
    __tablename__ = "marketplace_locations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    city: Mapped[str] = mapped_column(String(64), index=True)
    city_slug: Mapped[str] = mapped_column(String(64))
    area: Mapped[str] = mapped_column(String(128), default="")
    area_slug: Mapped[str] = mapped_column(String(128), default="")
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    sqft_per_marla: Mapped[int | None] = mapped_column(Integer, nullable=True)
    __table_args__ = (Index("uq_location_city_area", "city_slug", "area_slug", unique=True),)


class ListingRevisionRecord(Base):
    __tablename__ = "listing_revisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    property_id: Mapped[str] = mapped_column(ForeignKey("properties.id"), index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    proposed: Mapped[dict] = mapped_column(JSON)
    base_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="submitted")
    submitted_by: Mapped[str] = mapped_column(String(128))
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    review_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        Index(
            "uq_revision_submitted_property",
            "property_id",
            unique=True,
            sqlite_where=text("status = 'submitted'"),
            postgresql_where=text("status = 'submitted'"),
        ),
    )


class AgentScheduleRecord(Base):
    __tablename__ = "agent_schedules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    subject: Mapped[str] = mapped_column(String(128), index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    weekday: Mapped[int] = mapped_column(Integer)
    start_minute: Mapped[int] = mapped_column(Integer)
    end_minute: Mapped[int] = mapped_column(Integer)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    exception_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    unavailable: Mapped[bool] = mapped_column(Boolean, default=False)


class ApplicationSessionRecord(Base):
    __tablename__ = "application_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject: Mapped[str] = mapped_column(String(128), index=True)
    email: Mapped[str] = mapped_column(String(254))
    assurance: Mapped[str] = mapped_column(String(8))
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class CustomerFavoriteRecord(Base):
    __tablename__ = "customer_favorites"
    subject: Mapped[str] = mapped_column(String(128), primary_key=True)
    property_id: Mapped[str] = mapped_column(ForeignKey("properties.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class SavedSearchRecord(Base):
    __tablename__ = "saved_searches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    subject: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(100))
    filters: Mapped[dict] = mapped_column(JSON)
    notification_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    unsubscribe_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    unsubscribe_hash: Mapped[str] = mapped_column(String(64), unique=True)


class MarketplaceAuditRecord(Base):
    __tablename__ = "marketplace_audit"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    actor: Mapped[str] = mapped_column(String(128))
    organization_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class ListingReportRecord(Base):
    __tablename__ = "listing_reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    property_id: Mapped[str] = mapped_column(ForeignKey("properties.id"), index=True)
    category: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20), default="new")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class AlertDeliveryRecord(Base):
    __tablename__ = "alert_deliveries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    search_id: Mapped[str] = mapped_column(ForeignKey("saved_searches.id"), index=True)
    property_id: Mapped[str] = mapped_column(ForeignKey("properties.id"))
    publication_key: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        Index(
            "uq_alert_search_publication",
            "search_id",
            "property_id",
            "publication_key",
            unique=True,
        ),
    )


class CustomerProfileRecord(Base):
    __tablename__ = "customer_profiles"
    subject: Mapped[str] = mapped_column(String(128), primary_key=True)
    email_ciphertext: Mapped[str] = mapped_column(Text)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MarketplaceRateRecord(Base):
    __tablename__ = "marketplace_rate_windows"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window: Mapped[int] = mapped_column(Integer, primary_key=True)
    hits: Mapped[int] = mapped_column(Integer)


class ViewingOtpRecord(Base):
    __tablename__ = "viewing_otp_challenges"
    email_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
