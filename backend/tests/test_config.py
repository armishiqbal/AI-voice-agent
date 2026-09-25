import pytest

from app.core.config import Settings
from app.integrations.providers import provider_readiness


def test_production_rejects_sqlite_and_missing_pii_key() -> None:
    with pytest.raises(ValueError, match="PostgreSQL"):
        Settings(app_env="production", database_url="sqlite:///unsafe.db", pii_encryption_key=None)


def test_production_requires_admin_api_key() -> None:
    with pytest.raises(ValueError, match="ADMIN_API_KEY"):
        Settings(
            app_env="production",
            database_url="postgresql+psycopg://user:pass@host/db",
            pii_encryption_key="a" * 44,
        )


def test_production_requires_voice_session_hmac_key() -> None:
    with pytest.raises(ValueError, match="VOICE_SESSION_HMAC_KEY"):
        Settings(
            app_env="production",
            database_url="postgresql+psycopg://user:pass@host/db",
            pii_encryption_key="a" * 44,
            admin_api_key="admin-key",
        )


def test_production_requires_explicit_voice_session_capacity() -> None:
    with pytest.raises(ValueError, match="VOICE_SESSION_MAX_ACTIVE"):
        Settings(
            app_env="production",
            database_url="postgresql+psycopg://user:pass@host/db",
            pii_encryption_key="a" * 44,
            admin_api_key="admin-key",
            voice_session_hmac_key="s" * 44,
        )


def test_trusted_proxy_setting_requires_explicit_ip_or_cidr() -> None:
    with pytest.raises(ValueError, match="TRUSTED_PROXY_IPS"):
        Settings(trusted_proxy_ips="*")
    settings = Settings(trusted_proxy_ips="10.20.0.0/16,192.0.2.17")
    assert settings.trusted_proxy_ips == "10.20.0.0/16,192.0.2.17"


def test_upload_limit_must_be_positive() -> None:
    with pytest.raises(ValueError, match="MAX_UPLOAD_BYTES"):
        Settings(max_upload_bytes=0)


def test_production_twilio_requires_complete_https_boundary() -> None:
    with pytest.raises(ValueError, match="Twilio telephony"):
        Settings(
            app_env="production",
            database_url="postgresql+psycopg://user:pass@host/db",
            pii_encryption_key="a" * 44,
            admin_api_key="admin-key",
            voice_session_hmac_key="s" * 44,
            voice_session_max_active=10,
            telephony_provider="twilio",
            twilio_account_sid="AC123",
        )


def test_production_requires_open_source_multilingual_tts_workers() -> None:
    production = {
        "app_env": "production",
        "database_url": "postgresql+psycopg://user:pass@host/db",
        "pii_encryption_key": "a" * 44,
        "admin_api_key": "admin-key",
        "voice_session_hmac_key": "s" * 44,
        "voice_session_max_active": 10,
        "cors_origins": "https://voice.example.com",
    }

    with pytest.raises(ValueError, match="TTS_PROVIDER=opensource"):
        Settings(**production, tts_provider="fish", fish_audio_api_key="fish-key")

    settings = Settings(
        **production,
        tts_provider="opensource",
        tts_parler_service_url="https://parler.example.com",
        tts_chatterbox_service_url="https://chatterbox.example.com",
        tts_service_token="worker-token",
    )
    assert provider_readiness(settings).multilingual_tts is True


def test_commercial_tts_credentials_do_not_satisfy_open_source_readiness() -> None:
    settings = Settings(
        tts_provider="fish",
        fish_audio_api_key="fish-key",
        elevenlabs_api_key="eleven-key",
        elevenlabs_voice_id="voice-id",
    )
    assert provider_readiness(settings).multilingual_tts is False


def test_open_source_worker_urls_require_service_token_in_development() -> None:
    with pytest.raises(ValueError, match="TTS_SERVICE_TOKEN"):
        Settings(
            tts_provider="opensource",
            tts_parler_service_url="http://127.0.0.1:8021",
            tts_chatterbox_service_url="http://127.0.0.1:8022",
        )


def test_google_readiness_requires_refreshable_token_with_requested_scopes(tmp_path) -> None:
    token_path = tmp_path / "google.token.json"
    settings = Settings(google_token_path=str(token_path), gmail_sender="agent@example.test")
    assert provider_readiness(settings).calendar is False
    assert provider_readiness(settings).gmail is False

    token_path.write_text(
        '{"refresh_token":"refresh", "scopes":['
        '"https://www.googleapis.com/auth/calendar.events",'
        '"https://www.googleapis.com/auth/gmail.send"]}',
        encoding="utf-8",
    )
    readiness = provider_readiness(settings)
    assert readiness.calendar is True
    assert readiness.gmail is True


def test_google_readiness_does_not_claim_gmail_without_scope_or_sender(tmp_path) -> None:
    token_path = tmp_path / "google.token.json"
    token_path.write_text(
        '{"refresh_token":"refresh", "scopes":["https://www.googleapis.com/auth/calendar.events"]}',
        encoding="utf-8",
    )
    readiness = provider_readiness(Settings(google_token_path=str(token_path)))
    assert readiness.calendar is True
    assert readiness.gmail is False
