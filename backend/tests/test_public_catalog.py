from uuid import uuid4

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from listing_fixtures import import_publishable_demo_properties

from app.api.app import app
from app.core.config import settings
from app.repositories.bootstrap import create_schema_for_local_development
from app.repositories.database import Base, SessionLocal, engine
from app.repositories.properties import SqlPropertyRepository
from app.repositories.records import StaffUserRecord, WebsiteInquiryRecord


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
