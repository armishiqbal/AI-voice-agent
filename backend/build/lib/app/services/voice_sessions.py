"""Short-lived, one-use credentials and shared issuance limits for anonymous voice clients."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import urllib.parse
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from sqlalchemy import case, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.repositories.database import SessionLocal, engine
from app.repositories.records import (
    VoiceSessionLeaseRecord,
    VoiceSessionQuotaLockRecord,
    VoiceSessionRateLimitRecord,
    VoiceSessionTicketRecord,
)


class VoiceSessionConsumeResult(StrEnum):
    ACCEPTED = "accepted"
    INVALID = "invalid"
    CAPACITY = "capacity"


class VoiceSessionService:
    """Issue one-use tickets without storing raw credentials or client IP addresses."""

    def __init__(
        self,
        hmac_key: str,
        session_factory: Callable[[], Session] = SessionLocal,
        dialect_name: str = engine.dialect.name,
        issue_limit: int = 10,
        issue_window: timedelta = timedelta(minutes=1),
        ticket_lifetime: timedelta = timedelta(minutes=2),
        max_active_total: int = 20,
        max_active_per_client: int = 2,
        lease_lifetime: timedelta = timedelta(seconds=90),
    ) -> None:
        if len(hmac_key.encode("utf-8")) < 32:
            raise ValueError("Voice session HMAC key must contain at least 32 bytes")
        if dialect_name not in {"postgresql", "sqlite"}:
            raise ValueError("Voice session storage requires PostgreSQL or SQLite")
        if (
            issue_limit < 1
            or issue_window.total_seconds() <= 0
            or ticket_lifetime.total_seconds() <= 0
            or max_active_total < 1
            or max_active_per_client < 1
            or lease_lifetime.total_seconds() < 15
        ):
            raise ValueError("Voice session rate, capacity, and lease limits are invalid")
        self._hmac_key = hmac_key.encode("utf-8")
        self._session_factory = session_factory
        self._dialect_name = dialect_name
        self._issue_limit = issue_limit
        self._issue_window = issue_window
        self._ticket_lifetime = ticket_lifetime
        self._max_active_total = max_active_total
        self._max_active_per_client = max_active_per_client
        self._lease_lifetime = lease_lifetime

    def _lock_scopes(self, session: Session, scopes: set[str], now: datetime) -> None:
        insert = postgresql_insert if self._dialect_name == "postgresql" else sqlite_insert
        for scope in sorted(scopes):
            statement = insert(VoiceSessionQuotaLockRecord).values(
                scope=scope,
                touched_at=now,
            )
            session.execute(
                statement.on_conflict_do_update(
                    index_elements=[VoiceSessionQuotaLockRecord.scope],
                    set_={"touched_at": now},
                )
            )

    @staticmethod
    def _normalize_client_address(client_address: str) -> str:
        addr = client_address.strip().lower()
        if addr in {"127.0.0.1", "::1", "localhost", "0.0.0.0", "::ffff:127.0.0.1"}:
            return "127.0.0.1"
        return addr

    @staticmethod
    def _normalize_origin(origin: str) -> str:
        clean = origin.strip().casefold()
        try:
            parsed = urllib.parse.urlsplit(clean)
            hostname = parsed.hostname or ""
            if hostname in {"127.0.0.1", "::1", "localhost"}:
                port_part = f":{parsed.port}" if parsed.port else ""
                return f"{parsed.scheme}://127.0.0.1{port_part}"
        except ValueError:
            pass
        return clean

    def _fingerprint(self, client_address: str) -> str:
        normalized = self._normalize_client_address(client_address)
        return hmac.new(self._hmac_key, normalized.encode("utf-8"), hashlib.sha256).hexdigest()

    def issue(
        self, client_address: str, origin: str, mode: str = "standard"
    ) -> tuple[str, datetime] | None:
        """Return a bearer ticket unless the shared per-client issue limit is exhausted."""
        if not client_address or not origin or mode not in {"standard", "openai"}:
            return None
        norm_origin = self._normalize_origin(origin)
        now = datetime.now(UTC)
        fingerprint = self._fingerprint(client_address)
        cutoff = now - self._issue_window
        insert = postgresql_insert if self._dialect_name == "postgresql" else sqlite_insert
        limit_stmt = (
            insert(VoiceSessionRateLimitRecord)
            .values(
                client_fingerprint=fingerprint,
                window_started_at=now,
                request_count=1,
            )
            .on_conflict_do_update(
                index_elements=[VoiceSessionRateLimitRecord.client_fingerprint],
                set_={
                    "window_started_at": case(
                        (VoiceSessionRateLimitRecord.window_started_at <= cutoff, now),
                        else_=VoiceSessionRateLimitRecord.window_started_at,
                    ),
                    "request_count": case(
                        (VoiceSessionRateLimitRecord.window_started_at <= cutoff, 1),
                        else_=VoiceSessionRateLimitRecord.request_count + 1,
                    ),
                },
            )
            .returning(VoiceSessionRateLimitRecord.request_count)
        )
        raw_token = f"{mode}.{secrets.token_urlsafe(32)}"
        expires_at = now + self._ticket_lifetime
        token_hash = hashlib.sha256(raw_token.encode("ascii")).hexdigest()
        with self._session_factory() as session:
            count = int(session.scalar(limit_stmt) or 0)
            # Keep ephemeral credentials and quota state bounded without a separate cleanup job.
            session.execute(
                delete(VoiceSessionTicketRecord).where(VoiceSessionTicketRecord.expires_at <= now)
            )
            session.execute(
                delete(VoiceSessionRateLimitRecord).where(
                    VoiceSessionRateLimitRecord.window_started_at < now - timedelta(days=1)
                )
            )
            if count <= self._issue_limit:
                session.add(
                    VoiceSessionTicketRecord(
                        client_fingerprint=fingerprint,
                        origin=norm_origin,
                        token_hash=token_hash,
                        created_at=now,
                        expires_at=expires_at,
                    )
                )
            session.commit()
        if count > self._issue_limit:
            return None
        return raw_token, expires_at

    @staticmethod
    def mode_for_ticket(raw_token: str) -> str | None:
        """Read provider choice from an opaque ticket after consume() has validated it."""
        mode, separator, _secret = raw_token.partition(".")
        return mode if separator and mode in {"standard", "openai"} else None

    def consume(
        self, raw_token: str, client_address: str, origin: str
    ) -> VoiceSessionConsumeResult:
        """Consume a ticket and reserve global/per-client call capacity in one transaction."""
        if not raw_token or len(raw_token) > 128 or not client_address or not origin:
            return VoiceSessionConsumeResult.INVALID
        norm_origin = self._normalize_origin(origin)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        fingerprint = self._fingerprint(client_address)
        now = datetime.now(UTC)
        with self._session_factory() as session:
            self._lock_scopes(session, {"global", f"client:{fingerprint}"}, now)
            session.execute(
                delete(VoiceSessionLeaseRecord).where(VoiceSessionLeaseRecord.expires_at <= now)
            )
            result = session.execute(
                update(VoiceSessionTicketRecord)
                .where(
                    VoiceSessionTicketRecord.token_hash == token_hash,
                    VoiceSessionTicketRecord.client_fingerprint == fingerprint,
                    VoiceSessionTicketRecord.origin == norm_origin,
                    VoiceSessionTicketRecord.consumed_at.is_(None),
                    VoiceSessionTicketRecord.expires_at > now,
                )
                .values(consumed_at=now)
            )
            if result.rowcount != 1:
                session.rollback()
                return VoiceSessionConsumeResult.INVALID
            active_total = int(
                session.scalar(
                    select(func.count())
                    .select_from(VoiceSessionLeaseRecord)
                    .where(VoiceSessionLeaseRecord.expires_at > now)
                )
                or 0
            )
            active_for_client = int(
                session.scalar(
                    select(func.count())
                    .select_from(VoiceSessionLeaseRecord)
                    .where(
                        VoiceSessionLeaseRecord.client_fingerprint == fingerprint,
                        VoiceSessionLeaseRecord.expires_at > now,
                    )
                )
                or 0
            )
            if (
                active_total >= self._max_active_total
                or active_for_client >= self._max_active_per_client
            ):
                # The credential is still one-use even when capacity is full; retry by issuing
                # a fresh ticket after a lease is released or expires.
                session.commit()
                return VoiceSessionConsumeResult.CAPACITY
            session.add(
                VoiceSessionLeaseRecord(
                    token_hash=token_hash,
                    client_fingerprint=fingerprint,
                    created_at=now,
                    expires_at=now + self._lease_lifetime,
                )
            )
            session.commit()
            return VoiceSessionConsumeResult.ACCEPTED

    def renew(self, raw_token: str) -> bool:
        """Extend a live call lease; false means the lease expired or was released."""
        if not raw_token or len(raw_token) > 128:
            return False
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        now = datetime.now(UTC)
        with self._session_factory() as session:
            fingerprint = session.scalar(
                select(VoiceSessionLeaseRecord.client_fingerprint).where(
                    VoiceSessionLeaseRecord.token_hash == token_hash,
                    VoiceSessionLeaseRecord.expires_at > now,
                )
            )
            if not fingerprint:
                return False
            session.rollback()
            self._lock_scopes(session, {"global", f"client:{fingerprint}"}, now)
            result = session.execute(
                update(VoiceSessionLeaseRecord)
                .where(
                    VoiceSessionLeaseRecord.token_hash == token_hash,
                    VoiceSessionLeaseRecord.client_fingerprint == fingerprint,
                    VoiceSessionLeaseRecord.expires_at > now,
                )
                .values(expires_at=now + self._lease_lifetime)
            )
            session.commit()
            return result.rowcount == 1

    def release(self, raw_token: str) -> None:
        """Release capacity for a disconnected WebSocket; expiration handles worker crashes."""
        if not raw_token or len(raw_token) > 128:
            return
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        with self._session_factory() as session:
            fingerprint = session.scalar(
                select(VoiceSessionLeaseRecord.client_fingerprint).where(
                    VoiceSessionLeaseRecord.token_hash == token_hash
                )
            )
            if not fingerprint:
                return
            session.rollback()
            now = datetime.now(UTC)
            self._lock_scopes(session, {"global", f"client:{fingerprint}"}, now)
            session.execute(
                delete(VoiceSessionLeaseRecord).where(
                    VoiceSessionLeaseRecord.token_hash == token_hash,
                    VoiceSessionLeaseRecord.client_fingerprint == fingerprint,
                )
            )
            session.commit()

    def capacity_snapshot(self) -> dict[str, int]:
        """Expose current shared lease counts to the protected admin metrics endpoint."""
        now = datetime.now(UTC)
        with self._session_factory() as session:
            active_total = int(
                session.scalar(
                    select(func.count())
                    .select_from(VoiceSessionLeaseRecord)
                    .where(VoiceSessionLeaseRecord.expires_at > now)
                )
                or 0
            )
        return {
            "active": active_total,
            "maximum": self._max_active_total,
            "available": max(0, self._max_active_total - active_total),
            "per_client_maximum": self._max_active_per_client,
        }
