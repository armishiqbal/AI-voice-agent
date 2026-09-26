# Verification report — 2026-09-26

This report separates local implementation evidence from external acceptance. Actual deployment
is deferred. Re-run the commands after configuration or code changes; these are a dated snapshot.

## Local evidence

| Check | Result | Scope |
|---|---|---|
| Backend pytest | 202 passed, 3 skipped | SQLite/local contracts; skips need PostgreSQL concurrency |
| Frontend tests | 21 passed | Protocol, AudioWorklet, turn control, buffering and UI utilities |
| TypeScript + Vite production build | Passed | Build output generated locally |
| Ruff | Passed | `backend/app backend/tests scripts` |
| Multi-turn evaluation | 44/44 conversations, 92 turns, 11 categories | Isolated deterministic fixtures, not live audio |
| Original single-turn evaluation | 41/41 | Separate from the conversation count |
| SQL retrieval evaluation | 20/20 | Fixture property IDs; not arbitrary prose hallucination |
| Memory and appointment evaluations | Passed local release gates | Local state/service correctness |
| Chunk-size retrieval experiment | Six variants × 20 queries; real OpenAI embeddings + FAISS source recall@3 100% | See RAG report for denominators and retrieval modes |
| Fresh SQLite migration | Passed through 0022 | Separate temporary database, no production mutation |
| Python wheel | Built; 69 application files, API/agent/FAISS modules present | Package discovery now includes nested modules |
| Docker Compose configuration | Passed `config --quiet` | No container build/runtime claim; Docker daemon unavailable |
| Concurrent clause TTS smoke | Failed: first audio 21,519 ms; timeout at 30 s, 9,600 bytes | Kept opt-in; standard streaming default retained |
| Live OpenAI direct TTS smoke | Passed: 156,000 audio bytes; first audio 2,678 ms; total 3,373 ms | One synthetic phrase; excludes STT and physical playback, not p95 |
| Presentation | 10 slides, 10 speaker notes, 600 seconds | Offline HTML, no remote assets |

Source artifacts are under ignored `artifacts/evaluation/`: `backend-tests.txt`, `lint.txt`,
`release-report.json`, `multiturn-conversations.json`, `chunk-retrieval.json`,
`chunk-retrieval-live-embeddings.json`, `annotated-trace.json`, and `tts-comparison.json`. They contain fixture evidence and readiness,
not secret credentials or real caller recordings. The annotated trace labels guardrails,
intent, grounding and route responsibilities.

## Security and reliability coverage

Local tests cover prompt injection/refusal, forged citations/property IDs, unavailable inventory,
provider exceptions, scoped retrieval, session/origin validation, PII handling, slot conflicts,
appointment contact/reference checks, explicit confirmation, declining a voice action, idempotency,
outbox retries and retained partial provider receipts. These finite cases do not establish universal
prompt-injection resistance or an independent penetration-test certification.

The ordinary streaming path remains the default. Concurrent clause synthesis can be enabled with
`VOICE_EARLY_CLAUSE_STREAMING_ENABLED=true`, but is not latency-approved by these measurements.
The direct TTS first-audio result already exceeds two seconds, before STT/playback overhead.

Additional voice pipeline regressions cover legacy provider signatures, bounded current/next
clause prefetch, full-queue cancellation, provider cleanup and error recovery.

Two dependency deprecation warnings remain in Starlette/httpx/AnyIO test plumbing. Browser capture
uses AudioWorklet; the deprecated ScriptProcessorNode implementation has been removed.

## External evidence not established

- Real company inventory and brochures/FAQs have not been supplied. Runtime data remains empty until import.
- OpenAI authentication and one direct TTS request passed. An earlier clause-pipeline smoke timed out
  at 45 seconds while integration changes were in progress; its failure remains archived. These
  observations do not prove current physical-microphone quality or p95
  end-of-speech to audible reply below two seconds.
- Fish and ElevenLabs benchmark each returned 20 configuration errors / zero completed phrases;
  neither has configured credentials here. Null latency is unavailable, not zero milliseconds.
- Google Calendar/Gmail, employee directory, n8n runtime/CRM sink, and real inbound Twilio delivery
  need operator configuration and authorized test accounts. No real emails/events/calls were sent.
- No consented human recordings, native-speaker scoring or blinded provider quality winner is claimed.
- PostgreSQL contention, actual container build, deployed CI execution, backups/restores, uptime and
  load/soak evidence remain to be exercised in their corresponding environments.

## Reproduce

```bash
python -m pytest -q backend/tests
python -m ruff check backend/app backend/tests scripts
npm test --prefix frontend
npm run build --prefix frontend
python scripts/evaluation/release_report.py
python scripts/evaluation/evaluate_conversations.py --output artifacts/evaluation/multiturn-conversations.json
python scripts/benchmark/benchmark_chunk_retrieval.py
# From backend/, against a separate temporary database:
DATABASE_URL=sqlite:////tmp/awaaz-capstone-migration.db alembic upgrade head
```

Use the [requirement matrix](CAPSTONE_REQUIREMENTS.md) for complete coverage and the
[release checklist](RELEASE_CHECKLIST.md) for the external gates. Missing evidence must not be
converted into a passed requirement merely because an adapter or fixture test exists.
