# Awaaz Estate stakeholder report

## Outcome

Awaaz Estate is a browser-first, multilingual real-estate voice concierge. It answers property
questions from verified inventory, recommends available matches, routes seller requests to a human,
and safely manages visit bookings. The Python outbox worker replaces n8n for Calendar, Gmail, and
the internal CRM-ready lead log. Docker is intentionally not part of this delivery boundary.

## What is implemented

- FastAPI API and React/Vite console launched with `python run.py` and `npm run dev --prefix frontend`.
- LangGraph guardrails, typed decisions, durable 30-day state, source IDs, prompt-injection refusal,
  and deterministic SQL availability checks.
- Configurable language/script routing and isolated Parler/Chatterbox open-source TTS worker
  contracts. Model licensing, weight loading, multilingual voice quality, and live latency remain
  unverified; Fish Audio and ElevenLabs are comparisons only, not production substitutes.
- PostgreSQL/Alembic schema through `0021_voice_session_leases`; SQLite remains a development
  fallback.
- Anonymous browser voice access requires a short-lived, one-use, Origin/client-bound ticket with a
  shared database-backed issuance limit. Trusted-proxy configuration and a database-backed active
  call ceiling are implemented; local disconnect/capacity tests pass. PostgreSQL concurrency and
  deployed proxy behavior remain unverified, so the endpoint is not ready for public exposure.
- Appointment booking, rescheduling, cancellation, idempotency, employee conflict protection,
  encrypted email/optional phone, Calendar/Gmail outbox delivery, and CRM follow-up timestamps.
- Optional signed Twilio webhook/outbound call adapter with 8 kHz μ-law media conversion.

## Local evidence

- 98 backend tests pass and three PostgreSQL-only tests are skipped locally because no
  PostgreSQL server is installed/running. The new proxy middleware test confirms CIDR-based trust
  behavior locally; this does not verify a deployed reverse-proxy chain.
- 41 scripted conversations pass with zero prompt-injection bypasses.
- 20 SQL-grounded retrieval questions pass; this is a fixture baseline, not Pinecone evidence.
- Appointment evaluator passes 9/9 cases.
- Ruff, frontend tests/build, SQLite Alembic upgrade/downgrade/re-upgrade pass. PostgreSQL CI/live
  migration and concurrency evidence are still required.

## Release limitations

The repository does not claim live voice latency, live Pinecone retrieval quality, Calendar/Gmail
delivery, or telephony success until the corresponding provider credentials, test accounts, and
human evaluation runs exist. The release report labels these gates explicitly as blocked rather
than converting fixture results into production claims.

## Business value

The system gives a real-estate team a consistent first response, prevents unavailable-property
recommendations and duplicate visits, preserves consent and privacy boundaries, and leaves a
provider-neutral path for live voice and CRM integrations.
