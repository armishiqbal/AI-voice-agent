# Operations and troubleshooting

## Local process order

1. Copy `.env.example` to `.env` and set `OPENAI_API_KEY` locally.
2. Install the live voice dependencies with `backend/venv/bin/pip install -e 'backend[providers,voice-openai]'`.
3. For local work, start the API with `python run.py`; it creates the SQLite schema without inserting sample listings.
4. Start `python worker.py` only when a real outbox integration is configured.
5. Build and open the browser with `npm run build --prefix frontend` and `http://localhost:8000`.

The default live voice path uses OpenAI Realtime transcription, the structured OpenAI agent, and
OpenAI speech generation. `/readyz` must report `mode: live`, `live_voice.status: configured`, and
`providers.openai_voice_ready: true`. A missing SDK, key, or upstream account entitlement blocks
voice startup; the UI does not switch to browser speech recognition. Property search remains empty
until a verified CSV/JSON inventory is imported.

No Docker or n8n process is required.

Production also requires `VOICE_SESSION_HMAC_KEY` with at least 32 random bytes. The browser
obtains a one-use ticket from `POST /v1/voice/session`; issuance is limited to ten per minute per
client address. The database stores only a ticket hash and keyed client fingerprint. The ticket
endpoint and voice WebSocket currently use the ASGI peer address. Before deploying behind a reverse
proxy, configure and verify trusted-proxy address forwarding in the ASGI server; do not trust
caller-provided forwarding headers. Tickets limit session issuance but do not yet enforce a
concurrent-call ceiling or prove a named user's identity.

Phone entry is disabled by default. To enable the optional Twilio boundary, install
`pip install -e 'backend[telephony]'`, configure the four `TWILIO_*`/`TELEPHONY_PUBLIC_BASE_URL`
settings, expose the API over HTTPS, and validate the carrier signature/recording-consent policy.
The phone bridge requires a PCM16 TTS provider; Fish Audio MP3 output is not accepted by the media
bridge.

For local open-source multilingual TTS, run the Parler and Chatterbox workers in separate
virtual environments as documented in `TTS_EVALUATION.md`; their Transformers dependencies
conflict. The API's `/readyz` probes every required language route and reports degraded until
both worker services respond. Run the documented authenticated warmup command for each worker;
the worker readiness probe stays false until model weights load and a smoke synthesis succeeds.
This still does not prove native-speaker quality or production latency gates.

Outside development, startup fails closed unless `DATABASE_URL` is PostgreSQL and
`PII_ENCRYPTION_KEY`, `ADMIN_API_KEY`, and `VOICE_SESSION_HMAC_KEY` are set. Inventory and knowledge request bodies are capped by
`MAX_UPLOAD_BYTES` (10 MB by default).

## Common states

- `audio_input_available=false`: the selected server-side speech-recognition provider is unavailable; inspect `/readyz` and restart after installing dependencies or changing `.env`.
- `audio_unavailable`: TTS provider is disabled, missing, or failed; the browser keeps the written
  answer visible and does not silently switch to its built-in speech engine.
- Outbox `delivered_at` is null: inspect `attempts`, `last_error`, and `next_attempt_at`. Missing
  Google OAuth intentionally leaves events pending rather than fabricating delivery.
- `/readyz` degraded: the API or live voice path is not ready. Inspect provider booleans; the UI blocks voice instead of switching to browser recognition.
- `/healthz` reports that the API process responds. `/readyz` separately reports database
  availability and whether the live voice chain is configured (`live_voice.status` and
  `live_voice.blockers`). Provider configuration is not proof that an upstream account accepts
  requests; only a real end-to-end call and delivery run proves that. TTS readiness additionally
  probes each warmed worker and required language route. Google readiness checks for a refreshable
  local OAuth token with the Calendar/Gmail scopes, but does not send a test appointment/email.
- `/v1/admin/metrics` exposes `voice.decision_latency_ms`, `voice.first_audio_latency_ms`,
  `voice.tts_first_audio_latency_ms`, `voice.tts_stream_duration_ms`,
  `voice.end_of_turn_to_first_audio_ms`, `voice.barge_in_cancel_latency_ms`,
  `voice.stt_confidence`, and SQL/RAG latency measurements. `tts_first_audio` begins when TTS
  synthesis starts; `end_of_turn_to_first_audio` begins when the final STT event (or typed text)
  reaches the API and ends when the first audio frame is sent to the client/carrier. The latter
  includes agent decision time and should not be described as the precise acoustic end of caller
  speech. TTS stream duration is recorded on completion, provider error, and cancellation once
  synthesis has begun. Treat P95 values as unavailable until a representative live run has data.
- `python scripts/evaluation/release_report.py` prints the current local safety/grounding/retrieval gates and marks
  missing provider credentials or OAuth as `blocked by prerequisite`.

## Security controls

- Keep `.env`, OAuth token JSON, and provider keys outside source control.
- Never store raw audio. Transcript rows are redacted and expire after thirty days.
- Use the audit ledger and outbox payloads for incident review; they exclude contact email content.
- Production release still requires PostgreSQL, production secrets, provider contracts, a real
  inventory source, consent/recording policy, and measured latency and retrieval evidence.
