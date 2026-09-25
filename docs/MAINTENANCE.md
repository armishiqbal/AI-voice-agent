# Maintenance and troubleshooting

- Run `python -m pytest backend/tests`, `python -m ruff check backend/app backend/tests scripts`, and
  `npm run build --prefix frontend` on every change.
- Run `python scripts/evaluation/release_report.py` before a release. Local fixture results do not replace live
  provider measurements.
- Run Alembic migrations before starting a production API: `cd backend && alembic upgrade head`.
- If audio is unavailable, inspect `/readyz`, install the selected provider extra, and verify its
  key. Do not substitute synthetic audio for a failed provider.
- If outbox events remain pending, inspect attempts, `last_error`, and `next_attempt_at`; missing
  OAuth is an expected blocked state, not a successful delivery.
- Transcript and conversation-state retention is 30 days; raw audio is never persisted.
