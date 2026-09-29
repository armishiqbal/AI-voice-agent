# Capstone requirement audit

Audit scope: the attached **Week 4 — Production-Grade AI Voice Agent for Real Estate** brief.
Actual hosting/deployment is deferred by the user; deployment preparation stays in scope.

**Implemented** means code or a document exists, not that an external service has been accepted.
**Evidence pending** means the remaining proof needs real company data, operator credentials,
a running external service or human reviewers. Evaluation fixtures are synthetic and isolated.
Exact test counts and current results belong to generated evaluation output and the final run log,
not stale numbers copied into this matrix.

## Daily tasks

| Brief requirement | Implementation / artifact | Acceptance boundary |
|---|---|---|
| D1.1 STT, reasoning, tools, retrieval, memory, TTS, telephony, workflows and architecture diagram | [Architecture](ARCHITECTURE.md); `backend/app/integrations`, `agents`, `services`, `workers` | Implemented documentation and adapters; live carrier/provider acceptance pending |
| D1.2 Buyer, rental, commercial, investment, returning, reschedule, cancel flowcharts | [Conversation flows](CONVERSATION_FLOWS.md) | Shared inquiry flow branches by purpose; separate memory and lifecycle flows |
| D1.3 Pakistani professional/warm/patient persona; greeting, confirmation, hesitation, acknowledgement, objections | [Persona](PERSONA_AND_PROMPT.md); `agents/prompts.py`, `agents/graph.py` | Implemented style and safe responses; naturalness/persuasion require human scores |
| D1.4 Fish vs ElevenLabs latency, naturalness, emotion, streaming, cloning, pricing, multilingual, Urdu, switching, conclusion | [TTS protocol](TTS_EVALUATION.md), [comparison](FISH_ELEVENLABS_COMPARISON.md); live provider smoke | The configured paid Fish model returned HTTP 402; after fixing model selection, the $0 development model completed one synthetic TTS phrase (909 ms first audio, 1,805 ms total). ElevenLabs is unconfigured and no human scores exist, so no quality winner or complete provider comparison is claimed |
| D1.5 Scope, goals, guardrails, persuasion, booking, escalation system prompt | `agents/prompts.py`; [persona policy](PERSONA_AND_PROMPT.md) | Typed decisions with deterministic action validation |
| D2.1 Properties, prices, locations, amenities, schools, hospitals, payment plans, developers, FAQs | `domain/models.py`, CSV/JSON staff import panel with a headers-only template, inventory repository; source and availability surfaced in UI | Import API and UI validate rows and surface rejected-row errors; unrecognized availability values are rejected rather than silently converted to unavailable. When the live API confirms the inventory is empty, the staff import panel opens to guide the operator toward real listings. Current live dataset has zero listings. Real company inventory must be supplied and reviewed |
| D2.2 Loader, chunking, embedding, vector store, retriever, answers; compare chunk sizes | PDF/TXT/Markdown staff ingestion panel, `services/ingestion.py`, `services/retrieval.py`, Pinecone/FAISS adapters; `scripts/benchmark/benchmark_chunk_retrieval.py` | Upload preserves source, revision, property, city, and language metadata; the test mocks the vector store. Real company documents and retrieval quality are pending |
| D2.3 SQL facts vs semantic brochure/FAQ retrieval and justification | [Architecture](ARCHITECTURE.md); SQL repositories + filtered vector adapters | SQL stays authoritative for price, size, availability and staff |
| D2.4 Budget, city, area, bedrooms, purpose, amenities, investment goals | `domain/scoring.py`, property repository, agent preference state; live inventory browser filters by city, area, purpose, bedrooms, maximum PKR price, and price order | Deterministic matching/ranking; parses common spoken budget words in English, Roman Urdu, Devanagari, and Urdu script; browser filters operate only on returned company listings; no guarantee of investment returns |
| D2.5 Twenty questions; grounding, retrieval, hallucination | `evals/rag_questions.json`; `scripts/evaluation/evaluate_rag.py` | SQL fixture evaluator reports exact-match retrieval accuracy, SQL-grounded property-reference rate, and unexpected-property-ID rate with denominators. Separate 20 gold-source chunk questions run with real embeddings/FAISS over synthetic documents. Neither suite measures arbitrary generated-sentence entailment; real company data and claim-level human annotation remain pending |
| D3.1 Streaming speech→LLM→voice under two seconds | Voice WebSockets, OpenAI Realtime STT/TTS, Deepgram English/Urdu hybrid routes, AudioWorklet capture/playback and live transcripts | Browser VAD is the explicit turn boundary (425 ms). Hybrid Deepgram sends `Finalize` per utterance on one provider socket, keeps it alive between turns, and closes only at session end. The API waits for Deepgram before advertising microphone readiness and coalesces stable transcript segments. Earlier synthetic 2026-09-29 runs returned 3/3 final transcripts and contextual replies, but substantive audio took 2.06–2.71 seconds. Other same-day runs were variable, including a 5,772.7 ms first-turn transcript and a missing final. Two additional independent three-turn sessions returned 6/6 final transcripts, contextual replies, and audio at 1.17–1.59 seconds. The newest same-day loopback returned 3/3 replies and audio, with 2/3 under two seconds (1.14–2.11 seconds); generated macOS speech was poorly recognized, so it is not UrduLish accuracy evidence. Earlier slow/failed runs remain evidence against declaring the latency gate reliable; the sample does not establish p95. The API does not act on unconfirmed interim text. OpenAI structured decisions remain unverified and deterministic fallback is available; OpenAI Realtime voice is unavailable. Generated speech is not human-microphone, human-quality, or physical-playback acceptance. See the dated verification report and artifacts. |
| D3.2 Interruptions, fillers, hesitation, thinking pauses, laughter, acknowledgements | Voice cancellation/VAD, barge-in control, live turn captions, persona responses, timeout recovery | Interruption and concise, provider-generated non-factual acknowledgement audio are implemented on both the Realtime and configured hybrid TTS routes. When STT cannot finalize or the final transcript is below the confidence threshold, the configured live TTS asks the caller to repeat; uncertain words never reach the agent. Expressive laughter and human-equivalent delivery are not established |
| D3.3 Budget→DHA→cheaper contextual memory | Durable preference/history state; `scripts/evaluation/evaluate_memory.py` | Local memory evaluation; returning identity remains consent/session-bound |
| D3.4 Price, trust, location, investment, builder, maintenance objections | Grounded objection routing and clarification/handoff | Answers require available facts; no invented guarantees or valuations |
| D3.5 Record and score naturalness, persuasion, fluency, latency, flow | [Human rubric](HUMAN_VOICE_RUBRIC.md) | Evidence pending: consented recordings and independent native-speaker scores |
| D4.1 Calendar event: name, phone, employee, property, date/time, notes | `integrations/calendar.py`, validated appointment context | Adapter implemented; actual OAuth test-account acceptance pending |
| D4.2 Employee email: time/property/client/requirements | Gmail handler and validated `EMPLOYEE_EMAIL_DIRECTORY` | Never guess recipient; live delivery pending operator setup |
| D4.3 Book/reschedule/cancel plus Calendar/email updates | Appointment service/repository, voice confirmation and outbox handlers; UI gates visit requests on loaded availability | Deterministic contracts tested; external lifecycle delivery pending |
| D4.4 n8n Call→Intent→Match→Appointment→Calendar→Email→CRM; retry failures | [n8n export and contract](../workflows/n8n/README.md) | Trusted app owns early stages, durable worker Google stages, n8n final CRM; import/runtime acceptance pending |
| D4.5 Transcripts, preferences, appointment history, follow-up reminders | SQL transcripts/state/leads/appointments/outbox; scheduled `lead.follow_up_due` events; protected due-reminder panel | Due times are atomically enqueued once, delivered to the internal CRM log and forwarded to n8n when configured; staff can audit and mark completed. Client campaigns remain future scope |
| D5.1 History, profile, preferences, budget, intent, tool outputs, appointment state | `ConversationState` in `agents/graph.py`; durable state repository | Implemented state contract |
| D5.2 Greeting, detection, RAG, recommendation, booking, reschedule, cancel, email, goodbye graph | [Agent graph](ARCHITECTURE.md) | RAG inside grounded resolution; separate delivery LangGraph executes Calendar/email/CRM after confirmed SQL transaction |
| D5.3 Search, Calendar, email, CRM, availability, RAG tools | Typed service/adapters and deterministic API boundary | Model selects typed routes; business mutations run outside free-form LLM output |
| D5.4 No unavailable slots/properties; clarify uncertainty | SQL conflicts, available-only recommendations, strict evidence checks | Local PostgreSQL appointment-conflict and lease concurrency tests passed; external load/soak remains pending |
| D5.5 Every node transition and annotated execution traces | `core/observability.py`, graph traces, admin metrics/audit | Bounded local trace sink; archive redacted evidence for submission |
| D6.1 40+ conversations, all eleven named categories | Multi-turn evaluation suite plus original 41 single-turn cases | Current fixture run: 44/44 multi-turn conversations passed across all eleven categories (92 total turns). This is local reasoning/memory evidence, not live voice or human quality |
| D6.2 Ignore instructions, prompt reveal, fake appointments, private data attacks | Guardrail tests/evaluations, typed action validation | Local adversarial tests; finite cases do not prove universal safety |
| D6.3 Latency, conversation/booking success, tool failures, RAG, memory, hallucination | Evaluation CLIs, TTS benchmark, runtime metrics | Local metrics distinct from live voice and external service evidence |
| D6.4 Average latency, quality, API/Calendar/email failures, booking, RAG misses | Metrics/outbox/call outcomes and human quality rubric | Quality requires reviewer data; sustained monitoring/export pending deployment |
| D6.5 Docker, FastAPI, env, logs, health, CI/CD | Dockerfile/Compose, `.env.example`, `/healthz`, `/readyz`, GitHub CI | ARM64 image built locally and smoke-run: frontend served and `/healthz` returned `ok`; `/readyz` correctly stayed blocked in the isolated no-credentials container. Compose validates with a process-only placeholder; optional n8n is pinned to `2.40.7`. Remote CI and deployed runtime are not claimed |
| D7.1 Deploy backend/voice/graph/vector/DB/monitoring | Docker/process runbooks | **Deferred by user** |
| D7.2 Architecture, API, user, admin, maintenance, troubleshooting | [Docs index](README.md), [operations](OPERATIONS.md), staff inventory/document upload panels | Documentation and staff ingestion flows delivered; operator acceptance still required |
| D7.3 Thresholds, uptime, weekly retraining, vector refresh, prompts, backups, security | [Maintenance plan](MAINTENANCE.md) | Targets/procedures; uptime or recovery achievement not claimed |
| D7.4 Ten-minute call→inquiry→RAG→recommend→objection→book→Calendar/email→reschedule→cancel | [Script](DEMO_SCRIPT.md), [actual slide deck](DEMO_SLIDES.html) | Preparation delivered; full live demo waits for provider/data prerequisites |
| D7.5 WhatsApp, SMS, Salesforce/HubSpot, Urdu/English/Punjabi, cloning, analytics, scoring, followups, payments, MLS | [Future roadmap](FUTURE_ENHANCEMENTS.md); the UI now exposes the protected live metrics endpoint | Live service analytics view implemented; other roadmap items remain proposals, not acceptance features |

## Final submission cross-check

| Deliverable | Location | Status |
|---|---|---|
| Production-ready natural UrduLish voice agent | Runtime, voice UI, providers | Implemented local system; production/quality acceptance pending |
| LangGraph state and tool orchestration | `backend/app/agents`, services/workers | Implemented; graph/service division disclosed above |
| Grounded vector RAG | Pinecone/FAISS + ingestion/retrieval | Implemented; company-corpus evaluation pending |
| Property database/recommendations | SQL models/import/scoring | Implemented; actual inventory pending |
| Google appointment lifecycle | Calendar integration/outbox | Implemented; live OAuth acceptance pending |
| Assigned employee email | Gmail + validated directory | Implemented; live delivery pending |
| CRM logging | SQL lead/transcript/state/history + n8n sink | Internal logging implemented; external CRM acceptance pending |
| Documented FastAPI | `/docs`, [API reference](API.md) | Implemented |
| Optional web UI | `frontend/` | Implemented |
| Comprehensive evaluation report | Evaluation scripts + release report + [release checklist](RELEASE_CHECKLIST.md) | Local evidence available by execution; live latency/quality still pending |
| Injection/security documented results | Backend tests + evaluation outputs | Local evidence; production security acceptance pending |
| Monitoring/maintenance | [Plan](MAINTENANCE.md), protected `/v1/admin/metrics`, browser analytics panel | Delivered plan and local instrumentation; panel metrics are bounded to the running process and reset on restart |
| Docker/env configuration | Root Dockerfile/Compose/`.env.example` | Image build and isolated health smoke passed; actual deployment deferred |
| Complete technical docs | [Index](README.md) and linked guides | Delivered |
| Executive report | [Stakeholder report](STAKEHOLDER_REPORT.md) | Delivered with limits |
| Ten-minute script and slide deck | [Script](DEMO_SCRIPT.md), [HTML slides](DEMO_SLIDES.html) | Delivered; live external actions not fabricated |

## Outstanding inputs and evidence

1. Import reviewed **real company inventory and documents**; approve staff email mapping.
2. Configure test-account Google OAuth, actual n8n runtime and client CRM endpoint; verify committed deliveries.
3. Configure a phone number and public TLS endpoint for an inbound Twilio acceptance call (depends on deferred deployment).
4. Capture consented human UrduLish conversations; score the rubric and provider comparison; measure end-of-speech to audible reply, including p95 under two seconds.
5. Local PostgreSQL tests and migration-upgrade gates pass on disposable databases; the current PostgreSQL suite reports 341 passed and 2 optional FAISS skips because `faiss` is not installed, and a fresh PostgreSQL Alembic upgrade reached revision `0023_lead_follow_up_enqueued` (head). The ARM64 image builds and runs its static frontend and health endpoint locally. Remote CI, hosted-database load/soak, provider integrations, and production rollback/backup evidence remain; local checks cannot substitute for those environments.

See the [current verification report](VERIFICATION_REPORT.md) for the final executed checks and saved evidence.
