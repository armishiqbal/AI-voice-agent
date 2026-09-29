# Admin guide

## Inventory and knowledge

- Import CSV/JSON with `python scripts/data/import_inventory.py path.csv --source crm-export-v1`.
- The browser's inventory panel offers a headers-only CSV template. It contains no example listings; fill it with owner-approved records. Use `sale`, `rent`, `commercial`, or `investment` for purpose; enter prices as positive PKR integers; use `true`/`false` for availability; list-valued columns use `|` separators. Unknown availability values are rejected instead of silently becoming `false`.
- Ingest brochures/FAQs with `python scripts/data/ingest_knowledge.py path.pdf --source brochure-v1
  --property-id PROP-001` after configuring OpenAI and Pinecone.
- Inspect import validation errors and provenance before treating records as authoritative.
- Outside development, send `X-Admin-Api-Key: $ADMIN_API_KEY` for inventory imports, knowledge
  ingestion, metrics, evaluation, outbox, and audit endpoints. The consented lead form is public
  for the browser and must validate `consent: true`.
- Open the chart icon in the browser to view the live service analytics panel. Enter the admin key
  when the server requires it; the browser keeps it in component memory for that panel only and
  clears it when the panel closes. The view reads `/v1/admin/metrics`, shows provider readiness,
  active-session capacity, bounded latency samples and process counters, and does not display
  transcripts or call identifiers. Metrics are instance-local and reset on API restart; no data or
  zero-latency values are fabricated when the service has no samples. Due follow-up reminders omit
  contact details; staff can mark a reminder complete after making the follow-up.

## Appointments and leads

- Run `python worker.py` continuously for outbox delivery and retention maintenance.
- The worker schedules due lead follow-ups as durable, PII-minimized CRM events and records them
  locally. When n8n is configured, the same event is forwarded to the CRM workflow. The analytics
  panel lists due reminders; mark one complete only after the staff follow-up is done.
- Review `/v1/admin/metrics` for provider failures, latency, RAG misses, node traces, and due reminders.
- Calendar/Gmail events remain pending until the Google OAuth token is configured.

## Safety

- Never paste provider keys into the browser or inventory files.
- Keep `PII_ENCRYPTION_KEY` stable and secret; rotating it requires an explicit data migration.
