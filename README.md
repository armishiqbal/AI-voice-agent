# Awaaz Estate — real-estate voice agent

FastAPI + LangGraph + React application for continuous UrduLish property conversations.
SQL inventory is authoritative; document retrieval adds sourced context. Booking actions use
validated services and a durable outbox for Calendar, employee email, and n8n integration.

## Run locally

```bash
cp .env.example .env
python3 -m venv backend/venv
source backend/venv/bin/activate
pip install -e 'backend[dev,providers,local-rag,voice-openai]'
npm ci --prefix frontend
npm run build --prefix frontend
python run.py
```

Configure `OPENAI_API_KEY` in the ignored `.env`. Open http://localhost:8000, or run
`npm run dev --prefix frontend` for http://localhost:5173. `/readyz` reports the configured
voice routes. A ready provider is not evidence of a completed microphone conversation.
Run `python worker.py` separately for outbox processing.

No demo inventory is seeded into the runtime. Import authorized company CSV/JSON inventory
and documents using the authenticated admin endpoints documented in [API](docs/API.md).
For a single-process local vector store set `RAG_PROVIDER=faiss`; install `local-rag` and configure
OpenAI embeddings. Pinecone remains available for managed retrieval. Fixture data is used only
by isolated tests and evaluations.

## Business integrations

Google OAuth setup, employee directory, and credential paths are in [operations](docs/OPERATIONS.md).
`EMPLOYEE_EMAIL_DIRECTORY` maps assigned employees to trusted email addresses. Client confirmation
and validated contact details are required before a voice booking is submitted. Provider delivery
is asynchronous; a local booking does not imply Calendar/email delivery has succeeded.

The importable [n8n workflow](workflows/n8n/README.md) receives authenticated redacted business events.
The application owns booking transactions and retries; n8n handles downstream CRM automation.
Telephony uses the existing Twilio webhook/media adapter and requires a real number and public TLS.

## Container preparation

Set a strong `POSTGRES_PASSWORD` in `.env`, then `docker compose up --build` starts PostgreSQL,
migrations, API, and worker. Optional n8n: `docker compose --profile automation up --build`.
Pin `N8N_IMAGE` to a reviewed release/digest and set `N8N_ENCRYPTION_KEY` before deployment.
Google credentials belong in the read-only `secrets/` mount. Deployment is deferred.

## Verification

```bash
python -m pytest -q backend/tests
python -m ruff check backend/app backend/tests scripts
npm test --prefix frontend
npm run build --prefix frontend
python scripts/evaluation/evaluate.py
python scripts/evaluation/evaluate_conversations.py
python scripts/evaluation/evaluate_rag.py
python scripts/evaluation/evaluate_memory.py
python scripts/evaluation/evaluate_appointments.py
python scripts/evaluation/release_report.py --api-url http://127.0.0.1:8000
```

PostgreSQL concurrency tests require PostgreSQL; SQLite cannot establish those guarantees.
The fixture evaluations measure local behavior, not real caller quality or live voice latency.
No grade, conversion uplift, universal injection resistance, or production readiness is claimed.

## Submission documents

- [Requirement-by-requirement audit](docs/CAPSTONE_REQUIREMENTS.md)
- [Architecture](docs/ARCHITECTURE.md), [API](docs/API.md), [conversation flows](docs/CONVERSATION_FLOWS.md)
- [RAG evaluation](docs/RAG_EVALUATION.md), [Fish vs ElevenLabs](docs/FISH_ELEVENLABS_COMPARISON.md)
- [Human voice rubric](docs/HUMAN_VOICE_RUBRIC.md), [optional local TTS](docs/TTS_EVALUATION.md)
- [Release checklist](docs/RELEASE_CHECKLIST.md), [maintenance](docs/MAINTENANCE.md), [troubleshooting](docs/TROUBLESHOOTING.md)
- [Executive report](docs/STAKEHOLDER_REPORT.md), [demo script](docs/DEMO_SCRIPT.md), [slide deck](docs/DEMO_SLIDES.html)

Outstanding evidence requires real company data, configured external accounts, consented voice
recordings/native-speaker scoring, and measured end-to-end latency. See the audit for exact gates.
