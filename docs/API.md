# API guide

## Health and readiness

- `GET /healthz` — process health.
- `GET /readyz` — application and voice-route configuration. `mode` is `live` only when a real
  server-side voice option is configured; otherwise the response is degraded and voice is blocked.
  `live_voice.status="configured_unverified"` and `verification="configuration_only"` mean
  credentials and SDK checks passed; they do not prove provider account access or an end-to-end
  speech turn. The UI keeps the route selectable and verifies it when the caller starts a session.
  `structured_reasoning.status` distinguishes `unconfigured`, `configured_unverified`, `cooldown`,
  and persistent `provider_error`; `last_failure_category` contains only a sanitized category
  such as `rate_limited`, `authentication_failed`, `timeout`, or `invalid_response`. A prior failure
  remains visible after cooldown until a model request succeeds. Configured hybrid voice can still
  use its deterministic fallback. A configured key is not proof of model quota or a successful
  live decision.
- `GET /v1/admin/metrics` — bounded traces, counters, latency measurements, provider status, and
  due follow-up reminders with contact fields omitted.
- `POST /v1/admin/follow-ups/{lead_id}/complete` — mark a due reminder complete after staff
  confirms the follow-up; the action is audited and idempotent for already-contacted leads.
- Each WebSocket `agent_response` also includes `reasoning_status` and
  `reasoning_failure_category` so the UI can show deterministic-fallback status immediately after
  a turn without exposing raw provider error details.
- `GET /v1/admin/evaluations/report` — local 41-case report, explicitly fixture-scoped.
  Outside development both require the `X-Admin-Api-Key` header matching `ADMIN_API_KEY`.
- `GET /v1/admin/outbox?limit=50` — delivery attempts and retry state without encrypted contact
  payloads.
- `GET /v1/admin/call-outcomes?limit=50` — PII-free CRM-ready call outcomes, including qualified
  intent, area, budget, below-list flag, discussed property IDs, appointment reference, summary,
  and internal outbox delivery status.
- `GET /v1/admin/audit?limit=100` — redacted tool-action audit metadata.

## Inventory

- `GET /v1/properties?city=&purpose=&max_budget_pkr=&bedrooms=&amenities=&investment_goal=` —
  SQL-filtered inventory including amenities, payment plans, nearby schools, nearby hospitals,
  investment goals, provenance, and assigned employee.
- `GET /v1/properties/{property_id}` — available property details; unavailable records return 404.
- `POST /v1/properties/import` — validated Pydantic JSON import with source and batch ID.
- `POST /v1/properties/import-file?filename=inventory.csv&source=crm-export-v1` — raw CSV/JSON
  upload with row-level validation; accepted and rejected rows are both recorded in the batch ledger.
- `python scripts/data/import_inventory.py` — CSV/JSON importer with row-level validation errors.
- `POST /v1/knowledge/ingest-file?filename=brochure.pdf&source=brochure-v1&property_id=PROP-001`
  — chunks a PDF/text brochure or FAQ and upserts it to Pinecone when configured; returns 503
  instead of pretending ingestion succeeded when the provider is absent.

## Lead handoff

- `POST /v1/leads` — consent-bound seller or uncertain-intent handoff. Email is encrypted at
  rest, notes are redacted, and a `lead.created` event is written to the transactional outbox.
  The local worker records this CRM-ready event without requiring n8n. Due follow-up times create
  a separate PII-minimized `lead.follow_up_due` event; no client email or message is sent.

Outside development, inventory imports, knowledge ingestion, metrics, evaluation, outbox, and audit
endpoints require the `X-Admin-Api-Key` header. The consented lead form remains public so a browser
caller can request a handoff; it still requires `consent: true` and encrypts the submitted email.
Public browser conversation and appointment routes do not accept this header as a substitute for
consent or appointment identity.

## Conversations and voice

- `POST /v1/conversations/{conversation_id}/turn` accepts `{text, language}` and returns a
  structured `AgentDecision` plus redacted transcript text. LangGraph state is persisted in
  PostgreSQL/SQLite and expires after 30 days.
- `POST /v1/voice/session` issues a short-lived, one-use anonymous voice ticket. It requires an
  allowed `Origin`, applies a database-backed limit of ten tickets per client address per minute,
  and returns the bearer ticket with `Cache-Control: no-store`. The database stores only its hash
  and an HMAC fingerprint of the client address. Consuming a ticket atomically reserves a bounded
  active-call lease (global limit 20 in development; configured for non-development, two per client
  by default); PostgreSQL concurrency coverage passes locally.
- `WS /v1/voice` requires the ticket as its first JSON message (`{"type":"authenticate", "ticket":"…"}`)
  within five seconds. The ticket is bound to the same Origin and client address, expires after
  two minutes, and is atomically consumed once. Do not put it in the WebSocket URL. Then the socket
  accepts `set_language`, `user_text`, `audio_start`, binary 16 kHz PCM16 frames,
  `audio_end`, and `barge_in`; the selected response language applies to subsequent transcribed
  turns. The browser requests microphone access before opening an audio stream and pauses capture
  if its outbound WebSocket buffer reaches the configured high-water mark. It emits transcripts,
  structured decisions, ordered audio chunks, and explicit `stt_unavailable`/`audio_unavailable`
  events. Low-confidence final transcripts ask the caller to repeat or type the request. The UI
  replays only audio returned by the configured TTS provider; it does not use browser-native TTS as
  an implicit fallback. Tickets protect anonymous voice sessions; they do not establish a named
  user identity. Origin checks remain a browser abuse defense, not caller identity. Behind a
  reverse proxy, only use a client address supplied by an explicitly trusted proxy configuration;
  never trust arbitrary `X-Forwarded-For` values.
- `booking_contact` is a typed, consented form event scoped to the active WebSocket only. It is not
  passed to the model or transcript store. The socket emits `booking_slots` and
  `appointment_result` events for deterministic visit flow. On disconnect, the server writes one
  idempotent `voice.call_completed` outbox event with structured preferences and a short summary;
  it contains no raw audio, transcript, email, or phone. The local worker records that event in the
  CRM-ready log. A real CRM, SMS/WhatsApp follow-up, and live calendar success require configured
  integrations and are not claimed by this local automation.

## Appointments

- `POST /v1/appointments` books an available property for its assigned employee, a Monday–Saturday
  10:00–18:00 Asia/Karachi half-hour slot, and consented contact email. An optional consented phone
  number is encrypted at rest and included only in Calendar/Gmail delivery details.
- `POST /v1/appointments/reschedule` and `/cancel` require matching reference/email and persist
  idempotency keys.
- The response is not proof of Calendar delivery; the outbox worker handles external delivery.

Lead handoffs may include an optional `follow_up_at` timestamp. It is persisted in the CRM-ready
lead record and emitted in the internal outbox event for operator follow-up scheduling.

## Optional telephony

- `POST /v1/telephony/calls` — admin-protected outbound E.164 call request through the configured
  Twilio adapter. It returns a call SID and media WebSocket URL; no call is created without complete
  server-side credentials.
- `POST /v1/telephony/inbound` — signed Twilio webhook returning media-stream TwiML.
- `WS /v1/telephony/media` — signed Twilio 8 kHz μ-law media bridge to Deepgram, LangGraph, and
  PCM16 TTS. Fish/MP3 output is rejected at this boundary; configure a PCM16 TTS provider for
  phone calls.
