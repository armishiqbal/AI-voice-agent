# 🛠️ Awaaz Estate — Production Troubleshooting Guide

This guide covers operational diagnosis, failure isolation, and recovery procedures for the Awaaz Estate AI Voice Agent platform.

---

## 1. Quick Diagnostic Triage Matrix

| Symptom | Probable Cause | Diagnostic Command / Inspection | Resolution |
|:---|:---|:---|:---|
| **Agent hears nothing / No STT transcript** | Mic permission denied, low input gain, or VAD silence threshold too high | Browser Console: `[VAD]` logs or `/v1/voice` WS frames | Ensure microphone is allowed; test with 1-click query chips; check Web Speech API fallback or Deepgram API key |
| **Agent responds in text but no audio plays** | TTS provider timeout or browser audio autoplay policy | Check network tab for `audio_chunk` WS events; check console for Web Audio suspended state | Click anywhere in UI to enable audio context; check `OPENAI_API_KEY`, `FISH_AUDIO_API_KEY`, or local TTS service URLs |
| **WebSocket disconnects immediately (Code 1008)** | Invalid Origin header or missing session ticket | Inspect `POST /v1/voice/session` response and WS handshake headers | Verify `CORS_ORIGINS` in `.env` includes client domain (e.g. `http://localhost:5173`) |
| **Booking fails: "Slot unavailable"** | Slot outside business hours (Mon-Sat, 10:00-18:00 PKT) or employee booked | Query `GET /v1/appointments/slots?property_id=PROP-001` | Choose slot on half-hour boundary within business hours |
| **Google Calendar events not created** | Missing or expired `secrets/google.token.json` | Check outbox table: `SELECT * FROM outbox_events WHERE status = 'pending'` | Run `python scripts/admin/authorize_google.py` to refresh OAuth token |
| **Database error: "Table not found"** | Unmigrated SQLite/PostgreSQL schema | Run `alembic current` in `backend/` | Run `cd backend && alembic upgrade head` or delete dev SQLite DB for auto-rebuild |

---

## 2. Voice & Audio Pipeline Troubleshooting

### A. Browser Microphone & Web Audio Capture
* **Issue**: Microphone is active, but Neural Orbit particle sphere doesn't react.
* **Root Cause**: Web Audio `AudioContext` is in suspended state due to browser autoplay security policies.
* **Resolution**:
  1. Ensure the user clicks the microphone button or any UI element first to resume `AudioContext`.
  2. In `frontend/src/voiceAudio.ts`, verify `audioCtx.state === 'running'`.
  3. Ensure `audioCtx.createAnalyser()` is connected to the microphone `MediaStreamSource`.

### B. Dual-Language STT Recognition Drops
* **Issue**: Pakistani English/Urdu mixed words (*"Marla"*, *"Kanal"*, *"Clifton"*) are dropped or misheard.
* **Root Cause**: Web Speech API set to a single language model or Deepgram endpointing threshold too short.
* **Resolution**:
  1. The client utilizes dual recognition (`en-US` for Latin script UrduLish + `ur-PK` for Urdu script).
  2. For server-side Deepgram STT, configure:
     ```env
     STT_PROVIDER=deepgram
     STT_MODEL=nova-3
     STT_LANGUAGE=multi
     STT_ENDPOINTING_MS=300
     ```

### C. Barge-in / Interruption Timing
* **Issue**: User speaks while agent is talking, but agent keeps speaking.
* **Root Cause**: High noise floor preventing client VAD trigger, or server-side cancel event dropped.
* **Resolution**:
  1. The client implements Adaptive VAD (`frontend/src/voiceVad.ts`) learning the background ambient noise.
  2. Immediate cancellation sends `{"type": "cancel"}` over the WebSocket.
  3. Client stops `speechSynthesis.cancel()` immediately and flushes the incoming audio buffer.

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
  1. If credentials are unset, the outbox worker safely simulates delivery in development and logs the structured dispatch event.
  2. For live delivery, provide:
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
