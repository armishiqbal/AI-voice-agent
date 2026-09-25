# Ten-minute browser demonstration

1. Start API, worker, and frontend with the commands in `docs/OPERATIONS.md`.
2. Open the browser console and start a session. Show that no credentials means explicit text
   fallback, not fake streamed audio.
3. Ask: “Mera budget 3 crore hai, Karachi mein buy karna hai.” Show the verified IDs and fetched
   property details.
4. Ask for Lahore rentals and show that SQL filters change the options.
5. Say “Mujhe apna ghar sell karna hai.” Show the human handoff response.
6. Send an injection phrase. Show the guardrail handoff and no prompt disclosure.
7. Exercise the appointment API with a valid PKT slot, then retry the same idempotency key.
8. Try an unavailable property, wrong employee, and overlapping slot; show deterministic 422s.
9. Run `python scripts/evaluation/evaluate.py`, `python scripts/evaluation/evaluate_rag.py`, and `python scripts/benchmark/benchmark_tts.py`; explain
   fixture evidence, SQL baseline evidence, and missing live credentials separately.
10. Show `/v1/admin/metrics`, the audit ledger, and outbox retry fields. Do not claim Calendar,
    Gmail, Pinecone, or TTS latency is live unless those providers were configured and measured.
