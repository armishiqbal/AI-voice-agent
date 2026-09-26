# Release and submission checklist

The full [capstone requirement matrix](CAPSTONE_REQUIREMENTS.md) supersedes previous scope notes
that excluded Docker/n8n. Deployment is deferred; packaging and workflow preparation are included.
Check a gate only after retaining its actual output. A script existing or readiness flag being
true is not evidence of a successful external operation.

## Local checks

Run from the repository root in the configured development environment:

```bash
python -m pytest backend/tests
python -m ruff check backend/app backend/tests scripts
python -m compileall -q backend
npm test --prefix frontend
npm run build --prefix frontend
python scripts/evaluation/evaluate.py
python scripts/evaluation/evaluate_rag.py
python scripts/evaluation/evaluate_memory.py
python scripts/evaluation/evaluate_appointments.py
python scripts/evaluation/release_report.py
```

Also execute the multi-turn conversation evaluator included with the submission. Retain case
IDs, expected/actual outcomes, denominators and failures. The original 41 single-turn prompts do
not alone meet the requirement for forty test conversations. SQL retrieval results must retain
their fixture label; source-ID correctness is narrower than full factual claim correctness.

| Gate | Required evidence |
|---|---|
| Backend/frontend | Current tests, lint and build output; explain all skips |
| Packaging | Wheel contains nested `app` packages; Docker image builds without embedding secrets |
| Migrations | Upgrade on a disposable SQLite DB and PostgreSQL DB; never downgrade a real client DB for testing |
| Concurrency | PostgreSQL appointment conflict, ticket issuance and active-call lease checks |
| Agent/RAG | Multi-turn suite, twenty retrieval questions, memory, injection cases, chunk comparison |
| Workflow | Receipt persistence/retry tests, validated employee mapping, inactive n8n export structure |
| Voice | AudioWorklet capture, stop/reconnect/error handling and continuous turn contracts |
| Documentation | Matrix, diagrams, user/admin/API guides, executive report, actual slide deck and timed script |

Do not run migration checks against the default database by accident. Supply a unique disposable
`DATABASE_URL` and run `alembic upgrade head` from `backend/`. Record the actual migration head.
CI provisions PostgreSQL; a checked-in workflow is not proof that the remote CI job ran.

## Provider and company acceptance (still required)

- [ ] Import real reviewed company inventory, source versions and brochures/FAQs; confirm no fixture seed in runtime.
- [ ] Select the speech provider and verify `/readyz`; complete a real microphone→transcript→answer→audible response turn.
- [ ] Run continuous turns, silence recovery, interruption, device switching and connection failure recovery on target browsers.
- [ ] Benchmark speech-end→first audible response on representative calls; report p50/p95, failures and sample size. Required goal: under two seconds.
- [ ] Evaluate Fish/ElevenLabs on identical UrduLish recordings; retain consented audio, blind scores and actual measured latency/cost assumptions.
- [ ] Approve employee directory and Google OAuth scopes; book/reschedule/cancel in a test calendar, inspect employee notifications and outbox receipts.
- [ ] Import n8n workflow, set distinct auth credentials and an idempotent CRM sink; verify retries and committed receipt matching.
- [ ] Configure Twilio number, signed webhook and public TLS media endpoint; complete an inbound call. This depends on deferred hosting.
- [ ] Approve privacy/retention and backup restoration procedure; keep secrets out of evidence files.

## Deployment — deferred by user

The Dockerfile builds frontend assets and the Python runtime; Compose prepares PostgreSQL,
migrations, API, worker and optional n8n. A running Docker daemon is needed to build/execute it.
Pin the selected n8n image tag/digest before a reproducible release; do not rely on `latest`.
Deployment additionally needs trusted-proxy/origin settings, secret management, TLS, durable
monitoring, backups, resource/call limits and an operator rollback plan. No hosted environment,
carrier acceptance, uptime SLA or production readiness is claimed by this local handover.

## Evidence bundle

Retain timestamp, revision/worktree status, dependency versions, executed command, exit status,
case-level JSON and redacted traces. Identify fixture vs real input; distinguish configuration,
provider contract tests and actual end-to-end runs. List every remaining blocker. Human reviewers
must fill their own scores; do not prefill the rubric with invented results.

See the [current verification report](VERIFICATION_REPORT.md) for the final executed checks and saved evidence.
