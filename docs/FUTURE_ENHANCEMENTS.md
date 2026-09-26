# Future enhancements

These are intentionally outside the current acceptance boundary. Each should preserve the
existing SQL availability checks, consent requirements, redacted retention, and source-grounded
response contract.

- Telephony expansion beyond the current Twilio media-stream adapter: inbound number provisioning,
  recording consent, call transfer, and carrier retries.
- WhatsApp/SMS confirmations using the same appointment outbox and idempotency keys.
- Salesforce/HubSpot connectors behind a reviewed CRM adapter and least-privilege credentials.
- Lead scoring and follow-up campaigns built from consented preferences, not raw audio.
- Native-speaker-validated Urdu, English and Punjabi voice packs, including code-switching;
  consented, licensed voice cloning for approved brand representatives.
- Analytics dashboard for funnel conversion, provider latency, RAG misses, and booking outcomes.
- Payment gateway and live MLS/ERP feeds with import provenance and rollback support.
