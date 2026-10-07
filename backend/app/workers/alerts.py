"""Daily consent-based discovery alerts; outbox payloads contain record IDs only."""

import asyncio
import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.catalog.public import PublicCatalogRepository
from app.core.config import settings
from app.core.pii import ContactCipher
from app.repositories.database import SessionLocal
from app.repositories.records import (
    AlertDeliveryRecord,
    CustomerProfileRecord,
    OutboxEventRecord,
    PropertyRecord,
    SavedSearchRecord,
)


def enqueue_alerts(now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    if not settings.customer_features_enabled or now.astimezone(ZoneInfo("Asia/Karachi")).hour != 9:
        return 0
    count = 0
    with SessionLocal() as session:
        searches = session.scalars(
            select(SavedSearchRecord).where(
                SavedSearchRecord.active.is_(True), SavedSearchRecord.notification_consent.is_(True)
            )
        ).all()
        inputs = [(s.id, s.filters, s.activated_at.replace(tzinfo=UTC)) for s in searches]
    for sid, filters, activation in inputs:
        page = 1
        while True:
            result = PublicCatalogRepository().list_public(page=page, page_size=100, **filters)
            for p in result.data:
                if (
                    p.availability_status != "available"
                    or not PublicCatalogRepository().can_reserve(p.id)
                ):
                    continue
                with SessionLocal() as session:
                    record = session.get(PropertyRecord, p.id)
                    published = record.published_at
                    if not published or published.replace(tzinfo=UTC) <= activation:
                        continue
                    key = published.isoformat()
                try:
                    with SessionLocal.begin() as session:
                        existing = session.scalar(
                            select(AlertDeliveryRecord.id).where(
                                AlertDeliveryRecord.search_id == sid,
                                AlertDeliveryRecord.property_id == p.id,
                                AlertDeliveryRecord.publication_key == key,
                            )
                        )
                        if existing:
                            continue
                        aid = str(uuid4())
                        session.add(
                            AlertDeliveryRecord(
                                id=aid,
                                search_id=sid,
                                property_id=p.id,
                                publication_key=key,
                                status="pending",
                            )
                        )
                        session.add(
                            OutboxEventRecord(
                                id=str(uuid4()),
                                event_type="customer.listing_alert",
                                payload={"alert_id": aid},
                            )
                        )
                    count += 1
                except IntegrityError:
                    continue
            if page >= result.pagination.total_pages:
                break
            page += 1
    return count


def deliver_alert_sync(payload: dict[str, object]) -> dict[str, object]:
    with SessionLocal.begin() as session:
        alert = session.get(AlertDeliveryRecord, str(payload.get("alert_id")), with_for_update=True)
        if not alert or alert.status == "delivered":
            return {"status": "already_processed"}
        search = session.get(SavedSearchRecord, alert.search_id, with_for_update=True)
        profile = session.get(CustomerProfileRecord, search.subject) if search else None
        listing = PublicCatalogRepository().get_public_by_id(alert.property_id)
        if (
            not settings.customer_features_enabled
            or not search
            or not search.active
            or not search.notification_consent
            or not profile
            or not listing
            or listing.availability_status != "available"
            or not PublicCatalogRepository().can_reserve(alert.property_id)
        ):
            alert.status = "suppressed"
            return {"status": "suppressed"}
        # Re-check matching filters as well as eligibility before external delivery.
        matched = False
        page = 1
        while True:
            matches = PublicCatalogRepository().list_public(
                page=page, page_size=100, **search.filters
            )
            if any(p.id == alert.property_id for p in matches.data):
                matched = True
                break
            if page >= matches.pagination.total_pages:
                break
            page += 1
        if not matched:
            alert.status = "suppressed"
            return {"status": "suppressed"}
        if not settings.smtp_host or not settings.smtp_from_email:
            raise RuntimeError("Alert email delivery is not configured")
        cipher = ContactCipher()
        email = cipher.decrypt(profile.email_ciphertext)
        token = cipher.decrypt(search.unsubscribe_ciphertext)
        msg = EmailMessage()
        msg["From"] = str(settings.smtp_from_email)
        msg["To"] = email
        msg["Subject"] = "A new property matches your Awaaz search"
        msg["Message-ID"] = f"<awaaz-alert-{alert.id}@awaaz.local>"
        base = getattr(settings, "public_website_url", "http://localhost:3000").rstrip("/")
        msg.set_content(
            f"{listing.title}\nPKR {listing.price_pkr:,}\n{base}/properties/{listing.slug}\n\nUnsubscribe: {base}/account/unsubscribe?token={token}\n"
        )
        smtp_cls = smtplib.SMTP_SSL if settings.smtp_ssl else smtplib.SMTP
        try:
            with smtp_cls(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
                if settings.smtp_starttls and not settings.smtp_ssl:
                    smtp.starttls()
                if settings.smtp_username and settings.smtp_password:
                    smtp.login(settings.smtp_username, settings.smtp_password)
                refused = smtp.send_message(msg)
                if refused:
                    raise RuntimeError("Email provider rejected the recipient")
        except Exception as error:
            raise RuntimeError("Alert email delivery failed") from error
        alert.status = "delivered"
        alert.delivered_at = datetime.now(UTC)
        return {"status": "provider_accepted", "message_id": msg["Message-ID"]}


async def deliver_alert(payload: dict[str, object]) -> dict[str, object]:
    return await asyncio.to_thread(deliver_alert_sync, payload)
