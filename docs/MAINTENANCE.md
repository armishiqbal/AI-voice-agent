# Monitoring, maintenance and recovery

These are proposed operational targets and runbooks, not measured uptime promises. Assign an
operator and escalation contact before launch. The current metrics sink is bounded/in-process;
export it to durable monitoring during the deferred deployment phase.

## Signals and thresholds

| Signal | Target / alert | Response |
|---|---|---|
| API availability | Proposed 99.9% monthly; probe `/healthz` each minute, alert after 3 failures | Inspect process/DB/network; use approved rollback if regression |
| Dependency readiness | Selected provider or DB becomes unavailable for 2 minutes | Inspect `/readyz`; disable affected capability and explain failure |
| Voice response | Measure speech-end to first audible sample; goal p95 <2s; alert p95 >2s for 5 minutes with ≥20 turns | Separate VAD, STT, retrieval/LLM, TTS, buffering times; inspect failures too |
| API/provider errors | >2% failures in 5 minutes with ≥20 requests, or any sustained auth failure | Inspect sanitized provider code/quota; bound retries and escalate |
| Calendar/email delivery | Any exhausted event; pending event age >5 minutes | Inspect admin outbox attempts/error/next retry and provider receipts |
| Booking correctness | Zero unavailable/double bookings; alert on any invariant violation | Disable new bookings, preserve evidence, reconcile calendar and SQL |
| RAG | Review miss rate >20% over ≥20 relevant queries or any forged citation | Inspect filters, corpus/version freshness and source evidence |
| Voice quality | Weekly native-speaker rubric; review any dimension <4/5 mean | Review consented recordings, pronunciation and interruption samples |
| Capacity | Active call saturation >80% for 5 minutes | Check limits/resources; reject cleanly rather than silently queue audio |

`/v1/admin/metrics` exposes node/provider counters and latency summaries; admin outbox and call
outcomes expose delivery and call failures. Mean/p95 graph timings are not end-to-end voice
latency. Report sample size, unavailable/error rate and measurement window with every percentile.

## Cadence

**Every change:** run backend tests/lint, frontend tests/build and relevant evaluation suites.
Version prompts, import schemas and workflow changes; use a regression corpus and a rollback
revision. Review dependency updates before merging.

**Daily:** inspect failures, backlog age, suspicious authentication, remaining provider budget,
readiness and ingestion errors. Reconcile stuck appointments with remote Calendar before replay.
Run scheduled retention cleanup through the normal worker lifecycle and inspect its outcome.

**Weekly:** review at least twenty consented, representative conversations across UrduLish,
silence, interruptions and objections. Label failures, expand evaluation cases, adjust prompts
only when regression evidence supports the change. “Weekly retraining” means this reviewed
improvement cycle; no automatic fine-tuning or unsupervised learning from customer data is
implemented or authorized. Any future fine-tuning needs separate consent/data review and a
held-out evaluation. Review follow-up reminders with staff; do not start campaigns automatically.

**Knowledge refresh:** import changed SQL inventory as soon as the company approves it; never
serve stale availability from vectors. Re-ingest versioned brochure/FAQ changes within one
business day, and review the whole vector corpus weekly. Compare source counts, provenance,
retrieval gold cases and deleted/superseded chunks before switching a corpus version. Preserve
an approved prior version for rollback.

**Monthly:** review access, admin credentials, OAuth scope, employee directory, provider spend,
retention, library vulnerabilities and prompt-injection cases. Review voice/model licensing
before changing providers. Immediately rotate any exposed secret; exercise the incident plan
quarterly.

## Backups and recovery

Proposed targets: RPO ≤24 hours, RTO ≤4 hours; prove them in a timed restore before launch.
Back up PostgreSQL daily to encrypted access-controlled storage, retain seven daily and four
weekly copies, and follow client-approved retention law/policy. Back up imported source versions,
FAISS JSON/index metadata or hosted vector export strategy, n8n workflow/configuration, and
needed encryption keys through a separate secret-backup channel. Never put keys in the database
backup or repository. Calendar is not the source of truth for local consent records.

Monthly restore a backup into an isolated environment. Verify migrations, inventory counts,
contact decryptability, appointment history and outbox state. Disable external sending during
restore drills. Reconcile remote provider state before restarting delivery to avoid duplicate
emails or calendar edits. Record measured recovery time and restore failures.

## Troubleshooting

1. **Voice listens but never replies:** check final STT transcript, VAD commit, agent route, TTS
   chunks and playback separately. An open WebSocket proves only a transport connection.
2. **Connection lost:** retain sanitized close code/reason, readiness and current capacity;
   inspect queue overflow/provider errors. A user Stop is a normal close, not an API outage.
3. **No property match:** verify a real inventory import and exact filters; never enable demo
   seeding to hide missing data. Inspect provenance and RAG metadata filters.
4. **Calendar/email pending:** inspect OAuth scopes/expiry, employee mapping and outbox receipts.
   A Google auth failure is not a delivered notification. Do not repeatedly replay an ambiguous
   Gmail send; remote acceptance before local receipt persistence may cause duplication.
5. **n8n failed:** verify authenticated webhook and matching committed CRM `event_id` receipt.
   Preserve upstream receipts so retries skip already confirmed Google actions.
6. **Security incident:** stop affected external actions, revoke exposed tokens, preserve redacted
   evidence and notify the designated operator under the approved incident policy.

Runtime does not save raw microphone audio. Human evaluation recordings need separate explicit
consent, restricted storage and a documented deletion date. See [operations](OPERATIONS.md) and
[release gates](RELEASE_CHECKLIST.md).
