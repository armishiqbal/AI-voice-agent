# Awaaz Estate — executive handover

## Objective and delivered system

Awaaz Estate gives a real-estate company a consistent conversational intake channel: understand
buyer/renter/investor preferences, explain verified property options, preserve context, handle
objections, and coordinate visits. Seller valuations are handed to a human. The delivered
implementation combines a React voice console, FastAPI, LangGraph, SQL-authoritative property
facts, Pinecone or FAISS retrieval, configurable speech providers, validated appointments and a
durable Google Calendar/Gmail workflow with an n8n CRM handoff.

The latest capstone brief includes Docker, n8n and incoming phone calls. Docker/Compose and an
inactive n8n export are prepared; signed Twilio inbound/media adapters exist. Actual deployment
is deferred at the user's request. This handover does **not** certify a production launch.

## Business controls

- Available-only property recommendations and source-bound answers reduce invented inventory claims.
- Exact slot/employee validation, consent, idempotency and SQL conflict controls protect appointments.
- Operator-managed employee addresses prevent the model from guessing email recipients.
- Encrypted contacts, redacted transcripts, bounded retention and admin controls support privacy.
- Outbox retries and persisted delivery receipts make integration failures visible and recoverable.

## Evidence and limitations

Local unit/integration suites and evaluation scripts cover agent decisions, source validation,
voice state, appointment conflicts, memory, injection refusal and workflow failure handling.
The submission distinguishes single-turn fixture checks, multi-turn conversations, twenty SQL
retrieval questions and actual provider/device evidence. Use the latest saved output and
[release checklist](RELEASE_CHECKLIST.md) for counts; this report intentionally does not freeze
an obsolete test number. Fixture accuracy does not establish real company retrieval accuracy.

Real inventory is not supplied by synthetic fixtures. Google OAuth delivery, n8n runtime import,
external CRM writes, carrier calls, independently scored UrduLish recordings and representative
under-two-second voice latency need acceptance evidence. Fish-versus-ElevenLabs quality cannot
be decided from vendor claims. Configuration readiness alone does not prove a successful call.

Graph nodes select typed actions; trusted appointment services execute them and an independent
worker delivers email. This division differs from a graph containing direct email execution,
and keeps consequential writes behind deterministic validation. The runtime does not pretend to
be a human or fabricate expressive laughter to satisfy a checklist.

## Operating model and next decision

The company supplies reviewed inventory/documents, staff mappings and test-account credentials.
An operator follows the local setup, verifies the complete appointment lifecycle and collects
human voice scores. The team then reviews latency, quality, failure recovery, privacy and
concurrency evidence. Deploy only after explicit approval of these gates. See the
[complete requirement matrix](CAPSTONE_REQUIREMENTS.md) for each daily task and deliverable.

## Roadmap

After acceptance: WhatsApp/SMS confirmations, approved Salesforce/HubSpot connectors, validated
Urdu/English/Punjabi voices, consented brand cloning, funnel analytics, interpretable lead
scoring and consent-aware follow-up campaigns. Payments and live MLS feeds require separate
transaction, authorization and provenance controls. See [future enhancements](FUTURE_ENHANCEMENTS.md).

See the [current verification report](VERIFICATION_REPORT.md) for the final executed checks and saved evidence.
