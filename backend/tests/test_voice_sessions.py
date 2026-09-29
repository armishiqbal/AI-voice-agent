from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker

from app.repositories.database import Base
from app.repositories.records import VoiceSessionLeaseRecord, VoiceSessionTicketRecord
from app.services.voice_sessions import VoiceSessionConsumeResult, VoiceSessionService


def test_voice_ticket_is_hashed_bound_and_consumable_only_once(tmp_path: Path) -> None:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'voice-sessions.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    service = VoiceSessionService(f"integration-test-key-{uuid4()}", session_factory=sessions)
    issued = service.issue("192.0.2.17", "https://voice.example.com")
    assert issued is not None
    token, _ = issued

    with sessions() as session:
        stored = session.scalar(select(VoiceSessionTicketRecord))
        assert stored is not None
        assert stored.token_hash != token
        assert stored.consumed_at is None

    with ThreadPoolExecutor(max_workers=2) as executor:
        attempts = list(
            executor.map(
                lambda _: service.consume(token, "192.0.2.17", "https://voice.example.com"),
                range(2),
            )
        )

    assert sorted(result.value for result in attempts) == ["accepted", "invalid"]
    assert (
        service.consume(token, "192.0.2.18", "https://voice.example.com")
        == VoiceSessionConsumeResult.INVALID
    )
    assert (
        service.consume(token, "192.0.2.17", "https://evil.example")
        == VoiceSessionConsumeResult.INVALID
    )
    assert service.mode_for_ticket(token) == "standard"
    assert service.renew(token)
    service.release(token)
    assert not service.renew(token)
    engine.dispose()


def test_voice_ticket_binds_selected_audio_mode(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'voice-mode.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    service = VoiceSessionService(f"voice-mode-test-key-{uuid4()}", session_factory=sessions)
    issued = service.issue("192.0.2.41", "https://voice.example.com", "hybrid")
    assert issued is not None
    ticket, _ = issued
    assert service.mode_for_ticket(ticket) == "hybrid"
    assert (
        service.consume(ticket, "192.0.2.41", "https://voice.example.com")
        == VoiceSessionConsumeResult.ACCEPTED
    )
    service.release(ticket)
    engine.dispose()


def test_voice_session_leases_enforce_global_and_per_client_limits(tmp_path: Path) -> None:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'voice-session-limits.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    service = VoiceSessionService(
        f"capacity-test-key-{uuid4()}",
        session_factory=sessions,
        max_active_total=2,
        max_active_per_client=1,
    )
    first, second, third = [
        service.issue(address, "https://voice.example.com")
        for address in ("192.0.2.21", "192.0.2.21", "192.0.2.22")
    ]
    assert first is not None and second is not None and third is not None
    assert (
        service.consume(first[0], "192.0.2.21", "https://voice.example.com")
        == VoiceSessionConsumeResult.ACCEPTED
    )
    assert (
        service.consume(second[0], "192.0.2.21", "https://voice.example.com")
        == VoiceSessionConsumeResult.CAPACITY
    )
    assert (
        service.consume(third[0], "192.0.2.22", "https://voice.example.com")
        == VoiceSessionConsumeResult.ACCEPTED
    )

    with sessions() as session:
        session.execute(
            update(VoiceSessionLeaseRecord).values(
                expires_at=datetime.now(UTC) - timedelta(seconds=1)
            )
        )
        session.commit()

    retry = service.issue("192.0.2.21", "https://voice.example.com")
    assert retry is not None
    assert (
        service.consume(retry[0], "192.0.2.21", "https://voice.example.com")
        == VoiceSessionConsumeResult.ACCEPTED
    )
    service.release(first[0])
    service.release(third[0])
    service.release(retry[0])
    engine.dispose()


def test_external_call_leases_share_limits_and_are_idempotent(tmp_path: Path) -> None:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'voice-external-leases.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    service = VoiceSessionService(
        f"external-lease-test-key-{uuid4()}",
        session_factory=sessions,
        max_active_total=1,
        max_active_per_client=1,
    )

    browser_ticket = service.issue("192.0.2.41", "https://voice.example.com")
    assert browser_ticket is not None
    assert (
        service.consume(browser_ticket[0], "192.0.2.41", "https://voice.example.com")
        == VoiceSessionConsumeResult.ACCEPTED
    )
    assert not service.acquire_external_lease("twilio:CA-browser-blocked", "+923001234567")
    service.release(browser_ticket[0])

    assert service.acquire_external_lease("twilio:CA123", "+923001234567")
    assert service.acquire_external_lease("twilio:CA123", "+923001234567")
    assert not service.acquire_external_lease("twilio:CA456", "+923009876543")
    assert service.renew_external_lease("twilio:CA123")
    assert service.capacity_snapshot()["active"] == 1

    service.release_external_lease("twilio:CA123")
    assert not service.renew_external_lease("twilio:CA123")
    assert service.acquire_external_lease("twilio:CA456", "+923009876543")
    service.release_external_lease("twilio:CA456")
    assert service.capacity_snapshot()["active"] == 0
    engine.dispose()


def test_voice_session_normalizes_loopback_and_ports(tmp_path: Path) -> None:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'voice-loopback.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    service = VoiceSessionService(f"loopback-test-key-{uuid4()}", session_factory=sessions)

    # IPv4 loopback issued, IPv6 loopback consumed, localhost vs 127.0.0.1 origin
    issued = service.issue("127.0.0.1", "http://localhost:5173")
    assert issued is not None
    token, _ = issued
    assert (
        service.consume(token, "::1", "http://127.0.0.1:5173")
        == VoiceSessionConsumeResult.ACCEPTED
    )
    service.release(token)

    # Different port must still be rejected
    issued2 = service.issue("127.0.0.1", "http://localhost:5173")
    assert issued2 is not None
    token2, _ = issued2
    assert (
        service.consume(token2, "127.0.0.1", "http://localhost:5174")
        == VoiceSessionConsumeResult.INVALID
    )
    engine.dispose()
