# Operations and troubleshooting

## Local process order

1. Copy `.env.example` to `.env`; set `OPENAI_API_KEY`, `DEEPGRAM_API_KEY`, and `FISH_AUDIO_API_KEY`
   locally. The default UrduLish route uses Deepgram for STT and the configured TTS router. Select a
   Fish model and account with available credits; never put keys in source control.
2. Install the hybrid voice dependencies with `python -m pip install -e 'backend[providers,voice-openai,voice-deepgram,voice-fish]'`.
3. For local work, start the API with `python run.py`; it creates the SQLite schema without inserting sample listings.
4. Start `python worker.py` only when a real outbox integration is configured.
5. Build and open the browser with `npm run build --prefix frontend` and `http://localhost:8000`.

Backend tests use an isolated temporary SQLite database by default. To run the same suite against a
disposable PostgreSQL database, set `TEST_DATABASE_URL` to its SQLAlchemy URL before running pytest;
never point this variable at a production or developer database.

The PostgreSQL Alembic environment uses a 128-character version column because two existing
revision labels exceed Alembic's default 32-character width. On an existing PostgreSQL database,
the environment widens that metadata column before applying migrations; it does not change
application tables or shorten revision history.

Voice providers are selected by the requested session mode and backend configuration. English and
UrduLish use the hybrid route (Deepgram transcription, structured OpenAI agent, and the configured
TTS router; session-scoped OpenAI Realtime speech is optional). Other supported languages use the
OpenAI route. The local developer `.env` currently selects Deepgram, OpenAI reasoning, and Fish
Audio `s2.1-pro-free`, with OpenAI Realtime TTS disabled; the Realtime TTS route is opt-in because
its account quota must be verified separately. Fish uses its documented `balanced` latency mode
by default (`FISH_AUDIO_LATENCY=normal` is the quality-oriented alternative); one same-text live
provider sample started audio at 1,168 ms in balanced mode versus 3,462 ms with the old
undocumented `low` value, which is directional evidence only. `/readyz` performs and caches an
OpenAI Realtime session handshake for 30 seconds; the
other routes report configured/dependency readiness. OpenAI structured decisions make one bounded
attempt and use the deterministic graph fallback during a 30-second provider-failure cooldown.
`/readyz.structured_reasoning` reports the cooldown and retains a sanitized last failure category
after the cooldown until a model request succeeds. A previous provider failure marks overall
readiness degraded without blocking the configured hybrid voice route. The status does not verify all provider balances or
prove a completed call. The UI does not switch to browser speech recognition or fabricate audio.
Property search remains empty until a verified CSV/JSON inventory is imported.

After browser voice activity detection commits a turn, the API waits up to
`STT_FINALIZE_TIMEOUT_SECONDS` (default six seconds) for a stable transcript. If the provider
does not finalize in time, the API discards the partial turn and asks the caller to repeat the full
request. When partial words were recognized, the spoken retry briefly quotes them to explain what
was heard; without partial text it uses a generic retry. The quote is recovery context only: the
caller must restate the request, and unstable text is never sent to the agent or booking tools.

For Deepgram sessions, the API opens the provider WebSocket before sending the initial
`audio_input_available=true` state, so the browser does not start microphone capture against a
transport that is still connecting. The startup and reconnect waits are bounded by
`STT_TRANSPORT_TIMEOUT_SECONDS` (default eight seconds). A timeout or provider connection failure
returns a stable `stt_provider_timeout` or provider failure code and leaves the client in its
recoverable connection-error flow. This prevents the startup race; it does not guarantee a final
transcript or a sub-two-second answer for every utterance.

Hybrid and Realtime routes also hold a stable final that arrives just before browser VAD commits,
for up to two seconds, then process it against the committed turn. Deepgram can split a long
utterance across multiple `is_final` segments; the hybrid route joins those stable segments after
commit until `speech_final`/`from_finalize` or a 250 ms quiet gap. Interim text is never promoted to
a final. Deterministic Urdu intent matching removes Unicode diacritic marks first, since Urdu STT
may add them to English loanwords such as “rent.” This does not improve the provider's acoustic
recognition; inspect `/v1/admin/metrics` and consented human conversations when live accuracy is in
doubt.

The configured non-factual acknowledgement is synthesized once per language and TTS provider per
API process, then reused across voice sessions. On a cold process, the first caller can begin before
that provider request finishes; subsequent sessions reuse the cached audio. Cache entries are
process-local and cleared on shutdown. An acknowledgement confirms only that the agent is
processing; it does not confirm a transcript, listing, or booking.

## Staff data uploads

Open the property icon in the page header, then expand the staff upload forms in the location browser.
Use an owner-reviewed CSV/JSON inventory export and a source label that identifies its origin and
revision. The backend validates each row, reports accepted/rejected records, and updates existing
properties in place when an imported ID already exists. Confirm the file is approved before submit.
The inventory list refreshes after import; only loaded, available records can be recommended or booked.

Upload owner-approved brochures or FAQs as PDF, TXT, or Markdown. Set a unique source label and
revision, and scope the document to a property and city when appropriate; blank scope means global
knowledge. The server chunks the file and indexes it in Pinecone, returning the chunk count and
metadata. PDF extraction requires the ingestion extra. A Pinecone or file-validation error is shown
in the form and does not report the document as indexed.

Outside development, enter the configured Admin API key in the upload form. It remains in the
current component memory and is cleared when the inventory dialog closes; the page does not persist
it in local storage. Keep the key out of filenames and source labels. These forms do not create
sample/demo records; import only real, approved company files.

Hybrid Urdu/English turns use browser VAD as the turn-boundary authority. The API sends Deepgram
`Finalize` when the browser commits a turn and keeps the streaming STT connection open for follow-up
turns. The default Deepgram endpointing delay is 300 ms, below the browser's 425 ms silence threshold,
so Deepgram can stabilize speech before commit; an early provider final remains a transcript update
until browser VAD commits. A provider-stable final transcript is required before agent reasoning begins.

No Docker or n8n process is required for the local browser conversation. Start the outbox worker
only when a real external delivery integration is configured; without Google OAuth, Calendar and
Gmail events remain pending and are not presented as delivered.

Production also requires `VOICE_SESSION_HMAC_KEY` with at least 32 random bytes. The browser
obtains a one-use ticket from `POST /v1/voice/session`; issuance is limited to ten per minute per
client address. The database stores only a ticket hash and keyed client fingerprint. The ticket
endpoint and voice WebSocket use the ASGI client address after Uvicorn's trusted-proxy middleware;
set `TRUSTED_PROXY_IPS` to the actual proxy addresses/CIDRs before deployment. Untrusted
forwarding headers are ignored. Database-backed leases enforce the configured global active-call
limit (20 in development; `VOICE_SESSION_MAX_ACTIVE` is required outside development) and a
per-client limit of two by default (`VOICE_SESSION_MAX_ACTIVE_PER_CLIENT`). Lease expiry defaults
to 90 seconds and recovers abandoned calls. The PostgreSQL concurrency tests passed locally; hosted
load/soak still needs verification. Tickets remain anonymous and do not prove a named user's
identity.

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

- `audio_input_available=false`: the selected server-side speech-recognition provider is unavailable; inspect `/readyz`, the voice troubleshooting stages, and backend logs.
- `audio_unavailable`: TTS provider is disabled, missing, or failed; the browser keeps the written
  answer visible and does not silently switch to its built-in speech engine.
- Outbox `delivered_at` is null: inspect `attempts`, `last_error`, and `next_attempt_at`. Missing
  Google OAuth intentionally leaves events pending rather than fabricating delivery.
- `/readyz` degraded: the API or live voice path may need attention. If `mode=blocked`, the UI blocks voice rather than switching to browser recognition. A `configured_unverified` route remains selectable; provider access is proven only by a successful live session. If the selected OpenAI route is unavailable, check account credits/provider access; UrduLish hybrid can remain available independently.
- `/healthz` reports that the API process responds. `/readyz` separately reports database
  availability and whether the live voice chain is configured (`live_voice.status` and
  `live_voice.blockers`). `configured_unverified` means credentials and SDK checks passed; it
  does not prove a provider will accept audio. The OpenAI voice option verifies its transcription
  handshake, but TTS still needs a real turn. Other provider booleans do not prove that an upstream
  account accepts a full request; only a real end-to-end call and delivery run proves that. TTS
  readiness additionally probes each warmed worker and required language route. Google readiness checks for a refreshable
  local OAuth token with the Calendar/Gmail scopes, but does not send a test appointment/email.
- `/v1/admin/metrics` exposes `voice.decision_latency_ms`, `voice.first_audio_latency_ms`,
  `voice.tts_first_audio_latency_ms`, `voice.tts_stream_duration_ms`,
  `voice.final_transcript_to_first_audio_ms`, `voice.stt_speech_to_final_transcript_ms`,
  `voice.vad_end_to_acknowledgement_audio_ms`, `voice.barge_in_cancel_latency_ms`,
  `voice.stt_confidence`, and SQL/RAG latency measurements. `tts_first_audio` begins when TTS
  synthesis starts; `final_transcript_to_first_audio` begins when the final STT event (or typed text)
  reaches the API and ends when the first audio frame is sent to the client/carrier. It includes
  agent decision time and does not represent the acoustic end of caller speech. `stt_speech_to_final_transcript`
  starts at the STT provider's speech-start event and ends
  when its final transcript arrives. `vad_end_to_acknowledgement_audio_ms` begins when the API
  receives the browser's VAD-end event and ends when the first prepared, non-factual acknowledgement
  chunk is sent. It is a distinct filler metric: it does not measure the substantive answer, acoustic
  endpoint, or browser playback. Acknowledgement chunks are excluded from
  `final_transcript_to_first_audio_ms`, which measures the actual answer stream. Realtime speech falls back to HTTP `tts-1` if verified first
  audio misses `OPENAI_REALTIME_TTS_FIRST_AUDIO_TIMEOUT_SECONDS` (default 1.8 s); after playback
  begins, the longer TTS idle timeout applies. TTS stream duration is recorded on completion,
  provider error, and cancellation once synthesis has begun. Treat P95 values as unavailable until
  a representative live run has data.
- `python scripts/evaluation/release_report.py` prints the current local safety/grounding/retrieval gates and marks
  missing provider credentials or OAuth as `blocked by prerequisite`.

## Security controls

- Keep `.env`, OAuth token JSON, and provider keys outside source control.
- Never store raw audio. Transcript rows are redacted and expire after thirty days.
- Use the audit ledger and outbox payloads for incident review; they exclude contact email content.
- Production release still requires PostgreSQL, production secrets, provider contracts, a real
  inventory source, consent/recording policy, and measured latency and retrieval evidence.
