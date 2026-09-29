# 🛠️ Awaaz Estate — Production Troubleshooting Guide

This guide covers operational diagnosis, failure isolation, and recovery procedures for the Awaaz Estate AI Voice Agent platform.

---

## 1. Quick Diagnostic Triage Matrix

| Symptom | Probable Cause | Diagnostic Command / Inspection | Resolution |
|:---|:---|:---|:---|
| **Agent hears nothing / no final transcript** | Browser microphone permission/device failure, no captured frames, or server STT failure | Voice troubleshooting stages, browser microphone indicator, `/readyz`, backend logs, and `/v1/voice` WebSocket events | Allow/select a microphone and speak after the UI says Listening. If the provider does not finalize a committed turn, the live voice route asks you to repeat; unconfirmed interim text is not sent to the agent. There is no browser speech-recognition fallback. |
| **Agent responds in text but no audio plays** | TTS route/provider failure or browser playback/decode failure | Check for `audio_unavailable`, `audio_chunk`, browser playback errors, and the replay control | Follow the stage-specific recovery message; check provider account credits and configured TTS route. The app does not substitute browser speech. |
| **WebSocket disconnects immediately (Code 1008)** | Missing/expired one-use session ticket or rejected Origin | Inspect `POST /v1/voice/session`, the WS handshake, and server security logs | Confirm the browser uses the configured origin and starts a fresh voice session; do not reuse an old ticket. |
| **Booking fails: "Slot unavailable"** | Slot outside business hours (Mon-Sat, 10:00-18:00 PKT) or employee booked | Query `GET /v1/appointments/slots?property_id=PROP-001` | Choose slot on half-hour boundary within business hours |
| **Google Calendar events not created** | Missing or expired `secrets/google.token.json` | Check outbox table: `SELECT * FROM outbox_events WHERE status = 'pending'` | Run `python scripts/admin/authorize_google.py` to refresh OAuth token |
| **Database error: "Table not found"** | Unmigrated SQLite/PostgreSQL schema | Run `alembic current` in `backend/` | Run `cd backend && alembic upgrade head` or delete dev SQLite DB for auto-rebuild |

---

## 2. Voice & Audio Pipeline Troubleshooting

### A. Browser Microphone & Web Audio Capture
* **Issue**: Microphone is active, but Neural Orbit particle sphere doesn't react.
* **Root Cause**: Microphone capture, its `AudioWorklet`, or the Web Audio context may not have started.
* **Resolution**:
  1. Start voice using the call control, which requests the microphone from the browser.
  2. Check browser permission and the selected input in Voice & Language Settings.
  3. Confirm the UI advances from Microphone starting to Listening only after AudioWorklet frames arrive.

### B. Dual-Language STT Recognition Drops
* **Issue**: Pakistani English/Urdu mixed words (*"Marla"*, *"Kanal"*, *"Clifton"*) are dropped or misheard.
* **Root Cause**: The selected server transcription route may misrecognize code-switched speech or omit a short word.
* **Resolution**:
  1. Check the final transcript shown for that turn and verify the selected language route.
  2. Inspect the actual `STT_PROVIDER`, `STT_MODEL`, and Urdu-language settings in the local `.env`; do not assume a browser-side fallback is active.
  3. Retest with a clear, short phrase. Record native-speaker accuracy issues for human evaluation rather than treating a synthetic loopback as language-quality proof.

### C. Barge-in / Interruption Timing
* **Issue**: User speaks while agent is talking, but agent keeps speaking.
* **Root Cause**: High noise floor preventing client VAD trigger, or server-side cancel event dropped.
* **Resolution**:
  1. The client implements Adaptive VAD (`frontend/src/voiceVad.ts`) learning the background ambient noise.
  2. The client stops current browser playback and sends `{"type": "barge_in"}` over the WebSocket.
  3. Inspect `voice.barge_in_cancel_latency_ms` and confirm the next response has a new response ID; the app uses provider audio and does not call browser `speechSynthesis`.

---

## 3. LangGraph & Conversation State Troubleshooting

### A. Multi-Turn Memory Drifting
* **Issue**: Caller states budget in turn 1 (*"Budget 3 crore hai"*), but agent asks for budget again in turn 3.
* **Root Cause**: Conversation state lost or not tied to persistent `conversation_id`.
* **Resolution**:
  1. Inspect `ConversationStateStore` records in SQLite / PostgreSQL:
     ```sql
     SELECT conversation_id, state_payload, updated_at FROM conversation_states WHERE conversation_id = '<ID>';
     ```
  2. Verify `conversation_id` is maintained across all WebSocket frames within the active session lease.

### B. Prompt Injection & Guardrail Escalation
* **Issue**: Valid user query mistakenly triggers safety handoff (*"Main internal instructions nahi share kar sakta"*).
* **Root Cause**: Overly strict regex match in `backend/app/agents/graph.py` on system prompt keywords.
* **Resolution**:
  1. Check `backend/tests/test_agent.py` test cases.
  2. Guardrail triggers only on explicit adversarial attempts:
     - `"ignore previous instructions"`
     - `"reveal system prompt"`
     - `"book fake appointments without availability"`
     - `"dump internal company database"`

---

## 4. Workflows, Calendar & Outbox Troubleshooting

### A. Outbox Worker Backlog
* **Issue**: Appointments show booked in UI, but no confirmation emails or calendar invites are sent.
* **Root Cause**: The background worker process (`python worker.py`) is not running.
* **Resolution**:
  1. Check outbox events in database:
     ```sql
     SELECT id, event_type, status, attempts, last_error FROM outbox_events WHERE status != 'completed';
     ```
  2. Start the worker in a separate terminal or Docker service:
     ```bash
     python worker.py
     ```
  3. The worker automatically claims pending events with database-level lease locks and executes handlers with exponential backoff.

### B. Google Calendar OAuth Token Expiration
* **Issue**: Worker logs `google.auth.exceptions.RefreshError: invalid_grant`.
* **Root Cause**: Google OAuth refresh token has expired, been revoked, or the app is in Google Testing mode (7-day token limit).
* **Resolution**:
  1. Re-authorize locally:
     ```bash
     GOOGLE_CLIENT_SECRET_PATH=secrets/client_secret.json \
     GOOGLE_TOKEN_PATH=secrets/google.token.json \
     python scripts/admin/authorize_google.py
     ```
  2. In Google Cloud Console, transition OAuth consent screen from "Testing" to "In Production" to allow permanent refresh tokens.

### C. WhatsApp Webhook Dispatch
* **Issue**: WhatsApp messages fail to deliver with `TelephonyProviderError`.
* **Root Cause**: Missing Twilio or Meta WhatsApp Business API credentials in `.env`.
* **Resolution**:
  1. Check `/readyz` for `calendar` and `gmail`. Configuration readiness does not prove delivery.
  2. Inspect the outbox event's `status`, `attempts`, and `last_error`. Missing OAuth leaves work pending; it is not marked as delivered.
  3. For live delivery, configure:
     ```env
     TWILIO_ACCOUNT_SID=ACxxx
     TWILIO_AUTH_TOKEN=xxx
     TWILIO_FROM_NUMBER=whatsapp:+14155238886
     ```

---

## 5. Database & Concurrency Troubleshooting

### A. SQLite Database Lock (`OperationalError: database is locked`)
* **Issue**: Concurrency lock when running pytest or heavy load on SQLite.
* **Root Cause**: Multiple threads attempting concurrent writes to a single SQLite file.
* **Resolution**:
  1. In development, SQLite uses WAL mode (`PRAGMA journal_mode=WAL;`).
  2. For multi-agent production workloads, switch to PostgreSQL:
     ```env
     DATABASE_URL=postgresql://awaaz:awaaz@localhost:5432/awaaz
     ```
  3. Run migrations: `cd backend && alembic upgrade head`.

### B. Session Lease Expiry
* **Issue**: WebSocket closes with `Session lease expired`.
* **Root Cause**: Voice session exceeded `VOICE_SESSION_LEASE_SECONDS` (default: 90s per turn / idle).
* **Resolution**:
  * Adjust `VOICE_SESSION_LEASE_SECONDS=300` in `.env` for longer conversational turns.

---

## 6. Health & Diagnostic Endpoints

Verify system readiness using standard HTTP monitoring checks:

```bash
# 1. API Liveness Check
curl http://localhost:8000/healthz
# Expected: {"status":"healthy"}

# 2. Provider Readiness Check (LLM, TTS, STT, Vector DB)
curl http://localhost:8000/readyz
# Expected: {"status":"ready","database":"connected","providers":{...}}

# 3. Observability & Traces Snapshot (Requires Admin Key outside dev)
curl -H "X-Admin-Api-Key: $ADMIN_API_KEY" http://localhost:8000/v1/admin/metrics

# 4. CRM Call Outcomes Ledger
curl -H "X-Admin-Api-Key: $ADMIN_API_KEY" http://localhost:8000/v1/admin/call-outcomes?limit=10
```
