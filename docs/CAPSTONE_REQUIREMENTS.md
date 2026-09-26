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
| D1.4 Fish vs ElevenLabs latency, naturalness, emotion, streaming, cloning, pricing, multilingual, Urdu, switching, conclusion | [TTS protocol](TTS_EVALUATION.md), [comparison](FISH_ELEVENLABS_COMPARISON.md); benchmark harness | Documented comparison/protocol; no unsupported quality winner; real recordings and provider comparison pending |
| D1.5 Scope, goals, guardrails, persuasion, booking, escalation system prompt | `agents/prompts.py`; [persona policy](PERSONA_AND_PROMPT.md) | Typed decisions with deterministic action validation |
| D2.1 Properties, prices, locations, amenities, schools, hospitals, payment plans, developers, FAQs | `domain/models.py`, inventory ingestion and property repositories; isolated fixtures | Schemas and import path implemented; real company dataset must be supplied and reviewed |
| D2.2 Loader, chunking, embedding, vector store, retriever, answers; compare chunk sizes | `services/ingestion.py`, `services/retrieval.py`, Pinecone/FAISS adapters; `scripts/benchmark/benchmark_chunk_retrieval.py` | Pipeline implemented; fixture/chunk evidence does not establish real company retrieval quality |
| D2.3 SQL facts vs semantic brochure/FAQ retrieval and justification | [Architecture](ARCHITECTURE.md); SQL repositories + filtered vector adapters | SQL stays authoritative for price, size, availability and staff |
| D2.4 Budget, city, area, bedrooms, purpose, amenities, investment goals | `domain/scoring.py`, property repository, agent preference state | Deterministic matching/ranking; no guarantee of investment returns |
| D2.5 Twenty questions; grounding, retrieval, hallucination | `evals/rag_questions.json`; `scripts/evaluation/evaluate_rag.py` | SQL fixture baseline plus 20 gold-source questions with real embeddings/FAISS; synthetic corpus; property-ID error rate is narrower than claim-level hallucination |
| D3.1 Streaming speech→LLM→voice under two seconds | Voice WebSockets, STT/TTS adapters, AudioWorklet capture/playback | Streaming implemented; representative physical-device p95 <2s not established |
| D3.2 Interruptions, fillers, hesitation, thinking pauses, laughter, acknowledgements | Voice cancellation/VAD and persona responses | Interruption and concise acknowledgements implemented; expressive laughter and human-equivalent delivery not established |
| D3.3 Budget→DHA→cheaper contextual memory | Durable preference/history state; `scripts/evaluation/evaluate_memory.py` | Local memory evaluation; returning identity remains consent/session-bound |
| D3.4 Price, trust, location, investment, builder, maintenance objections | Grounded objection routing and clarification/handoff | Answers require available facts; no invented guarantees or valuations |
| D3.5 Record and score naturalness, persuasion, fluency, latency, flow | [Human rubric](HUMAN_VOICE_RUBRIC.md) | Evidence pending: consented recordings and independent native-speaker scores |
| D4.1 Calendar event: name, phone, employee, property, date/time, notes | `integrations/calendar.py`, validated appointment context | Adapter implemented; actual OAuth test-account acceptance pending |
| D4.2 Employee email: time/property/client/requirements | Gmail handler and validated `EMPLOYEE_EMAIL_DIRECTORY` | Never guess recipient; live delivery pending operator setup |
| D4.3 Book/reschedule/cancel plus Calendar/email updates | Appointment service/repository, voice confirmation and outbox handlers | Deterministic contracts tested; external lifecycle delivery pending |
| D4.4 n8n Call→Intent→Match→Appointment→Calendar→Email→CRM; retry failures | [n8n export and contract](../workflows/n8n/README.md) | Trusted app owns early stages, durable worker Google stages, n8n final CRM; import/runtime acceptance pending |
| D4.5 Transcripts, preferences, appointment history, follow-up reminders | SQL transcripts/state/leads/appointments/outbox | Follow-up timestamps stored; automatic campaigns are future scope |
| D5.1 History, profile, preferences, budget, intent, tool outputs, appointment state | `ConversationState` in `agents/graph.py`; durable state repository | Implemented state contract |
| D5.2 Greeting, detection, RAG, recommendation, booking, reschedule, cancel, email, goodbye graph | [Agent graph](ARCHITECTURE.md) | RAG inside grounded resolution; separate delivery LangGraph executes Calendar/email/CRM after confirmed SQL transaction |
| D5.3 Search, Calendar, email, CRM, availability, RAG tools | Typed service/adapters and deterministic API boundary | Model selects typed routes; business mutations run outside free-form LLM output |
| D5.4 No unavailable slots/properties; clarify uncertainty | SQL conflicts, available-only recommendations, strict evidence checks | Local validation; PostgreSQL concurrency gate required |
| D5.5 Every node transition and annotated execution traces | `core/observability.py`, graph traces, admin metrics/audit | Bounded local trace sink; archive redacted evidence for submission |
| D6.1 40+ conversations, all eleven named categories | Multi-turn evaluation suite plus original 41 single-turn cases | Use multi-turn report for this requirement; never rename single prompts as conversations |
| D6.2 Ignore instructions, prompt reveal, fake appointments, private data attacks | Guardrail tests/evaluations, typed action validation | Local adversarial tests; finite cases do not prove universal safety |
| D6.3 Latency, conversation/booking success, tool failures, RAG, memory, hallucination | Evaluation CLIs, TTS benchmark, runtime metrics | Local metrics distinct from live voice and external service evidence |
| D6.4 Average latency, quality, API/Calendar/email failures, booking, RAG misses | Metrics/outbox/call outcomes and human quality rubric | Quality requires reviewer data; sustained monitoring/export pending deployment |
| D6.5 Docker, FastAPI, env, logs, health, CI/CD | Dockerfile/Compose, `.env.example`, `/healthz`, `/readyz`, GitHub CI | Preparation implemented; image build requires daemon; CI definition is not an executed CI pass |
| D7.1 Deploy backend/voice/graph/vector/DB/monitoring | Docker/process runbooks | **Deferred by user** |
| D7.2 Architecture, API, user, admin, maintenance, troubleshooting | [Docs index](README.md), [operations](OPERATIONS.md) | Documentation delivered; operator acceptance still required |
| D7.3 Thresholds, uptime, weekly retraining, vector refresh, prompts, backups, security | [Maintenance plan](MAINTENANCE.md) | Targets/procedures; uptime or recovery achievement not claimed |
| D7.4 Ten-minute call→inquiry→RAG→recommend→objection→book→Calendar/email→reschedule→cancel | [Script](DEMO_SCRIPT.md), [actual slide deck](DEMO_SLIDES.html) | Preparation delivered; full live demo waits for provider/data prerequisites |
| D7.5 WhatsApp, SMS, Salesforce/HubSpot, Urdu/English/Punjabi, cloning, analytics, scoring, followups, payments, MLS | [Future roadmap](FUTURE_ENHANCEMENTS.md) | Proposal only, not implemented acceptance features |

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
| Monitoring/maintenance | [Plan](MAINTENANCE.md) | Delivered plan and local instrumentation |
| Docker/env configuration | Root Dockerfile/Compose/`.env.example` | Prepared; actual deployment deferred |
| Complete technical docs | [Index](README.md) and linked guides | Delivered |
| Executive report | [Stakeholder report](STAKEHOLDER_REPORT.md) | Delivered with limits |
| Ten-minute script and slide deck | [Script](DEMO_SCRIPT.md), [HTML slides](DEMO_SLIDES.html) | Delivered; live external actions not fabricated |

## Outstanding inputs and evidence

1. Import reviewed **real company inventory and documents**; approve staff email mapping.
2. Configure test-account Google OAuth, actual n8n runtime and client CRM endpoint; verify committed deliveries.
3. Configure a phone number and public TLS endpoint for an inbound Twilio acceptance call (depends on deferred deployment).
4. Capture consented human UrduLish conversations; score the rubric and provider comparison; measure end-of-speech to audible reply, including p95 under two seconds.
5. Run PostgreSQL concurrency/migrations, a Docker image build, and CI in their actual environments before release. Local fixture passes cannot substitute for these checks.

See the [current verification report](VERIFICATION_REPORT.md) for the final executed checks and saved evidence.
