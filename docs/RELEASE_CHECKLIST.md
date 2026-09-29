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
python scripts/evaluation/release_report.py --api-url http://127.0.0.1:8000
POSTGRES_PASSWORD=local-config-check-only docker compose config --quiet
docker build -t awaaz-estate:capstone-local .
```

Also execute the multi-turn conversation evaluator included with the submission. Retain case
IDs, expected/actual outcomes, denominators and failures. The original 41 single-turn prompts do
not alone meet the requirement for forty test conversations. SQL retrieval results must retain
their fixture label; source-ID correctness is narrower than full factual claim correctness.

The live voice evaluator writes its diagnostic artifact even when the acceptance gates fail; its
exit code is non-zero unless every turn has a final transcript, final audio, and substantive audio
within the configured two-second target. Acknowledgement audio does not satisfy the substantive
answer gate. The run still labels synthetic input and does not establish physical audibility or p95.

| Gate | Required evidence |
|---|---|
| Backend/frontend | Current tests, lint and build output; explain all skips |
| Packaging | Passed: wheel contains nested `app` packages; ARM64 Docker image builds without copying `.env`/secrets. Isolated container serves frontend and `/healthz` returns `ok`; provider readiness is blocked without runtime credentials |
| Migrations | Passed: upgraded disposable SQLite and PostgreSQL 18 databases to head; PostgreSQL also upgraded from revision `0006` with a legacy 32-character version column. Never downgrade a real client DB for testing |
| Concurrency | Passed locally: PostgreSQL appointment conflict, ticket issuance and active-call lease checks; hosted contention/soak remains outstanding |
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
migrations, API, worker and optional n8n. The local ARM64 image build and isolated health smoke
passed; this does not start the Compose stack or deploy it. The optional n8n image is pinned to
`docker.n8n.io/n8nio/n8n:2.40.7`, the stable release listed on 2026-09-25 ([official release
notes](https://github.com/n8n-io/n8n/releases)). Validate the exported workflow against that
version before changing the pin. The version tag improves repeatability; use a registry digest
for immutable release provenance.
Deployment additionally needs trusted-proxy/origin settings, secret management, TLS, durable
monitoring, backups, resource/call limits and an operator rollback plan. No hosted environment,
carrier acceptance, uptime SLA or production readiness is claimed by this local handover.

## Evidence bundle

Retain timestamp, revision/worktree status, dependency versions, executed command, exit status,
case-level JSON and redacted traces. Identify fixture vs real input; distinguish configuration,
provider contract tests and actual end-to-end runs. List every remaining blocker. Human reviewers
must fill their own scores; do not prefill the rubric with invented results.

See the [current verification report](VERIFICATION_REPORT.md) for the final executed checks and saved evidence.
