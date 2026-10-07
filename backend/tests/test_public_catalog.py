import re
import smtplib
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from listing_fixtures import import_publishable_demo_properties

from app.api.app import app
from app.core.config import settings
from app.repositories.bootstrap import create_schema_for_local_development
from app.repositories.database import Base, SessionLocal, engine
from app.repositories.properties import SqlPropertyRepository
from app.repositories.records import PropertyRecord, StaffUserRecord, WebsiteInquiryRecord


def test_public_catalog_exposes_only_approved_listing_fields_and_hides_drafts() -> None:
    Base.metadata.drop_all(bind=engine)
    create_schema_for_local_development()
    import_publishable_demo_properties(SqlPropertyRepository())
    try:
        with TestClient(app) as client:
            results = client.get("/v1/public/listings")
            assert results.status_code == 200
            body = results.json()
            assert body["pagination"]["total"] > 0
            listing = body["data"][0]
            assert listing["photos"][0]["url"].startswith("https://")
            assert "assigned_employee" not in listing
            assert "source" not in listing

            detail = client.get("/v1/public/listings/test-prop-001")
            assert detail.status_code == 200
            assert detail.json()["id"] == "PROP-001"
            assistant_detail = client.get("/v1/public/listings/by-id/PROP-001")
            assert assistant_detail.status_code == 200
            assistant_body = assistant_detail.json()
            assert assistant_body["slug"] == "test-prop-001"
            assert assistant_body["photos"]
            assert "assigned_employee" not in assistant_body
            assert "source" not in assistant_body
            with SessionLocal.begin() as session:
                stale = session.get(PropertyRecord, "PROP-001")
                assert stale is not None
                stale.availability_confirmed_at = datetime.now(UTC) - timedelta(days=40)
            stale_lookup = client.get("/v1/public/listings/by-id/PROP-001")
            assert stale_lookup.status_code == 409
            assert client.get("/v1/public/listings/by-id/PROP-003").status_code == 404
            assert client.get("/v1/public/listings/test-prop-003").status_code == 404
    finally:
        Base.metadata.drop_all(bind=engine)


def test_public_inquiry_is_encrypted_and_idempotent(monkeypatch) -> None:
    Base.metadata.drop_all(bind=engine)
    create_schema_for_local_development()
    import_publishable_demo_properties(SqlPropertyRepository())
    monkeypatch.setattr(settings, "pii_encryption_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "supabase_url", "https://example.supabase.co")
    with SessionLocal.begin() as session:
        session.add(
            StaffUserRecord(
                provider_subject="test-staff",
                email="agent@example.com",
                display_name="Test Agent",
                role="agent",
                is_active=True,
            )
        )

    idempotency_key = str(uuid4())
    payload = {
        "property_id": "PROP-001",
        "request_type": "property",
        "client_name": "Visitor Name",
        "contact_email": "visitor@example.com",
        "contact_preference": "email",
        "message": "I would like more information.",
        "consent": True,
        "consent_version": "2026-10-03",
        "idempotency_key": idempotency_key,
    }
    try:
        with TestClient(app) as client:
            first = client.post("/v1/public/inquiries", json=payload)
            retry = client.post("/v1/public/inquiries", json=payload)
            assert first.status_code == 201
            assert retry.status_code == 201
            assert retry.json()["inquiry_id"] == first.json()["inquiry_id"]
            assert first.json()["delivery_status"] == "not_configured"

            reused_key = {**payload, "message": "A different request."}
            conflict = client.post("/v1/public/inquiries", json=reused_key)
            assert conflict.status_code == 409
        with SessionLocal() as session:
            record = session.query(WebsiteInquiryRecord).one()
            assert record.client_name_ciphertext != payload["client_name"]
            assert record.contact_email_ciphertext != payload["contact_email"]
    finally:
        Base.metadata.drop_all(bind=engine)


def test_public_viewing_flow_and_staff_management(monkeypatch) -> None:
    from zoneinfo import ZoneInfo
    from app.repositories.records import AreaGuideRecord

    Base.metadata.drop_all(bind=engine)
    create_schema_for_local_development()
    import_publishable_demo_properties(SqlPropertyRepository())
    monkeypatch.setattr(settings, "pii_encryption_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "smtp_host", None)
    with SessionLocal.begin() as session:
        session.add(
            StaffUserRecord(
                provider_subject="agent-fatima",
                email="fatima@example.com",
                display_name="Fatima Noor",
                role="agent",
                is_active=True,
            )
        )
        session.add(
            StaffUserRecord(
                provider_subject="manager-ali",
                email="ali.mgr@example.com",
                display_name="Ali Manager",
                role="manager",
                is_active=True,
            )
        )

    try:
        with TestClient(app) as client:
            # 1. Fetch available slots
            slots_resp = client.get("/v1/public/listings/PROP-001/slots")
            assert slots_resp.status_code == 200
            available_slots = slots_resp.json()["data"]
            assert len(available_slots) > 0
            chosen_slot = available_slots[0]

            # 2. Request OTP
            monkeypatch.setattr(settings, "app_env", "staging")
            unconfigured_otp = client.post("/v1/public/viewings/request-otp", json={"email": "visitor@example.com"})
            assert unconfigured_otp.status_code == 503
            monkeypatch.setattr(settings, "app_env", "development")
            otp_req = client.post("/v1/public/viewings/request-otp", json={"email": "client@example.com"})
            assert otp_req.status_code == 200
            assert otp_req.json()["message"] == "Development code generated. No email was sent."
            debug_otp = otp_req.json().get("debug_otp")
            assert debug_otp is not None

            # 3. Invalid OTP rejected
            bad_verify = client.post("/v1/public/viewings/verify-otp", json={"email": "client@example.com", "otp": "000000"})
            assert bad_verify.status_code == 400

            # 4. Valid OTP verified
            good_verify = client.post("/v1/public/viewings/verify-otp", json={"email": "client@example.com", "otp": debug_otp})
            assert good_verify.status_code == 200
            token = good_verify.json()["verification_token"]
            assert token

            # 5. Book viewing
            idempotency_key = str(uuid4())
            booking_payload = {
                "property_id": "PROP-001",
                "starts_at": chosen_slot,
                "client_name": "Hamza Tariq",
                "contact_email": "client@example.com",
                "contact_phone": "+923001234567",
                "verification_token": token,
                "consent": True,
                "consent_version": "2026-10-03",
                "idempotency_key": idempotency_key,
            }
            booking_resp = client.post("/v1/public/viewings", json=booking_payload)
            assert booking_resp.status_code == 201
            ref = booking_resp.json()["reference"]
            assert ref.startswith("AES-")
            assert booking_resp.json()["status"] == "booked"

            # 6. Idempotent replay
            replay_resp = client.post("/v1/public/viewings", json=booking_payload)
            assert replay_resp.status_code == 201
            assert replay_resp.json()["reference"] == ref

            # 7. Slot conflict for concurrent request
            other_key = str(uuid4())
            conflict_payload = {**booking_payload, "idempotency_key": other_key, "client_name": "Another Person"}
            conflict_resp = client.post("/v1/public/viewings", json=conflict_payload)
            assert conflict_resp.status_code == 409

            # 8. Staff Viewings API
            staff_headers = {"Authorization": "Bearer dev-staff-manager-ali"}
            staff_list = client.get("/v1/staff/viewings", headers=staff_headers)
            assert staff_list.status_code == 200
            viewings = staff_list.json()["data"]
            assert any(v["reference"] == ref for v in viewings)

            # 9. Cancel Viewing
            cancel_resp = client.post(
                f"/v1/staff/viewings/{ref}/cancel",
                headers=staff_headers,
                json={"idempotency_key": str(uuid4()), "reason": "Client requested change"},
            )
            assert cancel_resp.status_code == 200
            assert cancel_resp.json()["status"] == "cancelled"

            # 10. Area Guide API
            # Not published yet:
            assert client.get("/v1/public/areas/karachi/clifton").status_code == 404

            # Create area guide via staff
            create_guide_resp = client.post(
                "/v1/staff/areas",
                headers=staff_headers,
                json={
                    "city_slug": "karachi",
                    "area_slug": "clifton",
                    "title": "Clifton, Karachi",
                    "overview_markdown": "Clifton is a premier seaside neighborhood in Karachi.",
                    "amenities_summary": "Top schools, shopping malls, and hospitals.",
                    "transport_info": "Connected via Marine Drive and Sunset Boulevard.",
                    "investment_outlook": "High rental yields and steady capital appreciation.",
                },
            )
            assert create_guide_resp.status_code == 201

            # Published area guide now accessible publicly:
            pub_guide_resp = client.get("/v1/public/areas/karachi/clifton")
            assert pub_guide_resp.status_code == 200
            assert pub_guide_resp.json()["title"] == "Clifton, Karachi"
            assert "premier seaside" in pub_guide_resp.json()["overview_markdown"]
    finally:
        Base.metadata.drop_all(bind=engine)


def test_viewing_otp_reports_only_configured_mail_delivery(monkeypatch) -> None:
    from app.catalog.public import _VIEWING_OTP_STORE

    email = "smtp-visitor@example.com"
    _VIEWING_OTP_STORE.pop(email, None)
    monkeypatch.setattr(settings, "app_env", "staging")
    monkeypatch.setattr(settings, "pii_encryption_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "smtp_host", "mail.example.test")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_username", None)
    monkeypatch.setattr(settings, "smtp_password", None)
    monkeypatch.setattr(settings, "smtp_from_email", "no-reply@example.test")
    monkeypatch.setattr(settings, "smtp_starttls", True)
    monkeypatch.setattr(settings, "smtp_ssl", False)

    with TestClient(app) as client, patch("app.catalog.public.smtplib.SMTP") as smtp_factory:
        smtp = smtp_factory.return_value.__enter__.return_value
        smtp.send_message.return_value = {}
        accepted = client.post("/v1/public/viewings/request-otp", json={"email": email})
        assert accepted.status_code == 200
        assert accepted.json()["message"] == "Verification email accepted by the configured mail server."
        assert accepted.json()["debug_otp"] is None
        sent_message = smtp.send_message.call_args.args[0]
        code = re.search(r"\b(\d{6})\b", sent_message.get_payload())
        assert code is not None
        verified = client.post("/v1/public/viewings/verify-otp", json={"email": email, "otp": code.group(1)})
        assert verified.status_code == 200

        failed_email = "smtp-failure@example.com"
        smtp.send_message.side_effect = smtplib.SMTPException("server rejected message")
        failed = client.post("/v1/public/viewings/request-otp", json={"email": failed_email})
        assert failed.status_code == 503
        assert failed_email not in _VIEWING_OTP_STORE
        not_stored = client.post("/v1/public/viewings/verify-otp", json={"email": failed_email, "otp": "123456"})
        assert not_stored.status_code == 400


def test_assistant_static_route_obeys_concierge_feature_flag(monkeypatch) -> None:
    monkeypatch.setattr(settings, "assistant_concierge_enabled", False)
    with TestClient(app) as client:
        disabled = client.get("/assistant/", follow_redirects=False)
        root = client.get("/", headers={"accept": "text/html"})
    assert disabled.status_code == 404
    assert disabled.json()["detail"] == "Property assistance is not enabled in this environment"
    assert root.status_code == 200
    assert root.json()["service"] == "Awaaz Estate API"
