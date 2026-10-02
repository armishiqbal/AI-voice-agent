import ipaddress
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import EmailStr, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./awaaz-dev.db"
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000"
    )
    admin_api_key: str | None = None
    voice_session_hmac_key: str | None = None
    voice_session_max_active: int | None = None
    voice_session_max_active_per_client: int = 2
    voice_session_lease_seconds: int = 90
    trusted_proxy_ips: str = "127.0.0.1,::1"
    pii_encryption_key: str | None = None
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    openai_api_key: str | None = None
    openai_tts_model: str = "tts-1"
    openai_tts_voice: str = "alloy"
    openai_realtime_tts_enabled: bool = False
    openai_realtime_tts_model: str = "gpt-realtime-1.5"
    openai_realtime_tts_first_audio_timeout_seconds: float = Field(default=1.8, ge=0.5, le=10)
    openai_realtime_transcription_model: str = "gpt-live-transcribe"
    openai_realtime_transcription_timeout_seconds: float = Field(default=8.0, ge=1, le=60)
    deepgram_api_key: str | None = None
    fish_audio_api_key: str | None = None
    fish_audio_model: Literal[
        "s1", "s2-pro", "s2.1-pro", "s2.1-pro-free", "drama-3-preview"
    ] = "s2.1-pro"
    fish_audio_reference_id: str | None = None
    fish_audio_sample_rate: Literal[32_000, 44_100] = 44_100
    fish_audio_latency: Literal["balanced", "normal"] = "balanced"
    voice_early_clause_streaming_enabled: bool = False
    voice_emotion_matching_enabled: bool = True
    elevenlabs_api_key: str | None = None
    elevenlabs_voice_id: str | None = None
    elevenlabs_model: str = "eleven_multilingual_v2"
    llm_timeout_seconds: float = 20.0
    llm_decision_timeout_seconds: float = Field(default=1.5, ge=0.5, le=20.0)
    rag_provider: Literal["pinecone", "faiss"] = "pinecone"
    rag_local_path: str = "artifacts/knowledge/faiss.json"
    pinecone_api_key: str | None = None
    pinecone_index: str | None = None
    pinecone_namespace: str = "default"
    embedding_model: str = "text-embedding-3-small"
    rag_top_k: int = 5
    tts_provider: str = "router"
    tts_parler_service_url: str | None = None
    tts_chatterbox_service_url: str | None = None
    tts_service_token: str | None = None
    tts_timeout_seconds: float = 60.0
    voice_tts_first_audio_timeout_seconds: float = Field(default=12.0, ge=1, le=60)
    voice_tts_idle_timeout_seconds: float = Field(default=8.0, ge=1, le=30)
    tts_urdu_model: str = "facebook/mms-tts-urd-script_latin"
    tts_english_model: str = "facebook/mms-tts-eng"
    tts_hindi_model: str = "facebook/mms-tts-hin"
    tts_arabic_model: str = "facebook/mms-tts-ara"
    tts_punjabi_model: str = "facebook/mms-tts-pan"
    tts_bengali_model: str = "facebook/mms-tts-ben"
    local_tts_enabled: bool = False
    stt_provider: str = "deepgram"
    stt_model: str = "nova-3"
    stt_language: str = "multi"
    stt_sample_rate: int = 16_000
    # Allow Deepgram to emit a stable segment before the browser's 425 ms
    # commit; browser VAD remains authoritative for completing the turn.
    stt_endpointing_ms: int = 300
    stt_utterance_end_ms: int = 1_000
    stt_min_confidence: float = 0.55
    stt_transport_timeout_seconds: float = Field(default=8.0, ge=1.0, le=30.0)
    stt_finalize_timeout_seconds: float = Field(default=6.0, ge=1.0, le=15.0)
    voice_max_audio_frame_bytes: int = 16_384
    voice_audio_queue_frames: int = 256
    voice_max_event_bytes: int = 8_192
    voice_max_ws_message_bytes: int = 32_768
    voice_ws_protocol_queue: int = 16
    telephony_provider: str = "none"
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None
    telephony_public_base_url: str | None = None
    google_token_path: str | None = None
    google_client_secret_path: str | None = None
    google_calendar_id: str = "primary"
    gmail_sender: str | None = None
    employee_email_directory: dict[str, EmailStr] = {}
    n8n_webhook_url: str | None = None
    n8n_webhook_token: str | None = None
    outbox_poll_seconds: float = 1.0
    outbox_max_attempts: int = 8
    max_upload_bytes: int = 10_000_000

    @model_validator(mode="after")
    def validate_runtime_boundary(self) -> "Settings":
        if bool(self.n8n_webhook_url) != bool(self.n8n_webhook_token):
            raise ValueError("N8N_WEBHOOK_URL and N8N_WEBHOOK_TOKEN must be configured together")
        if self.n8n_webhook_url:
            parsed_n8n = urlparse(self.n8n_webhook_url)
            local_n8n = parsed_n8n.hostname in {"127.0.0.1", "localhost", "::1", "n8n"}
            if (not parsed_n8n.hostname or parsed_n8n.username or parsed_n8n.password
                or parsed_n8n.fragment or parsed_n8n.query
                or (parsed_n8n.scheme != "https" and not (
                    self.app_env == "development" and local_n8n and parsed_n8n.scheme == "http"
                ))):
                raise ValueError("N8N_WEBHOOK_URL must use HTTPS (local HTTP allowed in development)")
            if self.google_token_path and not self.gmail_sender:
                raise ValueError(
                    "GMAIL_SENDER is required when n8n appointment delivery is enabled with Google Calendar"
                )
        if self.app_env != "development" and self.llm_provider != "openai":
            raise ValueError("LLM_PROVIDER=openai is required for live conversations")
        if self.app_env != "development" and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for live conversations")
        trusted_proxy_entries = [entry.strip() for entry in self.trusted_proxy_ips.split(",")]
        if not trusted_proxy_entries or any(
            not entry or entry == "*" for entry in trusted_proxy_entries
        ):
            raise ValueError("TRUSTED_PROXY_IPS must be explicit IP addresses or CIDR ranges")
        try:
            for entry in trusted_proxy_entries:
                ipaddress.ip_network(entry, strict=False)
        except ValueError as error:
            raise ValueError(
                "TRUSTED_PROXY_IPS must contain valid IP addresses or CIDR ranges"
            ) from error
        if self.voice_session_max_active_per_client < 1:
            raise ValueError("VOICE_SESSION_MAX_ACTIVE_PER_CLIENT must be positive")
        if self.voice_session_lease_seconds < 15:
            raise ValueError("VOICE_SESSION_LEASE_SECONDS must be at least 15 seconds")
        self.tts_provider = self.tts_provider.casefold()
        if self.tts_provider.casefold() not in {"router", "fish", "elevenlabs", "opensource"}:
            raise ValueError("TTS_PROVIDER must be router, fish, elevenlabs, or opensource")
        if self.tts_timeout_seconds <= 0:
            raise ValueError("TTS_TIMEOUT_SECONDS must be positive")
        if self.tts_provider.casefold() == "opensource" and self.app_env != "development":
            if not self.tts_parler_service_url or not self.tts_chatterbox_service_url:
                raise ValueError("Open-source multilingual TTS requires both model service URLs")
            if not self.tts_service_token:
                raise ValueError(
                    "TTS_SERVICE_TOKEN is required for open-source TTS outside development"
                )
        if (
            self.tts_provider == "opensource"
            and any((self.tts_parler_service_url, self.tts_chatterbox_service_url))
            and not self.tts_service_token
        ):
            raise ValueError(
                "TTS_SERVICE_TOKEN is required when open-source TTS workers are configured"
            )
        for service_url in (self.tts_parler_service_url, self.tts_chatterbox_service_url):
            if service_url:
                parsed = urlparse(service_url)
                local = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
                if parsed.scheme != "https" and not (self.app_env == "development" and local):
                    raise ValueError("Remote TTS service URLs must use HTTPS")
        if self.telephony_provider.casefold() not in {"none", "twilio"}:
            raise ValueError("TELEPHONY_PROVIDER must be none or twilio")
        if self.app_env != "development":
            if self.database_url.startswith("sqlite"):
                raise ValueError("DATABASE_URL must use PostgreSQL outside development")
            if not self.pii_encryption_key:
                raise ValueError("PII_ENCRYPTION_KEY is required outside development")
            if not self.admin_api_key:
                raise ValueError("ADMIN_API_KEY is required outside development")
            if (
                not self.voice_session_hmac_key
                or len(self.voice_session_hmac_key.encode("utf-8")) < 32
            ):
                raise ValueError(
                    "VOICE_SESSION_HMAC_KEY must contain at least 32 bytes outside development"
                )
            if self.voice_session_max_active is None or self.voice_session_max_active < 1:
                raise ValueError(
                    "VOICE_SESSION_MAX_ACTIVE must be set to a positive value outside development"
                )
            if self.telephony_provider.casefold() == "twilio":
                if not all(
                    (
                        self.twilio_account_sid,
                        self.twilio_auth_token,
                        self.twilio_from_number,
                        self.telephony_public_base_url,
                    )
                ):
                    raise ValueError(
                        "Twilio telephony requires complete server-side credentials outside development"
                    )
                if not self.telephony_public_base_url.startswith("https://"):
                    raise ValueError("TELEPHONY_PUBLIC_BASE_URL must use HTTPS outside development")
        if self.max_upload_bytes <= 0:
            raise ValueError("MAX_UPLOAD_BYTES must be positive")
        if self.voice_max_audio_frame_bytes < 2 or self.voice_max_audio_frame_bytes % 2:
            raise ValueError("VOICE_MAX_AUDIO_FRAME_BYTES must be a positive even number")
        if not 1 <= self.voice_audio_queue_frames <= 256:
            raise ValueError("VOICE_AUDIO_QUEUE_FRAMES must be between 1 and 256")
        if not 256 <= self.voice_max_event_bytes <= 65_536:
            raise ValueError("VOICE_MAX_EVENT_BYTES must be between 256 and 65536")
        if self.voice_max_ws_message_bytes < max(
            self.voice_max_audio_frame_bytes, self.voice_max_event_bytes
        ):
            raise ValueError("VOICE_MAX_WS_MESSAGE_BYTES must fit audio frames and voice events")
        if not 1 <= self.voice_ws_protocol_queue <= 256:
            raise ValueError("VOICE_WS_PROTOCOL_QUEUE must be between 1 and 256")
        if self.app_env != "development":
            origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
            if not origins or "*" in origins:
                raise ValueError("CORS_ORIGINS must be explicit outside development")
            for origin in origins:
                parsed = urlparse(origin)
                if (
                    parsed.scheme != "https"
                    or not parsed.netloc
                    or parsed.username
                    or parsed.password
                    or parsed.path not in {"", "/"}
                    or parsed.query
                    or parsed.fragment
                ):
                    raise ValueError("Production CORS_ORIGINS must contain HTTPS origins only")
            if self.tts_provider != "opensource":
                raise ValueError(
                    "TTS_PROVIDER=opensource is required outside development; commercial and "
                    "legacy local providers are evaluation-only"
                )
        return self

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", PROJECT_ROOT / "backend" / ".env"),
        extra="ignore",
    )


settings = Settings()
