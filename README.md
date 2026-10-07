# Awaaz Estate — Multilingual AI Voice Agent & Luxury Real Estate Marketplace


<p align="center">
  <img src="https://img.shields.io/badge/Next.js-15.5.24-black?style=flat-square&logo=next.js&logoColor=white" alt="Next.js" />
  <img src="https://img.shields.io/badge/React-19.3.0-61dafb?style=flat-square&logo=react&logoColor=black" alt="React 19" />
  <img src="https://img.shields.io/badge/TypeScript-5.7.3-3178c6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript" />
  <img src="https://img.shields.io/badge/FastAPI-Python%203.11+-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/PostgreSQL-16%20%C2%B7%20Supabase-336791?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/Civic%20Compliance-CDA%20%C2%B7%20DHA%20%C2%B7%20RDA-226e52?style=flat-square" alt="Civic Compliance" />
  <img src="https://img.shields.io/badge/Backend%20Tests-85%2F85%20Passing-2ea44f?style=flat-square&logo=pytest&logoColor=white" alt="Tests" />
  <img src="https://img.shields.io/badge/Design%20System-100%25%20SVG%20%C2%B7%20Zero%20Emojis-18523c?style=flat-square" alt="Design System" />
</p>

FastAPI and PostgreSQL remain the business authority for the Awaaz Estate property catalog,
inquiries, appointments, and the multilingual voice assistant. The public property website is a
separate Next.js application; the existing Vite voice client remains available at `/assistant/`.
Booking actions use validated services and a durable outbox for Calendar, employee email, and
n8n integration.

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

Set `VOICE_ENABLED=true` and configure the required providers in the ignored `.env` to run voice.
For API and website work without voice credentials, set `VOICE_ENABLED=false`. Open the existing
assistant at http://localhost:8000/assistant/ or use
`npm run dev --prefix frontend` for http://localhost:5173. `/readyz` reports configured voice
routes. A ready provider is not evidence of a completed microphone conversation. Run
`python worker.py` separately for outbox processing.

## Property website

The Next.js application in `website/` renders public pages on the server and reads listing data
from FastAPI. To run it alongside the local API:

```bash
npm ci --prefix website
AWAAZ_API_URL=http://127.0.0.1:8000 SITE_URL=http://localhost:3000 \
  ASSISTANT_URL=http://localhost:8000/assistant/ npm run dev --prefix website
```

Open http://localhost:3000. No real property fixtures are seeded. Imported listings begin as
drafts; staff must classify the transaction and property type, confirm availability, approve the
facts and photographs, and publish them before they enter public search or voice recommendations.

For a same-origin local stack, set `POSTGRES_PASSWORD` and the application encryption/admin keys
in `.env`, then run:

```bash
VOICE_ENABLED=false docker compose --profile website up --build
```

Open http://localhost:8080. Set `VOICE_ENABLED=true` only when the production voice providers and
voice capacity settings are configured. The gateway listens on loopback in this Compose file;
production TLS, DNS, trusted proxy addresses, approved business contact details, managed auth and
media credentials, and owner-reviewed inventory still require operator configuration. See
[website deployment notes](deploy/README.md) and [website acceptance gates](docs/PROPERTY_WEBSITE.md).

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
migrations, API, and worker. Add `--profile website` to include the Next.js site and same-origin
Nginx gateway. Optional n8n: `docker compose --profile automation up --build`.
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
