# Awaaz Estate architecture and flows

## Runtime architecture

```mermaid
flowchart LR
  UI[React/Vite voice console] -->|JSON + PCM16 WebSocket| API[FastAPI session API]
  PHONE[Optional Twilio media-stream adapter] -.-> API
  API --> STT[Deepgram streaming STT]
  API --> GRAPH[LangGraph guardrails and resolution]
  GRAPH --> SQL[(PostgreSQL inventory and appointments)]
  GRAPH --> STATE[(PostgreSQL conversation state, 30-day expiry)]
  GRAPH --> RAG[Pinecone filtered brochure/FAQ retrieval]
  GRAPH --> LLM[Structured LLM adapter]
  GRAPH --> TTS[Multilingual TTS router]
  TTS --> UI
  SQL --> OUTBOX[(Transactional outbox)]
  WORKER[python worker.py] --> OUTBOX
  WORKER --> CAL[Google Calendar OAuth]
  WORKER --> MAIL[Gmail OAuth]
  API --> AUDIT[(Tool audit ledger)]
  API --> LEAD[(Encrypted consented lead records)]
```

The database is authoritative for structured property facts and appointment state. Pinecone is
only a knowledge context source; it cannot make an unavailable property available. The model
returns a Pydantic decision and never receives direct tool execution privileges.

The complete scenario-specific flows are documented in
[`CONVERSATION_FLOWS.md`](CONVERSATION_FLOWS.md), including returning-customer memory,
seller handoff, rescheduling, cancellation, silence, low-confidence speech, and barge-in.

## Buyer flow

```mermaid
flowchart TD
  A[Greeting] --> B[Detect buy/rent/commercial/invest]
  B --> C{Enough city, purpose, and budget?}
  C -- No --> D[Ask one concise clarification]
  C -- Yes --> E[SQL availability and employee filter]
  E --> F{Matches?}
  F -- No --> D
  F -- Yes --> G[Optional filtered RAG context]
  G --> H[Validated recommendation with source IDs]
  H --> I{Visit?}
  I -- Yes --> J[Consent form and slot confirmation]
  I -- No --> K[Answer or objection route]
  J --> L[Deterministic booking service]
  L --> M[Confirmation and outbox event]
```

## Seller and safety flow

```mermaid
flowchart TD
  A[Caller text/audio] --> B[Injection and unsafe-intent guard]
  B -- Injection --> C[Refuse private instructions and offer human handoff]
  B -- Seller inquiry --> D[Human lead handoff; no invented valuation]
  B -- Normal --> E[Grounded resolution]
```

## Appointment lifecycle

```mermaid
stateDiagram-v2
  [*] --> booked: valid property + employee + PKT slot + consent
  booked --> rescheduled: matching reference/email + free slot
  booked --> cancelled: matching reference/email
  rescheduled --> rescheduled: matching update idempotency key
  cancelled --> cancelled: replayed cancel idempotency key
  booked --> [*]
  rescheduled --> [*]
  cancelled --> [*]
```

There is no n8n dependency. The internal worker handles retries, leases, Calendar, and Gmail.
Docker files may remain as historical scaffolding, but they are not part of the run path or
acceptance gate.

The telephony adapter is optional and fail-closed. It supports a signed Twilio media-stream
boundary, but a carrier, phone number, recording-consent policy, PCM16 TTS configuration, and
live-call test are required before enabling it.
