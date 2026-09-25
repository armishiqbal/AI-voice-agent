# Backend

FastAPI application, LangGraph orchestration, domain models, integrations, repository implementations, and backend tests belong here. Run backend checks from the repository root with `python -m pytest backend/tests`.

Schema changes are managed by Alembic. For a configured PostgreSQL database, run `DATABASE_URL=postgresql+psycopg://user:password@host/db alembic upgrade head` from this directory before starting the API; the current head is `0021_voice_session_leases`. The development app uses `create_all` plus a compatibility check only for a local SQLite demo; it is not the production migration path.

Production also requires `VOICE_SESSION_HMAC_KEY` (at least 32 random bytes). Anonymous browser
voice clients obtain a short-lived, one-use ticket before the WebSocket handshake; ticket issuance
is rate-limited in the shared database. Trusted proxy handling is allowlisted and active calls use
database-backed leases. Local WebSocket cleanup tests pass; do not expose the anonymous voice
endpoint publicly until PostgreSQL concurrency and deployed proxy behavior are verified.

Appointment notifications are dispatched by `app.workers.outbox.OutboxWorker`. It replaces an external n8n workflow with persisted retries, exponential backoff, and worker leases. Run it from the repository root with `python worker.py`. Calendar and email adapters register handlers for the `appointment.*` event types only when a pre-authorized Google OAuth token is configured; otherwise events remain pending.

Voice adapters are optional. Deepgram STT is enabled with `pip install -e '.[voice-deepgram]'`; without credentials the API reports `stt_unavailable` rather than faking transcripts. The open-source TTS runtime lives in `services/tts/` and runs in independent Parler and Chatterbox environments because their Transformers pins conflict. Configure `TTS_PROVIDER=opensource` and both worker URLs in the API environment; setup, explicit warmup, and model limitations are in `docs/TTS_EVALUATION.md`. Model downloads occur only on authenticated warmup, and the API reports `audio_unavailable` when a service or model is unavailable.

The optional Twilio phone boundary uses `pip install -e '.[telephony]'`, `TELEPHONY_PROVIDER=twilio`,
server-side Twilio credentials, and a public HTTPS base URL. It verifies webhook signatures and
bridges 8 kHz μ-law media to the same Deepgram/LangGraph/TTS pipeline. Keep `TELEPHONY_PROVIDER=none`
until a carrier number, recording/consent policy, and live-call test are approved.

`python scripts/benchmark/benchmark_tts.py` runs the configured Fish Audio and ElevenLabs providers against the same phrases and records latency/error rows without declaring a winner.

Inventory files are validated with `python scripts/data/import_inventory.py path.csv --source crm-export-v1`; brochure/FAQ chunks are sent to configured Pinecone with `python scripts/data/ingest_knowledge.py path.pdf --source brochure-v1`. Both commands preserve source/version metadata and fail clearly when their optional provider dependencies are absent.
