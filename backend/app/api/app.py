from __future__ import annotations

import asyncio
import base64
import json
import secrets
import time
import urllib.parse
from collections.abc import AsyncIterator
from datetime import timedelta
from pathlib import Path
from typing import Annotated, Literal
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
from app.integrations.stt import STTProviderError, build_openai_realtime_stt, build_stt_provider
from app.integrations.telephony import (
    TelephonyProviderError,
    TwilioTelephonyAdapter,
    build_telephony_adapter,
    mulaw_to_pcm16,
    pcm16_to_mulaw,
    resample_pcm16,
)
from app.integrations.tts import TTSProviderError, build_openai_tts_router, build_tts_router
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
from app.services.voice_booking import VoiceBookingFlow
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
stt = build_stt_provider(settings)
openai_voice_tts = build_openai_tts_router(settings)
openai_voice_stt = build_openai_realtime_stt(settings)
telephony = build_telephony_adapter(settings)
voice_sessions = VoiceSessionService(
    settings.voice_session_hmac_key or secrets.token_urlsafe(32),
    max_active_total=settings.voice_session_max_active or 20,
    max_active_per_client=settings.voice_session_max_active_per_client,
    lease_lifetime=timedelta(seconds=settings.voice_session_lease_seconds),
)
app = FastAPI(title="Awaaz Estate API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip().rstrip("/") for origin in settings.cors_origins.split(",") if origin.strip()
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_dist = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"
if not frontend_dist.exists():
    frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if (frontend_dist / "assets").exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

SUPPORTED_VOICE_LANGUAGES = {"ur-Latn", "ur-Arab", "en", "hi", "ar", "pa", "bn"}


class VoiceSessionRequest(BaseModel):
    mode: Literal["standard", "openai"] = "standard"


DEFAULT_VOICE_SESSION_REQUEST = VoiceSessionRequest()


async def voice_option_readiness() -> dict[str, bool]:
    provider_status = provider_readiness()
    standard_tts_ready = provider_status.multilingual_tts and await all_tts_languages_ready(tts)
    openai_tts_routes = await openai_voice_tts.readiness()
    openai_audio_ready = (
        provider_status.openai
        and await openai_voice_stt.is_ready()
        and openai_tts_routes.get("*", False)
    )
    return {
        "standard_voice_ready": provider_status.deepgram
        and provider_status.openai
        and standard_tts_ready,
        "openai_voice_ready": openai_audio_ready,
        "multilingual_tts": standard_tts_ready,
        "live_voice_pipeline_ready": (
            provider_status.deepgram
            and provider_status.openai
            and standard_tts_ready
        ) or openai_audio_ready,
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
        if provider_status["standard_voice_ready"] or provider_status["openai_voice_ready"]
        else standard_blockers + ["OpenAI Realtime transcription and speech configuration"]
    )
    live_voice_ready = (
        provider_status["standard_voice_ready"] or provider_status["openai_voice_ready"]
    )
    return {
        "status": "ready" if database_ready and live_voice_ready else "degraded",
        "mode": "live" if live_voice_ready else "blocked",
        "application": {"database_ready": database_ready},
        "live_voice": {
            "configured": live_voice_ready,
            "status": "configured" if live_voice_ready else "blocked",
            "blockers": voice_blockers,
            "options": {
                "standard": provider_status["standard_voice_ready"],
                "openai": provider_status["openai_voice_ready"],
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
        "voice_sessions": await asyncio.to_thread(voice_sessions.capacity_snapshot),
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
    try:
        twiml = telephony.inbound_twiml()
    except TelephonyProviderError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
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
    return {
        "decision": decision,
        "retained_transcript": redact_for_retention(turn.text),
        "latency_ms": round(latency_ms, 2),
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
    selected_ready = (
        options["openai_voice_ready"] if mode == "openai" else options["standard_voice_ready"]
    )
    if not selected_ready:
        raise HTTPException(status_code=503, detail=f"The {mode} voice option is not ready")
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
    if voice_mode not in {"standard", "openai"}:
        await asyncio.to_thread(voice_sessions.release, voice_ticket)
        await websocket.close(code=1008, reason="Invalid voice provider mode")
        return
    session_stt = openai_voice_stt if voice_mode == "openai" else stt
    session_tts = openai_voice_tts if voice_mode == "openai" else tts

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
        await asyncio.gather(lease_task, return_exceptions=True)
        await asyncio.to_thread(voice_sessions.release, voice_ticket)

    conversation_id = str(uuid4())
    booking_contact: AppointmentContactContext | None = None
    booking_flow = VoiceBookingFlow(properties, appointments)
    presented_property_ids: list[str] = []
    voice_call_started_at = time.perf_counter()
    appointment_reference: str | None = None
    try:
        stt_available = await session_stt.is_ready()
        await websocket.send_json(
            {
                "type": "state",
                "state": "listening",
                "conversation_id": conversation_id,
                "audio_input_available": stt_available,
                "voice_mode": voice_mode,
            }
        )
    except Exception:
        await release_session_lease()
        raise
    active_task: asyncio.Task[None] | None = None
    active_audio_started = False
    stt_task: asyncio.Task[None] | None = None
    audio_queue: asyncio.Queue[bytes | None] | None = None
    audio_started_at: float | None = None
    response_language = "ur-Latn"

    async def process_turn(text: str, language: str, turn_received_at: float) -> None:
        nonlocal appointment_reference, active_audio_started
        started = time.perf_counter()
        try:
            decision = await asyncio.to_thread(agent.respond, conversation_id, text, language)
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
                    await websocket.send_json(
                        {
                            "type": "booking_slots",
                            "property_id": booking_flow.property_id,
                            "slots": [slot.isoformat() for slot in booking_flow.slots[:3]],
                        }
                    )
                if booking_result.appointment is not None:
                    appointment_reference = booking_result.appointment.get("reference")
                    await websocket.send_json(
                        {"type": "appointment_result", **booking_result.appointment}
                    )
            await asyncio.to_thread(transcripts.append, conversation_id, "user", text)
            await asyncio.to_thread(
                transcripts.append, conversation_id, "assistant", decision.spoken_text
            )
        except Exception:  # noqa: BLE001 - voice sessions must fail closed and remain usable
            traces.increment("provider_failure:agent")
            await websocket.send_json(
                {"type": "agent_unavailable", "reason": "The agent could not complete this turn"}
            )
            await websocket.send_json({"type": "state", "state": "listening"})
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
        response_payload: dict[str, object] = {
            "type": "agent_response",
            "decision": decision.model_dump(),
            "latency_ms": round(decision_latency_ms, 2),
        }
        if emotion is not None:
            response_payload["emotion"] = emotion.as_dict()
        await websocket.send_json(response_payload)
        first_audio_recorded = False
        end_to_first_audio_recorded = False
        tts_started_at = time.perf_counter()
        try:
            stream = pipeline_synthesize_clauses(
                session_tts,
                decision.spoken_text,
                language=language,
                emotion=emotion,
                enabled=settings.voice_early_clause_streaming_enabled,
            )
            async for chunk in stream:
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
                await websocket.send_json(
                    {
                        "type": "audio_chunk",
                        "sequence": chunk.sequence,
                        "language": chunk.language,
                        "sample_rate": chunk.sample_rate,
                        "encoding": chunk.encoding,
                        "audio_base64": base64.b64encode(chunk.audio).decode("ascii"),
                        "is_final": chunk.is_final,
                    }
                )
                if chunk.audio and not end_to_first_audio_recorded:
                    traces.observe(
                        "voice.end_of_turn_to_first_audio_ms",
                        (time.perf_counter() - turn_received_at) * 1000,
                    )
                    end_to_first_audio_recorded = True
        except TTSProviderError as error:
            traces.increment("provider_failure:tts")
            await websocket.send_json({"type": "audio_unavailable", "reason": str(error)})
        finally:
            traces.observe(
                "voice.tts_stream_duration_ms", (time.perf_counter() - tts_started_at) * 1000
            )
        await websocket.send_json({"type": "state", "state": "listening"})

    def cancel_active(*, only_after_audio: bool = False) -> float | None:
        if active_task is None or active_task.done():
            return None
        if only_after_audio and not active_audio_started:
            return None
        cancel_started = time.perf_counter()
        active_task.cancel()
        return cancel_started

    async def audio_stream(queue: asyncio.Queue[bytes | None]) -> AsyncIterator[bytes]:
        while True:
            chunk = await queue.get()
            if chunk is None:
                return
            yield chunk

    async def consume_stt(queue: asyncio.Queue[bytes | None]) -> None:
        nonlocal active_task, active_audio_started, audio_started_at
        try:
            async for event in session_stt.stream(audio_stream(queue)):
                if event.speech_started:
                    cancel_started = cancel_active()
                    await websocket.send_json(
                        {
                            "type": "state",
                            "state": "listening",
                            "interrupt_playback": True,
                        }
                    )
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
                            "text": event.text,
                            "language": event.language,
                            "confidence": event.confidence,
                            "is_final": event.is_final,
                            "speech_final": event.speech_final,
                        }
                    )
                if event.is_final and event.speech_final and event.text:
                    if audio_started_at is not None:
                        traces.observe(
                            "voice.stt_turn_latency_ms",
                            (time.perf_counter() - audio_started_at) * 1000,
                        )
                        audio_started_at = None
                    if (
                        event.confidence is not None
                        and event.confidence < settings.stt_min_confidence
                    ):
                        traces.increment("stt:low_confidence")
                        await websocket.send_json(
                            {
                                "type": "transcript_low_confidence",
                                "text": event.text,
                                "confidence": event.confidence,
                            }
                        )
                        continue
                    cancel_started = cancel_active()
                    turn_received_at = time.perf_counter()
                    active_audio_started = False
                    active_task = asyncio.create_task(
                        process_turn(event.text, response_language, turn_received_at)
                    )
                    if cancel_started is not None:
                        traces.observe(
                            "voice.barge_in_cancel_latency_ms",
                            (time.perf_counter() - cancel_started) * 1000,
                        )
        except STTProviderError as error:
            traces.increment("provider_failure:stt")
            await websocket.send_json({"type": "stt_unavailable", "reason": str(error)})

    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if message.get("bytes") is not None:
                if not stt_available or audio_queue is None:
                    await websocket.send_json(
                        {"type": "stt_unavailable", "reason": "Streaming STT is not configured"}
                    )
                else:
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
                if stt_task is not None and not stt_task.done():
                    if audio_queue is not None:
                        try:
                            audio_queue.put_nowait(None)
                        except asyncio.QueueFull:
                            await websocket.close(code=1013, reason="Audio input queue is full")
                            break
                    stt_task.cancel()
                audio_queue = asyncio.Queue(maxsize=settings.voice_audio_queue_frames)
                audio_started_at = time.perf_counter()
                stt_task = asyncio.create_task(consume_stt(audio_queue))
                await websocket.send_json(
                    {"type": "state", "state": "listening", "audio_started": True}
                )
                continue
            if event.get("type") == "audio_end":
                if audio_queue is not None:
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
                if voice_mode == "openai" and audio_queue is not None:
                    try:
                        audio_queue.put_nowait(b"\x00")
                    except asyncio.QueueFull:
                        await websocket.close(code=1013, reason="Audio input queue is full")
                        break
                cancel_started = cancel_active(only_after_audio=True)
                await websocket.send_json(
                    {
                        "type": "state",
                        "state": "listening",
                        "interrupt_playback": True,
                    }
                )
                if cancel_started is not None:
                    traces.observe(
                        "voice.barge_in_cancel_latency_ms",
                        (time.perf_counter() - cancel_started) * 1000,
                    )
                continue
            if event.get("type") == "audio_turn_end":
                if voice_mode == "openai" and audio_queue is not None:
                    try:
                        audio_queue.put_nowait(b"")
                    except asyncio.QueueFull:
                        await websocket.close(code=1013, reason="Audio input queue is full")
                        break
                await websocket.send_json({"type": "state", "state": "processing"})
                continue
            if event.get("type") == "barge_in":
                cancel_started = cancel_active()
                await websocket.send_json(
                    {
                        "type": "state",
                        "state": "listening",
                        "interrupt_playback": True,
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
            active_task = asyncio.create_task(process_turn(user_text, language, turn_received_at))
            if cancel_started is not None:
                traces.observe(
                    "voice.barge_in_cancel_latency_ms",
                    (time.perf_counter() - cancel_started) * 1000,
                )
    except WebSocketDisconnect:
        pass
    finally:
        pending_tasks = [task for task in (active_task, stt_task) if task is not None]
        for task in pending_tasks:
            if not task.done():
                task.cancel()
        if pending_tasks:
            await asyncio.gather(*pending_tasks, return_exceptions=True)
        try:
            await asyncio.to_thread(
                record_voice_call_outcome,
                conversation_id=conversation_id,
                channel="browser",
                duration_ms=max(0, int((time.perf_counter() - voice_call_started_at) * 1000)),
                state=agent.states.get(conversation_id),
                appointment_reference=appointment_reference,
            )
        except Exception:  # noqa: BLE001 - record failure is observable without leaking caller data
            traces.increment("voice.call_outcome_persist_failure")
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
    audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    active_task: asyncio.Task[None] | None = None
    stt_task: asyncio.Task[None] | None = None
    telephony_call_started_at: float | None = None

    async def audio_stream() -> AsyncIterator[bytes]:
        while True:
            chunk = await audio_queue.get()
            if chunk is None:
                return
            yield chunk

    async def send_clear() -> None:
        if stream_sid:
            await websocket.send_json({"event": "clear", "streamSid": stream_sid})

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
            tts_started_at = decision_completed_at
            first_audio_recorded = False
            end_to_first_audio_recorded = False
            try:
                async for chunk in tts.synthesize_stream(decision.spoken_text, language):
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
                            "voice.end_of_turn_to_first_audio_ms",
                            (time.perf_counter() - turn_received_at) * 1000,
                        )
                        end_to_first_audio_recorded = True
            finally:
                traces.observe(
                    "voice.tts_stream_duration_ms",
                    (time.perf_counter() - tts_started_at) * 1000,
                )
        except TTSProviderError as error:
            traces.increment("provider_failure:telephony_tts")
            await websocket.send_json({"event": "telephony_error", "reason": str(error)})
        except Exception:  # noqa: BLE001 - carrier sessions fail closed
            traces.increment("provider_failure:telephony_agent")

    async def consume_stt() -> None:
        nonlocal active_task
        try:
            async for event in stt.stream(audio_stream()):
                if event.speech_started:
                    if active_task is not None and not active_task.done():
                        active_task.cancel()
                    await send_clear()
                if event.is_final and event.speech_final and event.text:
                    if (
                        event.confidence is not None
                        and event.confidence < settings.stt_min_confidence
                    ):
                        traces.increment("stt:low_confidence")
                        continue
                    if active_task is not None and not active_task.done():
                        active_task.cancel()
                    turn_received_at = time.perf_counter()
                    active_task = asyncio.create_task(
                        process_turn(
                            event.text,
                            normalize_voice_language(event.language),
                            turn_received_at,
                        )
                    )
        except STTProviderError:
            traces.increment("provider_failure:telephony_stt")
        except asyncio.CancelledError:
            raise

    try:
        while True:
            message = await websocket.receive_text()
            event = json.loads(message)
            event_type = event.get("event")
            if event_type == "start":
                start = event.get("start") or {}
                stream_sid = str(event.get("streamSid") or start.get("streamSid") or "")
                call_sid = str(start.get("callSid") or conversation_id)
                conversation_id = call_sid
                telephony_call_started_at = time.perf_counter()
                stt_task = asyncio.create_task(consume_stt())
                active_task = asyncio.create_task(
                    process_turn("Assalam-o-Alaikum", "ur-Latn", None)
                )
            elif event_type == "media":
                payload = (event.get("media") or {}).get("payload")
                if payload:
                    raw = base64.b64decode(payload)
                    pcm8 = mulaw_to_pcm16(raw)
                    await audio_queue.put(resample_pcm16(pcm8, 8_000, settings.stt_sample_rate))
            elif event_type == "stop":
                break
    except (WebSocketDisconnect, json.JSONDecodeError, ValueError):
        pass
    finally:
        await audio_queue.put(None)
        if active_task is not None and not active_task.done():
            active_task.cancel()
        if stt_task is not None and not stt_task.done():
            stt_task.cancel()
        await asyncio.gather(
            *(task for task in (active_task, stt_task) if task is not None), return_exceptions=True
        )
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
