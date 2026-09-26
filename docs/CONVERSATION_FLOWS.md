# Conversation flows

These flows describe the deterministic boundary around the voice model. The model may phrase a
response, but it cannot decide availability, create an appointment, or disclose an unverified
fact. Every consequential transition passes through a validated service. Voice actions require
explicit spoken confirmation and contact consent from the form.

## Buyer, rental, commercial, and investment

```mermaid
flowchart TD
  A[Greeting] --> B{Purpose known?}
  B -- No --> C[Ask buy, rent, commercial, or investment]
  B -- Yes --> D[Collect city, area, budget, bedrooms, amenities]
  D --> E{Enough criteria?}
  E -- No --> C
  E -- Yes --> F[SQL filter available inventory]
  F --> G{Available matches?}
  G -- No --> H[Explain no verified match and ask one clarification]
  G -- Yes --> I[Deterministic rank, then filtered RAG]
  I --> J[Source-backed recommendation]
  J --> K{Objection or detail question?}
  K -- Yes --> L[Grounded answer or clarify concern]
  K -- No --> M{Book a visit?}
  M -- No --> N[Continue conversation or goodbye]
  M -- Yes --> O[Consented contact and exact spoken or form PKT confirmation]
  O --> P[Availability, employee, and idempotency validation]
  P --> Q[Appointment record and outbox event]
```

## Returning customer and memory

```mermaid
flowchart LR
  A[Conversation ID] --> B[Load non-expired state]
  B --> C[Merge language, city, area, budget, intent]
  C --> D[Resolve the new turn]
  D --> E[Save redacted bounded state]
  E --> F[Expire after 30 days]
```

The state is a preference memory, not a source of property truth. Inventory and appointment
facts are always re-checked against SQL.

## Seller or valuation request

```mermaid
flowchart TD
  A[Seller request] --> B[Do not estimate valuation]
  B --> C[Explain human consultant handoff]
  C --> D{Consent and contact form?}
  D -- No --> E[Do not persist contact data]
  D -- Yes --> F[Encrypt contact, redact notes, write lead.created outbox event]
```

## Reschedule and cancellation

```mermaid
flowchart TD
  A[Reschedule or cancel] --> B[Ask for appointment reference]
  B --> C[Collect consented contact email through form]
  C --> D{Reference/email match?}
  D -- No --> E[Reject without revealing appointment details]
  D -- Yes --> F{Action}
  F -- Reschedule --> G[Validate PKT business hours, half-hour slot, employee conflict]
  F -- Cancel --> CONF[Ask explicit cancellation confirmation]
  CONF --> RECHECK[Recheck reference and contact ownership]
  RECHECK --> H[Mark cancelled]
  G --> CONF2[Offer slots and ask explicit confirmation]
  CONF2 --> RECHECK2[Recheck ownership and slot availability]
  RECHECK2 --> I[Write appointment.rescheduled outbox event]
  H --> J[Write appointment.cancelled outbox event]
  I --> K[Worker retries Calendar/Gmail delivery]
  J --> K
```

## Silence, low confidence, interruption, and injection

```mermaid
flowchart TD
  A[Audio input] --> B{Speech started?}
  B -- Yes --> C[Stop active TTS and cancel pending response]
  B -- No --> D[Continue streaming STT]
  D --> E{Final confidence above threshold?}
  E -- No --> F[Ask caller to repeat]
  E -- Yes --> G[Guardrail and grounded resolution]
  G --> H{Injection or unsafe request?}
  H -- Yes --> I[Refuse private instructions and offer human handoff]
  H -- No --> J[Respond with validated decision]
```

