# Release checklist and implementation matrix

This is the end-to-end handover checklist for Awaaz Estate. It distinguishes code that is
implemented and verified locally from evidence that requires provider credentials, a managed
database, or an approved live-call policy. A local pass is not a production claim.

## Scope decision

- Browser voice console is the v1 acceptance surface.
- PostgreSQL is the production database; SQLite is only the zero-setup development fallback.
- `python worker.py` is the transactional outbox worker for Calendar, Gmail, and the internal
  CRM-ready lead log.
- Docker and n8n are intentionally not required. Existing Docker files are historical scaffolding,
  not part of the run path or release gate.
- Telephony has a fail-closed Twilio media-stream adapter. A carrier, phone number,
  recording-consent policy, PCM16 TTS configuration, and live-call test are required before enabling
  phone calls.

## Requirement matrix

| Area | Implementation | Evidence/status | Remaining prerequisite |
|---|---|---|---|
| API runtime | FastAPI, `run.py`, health/readiness/OpenAPI | Passed locally | PostgreSQL process for production |
| Backend checks | Ruff, unit/integration suite | 93 passed; 2 PostgreSQL-only concurrency tests skipped locally | PostgreSQL CI run |
| Web console | React/Vite microphone, text fallback, playback, barge-in | Frontend build passed | Browser/device human voice test |
| STT | Deepgram streaming adapter, confidence gate, low-confidence event | Contract/tests passed | `DEEPGRAM_API_KEY`, live latency run |
| Reasoning | LangGraph routes and typed `AgentDecision` | 41/41 scripted fixture conversations passed | `OPENAI_API_KEY` and live model run |
| Grounding | SQL facts, filtered Pinecone context, source IDs, deterministic fallback, persisted tool results | Grounded local gate passed | Pinecone corpus and live RAG evaluation |
| Inventory | 36+ labeled fixtures, CSV/JSON validation, source/version ledger, amenities and investment goals | Ingestion tests passed | Real company export and import review |
| Multilingual TTS | Configurable language routes and isolated OSS worker contracts | Contract tests passed; model loading/voice quality not verified | Approved language/script scope, target hardware, model/license decision, native-speaker review |
| TTS benchmark | Balanced 20-phrase Fish-vs-ElevenLabs protocol | Harness implemented; no winner assumed | API keys and recorded human rubric |
| Appointments | PKT hours, Mon-Sat, 30-minute slots, employee ownership, conflict index, encrypted optional phone | 9/9 isolated cases passed | Production PostgreSQL concurrency test |
| Reschedule/cancel | Reference + matching consented email + idempotency | Deterministic tests passed | Operator acceptance test |
| Contact privacy | Fernet encryption, consent validation, redacted transcripts, no raw audio, 30-day expiry | Privacy tests passed | Key rotation/retention policy approval |
| Delivery | Transactional outbox, leases, retries, internal CRM sink, Calendar/Gmail handlers, lead follow-up timestamp | Worker tests passed | Google OAuth test account |
| Admin security | `X-Admin-Api-Key` protects metrics, reports, inventory imports, and knowledge ingestion outside development; consented lead form stays public | API boundary implemented | Strong secret in deployment secret store |
| Browser voice access | Short-lived one-use ticket, Origin/client binding, database-backed issue quota, active-call leases, trusted-proxy allowlist | Local replay/binding/throttle/capacity/disconnect tests and Uvicorn CIDR middleware test pass | Verify deployed proxy chain and PostgreSQL lease concurrency before public exposure |
| Observability | Counters, node transitions, provider failures, STT confidence, P95 latency | Local report implemented | Representative live traffic |
| Security | Prompt-injection guard, tool validation, no LLM direct execution | Injection/evaluation cases passed | Security review and threat-model sign-off |
| Telephony | Optional signed Twilio webhook/outbound call adapter, μ-law media bridge, no fake call state | Codec/signature tests passed; live call not claimed | Carrier, phone number, consent, PCM16 TTS, live-call test |
| Deployment | CI, Alembic head `0021_voice_session_leases`, process-based handover docs | Clean SQLite upgrade/downgrade/re-upgrade passed; PostgreSQL CI/live evidence not yet verified | Managed PostgreSQL, secrets, deployment operator |

## Release gates

Run these checks from the repository root:

```bash
python -m pytest backend/tests
python -m ruff check backend/app backend/tests scripts
python -m compileall -q backend
npm run build --prefix frontend
python scripts/evaluation/evaluate.py
python scripts/evaluation/evaluate_rag.py
python scripts/evaluation/evaluate_memory.py
python scripts/evaluation/evaluate_appointments.py
python scripts/evaluation/release_report.py
```

For a clean migration check (without touching the development database):

```bash
cd backend
DATABASE_URL=sqlite:///./awaaz-migration.db alembic upgrade head
DATABASE_URL=sqlite:///./awaaz-migration.db alembic current
```

The release report must show local passes for grounding, retrieval, memory, appointment
correctness, and prompt-injection safety. It must show live voice latency and Google delivery as
`blocked by prerequisite` until the relevant credentials and test runs exist. Telephony must also
remain `blocked by prerequisite` until Twilio signature, media, consent, and live-call checks pass.

## Ordered handover

1. Copy `.env.example` to `.env`; keep secrets out of source control.
2. Install the backend and frontend dependencies.
3. Set PostgreSQL `DATABASE_URL` and run `alembic upgrade head`.
4. Start `python run.py`, `python worker.py`, and the Vite frontend in separate terminals.
5. Verify `/healthz`, `/readyz`, the browser text path, and one appointment lifecycle.
6. Configure provider adapters one at a time, then rerun the release report after each live gate.
7. Perform human Urdu/English code-switching, barge-in, pronunciation, and consent review.
8. Only after all live gates pass, publish a production claim or enable telephony.
