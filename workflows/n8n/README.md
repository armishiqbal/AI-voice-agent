# Business workflow automation

The existing LangGraph and SQL service own **Call → Intent → Property Match → confirmed Appointment**. Google Calendar and Gmail run in the durable Python outbox; this n8n export completes **Calendar → Email → CRM Update**. Moving the same booking writes into n8n would duplicate validation and could create two appointments. The workflow checks upstream delivery receipts and refuses to claim success before its CRM sink confirms durable delivery.

## Configure locally

1. Import `awaaz-business-events.json` into n8n. It is inactive by default.
2. On `After Call Intent Property Appointment`, select a Header Auth credential named `X-Awaaz-Token` with a newly generated secret. Set the same secret as `N8N_WEBHOOK_TOKEN` in the backend's ignored `.env`.
3. Set `N8N_WEBHOOK_URL` to the workflow production webhook URL (local development example: `http://localhost:5678/webhook/awaaz-crm-events`). Remote URLs must use HTTPS; redirects are not followed.
4. Configure `AWAAZ_CRM_WEBHOOK_URL` in the n8n host environment. Set a separate Header Auth credential on `Idempotent CRM Update` for the receiving CRM adapter. Enable environment access to this non-secret URL in your n8n environment, or replace the URL expression in the editor with the approved fixed endpoint.
5. The receiving CRM adapter must atomically upsert by `event_id`, honor `Idempotency-Key`, and return JSON `{"event_id":"<same-id>","status":"delivered"}` **after** the write commits. An asynchronous `202` or `accepted` receipt is insufficient. Replays must return the original successful receipt. The internal SQL CRM is already retained independently; this endpoint is for a client-selected CRM system.
6. Configure Google OAuth (`GOOGLE_TOKEN_PATH`, `GOOGLE_CALENDAR_ID`, `GMAIL_SENDER`) and an operator-managed employee directory, for example `EMPLOYEE_EMAIL_DIRECTORY='{"Ayesha Khan":"ayesha@your-company.example"}'`. Use real employee addresses locally; none are shipped. The Gmail-enabled booking service refuses bookings until the directory is available; it never guesses a recipient.
7. Activate the workflow and run `python worker.py` separately from `python run.py`.

No call, email or CRM mutation is performed merely by importing this file. Google OAuth authorization, provider access, CRM adapter credentials, n8n runtime import and actual integration delivery remain operator live checks; this export has structural and transport tests, not an invented n8n execution result.

## Data and failure contract

- Appointment events: `appointment.booked`, `appointment.rescheduled`, `appointment.cancelled`.
- CRM events: `lead.created`, `lead.follow_up_due`, `voice.call_completed`. The worker emits one durable `lead.follow_up_due` event when a consented lead's scheduled follow-up becomes due; the CRM can create an operator task. Call transcript/preferences remain in the application database. Client email/SMS campaigns are not sent automatically.
- The allowlist forwards IDs, assigned employee, time, preferences and follow-up time. It excludes customer names, contact email/phone, encrypted contact fields, raw transcript and notes. Provider receipts forward only provider/status.
- The workflow's HTTP node retries three times; failures propagate to the synchronous webhook. The Python worker uses exponential backoff, a bounded attempt count and leased claims. `/v1/admin/outbox` exposes pending/failing deliveries to authorized operators.
- Successful provider receipts are retained when a later integration fails. A retry skips those providers, avoiding repeated Calendar/email calls caused by an n8n failure. There remains a process-crash window between a remote provider accepting a side effect and its local receipt being saved; Gmail does not provide an exactly-once send guarantee. Investigate ambiguous email delivery before manually replaying an exhausted event.
- N8n success/error execution data saving is disabled in the export. Restrict editor access and configure your instance retention separately.

## Incoming phone prerequisites

The existing Twilio adapter and `/v1/telephony/inbound` + `/v1/telephony/media` implement signed inbound webhook and bidirectional μ-law streaming. Set `TELEPHONY_PROVIDER=twilio`, Twilio account credentials/from number, and `TELEPHONY_PUBLIC_BASE_URL`, then configure the purchased number's voice webhook. A publicly reachable TLS endpoint is required for real inbound calls, so the user-deferred deployment step prevents a real carrier acceptance test here. Browser voice remains locally usable.
