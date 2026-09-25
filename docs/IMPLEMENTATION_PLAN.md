# Awaaz Estate: end-to-end implementation plan

This plan is the source of truth for the implementation. The target is a browser-first,
multilingual real-estate voice agent with deterministic property and appointment safety.
Docker and n8n are intentionally out of scope: the API, worker, PostgreSQL, and external
provider adapters run as ordinary local processes or deployable containers later.

## System boundary

```text
React/Vite microphone and playback
        │ WebSocket: JSON events + 16 kHz PCM16
        ▼
FastAPI session endpoint (/v1/voice)
        ├─ Deepgram streaming STT (optional live adapter)
        ├─ LangGraph guardrails, intent, grounded resolution
        │    ├─ PostgreSQL SQL facts and availability checks
        │    ├─ Pinecone knowledge retrieval (optional live adapter)
        │    └─ OpenAI structured decision (optional; validated before use)
        ├─ deterministic appointment service + encrypted contact data
        └─ multilingual TTS router (required isolated open-source workers)
             │ ordered PCM16 or compressed streaming audio chunks
             ▼
        browser playback + barge-in cancellation

Appointment transaction → PostgreSQL outbox → python worker.py
                                      ├─ Google Calendar (OAuth)
                                      └─ Gmail employee notification (OAuth)
```

## Remaining end-to-end execution plan (current baseline)

This section is the actionable plan from the repository's current state, not a claim that
the system is production-ready. The latest local `python scripts/evaluation/release_report.py` run on
2026-09-23 reports 41/41 scripted fixture conversations, 20/20 SQL-backed retrieval
questions, and 9/9 isolated appointment cases passing. The same report marks Pinecone
evidence false and live provider readiness false for voice, multilingual TTS, Google
delivery, and telephony. Those local fixture results do not establish live quality.

JEV ranked the next major workstream against the known prerequisites and selected the live
multilingual TTS proof gate first (1.0 recommendation probability and confidence, 2026-09-23).
The worker and adapters exist, but model weights, language quality, licensing, latency, and
resource use have not been demonstrated. This is a sequencing signal, not engineering
validation or quality evidence. A prior JEV review of this roadmap escalated for human
review because spec-match confidence was low (0.41), despite a high composite score
(0.8665); this roadmap remains manually reviewed, not automatically approved by JEV.

Because TTS installation needs the user's launch language/script and hardware choices, a
follow-up JEV decision ranked anonymous voice-session security work highest (0.97). The code now
contains database-backed active-session leases and trusted-proxy configuration. The WebSocket
capacity test now uses an isolated temporary database and explicitly closes the accepted socket;
the focused test and complete local backend suite pass. PostgreSQL concurrency and deployment
proxy behavior remain unverified. JEV is a prioritization aid; test and deployment evidence remain
the engineering acceptance criteria.

The PostgreSQL CI job now has a preflight that fails unless the backend test process actually
selected PostgreSQL, preventing the concurrency checks from silently becoming SQLite skips. The
backend development extra now installs `pytest-asyncio`, which its async tests require. Both
changes are locally checked; the hosted PostgreSQL job has not yet run.

The canonical `python run.py` launcher has a regression test that proves the configured
`TRUSTED_PROXY_IPS` reaches Uvicorn's `forwarded_allow_ips` setting. Its JEV review returned
`review`; manual inspection confirms it tests launch configuration, not forwarded-header behavior
through a live deployment proxy, which remains unverified. An ASGI integration test now wraps the
actual voice-session endpoint with Uvicorn's proxy middleware and verifies that a trusted proxy's
forwarded client IP is used while an untrusted proxy's header is ignored.
JEV reviewed the ASGI regression with `review` (safe-to-apply 0.64); manual review confirms it
covers the endpoint/middleware contract, while an actual deployment proxy remains outside local
test coverage.

Current local checks: 112 backend tests pass with three PostgreSQL-only tests skipped because no
local server is available; the launcher/proxy target passes 4/4;
`python scripts/evaluation/evaluate_appointments.py` passes 9/9; and a clean in-memory SQLite Alembic upgrade
reaches migration `0021`. The CI
preflight accepts a PostgreSQL SQLAlchemy URL, but this is only dialect-selection evidence, not a
database connection or concurrency result. The workspace has no Git remote to dispatch the
hosted workflow from here.

The frontend CI job now runs its Node test suite before the production build; locally, all 8
frontend protocol/audio tests pass and `npm run build --prefix frontend` succeeds. This adds local
browser-client contract coverage to CI but still does not replace a real browser/device voice test.
JEV reviewed this workflow patch with a high composite (0.9365) but returned `escalate` because
test-gap and blast-radius confidence were low; manual workflow inspection and local checks are the
available evidence, and the hosted job remains unrun.

For this turn's bounded sequencing decision, JEV selected `postgres_ci_proof` with probability
1.0 over installing large TTS models on this 8 GiB RAM / 11 GiB free-disk machine. This ranks
work; it does not prove CI behavior. A JEV review of the small patch escalated rather than
approving it, so the change was retained only after manual YAML, test, dependency-install, and
scope checks. Hosted PostgreSQL execution is still the authoritative next check.

### Immediate implementation queue

Execute these gates in order. Do not start the next dependent gate until its exit evidence
is recorded. Work that does not depend on the TTS result may proceed in parallel only where
it does not consume or overwrite provider/model configuration.

| Order | Work item | Why now | Exit evidence |
|---|---|---|---|
| 0 | Close the session-security gate: verify lease cleanup and trusted-proxy IP behavior; run PostgreSQL concurrency CI | Local lease/capacity regression is now deterministic and passes against an isolated test database. PostgreSQL race behavior and forwarded-client-IP trust still need deployment-shaped evidence | Focused WebSocket lifecycle tests and full suite pass; PostgreSQL concurrency CI passes; proxy tests prove only configured proxies can supply client IP |
| 1 | Confirm launch language/script matrix, inference hardware, licensing, and budget; install one candidate model in an isolated TTS service and run smoke generation | The worker is contract-tested but has never loaded weights; language quality and runtime fit are unknown | Approved matrix and hardware record; model/version/license record; successful warmup; per-language/script samples; measured cold/warm latency, memory, and disk |
| 2 | Run native-speaker multilingual TTS evaluation and select supported routing/fallback behavior | A configured route is not proof that the model pronounces it well; Roman Urdu and code-switching require their own evidence | Scored rubric by language/script, explicit supported/unsupported matrix, approved candidate, and documented fallback/refusal behavior |
| 3 | Complete a live browser voice vertical slice using the TTS route that passed evaluation | Validates codecs, event lifecycle, STT-to-first-audio latency, interruption, and provider degradation end to end | Browser/device report, live provider trace, latency percentiles, barge-in timing, and tested failure recovery |
| 4 | Validate PostgreSQL migrations/concurrency; import owner-approved inventory and ingest approved knowledge | SQL and retrieval must be proven against production-shaped rather than fixture data | Clean migration/restore/concurrency evidence, reconciled import, versioned index, and non-fixture RAG report |
| 5 | Exercise real Google test-account Calendar/Gmail delivery and outbox recovery | Local handlers do not prove OAuth refresh, provider delivery, or duplicate behavior | Test-account booking lifecycle, retry/restart/reconciliation evidence, and no duplicate side effects |
| 6 | Complete security/privacy/operations review and deploy staging | Public endpoints and external credentials need deployment-shaped controls before real calls | Threat-model signoff, retention/key-rotation/restore evidence, alerts, secrets, and staging rollback drill |
| 7 | Enable inbound telephony and run controlled pilot only after all prior gates | Phone calling introduces carrier, consent, signature, codec, and operational risks | Signed inbound test-call evidence, approved consent policy, pilot go/no-go, and rollback owner |

Blocking inputs for work item 1 are an approved language/script matrix, a target inference
machine (CPU/GPU and available memory/disk), Hugging Face access/token if the selected
checkpoint is gated, and license approval. Do not download multi-gigabyte weights or accept
model terms automatically. Existing Docker files remain untouched; the TTS worker is an
ordinary separate process during local development. No n8n is part of this plan.

### Phase 0 — Lock the product and release contract

- Confirm which languages/scripts are required at launch. Until confirmed, use the six
  currently configured languages (Urdu, English, Hindi, Arabic, Punjabi, Bengali) as a
  provisional test scope. Add Urdu-in-Arabic-script, Roman Urdu, and Urdu-English
  code-switching as distinct test classes; do not assume one model handles them equally.
- Define the first target deployment and hardware budget, peak concurrent calls, data
  residency, transcript policy, support hours, and whether the first live acceptance
  requires inbound PSTN. This plan assumes it does, after the browser pipeline is stable.
- Freeze business invariants: SQL is truth for availability/pricing, the model cannot
  execute tools, appointments require deterministic validation and consent, and unknown
  facts must result in clarification or human handoff.
- Deliver: signed language/consent/product acceptance matrix, threat model, provider
  inventory, environment/secret checklist, and production SLO definitions.
- Gate: product owner approves the language list, data/recording policy, inventory source,
  and the target environment. No production voice or phone numbers before this gate.

### Phase 1 — Prove the multilingual TTS choice before wiring the whole call path

- Keep the existing TTS provider boundary; add model adapters only after confirming
  supported language/script coverage, inference license, gated access terms, runtime
  dependencies, model size, cold-start, memory/VRAM, and cancellation behavior.
- Evaluate an open-weight hybrid as a candidate, not a preselected winner: Indic
  Parler-TTS documents Urdu, Bengali, Hindi, and English support (Punjabi is listed as
  unofficial); Chatterbox Multilingual documents Arabic, English, and Hindi. Neither
  alone establishes natural Roman-Urdu/UrduLish code-switching. Meta MMS Urdu Latin model
  cards are CC-BY-NC-4.0, so do not assume that checkpoint is suitable for commercial
  deployment without legal approval.
- Build a consented, native-speaker-reviewed phrase set per language and script covering
  greetings, property names, PKR amounts, dates/times, acronyms, questions, refusals,
  code-switching, and long responses. Record intelligibility, pronunciation, accent,
  consistency, latency, audio artifacts, and language-routing errors.
- Implement lazy model loading in an isolated inference process/service, bounded request
  queues, cancellation/timeout, health/readiness probes, version-pinned model artifacts,
  and explicit `audio_unavailable` behavior. Do not silently synthesize with an unsupported
  language or download multi-gigabyte weights at API startup.
- Deliver: provider/license decision record, reproducible benchmark, human rubric results,
  model resource profile, and TTS adapter with contract tests.
- Implementation progress: the backend now has an authenticated HTTP PCM16 adapter, separate
  `services/tts/` model workers, language-to-engine routes, lazy weight loading, and contract
  tests. The worker now fails startup without a service token in every environment, and the API
  rejects configured worker URLs without that token; direct Uvicorn launches cannot bypass the
  launcher check. Authenticated warmup runs a smoke synthesis, and worker readiness remains false
  until it succeeds. The API adapter also checks each loaded worker advertises every language
  routed to it, so an outdated or mismatched worker cannot make multilingual readiness pass
  accidentally; this remains capability evidence, not native-speaker quality approval. Model and
  tokenizer downloads now use explicit immutable Hugging Face commit revisions and report those
  revisions in readiness/warmup; no weights have been downloaded and model quality is untested.
  The Chatterbox source declares mutable `resemble-perth@master`; the TTS uv resolver now
  overrides it with a reviewed immutable Perth commit and records the full dependency graph in
  `services/tts/uv.lock`. The Parler and Chatterbox extras are declared mutually exclusive so
  their conflicting Transformers versions resolve in separate worker environments. Lockfile
  validation and per-engine install dry-runs pass; model downloads and live warmup remain unrun.
  Cancellation now stops response delivery immediately while retaining the single
  inference slot until non-interruptible native/model work in `asyncio.to_thread` has actually
  finished, preventing abandoned model threads from stacking up during barge-in. The TTS
  readiness response now exposes the worker's supported-language list, and
  `scripts/benchmark/benchmark_open_source_tts.py` produces reproducible per-language latency/audio artifacts
  plus a two-reviewer scoring sheet from an approved dataset. The TTS libraries and weights
  are not installed or downloaded in this workspace, so actual model loading, pronunciation,
  latency, resource usage, and the human acceptance gate remain incomplete.
- Gate: every required language/script passes the agreed native-speaker threshold; model
  license/access terms are approved; resource/cost budget fits the chosen host. If the
  open-source candidates fail, stop and choose whether to narrow language scope, fund
  fine-tuning, or approve a commercial fallback—do not label the failed coverage complete.

### Phase 2 — Complete and measure one browser voice vertical slice

- Configure one live STT, reasoning, and TTS path that passed Phase 1. WebSocket Origin
  validation, bounded JSON/audio payloads, bounded audio queues, PCM16 frame checks, and
  disconnect cleanup are implemented locally; verify them again in deployment-like settings.
  Anonymous voice entry now requires a two-minute, one-use REST-issued ticket bound to Origin
  and client address; only the ticket hash and keyed client fingerprint are persisted. Ticket
  issuance is limited atomically across workers at ten per minute per client address. A trusted
  proxy allowlist and database-backed active-call leases are implemented in code; local lease
  cleanup tests pass, but PostgreSQL concurrency and forwarded-IP behavior must be proven before
  public exposure. Tickets are not named-user authentication.
  The browser now starts its server-side audio session only after microphone/context setup,
  drains the session on setup failure, stops capture on outbound WebSocket backpressure, safely
  parses server events, unlocks playback from the user gesture, and sends selected response
  language over the voice protocol. Low-confidence STT now gives a retry instruction; TTS failure
  keeps the written response visible without silently switching to browser-native speech, and
  replay is limited to bounded audio returned by the selected provider. Verify these behaviors
  with actual browsers/devices. Validate audio sample rate/codec, provider timeouts, language
  detection, and low-confidence speech behavior.
- Test turn-taking with real microphones/headphones and noisy-room samples. A caller
  interruption must stop current playback, cancel in-flight generation, and prevent late
  audio from leaking into the next turn.
- Stream the first useful TTS segment as soon as safe text is available; measure each
  stage separately (audio end → final transcript → decision → first audio), not just a
  single aggregate number. The implemented `voice.end_of_turn_to_first_audio_ms` currently
  starts at final-transcript/text receipt, not a microphone-level acoustic endpoint; add a
  client/VAD timestamp if the SLO requires that exact boundary. Define whether the two-second
  P95 target is achievable on the chosen local hardware; report failed samples and concurrency,
  not only averages.
- Deliver: browser-to-agent-to-browser live call report, device/browser matrix, latency
  distributions, interruption results, provider/degraded-mode behavior, and operator-visible
  session diagnostics.
- Gate: no fabricated audio; failed STT/LLM/TTS produces a clear recovery or handoff path;
  p95 first-audio and barge-in limits pass under agreed load; native reviewers approve
  the required language mix.

### Phase 3 — Replace fixture-only proof with production data and grounded retrieval

- Provision PostgreSQL in a non-production environment; apply Alembic migrations from a
  clean database, verify migration upgrade/rollback procedure, unique constraints, backup,
  restore, and concurrent booking tests.
- Obtain a real, owner-approved company inventory export. Run it through the existing
  importer in dry-run, resolve validation errors with the inventory owner, import with
  source/version/timestamp provenance, and reconcile representative rows against the
  source system. Keep demo fixtures clearly labeled and out of customer responses.
- Populate a versioned Pinecone index from approved brochures, FAQs, payment plans, and
  property descriptions. Confirm namespace/metadata filters, deletion/re-index strategy,
  embedding/model version, tenant boundaries, retrieval traces, and source citations.
- Extend evaluation beyond the current fixture path: labeled questions with known source
  spans, no-answer/contradiction questions, stale inventory, mixed filters, multilingual
  queries, and prompt-injection in retrieved documents. Compare retrieval against a SQL
  baseline and report both metrics and per-language slices.
- Deliver: reconciled inventory import, indexed and versioned corpus, operational
  re-index command, real-data evaluation report, and rollback procedure.
- Gate: no response describes fixtures as live; every structured availability/price claim
  comes from SQL; Pinecone-grounded answers carry source IDs; misses and stale data fail
  closed to clarification/handoff; grounded-answer and retrieval thresholds pass on the
  agreed non-fixture evaluation set.

### Phase 4 — Validate agent behavior and safety on real provider paths

- Run all current scripted conversations against both deterministic fixture mode and the
  configured model path. Add adversarial cases for tool abuse, prompt leakage, retrieved
  injection, low-confidence/empty transcripts, duplicate turns, out-of-scope advice,
  seller valuation, angry caller, silence, and provider timeouts.
- Verify every LLM response is schema-validated, source-grounded where factual, and
  separated from deterministic tool execution. Record graph transitions and redacted
  decisions without logging secrets, raw audio, or unredacted contact details.
- Add request/session quotas, rate limits, retry bounds, circuit breakers, and safe
  degradation; prevent model retries from duplicating bookings or emails.
- Deliver: versioned prompt/decision schema, adversarial report, regression suite, audit
  event review, and incident/handoff playbook.
- Gate: zero successful injection/tool-permission bypasses in the agreed test set; every
  consequential action requires explicit confirmation and deterministic validation.

### Phase 5 — Prove appointments and business delivery against test accounts

- Run API + worker against PostgreSQL with real employee calendars in a dedicated Google
  test account. Verify OAuth scopes, token refresh/rotation, timezone/PKT mapping,
  employee assignment, overlapping bookings, idempotent retry, reschedule, cancellation,
  and outbox recovery after worker restart.
- Verify Gmail delivery, employee routing, message content minimization, duplicate-send
  behavior, retry/dead-letter handling, and outbox reconciliation. Confirm CRM-ready lead
  events with the target CRM owner; until a CRM exists, label the current internal sink as
  a log, not a CRM integration.
- Deliver: test-account evidence, worker runbook, outbox metrics/alerts, and reconciliation
  report.
- Gate: all booking lifecycle cases pass on PostgreSQL and Calendar; no event is marked
  delivered before provider confirmation; duplicates are controlled; operators can
  reconcile pending/failed events.

### Phase 6 — Security, privacy, and operational readiness

- Complete threat modeling for public WebSocket/REST/admin APIs, uploads, provider keys,
  OAuth, PII encryption, replay/abuse, webhook signatures, dependency/model supply chain,
  and tenant isolation if multiple agencies are in scope.
- Prove retention jobs purge transcript rows and encrypted contact details according to
  policy; exercise key rotation, least-privilege access, log redaction, consent capture,
  deletion requests, backup retention, and incident response. Keep raw audio out of
  persistence and telemetry.
- Add structured logs and production metrics/traces for provider latency/errors, turn
  transitions, STT confidence, RAG source/miss rates, TTS language routing, booking
  outcomes, outbox age, and cancellation latency. Set actionable alerts and dashboards.
- Deliver: security review, privacy/retention evidence, restore test, alerts, runbooks,
  dependency/model bill of materials, and secret rotation plan.
- Gate: no critical/high unresolved security finding; restore and retention verified;
  public routes and admin boundaries tested in deployment-like configuration.

### Phase 7 — Deploy a staging environment and test a production-shaped workload

- Choose managed PostgreSQL and a process/container host (Railway or Render are candidates);
  make API, TTS inference, outbox worker, and frontend deployment responsibilities explicit.
  Do not place large model inference in the API process until load tests prove isolation and
  resource headroom.
- Set secret-store values, HTTPS/WSS, restrictive CORS, migrations-before-rollout,
  readiness/liveness checks, static frontend origin, log/metric export, autoscaling or
  single-instance limits, persistent model cache policy, database pool sizing, and backup.
- Run CI from clean install: lint, unit/integration tests, migration upgrade, frontend
  typecheck/build, security/dependency scan, and release-report artifact. Deploy staging
  with no real customer data, then run smoke, load, restart, and rollback drills.
- Deliver: staging URL, reproducible deployment config/runbook, load-test report, rollback
  evidence, and release candidate report with each gate labeled local/live/blocked.
- Gate: clean deploy and rollback; restore point meets the agreed RPO/RTO; latency/error
  budgets hold under expected peak load; no secret or fixture leakage.

### Phase 8 — Enable and validate inbound telephony (required for full phone launch)

- Provision the carrier account/number, approved recording/consent wording, public HTTPS
  webhook and WSS endpoint, Twilio signature validation, and a test-call allowlist. Keep
  outbound calling separately disabled until purpose, consent, and policy are approved.
- Validate the telephony codec/sample-rate bridge, frame sequencing, silence handling,
  STT endpointing, TTS codec compatibility, interruptions, call hangup, carrier retries,
  signature replay, and cleanup. Test with several networks/devices and native speakers.
- Deliver: inbound test-call evidence, consent UX/policy approval, call failure runbook,
  and provider cost/recording configuration.
- Gate: successful signed inbound call end-to-end; invalid signature/replay rejected;
  no recording/raw-audio retention unless separately approved; live latency and handoff
  meet the agreed gate. Otherwise phone remains disabled and this is not a full voice-launch.

### Phase 9 — Controlled pilot and launch decision

- Pilot only with a small approved inventory and employee group, monitored operating
  hours, human takeover, spend/rate limits, and rollback switch. Review transcripts only
  under the consent/retention policy and include native-language human review.
- Compare live results to the release criteria by language, device, intent, provider, and
  call outcome; track failure denominators and blocked/abandoned calls. Fix regressions,
  repeat the same gates, and version every model, prompt, index, and inventory snapshot.
- Deliver: signed go/no-go report, support/on-call owner, known limitations, change process,
  and post-pilot backlog.
- Gate: product, operations, security/privacy, and business owners accept evidence; all
  hard gates pass; remaining limitations are explicit. Until then label the system
  staging/pilot and never production-ready.

### Cross-phase exit criteria

- Keep evidence classes separate: local unit/fixture checks, integration tests with test
  accounts, staging measurements, human language review, and production pilot outcomes.
- A gate without its required provider, inventory, human review, or operator evidence is
  `blocked by prerequisite`, not passed. The release report must preserve this distinction.
- No phase silently widens the supported language list, uses a commercial model as an
  “open-source” substitute, or enables outbound/recorded calls without explicit approval.

## Build order and completion criteria

1. **Foundation — complete locally**
   - Layered `backend/app` modules, settings from environment, SQLite development bootstrap.
   - PostgreSQL-compatible SQLAlchemy models and Alembic migrations through
     `0021_voice_session_leases` (PostgreSQL CI must still verify this migration and its concurrency behavior).
   - `python run.py` starts the API; `/healthz`, `/readyz`, OpenAPI, and CORS are available.

2. **Property intelligence — SQL and validated file ingestion implemented**
   - SQL repository is authoritative for price, inventory, availability, and employee assignment.
   - Fixtures/imports also carry amenities, payment plans, nearby schools, and nearby hospitals
     for verified factual answers.
   - Fixture data is explicitly demo data and cannot be described as live inventory.
   - Recommendations use a stable deterministic fit score (area, city, and budget fit) only
     after SQL availability filtering; the score never overrides inventory truth.
   - `scripts/data/import_inventory.py` validates CSV/JSON rows and records source, timestamp, and row errors
     in the import-batch ledger. Optional PDF extraction produces versioned chunks for Pinecone.
   - OpenAI embeddings and Pinecone upsert/query construction are implemented; live credentials
     and a populated corpus are still required for retrieval-quality gates.

3. **Agent safety and grounding — adapters and filtered retrieval implemented**
   - LangGraph guardrails reject prompt-injection patterns and route seller requests to handoff.
   - Conversation snapshots persist deterministic tool results and structured bedrooms, amenities,
     and investment-goal preferences.
   - OpenAI output is `AgentDecision`-validated; SQL availability remains authoritative.
   - Pinecone results are filtered by SQL-selected property IDs and source IDs are carried into
     structured recommendations. A retrieval miss falls back to SQL facts or clarification.
   - Explicit LangGraph action nodes now route `answer`, `ask_clarification`, `recommend`,
     `book`, `reschedule`, `cancel`, and `handoff`; deterministic property answers expose only
     verified SQL facts and their source IDs.
   - Conversation state snapshots are persisted in `conversation_states`, so language, criteria,
     selected properties, and appointment context survive API restarts and multiple workers; both
     snapshots and transcripts are purged after 30 days.

4. **Voice loop — browser pipeline and optional providers implemented**
   - Browser captures/resamples PCM16, sends WebSocket audio, receives ordered audio chunks,
     and stops playback on caller speech or `barge_in`.
   - A fail-closed Twilio media-stream adapter is implemented for optional phone entry; phone
     numbers and recording consent remain disabled until carrier credentials and a live-call policy
     are approved.
   - Deepgram and multilingual TTS adapters fail explicitly with `stt_unavailable` or
     `audio_unavailable`; no fake audio is generated.
   - The isolated open-source Parler/Chatterbox workers are the required production TTS route;
     production configuration now rejects Fish Audio, ElevenLabs, and legacy in-process MMS as
     the selected TTS provider. Those adapters remain available only in development for
     comparison. Readiness requires both configured authenticated OSS workers and successful
     per-language worker probes; this still does not mean native-speaker quality has passed.
   - The browser supports PCM16 and buffered compressed-audio decoding. Install and warm the
     model workers only after target hardware, model terms, and language/script scope are
     approved; then measure P95 end-of-turn to first audio and barge-in latency.

5. **Appointments, delivery, and audit — local workflow complete**
   - Booking validates available property, Asia/Karachi Monday-Saturday 10:00-18:00, and
     30-minute slots. Idempotency prevents duplicate appointments.
   - Consented appointment phone numbers are encrypted and included only at the Calendar/Gmail
     delivery boundary. Leads can carry an optional CRM follow-up reminder.
   - Reschedule/cancel requires reference plus matching consented email.
   - Outbox persists attempts, exponential backoff, and worker leases. `python worker.py` runs it.
   - Google Calendar and Gmail adapters are enabled only with a pre-authorized OAuth token;
     without it, events stay pending rather than being marked delivered.
   - Appointment outbox payloads carry the client name and encrypted contact ciphertext, so
     Calendar/Gmail can include consented client details without persisting raw email in the outbox.
   - Tool actions are recorded in the redacted `tool_audit_events` ledger.
   - Consent-bound seller/uncertain-intent leads are encrypted, redacted, persisted, and emitted
     as `lead.created` outbox events for the internal CRM-ready sink.
   - Employee assignment, overlapping slots, and update idempotency are enforced transactionally;
     PostgreSQL/SQLite also carry a partial unique index for active employee slots so concurrent
     workers cannot create duplicate visits.
   - Conversation turns store only redacted text with a 30-day expiry; raw audio is never stored.

6. **Evaluation and operations — local evidence implemented**
   - The scripted runner covers 41 conversations and the admin report endpoint labels its mode.
   - Report grounded-answer rate (factual decisions must carry property and source IDs), retrieval
     accuracy, prompt-injection bypasses, appointment correctness, STT confidence, provider
     failures, node transitions, and latency percentiles.
   - `python scripts/evaluation/release_report.py` emits machine-readable gate statuses and never turns missing live
     credentials into a passed production claim.
   - Keep fixture/demo results separate from live-provider evidence; a human voice-quality rubric
     and live-provider run remain open.

7. **Deployment and handover — non-Docker handover implemented; live prerequisites remain**
   - CI checks Ruff, pytest, Alembic upgrade, and frontend typecheck/build. It now provisions
     PostgreSQL 16, runs a PostgreSQL-only concurrent-booking regression, and upgrades a clean
     PostgreSQL database separately from the SQLite migration smoke test. This test is skipped
     locally when the configured database is not PostgreSQL; the current workstation has no
     PostgreSQL server, so a successful CI run is still required as authoritative race evidence.
   - The API's production TTS configuration accepts only the isolated open-source multilingual
     provider; commercial adapters and the legacy MMS provider cannot make release readiness
     pass. Live model and human-review gates remain open.
   - Use managed PostgreSQL and a process supervisor for API, frontend, and worker.
   - Configure secrets through environment/secret storage; never commit OAuth or provider keys.
   - Production claim requires provider credentials, Google test account, consent policy, and
     measured acceptance gates; local tests alone are not production evidence.

## Commands

From the repository root:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e 'backend[dev]'
python run.py                 # API: http://localhost:8000
python worker.py              # appointment outbox in a second terminal
npm install --prefix frontend
npm run dev --prefix frontend  # browser console: http://localhost:5173
python -m pytest backend/tests
python -m ruff check backend/app backend/tests scripts
python scripts/evaluation/evaluate_appointments.py
```

For PostgreSQL, set `DATABASE_URL`, then run `cd backend && alembic upgrade head` before
starting the API. For a local migration check, use
`DATABASE_URL=sqlite:///./awaaz-migration.db alembic upgrade head` from `backend/`.

Optional live adapters:

```bash
pip install -e 'backend[voice-deepgram]'  # Deepgram streaming STT
pip install -e 'backend[voice-local]'     # local MMS multilingual TTS
pip install -e 'backend[voice-fish]'      # Fish Audio streaming TTS
pip install -e 'backend[voice-elevenlabs]' # ElevenLabs streaming benchmark/provider
pip install -e 'backend[providers]'       # OpenAI + Pinecone adapters
pip install -e 'backend[google]'          # Calendar + Gmail adapters
```

## Release gates

The release report must label each gate `passed locally`, `passed with live evidence`, or
`blocked by prerequisite`:

- P95 voice latency < 2 seconds; barge-in response < 250 ms.
- Open-source multilingual TTS has a versioned model/license decision and native-reviewed samples
  for every approved language/script, with cold/warm latency, resource use, and failure behavior
  recorded. Fish Audio/ElevenLabs remain optional comparisons only and cannot satisfy this gate.
- Grounded-answer rate ≥ 95% on the curated set; retrieval accuracy ≥ 85%.
- Zero successful prompt-injection bypasses.
- 100% correct book/reschedule/cancel behavior in the isolated SQL appointment evaluation.
- No raw audio persistence; redacted transcript retention and consent are verified.
