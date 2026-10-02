from __future__ import annotations

import asyncio
import base64
import json
import secrets
import time
import urllib.parse
from collections import deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import Annotated, Any, Literal
from uuid import uuid4

from fastapi import (
    Body,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError
from sqlalchemy import select, text

from app.agents.graph import EstateAgent
from app.core.config import settings
from app.core.observability import TraceStore
from app.domain.emotions import infer_acoustic_emotion
from app.domain.models import (
    AppointmentContactContext,
    AppointmentRequest,
    AppointmentUpdate,
    ConversationTurn,
    LeadCreate,
    PropertyImport,
    PropertyQuery,
    TelephonyCallRequest,
)
from app.evaluation.runner import load_cases, run_evaluation
from app.integrations.llm import LLMDecisionError, build_decision_provider
from app.integrations.providers import all_tts_languages_ready, provider_readiness
from app.integrations.rag import RAGProviderError, build_knowledge_store
from app.integrations.stt import (
    OpenAIRealtimeSTT,
    STTEvent,
    STTProviderError,
    build_english_hybrid_stt,
    build_openai_realtime_stt,
    build_stt_provider,
    build_urdu_hybrid_stt,
    estimated_transcript_lag_ms,
    stt_provider_error_code,
)
from app.integrations.stt.deepgram import DeepgramStreamingSTT
from app.integrations.telephony import (
    TelephonyProviderError,
    TwilioTelephonyAdapter,
    build_telephony_adapter,
    mulaw_to_pcm16,
    pcm16_to_mulaw,
    resample_pcm16,
)
from app.integrations.tts import (
    AudioChunk,
    TTSProviderError,
    build_openai_tts_router,
    build_tts_router,
)
from app.integrations.tts.openai_realtime import OpenAIRealtimeSpeechProvider
from app.repositories.appointments import SqlAppointmentService
from app.repositories.bootstrap import create_schema_for_local_development
from app.repositories.conversation_state import ConversationStateStore
from app.repositories.database import SessionLocal
from app.repositories.leads import LeadRepository
from app.repositories.properties import SqlPropertyRepository
from app.repositories.records import OutboxEventRecord, ToolAuditEventRecord
from app.repositories.transcripts import TranscriptStore
from app.repositories.voice_outcomes import record_voice_call_outcome
from app.services.appointments import redact_for_retention
from app.services.voice_acknowledgement import (
    VoiceAcknowledgementCache,
    prepare_acknowledgement,
)
from app.services.voice_booking import VoiceBookingFlow
from app.services.voice_recovery import (
    telephony_provider_failure_prompt,
    transcription_recovery_prompt,
)
from app.services.voice_sessions import VoiceSessionConsumeResult, VoiceSessionService
from app.services.voice_stream import pipeline_synthesize_clauses

if settings.app_env == "development":
    create_schema_for_local_development()
properties = SqlPropertyRepository()
appointments = SqlAppointmentService(properties)
leads = LeadRepository()
traces = TraceStore()
transcripts = TranscriptStore()
conversation_states = ConversationStateStore()
agent = EstateAgent(properties, traces, build_decision_provider(settings), conversation_states)
knowledge_store = build_knowledge_store(settings)
agent.retriever.knowledge_store = knowledge_store
tts = build_tts_router(settings)
voice_acknowledgements = VoiceAcknowledgementCache()
stt = build_stt_provider(settings)
openai_voice_tts = build_openai_tts_router(settings)
telephony = build_telephony_adapter(settings)
voice_sessions = VoiceSessionService(
    settings.voice_session_hmac_key or secrets.token_urlsafe(32),
    max_active_total=settings.voice_session_max_active or 20,
    max_active_per_client=settings.voice_session_max_active_per_client,
    lease_lifetime=timedelta(seconds=settings.voice_session_lease_seconds),
)
STT_FINAL_SEGMENT_QUIET_SECONDS = 0.25
STT_RECOVERABLE_FAILURES = frozenset(
    {
        "stt_stream_ended",
        "stt_finalize_timeout",
        "stt_provider_timeout",
        "stt_provider_error",
    }
)


def _stt_failure_is_recoverable(reason: str) -> bool:
    """Only auto-restart known transient failures; unknown and permanent errors stop."""
    return reason in STT_RECOVERABLE_FAILURES


def _is_turn_final(voice_mode: str, event: STTEvent, browser_committed: bool) -> bool:
    """Use browser VAD as the turn boundary for explicit-commit voice routes."""
    if voice_mode in {"openai", "hybrid"}:
        return event.is_final and browser_committed
    return event.speech_final or event.from_finalize


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        await voice_acknowledgements.aclose()
        await asyncio.gather(
            close_provider_router(tts),
            close_provider_router(openai_voice_tts),
        )


async def close_provider_router(router: object) -> None:
    close = getattr(router, "aclose", None)
    if callable(close):
        await close()


app = FastAPI(title="Awaaz Estate API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip().rstrip("/") for origin in settings.cors_origins.split(",") if origin.strip()
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _voice_tts_failure_code(error: TTSProviderError) -> str:
    """Classify provider failures for local metrics without retaining provider bodies or caller text."""
    current: BaseException | None = error
    messages: list[str] = []
    while current is not None:
        messages.append(str(current).casefold())
        current = current.__cause__
    message = " ".join(messages)
    if "http 429" in message or "rate limit" in message:
        return "rate_limited"
    if (
        "http 402" in message
        or "insufficient credit" in message
        or "insufficient api credits" in message
        or "insufficient_quota" in message
        or "credit_balance_exhausted" in message
    ):
        return "insufficient_credits"
    if "http 401" in message or "http 403" in message or "unauthorized" in message:
        return "auth_rejected"
    if "did not produce first audio" in message or "first audio" in message and "deadline" in message:
        return "first_audio_deadline"
    if "timed out" in message or "timeout" in message:
        return "provider_timeout"
    if "did not match" in message or "did not follow the approved text" in message:
        return "speech_integrity_rejected"
    return "provider_error"


class STTFinalizeTimeout(TimeoutError):
    """The provider did not return a stable turn transcript before its deadline."""


def _consume_background_task_result(task: asyncio.Task[Any]) -> None:
    if not task.cancelled():
        task.exception()


frontend_dist = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"
if not frontend_dist.exists():
    frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if (frontend_dist / "assets").exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

SUPPORTED_VOICE_LANGUAGES = {"ur-Latn", "ur-Arab", "en", "hi", "ar", "pa", "bn"}
OPENAI_STT_READINESS_CACHE_TTL_SECONDS = 30.0
_openai_stt_readiness_cache: tuple[float, bool] | None = None


class VoiceSessionRequest(BaseModel):
    mode: Literal["standard", "openai", "hybrid"] = "standard"


DEFAULT_VOICE_SESSION_REQUEST = VoiceSessionRequest()


async def live_openai_stt_ready() -> bool:
    """Cache a real Realtime handshake; credentials alone do not prove a usable voice route."""
    global _openai_stt_readiness_cache
    now = time.monotonic()
    cached = _openai_stt_readiness_cache
    if cached is not None and now - cached[0] < OPENAI_STT_READINESS_CACHE_TTL_SECONDS:
        return cached[1]

    probe = build_openai_realtime_stt(settings)
    ready = False
    try:
        if await probe.is_ready():
            ready = await asyncio.wait_for(
                probe.warmup(),
                timeout=min(settings.openai_realtime_transcription_timeout_seconds, 5.0),
            )
    except Exception:  # noqa: BLE001 - readiness reports provider state, never leaks upstream details
        ready = False
    finally:
        await probe.aclose()
    _openai_stt_readiness_cache = (time.monotonic(), ready)
    return ready


async def voice_option_readiness() -> dict[str, bool]:
    provider_status = provider_readiness()
    deepgram_stt_ready = await stt.is_ready()
    standard_tts_ready = provider_status.multilingual_tts and await all_tts_languages_ready(tts)
    openai_tts_routes = await openai_voice_tts.readiness()
    openai_audio_ready = (
        provider_status.openai
        and settings.openai_realtime_tts_enabled
        and await live_openai_stt_ready()
        and openai_tts_routes.get("*", False)
    )
    hybrid_realtime_audio_ready = (
        deepgram_stt_ready
        and provider_status.openai
        and settings.openai_realtime_tts_enabled
        and openai_tts_routes.get("*", False)
    )
    standard_audio_ready = (
        deepgram_stt_ready and provider_status.openai and standard_tts_ready
    )
    configured_hybrid_routes = await tts.readiness()
    configured_hybrid_tts_ready = all(
        configured_hybrid_routes.get(language, configured_hybrid_routes.get("*", False))
        for language in ("ur-Latn", "en")
    )
    hybrid_audio_ready = hybrid_realtime_audio_ready or (
        deepgram_stt_ready and provider_status.openai and configured_hybrid_tts_ready
    )
    return {
        "standard_voice_ready": standard_audio_ready,
        "openai_voice_ready": openai_audio_ready,
        "hybrid_voice_ready": hybrid_audio_ready,
        "multilingual_tts": standard_tts_ready,
        "live_voice_pipeline_ready": standard_audio_ready or openai_audio_ready or hybrid_audio_ready,
    }


def voice_origin_allowed(origin: str | None, app_env: str, cors_origins: str) -> bool:
    """Check browser Origin against CORS configuration; this is not client authentication."""

    if not origin:
        return app_env == "development"

    def normalized(value: str) -> str | None:
        parsed = urllib.parse.urlsplit(value)
        if (
            parsed.scheme.casefold() not in {"http", "https"}
            or not parsed.netloc
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            return None
        return f"{parsed.scheme.casefold()}://{parsed.netloc.casefold()}"

    candidate = normalized(origin)
    if candidate is None:
        return False
    allowed = {normalized(value.strip()) for value in cors_origins.split(",") if value.strip()}
    return candidate in allowed


def normalize_voice_language(value: str) -> str:
    lowered = value.casefold()
    if lowered.startswith("en"):
        return "en"
    if lowered.startswith("ur"):
        return "ur-Latn"
    for language in ("hi", "ar", "pa", "bn"):
        if lowered.startswith(language):
            return language
    return "ur-Latn"


def require_admin_api_key(x_admin_api_key: str | None = Header(default=None)) -> None:
    """Protect operational endpoints while keeping local development friction-free."""

    if settings.app_env == "development":
        return
    if (
        not settings.admin_api_key
        or not x_admin_api_key
        or not secrets.compare_digest(x_admin_api_key, settings.admin_api_key)
    ):
        raise HTTPException(status_code=401, detail="Admin API key required")


@app.get("/")
def root(request: Request) -> Response:
    index_file = frontend_dist / "index.html"
    accept = request.headers.get("accept", "")
    if index_file.exists() and ("text/html" in accept or "application/json" not in accept):
        return FileResponse(index_file)
    return JSONResponse(
        {
            "status": "online",
            "service": "Awaaz Estate API",
            "version": "0.1.0",
            "docs": "/docs",
            "ready": "/readyz",
            "health": "/healthz",
        }
    )


@app.get("/json/version")
def chrome_devtools_version() -> dict[str, str]:
    return {
        "Browser": "AwaazEstateAPI/0.1.0",
        "Protocol-Version": "1.3",
    }


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> dict[str, object]:
    providers = provider_readiness()
    voice_status = await voice_option_readiness()
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
        database_ready = True
    except Exception:  # noqa: BLE001 - readiness must report database failures, not crash
        database_ready = False
    provider_status = {
        **providers.__dict__,
        **voice_status,
    }
    standard_blockers = [
        name
        for name, is_ready in (
            ("Deepgram streaming STT", provider_status["deepgram"]),
            ("OpenAI structured agent", provider_status["openai"]),
            ("multilingual open-source TTS workers", provider_status["multilingual_tts"]),
        )
        if not is_ready
    ]
    voice_blockers = (
        []
        if (
            provider_status["standard_voice_ready"]
            or provider_status["openai_voice_ready"]
            or provider_status["hybrid_voice_ready"]
        )
        else standard_blockers + ["OpenAI Realtime transcription and speech configuration"]
    )
    live_voice_ready = (
        provider_status["standard_voice_ready"]
        or provider_status["openai_voice_ready"]
        or provider_status["hybrid_voice_ready"]
    )
    reasoning_status = _structured_reasoning_status()
    return {
        "status": "ready"
        if database_ready
        and live_voice_ready
        and reasoning_status["status"] not in {"cooldown", "provider_error"}
        else "degraded",
        "mode": "live" if live_voice_ready else "blocked",
        "application": {"database_ready": database_ready},
        "structured_reasoning": reasoning_status,
        "live_voice": {
            "configured": live_voice_ready,
            "status": "configured_unverified" if live_voice_ready else "blocked",
            "verification": "configuration_only",
            "blockers": voice_blockers,
            "options": {
                "standard": provider_status["standard_voice_ready"],
                "openai": provider_status["openai_voice_ready"],
                "hybrid": provider_status["hybrid_voice_ready"],
            },
        },
        "providers": provider_status,
    }


@app.get("/v1/admin/metrics", dependencies=[Depends(require_admin_api_key)])
async def metrics() -> dict[str, object]:
    providers = provider_readiness()
    provider_status = {
        **providers.__dict__,
        **(await voice_option_readiness()),
    }
    return {
        "traces": traces.snapshot(),
        "providers": provider_status,
        "structured_reasoning": _structured_reasoning_status(),
        "voice_sessions": await asyncio.to_thread(voice_sessions.capacity_snapshot),
        "follow_ups_due": await asyncio.to_thread(leads.list_due_followups),
    }


@app.post("/v1/admin/follow-ups/{lead_id}/complete", dependencies=[Depends(require_admin_api_key)])
def complete_due_follow_up(lead_id: str) -> dict[str, str]:
    """Mark an operator-confirmed follow-up complete without exposing contact details."""
    try:
        return leads.complete_due_followup(lead_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


def _structured_reasoning_status() -> dict[str, object]:
    """Report configured-vs-cooldown state without implying an upstream health check."""
    decision_provider = agent.decision_provider
    try:
        cooldown_remaining = max(
            0.0,
            float(getattr(decision_provider, "failure_cooldown_remaining", 0.0)),
        )
    except (TypeError, ValueError):
        cooldown_remaining = 0.0
    configured = decision_provider is not None
    last_failure_category = getattr(decision_provider, "last_failure_category", None)
    status = (
        "unconfigured"
        if not configured
        else "cooldown"
        if cooldown_remaining > 0
        else "provider_error"
        if last_failure_category
        else "configured_unverified"
    )
    return {
        "configured": configured,
        "status": status,
        "fallback": "deterministic",
        "cooldown_remaining_seconds": round(cooldown_remaining, 1),
        "last_failure_category": last_failure_category,
    }


@app.get("/v1/admin/call-outcomes", dependencies=[Depends(require_admin_api_key)])
def call_outcomes(limit: int = Query(default=50, ge=1, le=200)) -> list[dict[str, object]]:
    """Read CRM-ready call outcomes without audio, transcripts, or contact details."""
    with SessionLocal() as session:
        events = session.scalars(
            select(OutboxEventRecord)
            .where(OutboxEventRecord.event_type == "voice.call_completed")
            .order_by(OutboxEventRecord.created_at.desc())
            .limit(limit)
        ).all()
        safe_fields = (
            "call_id",
            "channel",
            "status",
            "duration_ms",
            "language",
            "intent",
            "city",
            "area",
            "budget_pkr",
            "budget_below_list",
            "lowest_matching_price_pkr",
            "property_ids",
            "source_ids",
            "appointment_reference",
            "escalation_reason",
            "summary",
            "completed_at",
        )
        return [
            {
                **{key: event.payload.get(key) for key in safe_fields},
                "delivery_status": "delivered" if event.delivered_at else "pending",
                "delivery_attempts": event.attempts,
                "last_delivery_error": event.last_error,
            }
            for event in events
        ]


@app.get("/v1/admin/evaluations/report", dependencies=[Depends(require_admin_api_key)])
def evaluation_report() -> dict[str, object]:
    cases_path = Path(__file__).resolve().parents[3] / "evals" / "conversations.json"
    report = run_evaluation(lambda: EstateAgent(properties), load_cases(cases_path))
    return report.as_dict()


@app.get("/v1/admin/outbox", dependencies=[Depends(require_admin_api_key)])
def outbox_status(limit: int = Query(default=50, ge=1, le=200)) -> list[dict[str, object]]:
    """Expose delivery state without returning encrypted contact payloads."""

    with SessionLocal() as session:
        events = session.scalars(
            select(OutboxEventRecord).order_by(OutboxEventRecord.created_at.desc()).limit(limit)
        ).all()
        return [
            {
                "id": event.id,
                "event_type": event.event_type,
                "created_at": event.created_at.isoformat() if event.created_at else None,
                "delivered_at": event.delivered_at.isoformat() if event.delivered_at else None,
                "attempts": event.attempts,
                "last_error": event.last_error,
                "next_attempt_at": event.next_attempt_at.isoformat()
                if event.next_attempt_at
                else None,
            }
            for event in events
        ]


@app.get("/v1/admin/audit", dependencies=[Depends(require_admin_api_key)])
def audit_events(limit: int = Query(default=100, ge=1, le=500)) -> list[dict[str, object]]:
    """Return redacted tool audit metadata for operator investigation."""

    with SessionLocal() as session:
        events = session.scalars(
            select(ToolAuditEventRecord)
            .order_by(ToolAuditEventRecord.created_at.desc())
            .limit(limit)
        ).all()
        return [
            {
                "id": event.id,
                "action": event.action,
                "status": event.status,
                "reference": event.reference,
                "payload": event.payload,
                "created_at": event.created_at.isoformat() if event.created_at else None,
            }
            for event in events
        ]


@app.get("/v1/properties")
def list_properties(
    city: str | None = None,
    purpose: str | None = None,
    max_budget_pkr: int | None = Query(default=None, gt=0),
    bedrooms: int | None = Query(default=None, ge=0),
    amenities: list[str] | None = None,
    investment_goal: str | None = None,
):
    if amenities and len(amenities) > 10:
        raise HTTPException(status_code=422, detail="At most ten amenities may be requested")
    if investment_goal and len(investment_goal) > 100:
        raise HTTPException(status_code=422, detail="Investment goal is too long")
    return properties.list(
        PropertyQuery(
            city=city,
            purpose=purpose,
            max_budget_pkr=max_budget_pkr,
            bedrooms=bedrooms,
            amenities=amenities or [],
            investment_goal=investment_goal,
        )
    )


@app.get("/v1/properties/{property_id}")
def get_property(property_id: str):
    property_item = properties.get_available(property_id)
    if property_item is None:
        raise HTTPException(404, "Verified available property was not found")
    return property_item


@app.post("/v1/properties/import", status_code=202, dependencies=[Depends(require_admin_api_key)])
def import_properties(payload: PropertyImport):
    batch_id = properties.import_properties(payload.properties, source=payload.source)
    return {
        "accepted": len(payload.properties),
        "source": payload.source,
        "batch_id": batch_id,
        "validation_errors": [],
    }


@app.post(
    "/v1/properties/import-file", status_code=202, dependencies=[Depends(require_admin_api_key)]
)
async def import_inventory_file(request: Request, filename: str, source: str):
    """Validate a CSV/JSON inventory upload without trusting model-generated fields.

    The raw request body keeps this endpoint usable without a multipart dependency. Clients
    send the file bytes and provide the original filename and immutable source label as query
    parameters. Invalid rows are recorded in the import-batch ledger and never imported.
    """
    from app.services.ingestion import parse_inventory_bytes

    body = await request.body()
    if len(body) > settings.max_upload_bytes:
        raise HTTPException(413, "Inventory upload exceeds MAX_UPLOAD_BYTES")
    try:
        result = parse_inventory_bytes(body, filename, source)
    except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HTTPException(422, str(error)) from error
    batch_id = properties.import_properties(
        result.records,
        source=result.source,
        validation_errors=[issue.as_dict() for issue in result.errors],
    )
    return {
        "accepted": len(result.records),
        "rejected": len(result.errors),
        "source": result.source,
        "batch_id": batch_id,
        "validation_errors": [issue.as_dict() for issue in result.errors],
    }


@app.post(
    "/v1/knowledge/ingest-file", status_code=202, dependencies=[Depends(require_admin_api_key)]
)
async def ingest_knowledge_file(
    request: Request,
    filename: str,
    source: str,
    property_id: str | None = None,
    city: str | None = None,
    language: str = "en",
    source_version: str = "import-1",
):
    """Chunk a brochure/FAQ and upsert it only when Pinecone is configured."""
    if knowledge_store is None:
        raise HTTPException(503, "Pinecone knowledge store is not configured")
    from app.services.ingestion import chunk_text, extract_pdf_chunks

    metadata = {
        "property_id": property_id or "global",
        "city": city or "global",
        "language": language,
        "version": source_version,
    }
    body = await request.body()
    if len(body) > settings.max_upload_bytes:
        raise HTTPException(413, "Knowledge upload exceeds MAX_UPLOAD_BYTES")
    try:
        if filename.lower().endswith(".pdf"):
            chunks = extract_pdf_chunks(body, filename, source, metadata=metadata)
        elif filename.lower().endswith((".txt", ".md")):
            chunks = chunk_text(body.decode("utf-8"), source, metadata=metadata)
        else:
            raise ValueError("Knowledge files must be .pdf, .txt, or .md")
        knowledge_store.upsert(chunks)
    except (RAGProviderError, RuntimeError, UnicodeDecodeError, ValueError) as error:
        raise HTTPException(422, str(error)) from error
    return {"accepted": len(chunks), "source": source, "metadata": metadata}


@app.post("/v1/leads", status_code=201)
def create_lead(request: LeadCreate):
    return leads.create(request)


def _twilio_signature_url(path: str, query: str = "") -> str:
    base = str(settings.telephony_public_base_url or "").rstrip("/")
    return f"{base}{path}{('?' + query) if query else ''}"


def _parse_form_body(body: bytes) -> dict[str, str]:
    parsed = urllib.parse.parse_qs(body.decode("utf-8"), keep_blank_values=True)
    return {key: values[-1] for key, values in parsed.items() if values}


TWILIO_CAPACITY_REJECTION_TWIML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<Response><Say>Please call us back shortly. Our team is helping other callers.</Say>'
    "<Hangup/></Response>"
)


@app.post("/v1/telephony/calls", dependencies=[Depends(require_admin_api_key)])
async def start_telephony_call(request: TelephonyCallRequest) -> dict[str, str]:
    try:
        session = await telephony.start_session(request.destination)
    except TelephonyProviderError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return {"call_id": session.call_id, "websocket_url": session.websocket_url}


@app.post("/v1/telephony/inbound", response_class=Response)
async def telephony_inbound(request: Request) -> Response:
    """Twilio webhook: return a media-stream TwiML document after signature validation."""

    if not isinstance(telephony, TwilioTelephonyAdapter):
        raise HTTPException(status_code=503, detail="Telephony provider is not configured")
    body = await request.body()
    params = _parse_form_body(body)
    signature = request.headers.get("x-twilio-signature")
    if (
        settings.app_env != "development" or settings.twilio_auth_token
    ) and not telephony.verify_signature(
        _twilio_signature_url("/v1/telephony/inbound", request.url.query),
        params,
        signature,
        settings.twilio_auth_token,
    ):
        raise HTTPException(status_code=401, detail="Invalid telephony signature")
    call_sid = params.get("CallSid", "").strip()
    caller = params.get("From", "").strip()
    if not call_sid or not caller:
        raise HTTPException(status_code=400, detail="Twilio call identity is required")
    try:
        twiml = telephony.inbound_twiml()
    except TelephonyProviderError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    lease_id = f"twilio:{call_sid}"
    if not await asyncio.to_thread(voice_sessions.acquire_external_lease, lease_id, caller):
        traces.increment("voice:telephony_capacity_rejected")
        return Response(content=TWILIO_CAPACITY_REJECTION_TWIML, media_type="application/xml")
    return Response(content=twiml, media_type="application/xml")


@app.post("/v1/conversations/{conversation_id}/turn")
def conversation_turn(conversation_id: str, turn: ConversationTurn):
    if agent.decision_provider is None:
        raise HTTPException(status_code=503, detail="Live AI provider is not configured")
    started = time.perf_counter()
    try:
        decision = agent.respond(conversation_id, turn.text, turn.language)
    except LLMDecisionError as error:
        raise HTTPException(status_code=503, detail="Live AI provider could not complete this turn") from error
    latency_ms = (time.perf_counter() - started) * 1000
    traces.observe("rest.decision_latency_ms", latency_ms)
    transcripts.append(conversation_id, "user", turn.text)
    transcripts.append(conversation_id, "assistant", decision.spoken_text)
    reasoning_status = _structured_reasoning_status()
    return {
        "decision": decision,
        "retained_transcript": redact_for_retention(turn.text),
        "latency_ms": round(latency_ms, 2),
        "reasoning_status": reasoning_status["status"],
        "reasoning_failure_category": reasoning_status["last_failure_category"],
    }


@app.post("/v1/appointments")
def book_appointment(request: AppointmentRequest):
    try:
        return appointments.book(request)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@app.post("/v1/appointments/reschedule")
def reschedule_appointment(request: AppointmentUpdate):
    try:
        return appointments.update(request)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@app.post("/v1/appointments/cancel")
def cancel_appointment(request: AppointmentUpdate):
    try:
        return appointments.update(request, cancel=True)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@app.post("/v1/voice/session")
async def create_voice_session(
    request: Request,
    response: Response,
    payload: Annotated[VoiceSessionRequest, Body()] = DEFAULT_VOICE_SESSION_REQUEST,
) -> dict[str, str]:
    mode = payload.mode
    origin = request.headers.get("origin")
    if not origin or not voice_origin_allowed(origin, settings.app_env, settings.cors_origins):
        raise HTTPException(status_code=403, detail="Voice origin is not allowed")
    client_address = request.client.host if request.client else None
    options = await voice_option_readiness()
    readiness_key = {
        "standard": "standard_voice_ready",
        "openai": "openai_voice_ready",
        "hybrid": "hybrid_voice_ready",
    }[mode]
    selected_ready = options[readiness_key]
    if not selected_ready:
        raise HTTPException(status_code=503, detail=f"The {mode} voice option is not ready")
    if mode == "openai":
        warmup_started = time.perf_counter()
        try:
            warmed = await asyncio.wait_for(openai_voice_tts.warmup(), timeout=1.6)
        except Exception:  # noqa: BLE001 - cold voice stays usable if warmup fails
            warmed = False
        traces.observe(
            "voice.tts_transport_warmup_ms", (time.perf_counter() - warmup_started) * 1000
        )
        if not warmed:
            traces.increment("voice.tts_transport_warmup_failed")
    issued = (
        voice_sessions.issue(client_address or "", origin)
        if mode == "standard"
        else voice_sessions.issue(client_address or "", origin, mode)
    )
    if issued is None:
        raise HTTPException(
            status_code=429, detail="Voice session limit reached; try again shortly"
        )
    ticket, expires_at = issued
    response.headers["Cache-Control"] = "no-store"
    return {"ticket": ticket, "expires_at": expires_at.isoformat()}


@app.websocket("/v1/voice")
async def voice_socket(websocket: WebSocket):
    if not voice_origin_allowed(
        websocket.headers.get("origin"), settings.app_env, settings.cors_origins
    ):
        await websocket.close(code=1008, reason="Voice origin is not allowed")
        return
    await websocket.accept()
    try:
        auth_message = await asyncio.wait_for(websocket.receive(), timeout=5)
    except (TimeoutError, WebSocketDisconnect):
        await websocket.close(code=1008, reason="Voice session authentication required")
        return
    if auth_message.get("type") == "websocket.disconnect":
        return
    auth_text = auth_message.get("text")
    if (
        auth_message.get("type") != "websocket.receive"
        or not isinstance(auth_text, str)
        or len(auth_text.encode("utf-8")) > settings.voice_max_event_bytes
    ):
        await websocket.close(code=1008, reason="Invalid voice session authentication")
        return
    try:
        auth_payload = json.loads(auth_text)
    except json.JSONDecodeError:
        auth_payload = None
    client_address = websocket.client.host if websocket.client else None
    origin = websocket.headers.get("origin")
    if (
        not isinstance(auth_payload, dict)
        or auth_payload.get("type") != "authenticate"
        or not isinstance(auth_payload.get("ticket"), str)
        or not client_address
        or not origin
    ):
        await websocket.close(code=1008, reason="Invalid or expired voice session")
        return
    authenticated_language = auth_payload.get("language", "ur-Latn")
    if (
        not isinstance(authenticated_language, str)
        or authenticated_language not in SUPPORTED_VOICE_LANGUAGES
    ):
        await websocket.close(code=1008, reason="Unsupported voice language")
        return
    voice_ticket = auth_payload["ticket"]
    consume_result = await asyncio.to_thread(
        voice_sessions.consume, voice_ticket, client_address, origin
    )
    if consume_result != VoiceSessionConsumeResult.ACCEPTED:
        if consume_result == VoiceSessionConsumeResult.CAPACITY:
            traces.increment("voice:session_capacity_rejected")
            await websocket.close(code=1013, reason="Voice session capacity reached")
        else:
            await websocket.close(code=1008, reason="Invalid or expired voice session")
        return

    voice_mode = voice_sessions.mode_for_ticket(voice_ticket)
    if voice_mode not in {"standard", "openai", "hybrid"}:
        await asyncio.to_thread(voice_sessions.release, voice_ticket)
        await websocket.close(code=1008, reason="Invalid voice provider mode")
        return
    stt_transport_ready = asyncio.Event()
    stt_transport_failed = asyncio.Event()
    stt_transport_failure_reason = "stt_provider_unavailable"
    stt_startup_in_progress = False
    session_stt = (
        build_openai_realtime_stt(settings)
        if voice_mode == "openai"
        else build_urdu_hybrid_stt(settings)
        if voice_mode == "hybrid" and authenticated_language in {"ur-Latn", "ur-Arab"}
        else build_english_hybrid_stt(settings)
        if voice_mode == "hybrid"
        else stt
    )
    if isinstance(session_stt, DeepgramStreamingSTT):
        session_stt.on_transport_ready = stt_transport_ready.set
    response_language = authenticated_language
    if isinstance(session_stt, OpenAIRealtimeSTT):
        session_stt.configure_response_language(response_language)
    session_realtime_tts = (
        OpenAIRealtimeSpeechProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_realtime_tts_model,
            voice=settings.openai_tts_voice,
            connect_timeout_seconds=settings.openai_realtime_transcription_timeout_seconds,
            response_timeout_seconds=settings.voice_tts_idle_timeout_seconds,
            first_audio_timeout_seconds=settings.openai_realtime_tts_first_audio_timeout_seconds,
        )
        if settings.openai_realtime_tts_enabled and voice_mode in {"openai", "hybrid"}
        else None
    )
    session_tts = session_realtime_tts or (
        tts if voice_mode == "hybrid" else openai_voice_tts if voice_mode == "openai" else tts
    )
    prepared_acknowledgement = voice_acknowledgements.get(tts, response_language) or ()
    prepared_acknowledgement_language = (
        response_language if prepared_acknowledgement else None
    )
    realtime_tts_failure_code: str | None = None
    realtime_tts_warmup: asyncio.Task[bool] | None = None
    configured_tts_ack_warmup: asyncio.Task[bool] | None = None

    async def warm_configured_tts_acknowledgement() -> bool:
        nonlocal prepared_acknowledgement, prepared_acknowledgement_language
        try:
            task = voice_acknowledgements.warm(tts, response_language)
            acknowledgement = (
                voice_acknowledgements.get(tts, response_language)
                if task is None
                else await task
            )
            if acknowledgement is None:
                return False
        except Exception:  # noqa: BLE001 - acknowledgement is optional; answer route remains live
            traces.increment("voice:configured_tts_acknowledgement_failed")
            return False
        prepared_acknowledgement = acknowledgement
        prepared_acknowledgement_language = response_language
        traces.increment("voice:configured_tts_acknowledgement_ready")
        return True

    async def warm_realtime_tts() -> bool:
        nonlocal prepared_acknowledgement, prepared_acknowledgement_language
        nonlocal session_realtime_tts, session_tts, realtime_tts_failure_code
        if session_realtime_tts is None:
            return False
        try:
            warmed = await session_realtime_tts.warmup()
            if warmed:
                prepared_acknowledgement = await prepare_acknowledgement(
                    session_realtime_tts, response_language
                )
                prepared_acknowledgement_language = response_language
                return True
        except Exception as error:  # noqa: BLE001 - fallback TTS remains available if warmup fails
            if isinstance(error, TTSProviderError):
                realtime_tts_failure_code = _voice_tts_failure_code(error)
            traces.increment("voice:realtime_tts_acknowledgement_failed")
        else:
            traces.increment("voice:realtime_tts_warmup_failed")
            traces.increment("voice:realtime_tts_acknowledgement_failed")
        traces.increment("voice:realtime_tts_fallback")
        await session_realtime_tts.aclose()
        session_realtime_tts = None
        session_tts = tts if voice_mode == "hybrid" else openai_voice_tts
        if voice_mode == "hybrid":
            await warm_configured_tts_acknowledgement()
        return False

    if session_realtime_tts is not None:
        realtime_tts_warmup = asyncio.create_task(warm_realtime_tts())
    elif voice_mode == "hybrid":
        configured_tts_ack_warmup = asyncio.create_task(
            warm_configured_tts_acknowledgement()
        )

    async def maintain_session_lease() -> None:
        renewal_interval = max(5, settings.voice_session_lease_seconds / 3)
        while True:
            await asyncio.sleep(renewal_interval)
            try:
                renewed = await asyncio.to_thread(voice_sessions.renew, voice_ticket)
            except Exception:  # noqa: BLE001 - lease loss must close the billable voice session
                renewed = False
            if not renewed:
                traces.increment("voice:session_lease_lost")
                try:
                    await websocket.close(code=1013, reason="Voice session lease expired")
                except RuntimeError:
                    pass
                return

    lease_task = asyncio.create_task(maintain_session_lease())

    async def release_session_lease() -> None:
        if not lease_task.done():
            lease_task.cancel()
        lease_task.add_done_callback(_consume_background_task_result)
        await asyncio.to_thread(voice_sessions.release, voice_ticket)

    conversation_id = str(uuid4())
    booking_contact: AppointmentContactContext | None = None
    booking_flow = VoiceBookingFlow(properties, appointments)
    presented_property_ids: list[str] = []
    voice_call_started_at = time.perf_counter()
    appointment_reference: str | None = None
    try:
        stt_available = await session_stt.is_ready()
        stt_warmup_failed = False
        stt_warmup_reason = "stt_provider_unavailable"
        if stt_available and isinstance(session_stt, OpenAIRealtimeSTT):
            stt_warmup_started = time.perf_counter()
            try:
                stt_available = await asyncio.wait_for(
                    session_stt.warmup(),
                    timeout=settings.openai_realtime_transcription_timeout_seconds,
                )
            except Exception as error:  # noqa: BLE001 - expose only a stable provider status code
                stt_available = False
                stt_warmup_reason = f"stt_{stt_provider_error_code(error)}"
            traces.observe(
                "voice.stt_transport_warmup_ms",
                (time.perf_counter() - stt_warmup_started) * 1000,
            )
            if not stt_available:
                stt_warmup_failed = True
                traces.increment("voice:stt_transport_warmup_failed")
        if realtime_tts_warmup is not None:
            try:
                await asyncio.wait_for(
                    asyncio.shield(realtime_tts_warmup),
                    timeout=settings.openai_realtime_transcription_timeout_seconds + 2,
                )
            except TimeoutError:
                traces.increment("voice:realtime_tts_acknowledgement_timeout")
                realtime_tts_warmup.cancel()
                await asyncio.gather(realtime_tts_warmup, return_exceptions=True)
                if session_realtime_tts is not None:
                    await session_realtime_tts.aclose()
                    session_realtime_tts = None
                    session_tts = openai_voice_tts
            except Exception:  # noqa: BLE001 - voice can continue through the HTTP TTS fallback
                traces.increment("voice:realtime_tts_acknowledgement_failed")
    except Exception:
        await release_session_lease()
        raise
    active_task: asyncio.Task[None] | None = None
    active_audio_started = False
    stt_task: asyncio.Task[None] | None = None
    audio_queue: asyncio.Queue[bytes | None] | None = None
    audio_started_at: float | None = None
    stt_commit_at: float | None = None
    stt_commit_signal = asyncio.Event()
    stt_speech_started_at: float | None = None
    stt_turn_active = False
    stt_latest_transcript = ""
    stt_final_segments: list[STTEvent] = []
    stt_auto_recovered = False
    response_id = 0
    active_tts_started = False
    business_lock = asyncio.Lock()
    turn_tasks: set[asyncio.Task[None]] = set()
    ending_audio_queues: set[int] = set()

    async def send_turn(payload: dict[str, object], turn_id: int) -> None:
        if turn_id == response_id:
            await websocket.send_json({**payload, "response_id": turn_id})

    async def send_transcription_recovery(
        recovery_source: Literal["timeout", "low_confidence"],
        transcript: str | None = None,
    ) -> bool:
        """Speak a live retry prompt when STT cannot safely confirm the utterance."""
        nonlocal response_id, active_audio_started
        recovery_text = transcription_recovery_prompt(response_language, transcript)
        if recovery_text is None:
            return False

        response_id += 1
        turn_id = response_id
        stream = pipeline_synthesize_clauses(
            session_tts,
            recovery_text,
            language=response_language,
            enabled=False,
        )
        iterator = stream.__aiter__()
        deadline = time.perf_counter() + settings.voice_tts_first_audio_timeout_seconds
        sent_audio = False
        response_sent = False
        sequence = 0
        try:
            while turn_id == response_id:
                try:
                    chunk = await asyncio.wait_for(
                        anext(iterator), timeout=max(0.0, deadline - time.perf_counter())
                    )
                except StopAsyncIteration:
                    break
                if turn_id != response_id:
                    return True
                if chunk.audio:
                    if not response_sent:
                        await send_turn(
                            {
                                "type": "agent_response",
                                "decision": {
                                    "kind": "ask_clarification",
                                    "spoken_text": recovery_text,
                                    "property_ids": [],
                                    "source_ids": [],
                                    "reason": "transcription_incomplete",
                                },
                            },
                            turn_id,
                        )
                        response_sent = True
                    sent_audio = True
                    active_audio_started = True
                    deadline = time.perf_counter() + settings.voice_tts_idle_timeout_seconds
                if chunk.audio or chunk.is_final:
                    await send_turn(
                        {
                            "type": "audio_chunk",
                            "sequence": sequence,
                            "language": chunk.language,
                            "sample_rate": chunk.sample_rate,
                            "encoding": chunk.encoding,
                            "audio_base64": base64.b64encode(chunk.audio).decode("ascii"),
                            "is_final": chunk.is_final,
                        },
                        turn_id,
                    )
                    if chunk.audio:
                        sequence += 1
        except (TimeoutError, TTSProviderError):
            if turn_id != response_id:
                return True
            traces.increment(f"voice:stt_{recovery_source}_recovery_tts_failed")
            return False
        finally:
            close = getattr(stream, "aclose", None)
            if close is not None:
                try:
                    await close()
                except Exception:  # noqa: BLE001 - a recovery stream is best-effort
                    traces.increment("voice:stt_timeout_recovery_cleanup_failed")

        if sent_audio and turn_id == response_id:
            traces.increment(f"voice:stt_{recovery_source}_spoken_recovery")
            await send_turn({"type": "state", "state": "listening"}, turn_id)
            return True
        return turn_id != response_id

    def launch_turn(text: str, language: str, received_at: float) -> asyncio.Task[None]:
        nonlocal response_id, active_audio_started, active_tts_started
        response_id += 1
        active_audio_started = False
        active_tts_started = False
        task = asyncio.create_task(process_turn(text, language, received_at, response_id))
        turn_tasks.add(task)
        task.add_done_callback(turn_tasks.discard)
        return task

    async def process_turn(text: str, language: str, turn_received_at: float, turn_id: int) -> None:
        nonlocal appointment_reference, active_audio_started, active_tts_started
        started = time.perf_counter()
        await send_turn({"type": "state", "state": "thinking"}, turn_id)
        try:
            async with business_lock:
                if turn_id != response_id:
                    return
                decision = await asyncio.to_thread(agent.respond, conversation_id, text, language)
                if turn_id != response_id:
                    return
                if decision.kind == "recommend":
                    presented_property_ids[:] = decision.property_ids
                conversation_state = agent.states.get(conversation_id)
                selected_ids = presented_property_ids or (
                    conversation_state.selected_property_ids if conversation_state else []
                )
                booking_result = await asyncio.to_thread(
                    booking_flow.handle,
                    text,
                    decision,
                    selected_ids,
                    booking_contact,
                    conversation_id,
                    "; ".join(
                        f"{name}: {value}"
                        for name, value in (
                            ("City", conversation_state.city),
                            ("Area", conversation_state.area),
                            ("Budget PKR", conversation_state.budget),
                            ("Bedrooms", conversation_state.bedrooms),
                            ("Size sqft", conversation_state.target_size_sqft),
                            ("Amenities", ", ".join(conversation_state.amenities)),
                            ("Investment goal", conversation_state.investment_goal),
                        )
                        if value is not None and value != ""
                    ) if conversation_state else "",
                )
                if booking_result is not None:
                    decision = booking_result.decision
                    if not decision.property_ids:
                        decision = decision.model_copy(
                            update={
                                "property_ids": [booking_flow.property_id]
                                if booking_flow.property_id
                                else booking_flow.property_choices
                            }
                        )
                    if booking_flow.phase in {"slots", "manage_slots"}:
                        await send_turn(
                            {
                                "type": "booking_slots",
                                "property_id": booking_flow.property_id,
                                "slots": [slot.isoformat() for slot in booking_flow.slots[:3]],
                            }, turn_id
                        )
                    if booking_result.appointment is not None:
                        appointment_reference = booking_result.appointment.get("reference")
                        await send_turn(
                            {"type": "appointment_result", **booking_result.appointment}, turn_id
                        )
                await asyncio.to_thread(transcripts.append, conversation_id, "user", text)
                await asyncio.to_thread(
                    transcripts.append, conversation_id, "assistant", decision.spoken_text
                )
        except Exception:  # noqa: BLE001 - voice sessions must fail closed and remain usable
            traces.increment("provider_failure:agent")
            await send_turn(
                {"type": "agent_unavailable", "reason": "agent_turn_failed", "recoverable": True}, turn_id
            )
            await send_turn({"type": "state", "state": "listening"}, turn_id)
            return
        if turn_id != response_id:
            return
        decision_latency_ms = (time.perf_counter() - started) * 1000
        traces.observe("voice.decision_latency_ms", decision_latency_ms)
        emotion = (
            infer_acoustic_emotion(
                text=text,
                decision_kind=decision.kind,
                intent=conversation_state.intent.value if conversation_state else None,
                response_text=decision.spoken_text,
            )
            if settings.voice_emotion_matching_enabled
            else None
        )
        reasoning = _structured_reasoning_status()
        response_payload: dict[str, object] = {
            "type": "agent_response",
            "decision": decision.model_dump(),
            "latency_ms": round(decision_latency_ms, 2),
            "reasoning_status": reasoning["status"],
            "reasoning_failure_category": reasoning["last_failure_category"],
        }
        if emotion is not None:
            response_payload["emotion"] = emotion.as_dict()
        await send_turn(response_payload, turn_id)
        first_audio_recorded = False
        end_to_first_audio_recorded = False
        tts_started_at = time.perf_counter()
        stream = None
        active_tts_started = True
        try:
            primary_stream = pipeline_synthesize_clauses(
                session_tts,
                decision.spoken_text,
                language=language,
                emotion=emotion,
                enabled=settings.voice_early_clause_streaming_enabled,
            )

            async def fallback_to_http_tts_if_needed() -> AsyncIterator[AudioChunk]:
                try:
                    async for audio_chunk in primary_stream:
                        yield audio_chunk
                except TTSProviderError:
                    if session_realtime_tts is None or first_audio_recorded:
                        raise
                    traces.increment("voice:realtime_tts_fallback")
                    fallback_stream = pipeline_synthesize_clauses(
                        openai_voice_tts,
                        decision.spoken_text,
                        language=language,
                        emotion=emotion,
                        enabled=settings.voice_early_clause_streaming_enabled,
                    )
                    try:
                        async for audio_chunk in fallback_stream:
                            yield audio_chunk
                    except TTSProviderError as openai_error:
                        if voice_mode != "hybrid":
                            raise
                        traces.increment("voice:configured_tts_fallback")
                        configured_stream = pipeline_synthesize_clauses(
                            tts,
                            decision.spoken_text,
                            language=language,
                            emotion=emotion,
                            enabled=settings.voice_early_clause_streaming_enabled,
                        )
                        try:
                            async for audio_chunk in configured_stream:
                                yield audio_chunk
                        except TTSProviderError as configured_error:
                            raise configured_error from openai_error

            stream = fallback_to_http_tts_if_needed()
            next_audio_deadline = time.perf_counter() + settings.voice_tts_first_audio_timeout_seconds
            while True:
                try:
                    chunk = await asyncio.wait_for(
                        anext(stream), timeout=max(0.0, next_audio_deadline - time.perf_counter())
                    )
                except StopAsyncIteration:
                    break
                if turn_id != response_id:
                    return
                if chunk.audio:
                    next_audio_deadline = time.perf_counter() + settings.voice_tts_idle_timeout_seconds
                if chunk.audio and not first_audio_recorded:
                    active_audio_started = True
                    audio_ready_at = time.perf_counter()
                    traces.observe(
                        "voice.first_audio_latency_ms", (audio_ready_at - started) * 1000
                    )
                    traces.observe(
                        "voice.tts_first_audio_latency_ms",
                        (audio_ready_at - tts_started_at) * 1000,
                    )
                    first_audio_recorded = True
                await send_turn(
                    {
                        "type": "audio_chunk",
                        "sequence": chunk.sequence,
                        "language": chunk.language,
                        "sample_rate": chunk.sample_rate,
                        "encoding": chunk.encoding,
                        "audio_base64": base64.b64encode(chunk.audio).decode("ascii"),
                        "is_final": chunk.is_final,
                    }, turn_id
                )
                if chunk.audio and not end_to_first_audio_recorded:
                    traces.observe(
                        "voice.final_transcript_to_first_audio_ms",
                        (time.perf_counter() - turn_received_at) * 1000,
                    )
                    end_to_first_audio_recorded = True
            if not first_audio_recorded:
                await send_turn({"type": "audio_unavailable", "reason": "tts_empty_audio", "recoverable": True}, turn_id)
        except TimeoutError:
            reason = "tts_idle_timeout" if first_audio_recorded else "tts_first_audio_timeout"
            traces.increment(f"provider_failure:{reason}")
            await send_turn({"type": "audio_unavailable", "reason": reason, "recoverable": True}, turn_id)
        except TTSProviderError as error:
            traces.increment("provider_failure:tts")
            failure_code = _voice_tts_failure_code(error)
            if failure_code == "rate_limited" and realtime_tts_failure_code == "insufficient_credits":
                failure_code = realtime_tts_failure_code
            traces.increment(f"provider_failure:tts_{failure_code}")
            await send_turn(
                {
                    "type": "audio_unavailable",
                    "reason": f"tts_{failure_code}",
                    "recoverable": failure_code != "insufficient_credits",
                },
                turn_id,
            )
        except Exception as error:  # noqa: BLE001 - provider diagnostics must not leak through the voice protocol
            traces.increment("provider_failure:tts")
            traces.increment(f"provider_failure:tts_unexpected_{type(error).__name__}")
            await send_turn({"type": "audio_unavailable", "reason": "tts_provider_error", "recoverable": True}, turn_id)
        finally:
            if stream is not None:
                try:
                    await asyncio.wait_for(stream.aclose(), settings.voice_tts_idle_timeout_seconds)
                except Exception:  # noqa: BLE001 - generator cleanup is best effort
                    traces.increment("provider_failure:tts_cleanup")
            traces.observe(
                "voice.tts_stream_duration_ms", (time.perf_counter() - tts_started_at) * 1000
            )
        await send_turn({"type": "state", "state": "listening"}, turn_id)

    def cancel_active(*, only_after_audio: bool = False) -> float | None:
        nonlocal response_id
        if only_after_audio and not active_audio_started:
            return None
        response_id += 1
        if active_task is None or active_task.done():
            return None
        cancel_started = time.perf_counter()
        # Let already-running reasoning/business writes settle under their lock.
        # A stale turn checks its generation before executing booking or speaking.
        if active_tts_started:
            active_task.cancel()
        return cancel_started

    async def audio_stream(queue: asyncio.Queue[bytes | None]) -> AsyncIterator[bytes]:
        while True:
            chunk = await queue.get()
            if chunk is None:
                return
            yield chunk

    async def bounded_stt_events(
        queue: asyncio.Queue[bytes | None],
        audio: AsyncIterator[bytes],
    ) -> AsyncIterator[STTEvent]:
        """Bound commits and assemble Deepgram's stable transcript segments per turn."""
        stream = session_stt.stream(audio)
        iterator = stream.__aiter__()
        read_task: asyncio.Task[STTEvent] | None = None
        commit_task: asyncio.Task[bool] | None = None
        buffered_events: deque[STTEvent] = deque()

        async def await_finalized_read(
            pending_read: asyncio.Task[STTEvent], timeout: float
        ) -> STTEvent:
            done, _ = await asyncio.wait({pending_read}, timeout=timeout)
            if done:
                return pending_read.result()
            # Stop further provider input and let the adapter complete its
            # normal finalize/close sequence before considering cancellation.
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:
                pass
            pending_read.cancel()
            done, _ = await asyncio.wait({pending_read}, timeout=0.2)
            if not done:
                pending_read.add_done_callback(_consume_background_task_result)
            raise STTFinalizeTimeout

        async def coalesce_final_segments(first: STTEvent) -> STTEvent:
            """Join stable segments until Deepgram marks the end or the stream goes quiet."""
            nonlocal read_task
            segments = [first]
            interim_events: list[STTEvent] = []
            trailing_events: list[STTEvent] = []
            if first.speech_final or first.from_finalize:
                return first
            quiet_deadline = time.perf_counter() + STT_FINAL_SEGMENT_QUIET_SECONDS
            while True:
                if read_task is None:
                    read_task = asyncio.create_task(anext(iterator))
                quiet_remaining = quiet_deadline - time.perf_counter()
                finalize_remaining = (
                    stt_commit_at
                    + settings.stt_finalize_timeout_seconds
                    - time.perf_counter()
                    if stt_commit_at is not None
                    else 0.0
                )
                if finalize_remaining <= 0:
                    await await_finalized_read(read_task, 0.0)
                wait_for = min(quiet_remaining, finalize_remaining)
                if wait_for <= 0:
                    break
                done, _ = await asyncio.wait({read_task}, timeout=wait_for)
                if not done:
                    if finalize_remaining <= quiet_remaining:
                        await await_finalized_read(read_task, 0.0)
                    break
                try:
                    candidate = read_task.result()
                except StopAsyncIteration:
                    read_task = None
                    break
                read_task = None
                if candidate.is_final and candidate.text:
                    segments.append(candidate)
                    if candidate.speech_final or candidate.from_finalize:
                        break
                    quiet_deadline = time.perf_counter() + STT_FINAL_SEGMENT_QUIET_SECONDS
                elif candidate.text and not candidate.speech_started:
                    interim_events.append(candidate)
                else:
                    trailing_events.append(candidate)
                    if candidate.speech_started:
                        break

            if len(segments) == 1:
                combined = first
            else:
                traces.increment("stt:final_segments_coalesced")
                confidences = [
                    segment.confidence
                    for segment in segments
                    if segment.confidence is not None
                ]
                language = next(
                    (
                        segment.language
                        for segment in reversed(segments)
                        if segment.language != "und"
                    ),
                    first.language,
                )
                combined = STTEvent(
                    text=" ".join(segment.text for segment in segments).strip(),
                    language=language,
                    confidence=min(confidences) if confidences else None,
                    is_final=True,
                    speech_final=any(segment.speech_final for segment in segments),
                    from_finalize=any(segment.from_finalize for segment in segments),
                )
            if interim_events or trailing_events:
                buffered_events.extend(interim_events)
                buffered_events.append(combined)
                buffered_events.extend(trailing_events)
                return buffered_events.popleft()
            return combined

        try:
            while True:
                if voice_mode != "hybrid":
                    try:
                        yield await anext(iterator)
                    except StopAsyncIteration:
                        return
                    continue
                if buffered_events:
                    event = buffered_events.popleft()
                else:
                    if read_task is None:
                        read_task = asyncio.create_task(anext(iterator))
                    assert read_task is not None
                    try:
                        if stt_commit_at is None:
                            commit_task = asyncio.create_task(stt_commit_signal.wait())
                            done, _ = await asyncio.wait(
                                {read_task, commit_task},
                                return_when=asyncio.FIRST_COMPLETED,
                            )
                            if read_task not in done:
                                # The browser commit owns the turn boundary. Give the
                                # provider time remaining in the committed-turn budget
                                # to return a stable transcript.
                                remaining = (
                                    stt_commit_at
                                    + settings.stt_finalize_timeout_seconds
                                    - time.perf_counter()
                                    if stt_commit_at is not None
                                    else settings.stt_finalize_timeout_seconds
                                )
                                event = await await_finalized_read(
                                    read_task,
                                    max(0.0, remaining),
                                )
                            else:
                                event = read_task.result()
                        else:
                            remaining = (
                                stt_commit_at
                                + settings.stt_finalize_timeout_seconds
                                - time.perf_counter()
                            )
                            event = await await_finalized_read(read_task, max(0.0, remaining))
                    except StopAsyncIteration:
                        return
                    finally:
                        if commit_task is not None:
                            commit_task.cancel()
                            await asyncio.gather(commit_task, return_exceptions=True)
                            commit_task = None
                    read_task = None
                    if (
                        event.is_final
                        and event.text
                        and stt_turn_active
                        and stt_commit_at is None
                    ):
                        commit_wait_started = time.perf_counter()
                        traces.increment("stt:provider_final_before_browser_commit")
                        try:
                            await asyncio.wait_for(
                                stt_commit_signal.wait(),
                                timeout=min(2.0, settings.stt_finalize_timeout_seconds),
                            )
                        except TimeoutError:
                            pass
                        finally:
                            traces.observe(
                                "voice.stt_final_to_browser_commit_wait_ms",
                                (time.perf_counter() - commit_wait_started) * 1000,
                            )
                    if (
                        event.is_final
                        and event.text
                        and stt_commit_at is not None
                    ):
                        event = await coalesce_final_segments(event)
                yield event
        finally:
            if commit_task is not None and not commit_task.done():
                commit_task.cancel()
            if read_task is not None and not read_task.done():
                read_task.cancel()
            pending = [task for task in (commit_task, read_task) if task is not None]
            if pending:
                done, still_running = await asyncio.wait(pending, timeout=0.25)
                if done:
                    await asyncio.gather(*done, return_exceptions=True)
                if still_running:
                    for task in still_running:
                        task.add_done_callback(_consume_background_task_result)

    async def consume_stt(queue: asyncio.Queue[bytes | None]) -> None:
        nonlocal active_task, active_audio_started, audio_started_at, audio_queue
        nonlocal stt_commit_at, stt_speech_started_at, stt_turn_active
        nonlocal stt_transport_failure_reason, stt_latest_transcript, stt_final_segments
        failure_reason = "stt_stream_ended"
        completed_turns = 0
        recovery_delivered = False
        audio_cursor_seconds = 0.0

        async def counted_audio_stream() -> AsyncIterator[bytes]:
            nonlocal audio_cursor_seconds
            async for frame in audio_stream(queue):
                if frame:
                    audio_cursor_seconds += len(frame) / (2 * settings.stt_sample_rate)
                yield frame

        try:
            async for event in bounded_stt_events(queue, counted_audio_stream()):
                if (
                    isinstance(session_stt, DeepgramStreamingSTT)
                    and event.text
                ):
                    cursor_lag_ms = estimated_transcript_lag_ms(
                        audio_cursor_seconds, event
                    )
                    if cursor_lag_ms is not None:
                        traces.observe("voice.stt_audio_cursor_lag_ms", cursor_lag_ms)
                if event.text and stt_turn_active:
                    if event.is_final:
                        stt_final_segments.append(event)
                        stt_latest_transcript = " ".join(
                            segment.text for segment in stt_final_segments
                        ).strip()
                    else:
                        stt_latest_transcript = " ".join(
                            [
                                *(segment.text for segment in stt_final_segments),
                                event.text,
                            ]
                        ).strip()
                assembled_transcript = " ".join(
                    segment.text for segment in stt_final_segments
                ).strip()
                assembled_confidences = [
                    segment.confidence
                    for segment in stt_final_segments
                    if segment.confidence is not None
                ]
                turn_transcript = assembled_transcript or event.text
                turn_confidence = (
                    min(assembled_confidences) if assembled_confidences else event.confidence
                )
                browser_committed_final = event.is_final and stt_commit_at is not None
                # Provider endpointing can produce a stable final before
                # browser VAD commits. Surface it, but do not end the turn yet.
                turn_final = _is_turn_final(voice_mode, event, stt_commit_at is not None)
                if event.is_final:
                    traces.increment("stt:segment_final")
                if event.speech_final:
                    traces.increment("stt:speech_final")
                if event.from_finalize:
                    traces.increment("stt:from_finalize")
                if browser_committed_final:
                    traces.increment("stt:browser_commit_final")
                if event.speech_started:
                    stt_speech_started_at = time.perf_counter()
                    # Provider speech-start notifications can arrive after a
                    # browser-committed final. Only the browser's active speech
                    # turn is allowed to interrupt an assistant response.
                    interrupt_playback = stt_turn_active
                    cancel_started = cancel_active() if interrupt_playback else None
                    state_event: dict[str, object] = {
                        "type": "state",
                        "state": "listening",
                        "response_id": response_id,
                    }
                    if interrupt_playback:
                        state_event["interrupt_playback"] = True
                    await websocket.send_json(state_event)
                    if cancel_started is not None:
                        traces.observe(
                            "voice.barge_in_cancel_latency_ms",
                            (time.perf_counter() - cancel_started) * 1000,
                        )
                if event.text:
                    if event.confidence is not None:
                        traces.observe("voice.stt_confidence", event.confidence)
                    await websocket.send_json(
                        {
                            "type": "transcript",
                            "text": turn_transcript if event.is_final else event.text,
                            "language": event.language,
                            "confidence": event.confidence,
                            "is_final": event.is_final,
                            # The browser owns the boundary on explicit-commit
                            # routes. Deepgram may return a stable is_final
                            # segment without setting either optional marker.
                            "speech_final": turn_final,
                        }
                    )
                # Explicit-commit routes use browser VAD as the turn boundary.
                # Deepgram's stable segments are coalesced after the browser commit;
                # its optional speech_final/from_finalize flags remain provider metadata.
                if event.is_final and turn_final and event.text:
                    completed_turns += 1
                    stt_turn_active = False
                    if stt_commit_at is not None:
                        traces.observe(
                            "voice.stt_commit_to_final_ms",
                            (time.perf_counter() - stt_commit_at) * 1000,
                        )
                        stt_commit_at = None
                        stt_commit_signal.clear()
                    if stt_speech_started_at is not None:
                        traces.observe(
                            "voice.stt_speech_to_final_transcript_ms",
                            (time.perf_counter() - stt_speech_started_at) * 1000,
                        )
                        stt_speech_started_at = None
                    if audio_started_at is not None:
                        traces.observe(
                            "voice.stt_turn_latency_ms",
                            (time.perf_counter() - audio_started_at) * 1000,
                        )
                        audio_started_at = None
                    if (
                        turn_confidence is not None
                        and turn_confidence < settings.stt_min_confidence
                    ):
                        traces.increment("stt:low_confidence")
                        await websocket.send_json(
                            {
                                "type": "transcript_low_confidence",
                                "text": turn_transcript,
                                "confidence": turn_confidence,
                            }
                        )
                        spoken_recovery = await send_transcription_recovery(
                            "low_confidence", turn_transcript
                        )
                        stt_final_segments.clear()
                        stt_latest_transcript = ""
                        if not spoken_recovery:
                            await send_turn(
                                {"type": "audio_unavailable", "reason": "tts_provider_unavailable"},
                                response_id,
                            )
                        continue
                    cancel_started = cancel_active()
                    turn_received_at = time.perf_counter()
                    active_audio_started = False
                    stt_final_segments.clear()
                    stt_latest_transcript = ""
                    active_task = launch_turn(
                        turn_transcript,
                        response_language,
                        turn_received_at,
                    )
                    if cancel_started is not None:
                        traces.observe(
                            "voice.barge_in_cancel_latency_ms",
                            (time.perf_counter() - cancel_started) * 1000,
                        )
        except asyncio.CancelledError:
            raise
        except STTFinalizeTimeout:
            committed_at = stt_commit_at
            stt_commit_at = None
            stt_commit_signal.clear()
            stt_speech_started_at = None
            failure_reason = "stt_finalize_timeout"
            traces.increment("provider_failure:stt_finalize_timeout")
            if committed_at is not None:
                traces.observe(
                    "voice.stt_finalize_timeout_ms",
                    (time.perf_counter() - committed_at) * 1000,
                )
            # Make the failed stream replaceable while the recovery prompt is
            # speaking; a caller who barges in can start a fresh STT stream.
            if audio_queue is queue:
                audio_queue = None
            recovery_delivered = await send_transcription_recovery(
                "timeout", stt_latest_transcript or None
            )
        except Exception as error:  # noqa: BLE001 - map adapter errors to a recoverable state
            provider_error_code = stt_provider_error_code(error)
            failure_reason = (
                f"stt_{provider_error_code}"
                if provider_error_code != "provider_unavailable"
                else "stt_provider_error"
            )
            traces.increment("provider_failure:stt")
            traces.increment(f"provider_failure:stt:{provider_error_code}")
            traces.increment(f"provider_failure:stt_exception:{type(error).__name__}")
        finally:
            if (
                isinstance(session_stt, DeepgramStreamingSTT)
                and not stt_transport_ready.is_set()
                and not asyncio.current_task().cancelling()
            ):
                stt_transport_failure_reason = failure_reason
                stt_transport_failed.set()
            expected_end = id(queue) in ending_audio_queues
            ending_audio_queues.discard(id(queue))
            superseded_by_new_stream = audio_queue is not None and audio_queue is not queue
            if audio_queue is queue:
                audio_queue = None
            stream_failed = failure_reason != "stt_stream_ended"
            # This queue belongs to one STT stream. A later browser turn may
            # already have marked the shared turn flag active, but that must
            # not turn this completed stream's idle close into a user error.
            completed_stream_turn = completed_turns > 0
            should_report_failure = (
                (not expected_end or stream_failed)
                and not completed_stream_turn
                and not recovery_delivered
                and not superseded_by_new_stream
                and not stt_startup_in_progress
            )
            if should_report_failure and not asyncio.current_task().cancelling():
                stt_turn_active = False
                await websocket.send_json({
                    "type": "stt_unavailable", "reason": failure_reason,
                    "recoverable": _stt_failure_is_recoverable(failure_reason),
                    "restart_required": True,
                })

    async def start_stt_stream() -> bool:
        """Open an STT stream and wait for the Deepgram socket handshake."""
        nonlocal audio_queue, stt_task, audio_started_at, stt_transport_failure_reason
        nonlocal stt_startup_in_progress
        if stt_task is not None and not stt_task.done() and audio_queue is not None:
            return not isinstance(session_stt, DeepgramStreamingSTT) or stt_transport_ready.is_set()

        if not isinstance(session_stt, DeepgramStreamingSTT):
            queue: asyncio.Queue[bytes | None] = asyncio.Queue(
                maxsize=settings.voice_audio_queue_frames
            )
            audio_queue = queue
            audio_started_at = time.perf_counter()
            stt_task = asyncio.create_task(consume_stt(queue))
            return True

        started_at = time.perf_counter()
        deadline = started_at + settings.stt_transport_timeout_seconds
        max_attempts = 2
        stt_startup_in_progress = True
        for attempt in range(max_attempts):
            attempt_started_at = time.perf_counter()
            stt_transport_ready.clear()
            stt_transport_failed.clear()
            stt_transport_failure_reason = "stt_provider_unavailable"
            queue: asyncio.Queue[bytes | None] = asyncio.Queue(
                maxsize=settings.voice_audio_queue_frames
            )
            audio_queue = queue
            audio_started_at = time.perf_counter()
            task = asyncio.create_task(consume_stt(queue))
            stt_task = task

            ready_waiter = asyncio.create_task(stt_transport_ready.wait())
            failed_waiter = asyncio.create_task(stt_transport_failed.wait())
            try:
                await asyncio.wait(
                    (ready_waiter, failed_waiter),
                    timeout=max(0.0, deadline - time.perf_counter()),
                    return_when=asyncio.FIRST_COMPLETED,
                )
            finally:
                for waiter in (ready_waiter, failed_waiter):
                    if not waiter.done():
                        waiter.cancel()
                await asyncio.gather(ready_waiter, failed_waiter, return_exceptions=True)

            attempt_ms = (time.perf_counter() - attempt_started_at) * 1000
            if stt_transport_ready.is_set():
                stt_startup_in_progress = False
                traces.observe(
                    "voice.stt_transport_warmup_ms",
                    (time.perf_counter() - started_at) * 1000,
                )
                traces.observe("voice.stt_transport_attempt_ms", attempt_ms)
                traces.increment("voice:stt_transport_ready")
                return True

            timed_out = not stt_transport_failed.is_set()
            if timed_out:
                stt_transport_failure_reason = "stt_provider_timeout"
                traces.increment("voice:stt_transport_warmup_timeout")
            else:
                traces.increment("voice:stt_transport_warmup_failed")
            traces.observe("voice.stt_transport_attempt_ms", attempt_ms)

            if audio_queue is queue:
                audio_queue = None
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

            # Retry one quickly rejected Deepgram connection within the original
            # startup deadline. A socket that hangs or a permanent provider error
            # must not extend microphone startup or be retried.
            if (
                attempt == 0
                and not timed_out
                and stt_transport_failure_reason == "stt_provider_timeout"
                and time.perf_counter() < deadline
            ):
                traces.increment("voice:stt_transport_retry")
                await asyncio.sleep(min(0.05, max(0.0, deadline - time.perf_counter())))
                continue
            stt_startup_in_progress = False
            return False

        stt_startup_in_progress = False
        return False

    try:
        # Only advertise microphone readiness after the Deepgram transport
        # is actually open; is_ready() validates configuration, not a socket.
        if stt_available and isinstance(session_stt, DeepgramStreamingSTT):
            stt_available = await start_stt_stream()
            if not stt_available:
                stt_warmup_failed = True
                stt_warmup_reason = stt_transport_failure_reason
        await websocket.send_json(
            {
                "type": "state",
                "state": "listening" if stt_available else "error",
                "audio_input_available": stt_available,
            }
        )
        if stt_warmup_failed:
            await websocket.send_json(
                {"type": "stt_unavailable", "reason": stt_warmup_reason}
            )

        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                traces.increment("voice:websocket_disconnect_received")
                break
            if message.get("bytes") is not None:
                if not stt_available:
                    await websocket.send_json(
                        {"type": "stt_unavailable", "reason": "Streaming STT is not configured"}
                    )
                else:
                    # A provider stream can end between utterances even though the
                    # browser capture is still live. Recover on the next frame so
                    # a single frame cannot turn a transient disconnect into a
                    # terminal client-side STT error.
                    if audio_queue is None:
                        if not await start_stt_stream():
                            await websocket.send_json(
                                {
                                    "type": "stt_unavailable",
                                    "reason": stt_transport_failure_reason,
                                    "recoverable": _stt_failure_is_recoverable(stt_transport_failure_reason),
                                    "restart_required": True,
                                }
                            )
                            continue
                        stt_auto_recovered = True
                        traces.increment("voice:stt_auto_recovered")
                        await websocket.send_json(
                            {
                                "type": "state",
                                "state": "listening",
                                "audio_started": True,
                                "audio_recovered": True,
                            }
                        )
                    frame = message["bytes"]
                    if len(frame) > settings.voice_max_audio_frame_bytes or len(frame) % 2:
                        await websocket.close(code=1009, reason="Invalid or oversized PCM16 frame")
                        break
                    try:
                        audio_queue.put_nowait(frame)
                    except asyncio.QueueFull:
                        traces.increment("voice:audio_queue_overflow")
                        await websocket.close(code=1013, reason="Audio input queue is full")
                        break
                continue
            raw_text = message.get("text")
            if not raw_text:
                await websocket.send_json(
                    {"type": "error", "message": "Expected a JSON voice event"}
                )
                continue
            if len(raw_text.encode("utf-8")) > settings.voice_max_event_bytes:
                await websocket.close(code=1009, reason="Voice event is too large")
                break
            try:
                event = json.loads(raw_text)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON voice event"})
                continue
            if not isinstance(event, dict) or not isinstance(event.get("type"), str):
                await websocket.send_json(
                    {"type": "error", "message": "Voice event must be a JSON object with a type"}
                )
                continue
            if event.get("type") == "booking_contact":
                contact_value = event.get("contact")
                if contact_value is None:
                    booking_contact = None
                    await websocket.send_json({"type": "booking_contact_status", "ready": False})
                    continue
                try:
                    booking_contact = AppointmentContactContext.model_validate(contact_value)
                except (ValidationError, TypeError):
                    booking_contact = None
                    await websocket.send_json({"type": "booking_contact_status", "ready": False})
                    continue
                await websocket.send_json({"type": "booking_contact_status", "ready": True})
                continue
            if event.get("type") == "audio_start":
                if not stt_available:
                    await websocket.send_json(
                        {"type": "stt_unavailable", "reason": "Streaming STT is not configured"}
                    )
                    continue
                if stt_auto_recovered and audio_queue is not None and stt_task is not None and not stt_task.done():
                    # The browser's scheduled retry may arrive after the next
                    # microphone frame already restarted STT. Treat that retry
                    # as an acknowledgement instead of interrupting the new stream.
                    stt_auto_recovered = False
                    await websocket.send_json(
                        {"type": "state", "state": "listening", "audio_started": True}
                    )
                    continue
                if (
                    isinstance(session_stt, DeepgramStreamingSTT)
                    and audio_queue is not None
                    and stt_task is not None
                    and not stt_task.done()
                    and stt_transport_ready.is_set()
                ):
                    stt_auto_recovered = False
                    audio_started_at = time.perf_counter()
                    await websocket.send_json(
                        {"type": "state", "state": "listening", "audio_started": True}
                    )
                    continue
                stt_auto_recovered = False
                if stt_task is not None and not stt_task.done():
                    if audio_queue is not None:
                        try:
                            audio_queue.put_nowait(None)
                        except asyncio.QueueFull:
                            await websocket.close(code=1013, reason="Audio input queue is full")
                            break
                    stt_task.cancel()
                    await asyncio.gather(stt_task, return_exceptions=True)
                if not await start_stt_stream():
                    await websocket.send_json(
                        {
                            "type": "stt_unavailable",
                            "reason": stt_transport_failure_reason,
                            "recoverable": _stt_failure_is_recoverable(stt_transport_failure_reason),
                            "restart_required": True,
                        }
                    )
                    continue
                await websocket.send_json(
                    {"type": "state", "state": "listening", "audio_started": True}
                )
                continue
            if event.get("type") == "audio_end":
                if audio_queue is not None:
                    ending_audio_queues.add(id(audio_queue))
                    if voice_mode == "openai":
                        try:
                            audio_queue.put_nowait(b"")
                        except asyncio.QueueFull:
                            traces.increment("voice:audio_queue_overflow")
                    try:
                        audio_queue.put_nowait(None)
                    except asyncio.QueueFull:
                        traces.increment("voice:audio_queue_overflow")
                        await websocket.close(code=1013, reason="Audio input queue is full")
                        break
                await websocket.send_json({"type": "state", "state": "processing"})
                continue
            if event.get("type") == "audio_turn_start":
                stt_turn_active = True
                stt_latest_transcript = ""
                stt_final_segments.clear()
                stt_commit_at = None
                stt_commit_signal.clear()
                # Usually the conversation keeps the same Deepgram socket
                # across turns. If it ended after provider inactivity or a
                # recoverable error, reconnect as soon as speech starts so the
                # handshake overlaps caller audio.
                if voice_mode == "hybrid" and stt_available and audio_queue is None:
                    if not await start_stt_stream():
                        await websocket.send_json(
                            {
                                "type": "stt_unavailable",
                                "reason": stt_transport_failure_reason,
                                "recoverable": _stt_failure_is_recoverable(stt_transport_failure_reason),
                                "restart_required": True,
                            }
                        )
                        stt_turn_active = False
                        continue
                    traces.increment("voice:stt_preconnected_on_turn_start")
                elif audio_queue is not None:
                    audio_started_at = time.perf_counter()
                if voice_mode == "openai" and audio_queue is not None:
                    try:
                        audio_queue.put_nowait(b"\x00")
                    except asyncio.QueueFull:
                        await websocket.close(code=1013, reason="Audio input queue is full")
                        break
                cancel_started = cancel_active()
                await websocket.send_json(
                    {
                        "type": "state",
                        "state": "listening",
                        "interrupt_playback": True,
                            "response_id": response_id,
                    }
                )
                if cancel_started is not None:
                    traces.observe(
                        "voice.barge_in_cancel_latency_ms",
                        (time.perf_counter() - cancel_started) * 1000,
                    )
                continue
            if event.get("type") == "audio_turn_end":
                await websocket.send_json({"type": "state", "state": "processing"})
                if audio_queue is not None:
                    # Commit the caller audio before sending acknowledgement output.
                    # The STT consumer then finalizes in parallel with playback,
                    # rather than waiting for the outbound audio path to drain.
                    stt_commit_at = time.perf_counter()
                    stt_commit_signal.set()
                    try:
                        audio_queue.put_nowait(b"")
                        traces.increment("stt:browser_commit_sent")
                    except asyncio.QueueFull:
                        await websocket.close(code=1013, reason="Audio input queue is full")
                        break
                if (
                    prepared_acknowledgement
                    and prepared_acknowledgement_language == response_language
                ):
                    acknowledgement_turn_id = response_id
                    acknowledgement_started = time.perf_counter()
                    sent_ack_audio = False
                    for sequence, chunk in enumerate(prepared_acknowledgement):
                        if acknowledgement_turn_id != response_id:
                            break
                        if not chunk.audio:
                            continue
                        await send_turn(
                            {
                                "type": "audio_chunk",
                                "sequence": sequence,
                                "language": chunk.language,
                                "sample_rate": chunk.sample_rate,
                                "encoding": chunk.encoding,
                                "audio_base64": base64.b64encode(chunk.audio).decode("ascii"),
                                "is_final": False,
                                "acknowledgement": True,
                            },
                            acknowledgement_turn_id,
                        )
                        if not sent_ack_audio:
                            traces.observe(
                                "voice.vad_end_to_acknowledgement_audio_ms",
                                (time.perf_counter() - acknowledgement_started) * 1000,
                            )
                            sent_ack_audio = True
                continue
            if event.get("type") == "barge_in":
                cancel_started = cancel_active()
                await websocket.send_json(
                    {
                        "type": "state",
                        "state": "listening",
                        "interrupt_playback": True,
                            "response_id": response_id,
                    }
                )
                if cancel_started is not None:
                    traces.observe(
                        "voice.barge_in_cancel_latency_ms",
                        (time.perf_counter() - cancel_started) * 1000,
                    )
                continue
            if event.get("type") == "set_language":
                language_value = event.get("language")
                if (
                    not isinstance(language_value, str)
                    or language_value not in SUPPORTED_VOICE_LANGUAGES
                ):
                    await websocket.send_json(
                        {"type": "error", "message": "Unsupported response language"}
                    )
                    continue
                response_language = language_value
                if prepared_acknowledgement_language != response_language:
                    prepared_acknowledgement = ()
                if isinstance(session_stt, OpenAIRealtimeSTT):
                    settings_changed = session_stt.configure_response_language(language_value)
                    # Realtime session transcription settings are fixed when a stream
                    # starts. Restart only this client's STT stream so a language
                    # change takes effect without reconnecting the whole voice call.
                    if settings_changed:
                        if audio_queue is not None and stt_task is not None and not stt_task.done():
                            ending_audio_queues.add(id(audio_queue))
                            audio_queue = None
                            stt_task.cancel()
                            await asyncio.gather(stt_task, return_exceptions=True)
                        await session_stt.aclose()
                        try:
                            await session_stt.warmup()
                        except STTProviderError:
                            await websocket.send_json(
                                {"type": "stt_unavailable", "reason": "Speech recognition could not reconnect"}
                            )
                            continue
                await websocket.send_json(
                    {"type": "state", "state": "listening", "response_language": response_language}
                )
                continue
            if event.get("type") != "user_text":
                await websocket.send_json(
                    {"type": "error", "message": "Expected user_text, set_language, or barge_in"}
                )
                continue
            text_value = event.get("text", "")
            if not isinstance(text_value, str):
                await websocket.send_json({"type": "error", "message": "Text must be a string"})
                continue
            user_text = text_value.strip()
            if not user_text or len(user_text) > 1000:
                await websocket.send_json(
                    {"type": "error", "message": "Text must contain 1-1000 characters"}
                )
                continue
            language_value = event.get("language", "ur-Latn")
            if not isinstance(language_value, str):
                await websocket.send_json({"type": "error", "message": "Language must be a string"})
                continue
            requested_language = language_value
            language = (
                requested_language
                if requested_language in SUPPORTED_VOICE_LANGUAGES
                else normalize_voice_language(requested_language)
            )
            cancel_started = cancel_active()
            turn_received_at = time.perf_counter()
            active_task = launch_turn(user_text, language, turn_received_at)
            if cancel_started is not None:
                traces.observe(
                    "voice.barge_in_cancel_latency_ms",
                    (time.perf_counter() - cancel_started) * 1000,
                )
    except WebSocketDisconnect:
        traces.increment("voice:websocket_disconnect_received")
    finally:
        try:
            if stt_task is not None and not stt_task.done() and audio_queue is not None:
                try:
                    audio_queue.put_nowait(None)
                except asyncio.QueueFull:
                    pass

            pending_tasks = list(turn_tasks)
            if stt_task is not None:
                pending_tasks.append(stt_task)
            for task in pending_tasks:
                if not task.done():
                    task.cancel()
                    task.add_done_callback(_consume_background_task_result)

            warmup_tasks = [
                task
                for task in (realtime_tts_warmup, configured_tts_ack_warmup)
                if task is not None
            ]
            for task in warmup_tasks:
                if not task.done():
                    task.cancel()
                    task.add_done_callback(_consume_background_task_result)

            providers_to_close = []
            if session_realtime_tts is not None:
                providers_to_close.append(("tts", session_realtime_tts))
            if isinstance(session_stt, OpenAIRealtimeSTT):
                providers_to_close.append(("stt", session_stt))
            for provider_name, provider in providers_to_close:
                async def close_provider(provider_name: str = provider_name, provider: object = provider) -> None:
                    try:
                        await asyncio.wait_for(provider.aclose(), timeout=1.0)
                    except TimeoutError:
                        traces.increment(f"voice:{provider_name}_cleanup_timeout")
                    except Exception:  # noqa: BLE001 - provider close failure must not retain the call lease
                        traces.increment(f"voice:{provider_name}_cleanup_failed")

                close_task = asyncio.create_task(close_provider())
                close_task.add_done_callback(_consume_background_task_result)
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(
                        record_voice_call_outcome,
                        conversation_id=conversation_id,
                        channel="browser",
                        duration_ms=max(0, int((time.perf_counter() - voice_call_started_at) * 1000)),
                        state=agent.states.get(conversation_id),
                        appointment_reference=appointment_reference,
                    ),
                    timeout=1.0,
                )
            except TimeoutError:
                traces.increment("voice.call_outcome_persist_timeout")
            except Exception:  # noqa: BLE001 - record failure is observable without leaking caller data
                traces.increment("voice.call_outcome_persist_failure")
        finally:
            await release_session_lease()


@app.websocket("/v1/telephony/media")
async def telephony_media_socket(websocket: WebSocket) -> None:
    """Bridge Twilio 8 kHz μ-law media to the existing STT/LangGraph/TTS pipeline."""

    if not isinstance(telephony, TwilioTelephonyAdapter):
        await websocket.close(code=1013, reason="Telephony provider is not configured")
        return
    signature = websocket.headers.get("x-twilio-signature")
    query = str(websocket.url.query)
    if (
        settings.app_env != "development" or settings.twilio_auth_token
    ) and not telephony.verify_websocket_signature(
        _twilio_signature_url("/v1/telephony/media", query),
        signature,
        settings.twilio_auth_token,
    ):
        await websocket.close(code=1008, reason="Invalid telephony signature")
        return
    await websocket.accept()
    conversation_id = str(uuid4())
    stream_sid: str | None = None
    audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=100)
    active_task: asyncio.Task[None] | None = None
    stt_task: asyncio.Task[None] | None = None
    lease_renewal_task: asyncio.Task[None] | None = None
    telephony_lease_id: str | None = None
    telephony_call_started_at: float | None = None
    telephony_language = "ur-Latn"
    call_termination = asyncio.Event()
    call_termination_code = 1011
    call_termination_reason = "Call processing failed"
    receive_task: asyncio.Task[str] | None = None
    termination_wait_task: asyncio.Task[bool] | None = None

    def request_call_termination(code: int, reason: str) -> None:
        nonlocal call_termination_code, call_termination_reason
        call_termination_code = code
        call_termination_reason = reason
        call_termination.set()

    async def renew_telephony_lease() -> None:
        interval = max(5.0, min(30.0, settings.voice_session_lease_seconds / 3))
        while True:
            await asyncio.sleep(interval)
            try:
                renewed = telephony_lease_id is not None and await asyncio.to_thread(
                    voice_sessions.renew_external_lease, telephony_lease_id
                )
            except Exception:  # noqa: BLE001 - fail closed when shared call capacity is unavailable
                renewed = False
            if not renewed:
                traces.increment("voice:telephony_lease_lost")
                request_call_termination(1013, "Telephony call capacity lease expired")
                return

    async def audio_stream() -> AsyncIterator[bytes]:
        while True:
            chunk = await audio_queue.get()
            if chunk is None:
                return
            yield chunk

    async def send_clear() -> None:
        if stream_sid:
            await websocket.send_json({"event": "clear", "streamSid": stream_sid})

    async def stream_spoken_text(
        text: str, language: str, turn_received_at: float | None = None
    ) -> None:
        if not stream_sid:
            return
        tts_started_at = time.perf_counter()
        first_audio_recorded = False
        end_to_first_audio_recorded = False
        try:
            async for chunk in tts.synthesize_stream(text, language):
                if chunk.encoding != "pcm_s16le" or not chunk.audio:
                    raise TTSProviderError("Twilio media bridge requires PCM16 TTS output")
                if not first_audio_recorded:
                    traces.observe(
                        "voice.tts_first_audio_latency_ms",
                        (time.perf_counter() - tts_started_at) * 1000,
                    )
                    first_audio_recorded = True
                pcm8 = resample_pcm16(chunk.audio, chunk.sample_rate, 8_000)
                await websocket.send_json(
                    {
                        "event": "media",
                        "streamSid": stream_sid,
                        "media": {
                            "payload": base64.b64encode(pcm16_to_mulaw(pcm8)).decode("ascii")
                        },
                    }
                )
                if turn_received_at is not None and not end_to_first_audio_recorded:
                    traces.observe(
                        "voice.final_transcript_to_first_audio_ms",
                        (time.perf_counter() - turn_received_at) * 1000,
                    )
                    end_to_first_audio_recorded = True
        finally:
            traces.observe(
                "voice.tts_stream_duration_ms",
                (time.perf_counter() - tts_started_at) * 1000,
            )

    async def speak_recovery(text: str, language: str) -> None:
        try:
            try:
                await asyncio.to_thread(transcripts.append, conversation_id, "assistant", text)
            except Exception:  # noqa: BLE001 - preserve caller audio when transcript storage fails
                traces.increment("voice:telephony_recovery_transcript_failure")
            await stream_spoken_text(text, language)
        except TTSProviderError:
            traces.increment("provider_failure:telephony_tts")
            request_call_termination(1011, "Speech output unavailable")
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - recovery must not hide provider failures
            traces.increment("provider_failure:telephony_recovery")
            request_call_termination(1011, "Call recovery failed")

    async def process_turn(text: str, language: str, turn_received_at: float | None) -> None:
        started = time.perf_counter()
        try:
            decision = await asyncio.to_thread(agent.respond, conversation_id, text, language)
            await asyncio.to_thread(transcripts.append, conversation_id, "user", text)
            await asyncio.to_thread(
                transcripts.append, conversation_id, "assistant", decision.spoken_text
            )
            if not stream_sid:
                return
            decision_completed_at = time.perf_counter()
            traces.observe("voice.decision_latency_ms", (decision_completed_at - started) * 1000)
            await stream_spoken_text(decision.spoken_text, language, turn_received_at)
        except TTSProviderError:
            traces.increment("provider_failure:telephony_tts")
            request_call_termination(1011, "Speech output unavailable")
        except Exception:  # noqa: BLE001 - carrier sessions fail closed
            traces.increment("provider_failure:telephony_agent")
            await speak_recovery(
                telephony_provider_failure_prompt(language), language
            )
            request_call_termination(1011, "Agent processing unavailable")

    async def consume_stt() -> None:
        nonlocal active_task, telephony_language
        restarts = 0
        while True:
            failure_reason: str | None = None
            try:
                async for event in stt.stream(audio_stream()):
                    if event.speech_started:
                        if active_task is not None and not active_task.done():
                            active_task.cancel()
                        await send_clear()
                    if event.is_final and event.speech_final and event.text:
                        telephony_language = normalize_voice_language(event.language)
                        if (
                            event.confidence is not None
                            and event.confidence < settings.stt_min_confidence
                        ):
                            traces.increment("stt:low_confidence")
                            if active_task is not None and not active_task.done():
                                active_task.cancel()
                                await send_clear()
                            recovery = transcription_recovery_prompt(telephony_language)
                            if recovery:
                                active_task = asyncio.create_task(
                                    speak_recovery(recovery, telephony_language)
                                )
                            continue
                        restarts = 0
                        if active_task is not None and not active_task.done():
                            active_task.cancel()
                        turn_received_at = time.perf_counter()
                        active_task = asyncio.create_task(
                            process_turn(event.text, telephony_language, turn_received_at)
                        )
                failure_reason = "stt_stream_ended"
            except asyncio.CancelledError:
                raise
            except Exception as error:  # noqa: BLE001 - convert failures to safe caller guidance
                code = stt_provider_error_code(error)
                failure_reason = (
                    f"stt_{code}" if code != "provider_unavailable" else "stt_provider_error"
                )

            traces.increment("provider_failure:telephony_stt")
            traces.increment(f"provider_failure:telephony_stt:{failure_reason}")
            if _stt_failure_is_recoverable(failure_reason) and restarts < 2:
                restarts += 1
                traces.increment("voice:telephony_stt_auto_recovered")
                recovery = transcription_recovery_prompt(telephony_language)
                if recovery:
                    if active_task is not None and not active_task.done():
                        active_task.cancel()
                    active_task = asyncio.create_task(
                        speak_recovery(recovery, telephony_language)
                    )
                await asyncio.sleep(0.1 * restarts)
                continue

            if active_task is not None and not active_task.done():
                active_task.cancel()
            failure_prompt = telephony_provider_failure_prompt(telephony_language)
            active_task = asyncio.create_task(speak_recovery(failure_prompt, telephony_language))
            await active_task
            request_call_termination(1011, "Speech recognition unavailable")
            return

    try:
        receive_task = asyncio.create_task(websocket.receive_text())
        termination_wait_task = asyncio.create_task(call_termination.wait())
        while True:
            done, _pending = await asyncio.wait(
                {receive_task, termination_wait_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if termination_wait_task in done:
                try:
                    await websocket.close(
                        code=call_termination_code,
                        reason=call_termination_reason,
                    )
                except RuntimeError:
                    pass
                break
            message = receive_task.result()
            receive_task = asyncio.create_task(websocket.receive_text())
            event = json.loads(message)
            event_type = event.get("event")
            if event_type == "start":
                start = event.get("start") or {}
                stream_sid = str(event.get("streamSid") or start.get("streamSid") or "")
                call_sid = str(start.get("callSid") or "").strip()
                if not stream_sid or not call_sid:
                    traces.increment("voice:telephony_invalid_start")
                    await websocket.close(code=1008, reason="Invalid Twilio start event")
                    break
                candidate_lease_id = f"twilio:{call_sid}"
                try:
                    lease_active = await asyncio.to_thread(
                        voice_sessions.renew_external_lease, candidate_lease_id
                    )
                except Exception:  # noqa: BLE001 - capacity must be available before using providers
                    lease_active = False
                if not lease_active:
                    traces.increment("voice:telephony_unreserved_call")
                    try:
                        await websocket.close(
                            code=1013, reason="Inbound call capacity reservation unavailable"
                        )
                    except RuntimeError:
                        pass
                    break
                telephony_lease_id = candidate_lease_id
                conversation_id = call_sid
                telephony_call_started_at = time.perf_counter()
                lease_renewal_task = asyncio.create_task(renew_telephony_lease())
                stt_task = asyncio.create_task(consume_stt())
                active_task = asyncio.create_task(
                    process_turn("Assalam-o-Alaikum", "ur-Latn", None)
                )
            elif event_type == "media":
                payload = (event.get("media") or {}).get("payload")
                if payload:
                    if not isinstance(payload, str) or len(payload) > 16_384:
                        traces.increment("voice:telephony_invalid_media")
                        await websocket.close(code=1009, reason="Telephony media frame is too large")
                        break
                    try:
                        raw = base64.b64decode(payload, validate=True)
                    except (ValueError, base64.binascii.Error):
                        traces.increment("voice:telephony_invalid_media")
                        await websocket.close(code=1003, reason="Invalid telephony media payload")
                        break
                    pcm8 = mulaw_to_pcm16(raw)
                    try:
                        audio_queue.put_nowait(
                            resample_pcm16(pcm8, 8_000, settings.stt_sample_rate)
                        )
                    except asyncio.QueueFull:
                        traces.increment("voice:telephony_audio_backpressure")
                        await websocket.close(code=1013, reason="Telephony audio pipeline is busy")
                        break
            elif event_type == "stop":
                break
    except (WebSocketDisconnect, json.JSONDecodeError, ValueError):
        pass
    finally:
        if audio_queue.full():
            try:
                audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        audio_queue.put_nowait(None)
        if active_task is not None and not active_task.done():
            active_task.cancel()
        if stt_task is not None and not stt_task.done():
            stt_task.cancel()
        if lease_renewal_task is not None and not lease_renewal_task.done():
            lease_renewal_task.cancel()
        if receive_task is not None and not receive_task.done():
            receive_task.cancel()
        if termination_wait_task is not None and not termination_wait_task.done():
            termination_wait_task.cancel()
        await asyncio.gather(
            *(
                task
                for task in (
                    active_task,
                    stt_task,
                    lease_renewal_task,
                    receive_task,
                    termination_wait_task,
                )
                if task is not None
            ),
            return_exceptions=True,
        )
        if telephony_lease_id is not None:
            try:
                await asyncio.to_thread(
                    voice_sessions.release_external_lease, telephony_lease_id
                )
            except Exception:  # noqa: BLE001 - expired lease cleanup remains a fallback
                traces.increment("voice:telephony_lease_release_failure")
        if telephony_call_started_at is not None:
            try:
                await asyncio.to_thread(
                    record_voice_call_outcome,
                    conversation_id=conversation_id,
                    channel="twilio",
                    duration_ms=max(
                        0, int((time.perf_counter() - telephony_call_started_at) * 1000)
                    ),
                    state=agent.states.get(conversation_id),
                )
            except Exception:  # noqa: BLE001 - do not expose provider/session details
                traces.increment("voice.call_outcome_persist_failure")
