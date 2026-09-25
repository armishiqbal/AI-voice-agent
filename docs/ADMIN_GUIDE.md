# Admin guide

## Inventory and knowledge

- Import CSV/JSON with `python scripts/data/import_inventory.py path.csv --source crm-export-v1`.
- Ingest brochures/FAQs with `python scripts/data/ingest_knowledge.py path.pdf --source brochure-v1
  --property-id DEMO-001` after configuring OpenAI and Pinecone.
- Inspect import validation errors and provenance before treating records as authoritative.
- Outside development, send `X-Admin-Api-Key: $ADMIN_API_KEY` for inventory imports, knowledge
  ingestion, metrics, evaluation, outbox, and audit endpoints. The consented lead form is public
  for the browser and must validate `consent: true`.

## Appointments and leads

- Run `python worker.py` continuously for outbox delivery and retention maintenance.
- Review `/v1/admin/metrics` for provider failures, latency, RAG misses, and node traces.
- Calendar/Gmail events remain pending until the Google OAuth token is configured.

## Safety

- Never paste provider keys into the browser or inventory files.
- Keep `PII_ENCRYPTION_KEY` stable and secret; rotating it requires an explicit data migration.
