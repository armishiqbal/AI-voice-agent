from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from fastapi.testclient import TestClient
from listing_fixtures import import_publishable_demo_properties
from sqlalchemy import select

from app.api.app import app
from app.catalog.identity import Identity, digest, require_identity
from app.catalog.marketplace import Proposal, Review, authorize, owned, review, submit
from app.catalog.public import PublicCatalogRepository
from app.catalog.scheduling import eligible_schedule
from app.catalog.staff_auth import StaffPrincipal
from app.core.config import settings
from app.core.pii import ContactCipher
from app.repositories.database import Base, SessionLocal, engine
from app.repositories.properties import SqlPropertyRepository
from app.repositories.records import (
    AgentScheduleRecord,
    ApplicationSessionRecord,
    AppointmentRecord,
    CustomerProfileRecord,
    LocationRecord,
    MembershipRecord,
    OrganizationRecord,
    OutboxEventRecord,
    PropertyRecord,
    SavedSearchRecord,
    WebsiteInquiryRecord,
)
from app.workers.alerts import deliver_alert_sync, enqueue_alerts
from app.workers.retention import purge_expired_customer_data


@pytest.fixture()
def marketplace():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    import_publishable_demo_properties(SqlPropertyRepository())
    with (
        patch.object(settings, "marketplace_enabled", True),
        patch.object(settings, "map_enabled", True),
        patch.object(settings, "customer_features_enabled", True),
        patch.object(settings, "pii_encryption_key", Fernet.generate_key().decode()),
    ):
        with SessionLocal.begin() as session:
            for oid in ("one", "two"):
                session.add(
                    OrganizationRecord(
                        id=oid, slug=oid, name=oid, status="approved", coverage=["Islamabad"]
                    )
                )
                session.add(
                    MembershipRecord(
                        id=oid,
                        organization_id=oid,
                        subject=oid,
                        email=f"{oid}@example.com",
                        display_name=oid,
                        role="manager",
                        active=True,
                    )
                )
            session.add(
                LocationRecord(
                    id="location",
                    city="Islamabad",
                    city_slug="islamabad",
                    area="F-10",
                    area_slug="f-10",
                    reviewed=True,
                )
            )
            for p in session.scalars(select(PropertyRecord)).all():
                p.organization_id = "one"
                p.classification = "residential"
                p.rental_period = "monthly" if p.transaction_type == "rent" else None
                p.assigned_staff_id = "one"
                p.assigned_employee = "agent:one"
        yield
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def test_organization_and_assignment_isolation(marketplace):
    with SessionLocal() as session:
        member = authorize(session, "one", Identity("one", "one@example.com", "aal2"))
        with pytest.raises(HTTPException) as e:
            authorize(session, "two", Identity("one", "one@example.com", "aal2"))
        assert e.value.status_code == 403
        with pytest.raises(HTTPException):
            owned(session, "two", "PROP-001", member)
        with pytest.raises(HTTPException):
            authorize(session, "one", Identity("one", "one@example.com", "aal1"))


def test_suspension_shared_catalog_and_voice(marketplace):
    catalog = PublicCatalogRepository()
    assert catalog.list_public().pagination.total > 0
    with SessionLocal.begin() as session:
        session.get(OrganizationRecord, "one").status = "suspended"
    assert catalog.list_public().pagination.total == 0
    assert SqlPropertyRepository().get_available("PROP-001") is None
    with TestClient(app) as client:
        assert client.get("/v1/public/agencies/one").status_code == 404
        response = client.get("/v1/public/listings/map?west=70&east=75&south=30&north=35")
        assert response.status_code == 200
        assert response.json()["features"] == []


def test_city_directory_uses_current_public_inventory(marketplace):
    with TestClient(app) as client:
        response = client.get("/v1/public/cities")
    assert response.status_code == 200
    assert response.json()["data"]
    assert response.json()["data"] == sorted(set(response.json()["data"]))
    with SessionLocal.begin() as session:
        session.get(OrganizationRecord, "one").status = "suspended"
    with TestClient(app) as client:
        assert client.get("/v1/public/cities").json() == {"data": []}


def test_revision_preserves_public_content_and_conflicts(marketplace):
    before = PublicCatalogRepository().get_public_by_id("PROP-001")
    result = submit(
        "one",
        "PROP-001",
        Proposal(edit_version=1, title="Proposed title"),
        Identity("one", "one@example.com", "aal2"),
    )
    assert PublicCatalogRepository().get_public_by_id("PROP-001").title == before.title
    with SessionLocal.begin() as session:
        session.get(PropertyRecord, "PROP-001").edit_version += 1
    with pytest.raises(HTTPException) as e:
        review(
            result["id"],
            Review(decision="approved"),
            StaffPrincipal("platform", "p@example.com", "Platform", "manager"),
        )
    assert e.value.status_code == 409
    assert PublicCatalogRepository().get_public_by_id("PROP-001").title == before.title


def test_no_synthetic_slots_and_schedule_exceptions(marketplace):
    future = (datetime.now(UTC) + timedelta(days=2)).replace(
        hour=6, minute=0, second=0, microsecond=0
    )
    from zoneinfo import ZoneInfo

    local = future.astimezone(ZoneInfo("Asia/Karachi"))
    with SessionLocal.begin() as session:
        assert not eligible_schedule(session, "PROP-001", future)
        session.add(
            AgentScheduleRecord(
                id="weekly",
                organization_id="one",
                subject="one",
                weekday=local.weekday(),
                start_minute=600,
                end_minute=1080,
                approved=True,
            )
        )
    with SessionLocal() as session:
        assert eligible_schedule(session, "PROP-001", future)
    with SessionLocal.begin() as session:
        session.add(
            AgentScheduleRecord(
                id="exception",
                organization_id="one",
                subject="one",
                weekday=local.weekday(),
                start_minute=0,
                end_minute=1440,
                exception_date=local.date().isoformat(),
                unavailable=True,
                approved=True,
            )
        )
    with SessionLocal() as session:
        assert not eligible_schedule(session, "PROP-001", future)


def test_agency_reschedule_keeps_recorded_agent_after_listing_assignment_changes(marketplace):
    appointment_id = str(uuid4())
    local_start = (datetime.now(ZoneInfo("Asia/Karachi")) + timedelta(days=10)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    current = local_start - timedelta(days=7)
    with SessionLocal.begin() as session:
        session.add(
            MembershipRecord(
                id="replacement-agent",
                organization_id="one",
                subject="replacement-agent",
                email="replacement@example.com",
                display_name="Replacement",
                role="agent",
                active=True,
            )
        )
        session.add(
            AgentScheduleRecord(
                id="original-agent-slot",
                organization_id="one",
                subject="one",
                weekday=local_start.weekday(),
                start_minute=600,
                end_minute=630,
                approved=True,
            )
        )
        session.get(PropertyRecord, "PROP-001").assigned_staff_id = "replacement-agent"
        session.get(PropertyRecord, "PROP-001").assigned_employee = "agent:replacement-agent"
        session.add(
            AppointmentRecord(
                id=appointment_id,
                reference="AE-AGENCY-1",
                property_id="PROP-001",
                employee="agent:one",
                starts_at=current.astimezone(UTC),
                client_name="Customer",
                contact_email_ciphertext=ContactCipher().encrypt("customer@example.com"),
                contact_phone_ciphertext=None,
                status="booked",
                idempotency_key=str(uuid4()),
                organization_id="one",
                agent_subject="one",
            )
        )
    app.dependency_overrides[require_identity] = lambda: Identity("one", "one@example.com", "aal2")
    with TestClient(app) as client:
        response = client.post(
            "/v1/agency/one/viewings/AE-AGENCY-1/reschedule",
            json={
                "new_starts_at": local_start.isoformat(),
                "idempotency_key": str(uuid4()),
            },
        )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "rescheduled"
    assert response.json()["delivery_status"] == "pending"
    with SessionLocal() as session:
        record = session.get(AppointmentRecord, appointment_id)
        assert record.agent_subject == "one"
        assert record.employee == "agent:one"


def test_retention_erases_expired_contacts_but_keeps_authoritative_references(marketplace):
    now = datetime.now(UTC)
    old = now - timedelta(days=400)
    cipher = ContactCipher()
    appointment_id = str(uuid4())
    with SessionLocal.begin() as session:
        session.add(
            WebsiteInquiryRecord(
                id=str(uuid4()),
                idempotency_key=str(uuid4()),
                request_fingerprint="a" * 64,
                property_id="PROP-001",
                request_type="property",
                client_name_ciphertext=cipher.encrypt("Customer Name"),
                contact_email_ciphertext=cipher.encrypt("customer@example.com"),
                contact_phone_ciphertext=None,
                contact_preference="email",
                message_redacted="Please call me",
                consent_version="test-v1",
                consent_purpose="website_property",
                consent_channel="website",
                consented_at=old,
                workflow_status="closed",
                delivery_status="not_configured",
                edit_version=1,
                created_at=old,
                expires_at=old,
            )
        )
        session.add(
            AppointmentRecord(
                id=appointment_id,
                reference="AE-EXPIRED-1",
                property_id="PROP-001",
                employee="agent:one",
                starts_at=old,
                closed_at=old,
                client_name="Customer Name",
                contact_email_ciphertext=cipher.encrypt("customer@example.com"),
                contact_phone_ciphertext=None,
                status="completed",
                idempotency_key=str(uuid4()),
                organization_id="one",
                agent_subject="one",
            )
        )
        session.add(
            OutboxEventRecord(
                id=str(uuid4()),
                event_type="appointment.booked",
                payload={
                    "reference": "AE-EXPIRED-1",
                    "contact_email_ciphertext": cipher.encrypt("customer@example.com"),
                },
                created_at=old,
                delivered_at=now - timedelta(days=31),
            )
        )
        pending_id = str(uuid4())
        session.add(
            OutboxEventRecord(
                id=pending_id,
                event_type="appointment.booked",
                payload={"reference": "AE-PENDING-1", "contact_email_ciphertext": "keep-for-retry"},
                created_at=old,
                delivered_at=None,
            )
        )

    result = purge_expired_customer_data(now)
    assert result == {"inquiry_contacts": 1, "viewing_contacts": 1, "delivered_payloads": 1}
    with SessionLocal() as session:
        inquiry = session.scalar(select(WebsiteInquiryRecord))
        appointment = session.get(AppointmentRecord, appointment_id)
        delivered = session.scalar(
            select(OutboxEventRecord).where(OutboxEventRecord.delivered_at.is_not(None))
        )
        pending = session.get(OutboxEventRecord, pending_id)
        assert (
            inquiry is not None
            and inquiry.client_name_ciphertext == ""
            and inquiry.contact_email_ciphertext is None
        )
        assert (
            appointment is not None
            and appointment.reference == "AE-EXPIRED-1"
            and appointment.contact_email_ciphertext == ""
        )
        assert delivered is not None and "contact_email_ciphertext" not in delivered.payload
        assert (
            pending is not None and pending.payload["contact_email_ciphertext"] == "keep-for-retry"
        )


def test_revocable_cookie_session_and_csrf(marketplace):
    with SessionLocal.begin() as session:
        session.add(
            ApplicationSessionRecord(
                token_hash=digest("token"),
                subject="customer",
                email="c@example.com",
                assurance="aal1",
                csrf_hash=digest("csrf"),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                revoked=False,
            )
        )
    with TestClient(app) as client:
        client.cookies.set("awaaz_session", "token")
        assert client.get("/v1/auth/session").status_code == 200
        assert client.post("/v1/auth/logout").status_code == 403
        assert client.post("/v1/auth/logout", headers={"x-csrf-token": "csrf"}).status_code == 200
        assert client.get("/v1/auth/session").status_code == 401


def test_alert_dedup_and_unsubscribe_while_queued(marketplace):
    cipher = ContactCipher()
    now = datetime.now(UTC).replace(hour=4, minute=0)  # 09:00 PKT
    with SessionLocal.begin() as session:
        session.add(
            CustomerProfileRecord(
                subject="customer",
                email_ciphertext=cipher.encrypt("c@example.com"),
                verified_at=now,
            )
        )
        session.add(
            SavedSearchRecord(
                id="search",
                subject="customer",
                name="Homes",
                filters={},
                notification_consent=True,
                consent_version="2026-10-04",
                activated_at=now - timedelta(days=2),
                active=True,
                unsubscribe_hash=digest("unsubscribe"),
                unsubscribe_ciphertext=cipher.encrypt("unsubscribe"),
            )
        )
    assert enqueue_alerts(now) > 0
    assert enqueue_alerts(now) == 0
    with SessionLocal.begin() as session:
        session.get(SavedSearchRecord, "search").active = False
        event = session.scalar(
            select(OutboxEventRecord).where(
                OutboxEventRecord.event_type == "customer.listing_alert"
            )
        )
        payload = event.payload
    with patch("smtplib.SMTP") as smtp:
        assert deliver_alert_sync(payload)["status"] == "suppressed"
        smtp.assert_not_called()


def test_unapproved_coordinates_and_rental_monthly_budget(marketplace):
    with SessionLocal.begin() as session:
        p = session.get(PropertyRecord, "PROP-001")
        p.latitude = 33.7
        p.longitude = 73.1
        p.transaction_type = "rent"
        p.rental_period = "yearly"
        p.price_pkr = 1200000
    assert PublicCatalogRepository().get_public_by_id("PROP-001").coordinates is None
    result = PublicCatalogRepository().list_public(
        transaction_type="rent", min_price_pkr=99999, max_price_pkr=100001
    )
    assert any(p.id == "PROP-001" for p in result.data)
