# Local Development Runbook

## Integrated parity path

1. Ensure Docker is running and port `127.0.0.1:8080` is free.
2. Copy `.env.example` to ignored `.env` and replace the local-only password.
3. Start the stack:

   ```bash
   docker compose up --build -d
   docker compose ps
   ```

4. Require both probes:

   ```bash
   curl --fail --silent --show-error http://127.0.0.1:8080/healthz
   curl --fail --silent --show-error http://127.0.0.1:8080/readyz
   ```

5. Run the repeatable sandbox-only HTTP flow, then open the UI:

   ```bash
   python3 scripts/http_smoke.py \
     --base-url http://127.0.0.1:8080
   ```

   The script must report `PASS`, `completed`, eight artifacts/evidence records and `external_side_effects=false`. Open `http://127.0.0.1:8080`, confirm eight persisted steps, approve or reject the exact hash, refresh, and confirm the decision survives.

Inspect failures with `docker compose ps` and `docker compose logs --no-color database migrate app`. The migration service must exit zero before `app` starts.

Stop while preserving PostgreSQL data:

```bash
docker compose down
```

Deleting the `postgres-data` volume is destructive. Export anything needed and use `docker compose down --volumes` only for an intentional local reset.

## Fast edit path

```bash
npm ci --ignore-scripts --no-audit --no-fund
cd backend && uv sync --frozen && cd ..
```

Run `cd backend && uv run agency-control-plane` in one terminal and `npm run dev` in another. This path defaults to an auto-created local SQLite file and development-header identity. It is not a production topology.

To exercise Alembic explicitly against a disposable SQLite database:

```bash
cd backend
AGENCY_DATABASE_URL=sqlite+pysqlite:////tmp/agency-control-plane.sqlite3 \
  uv run alembic -c alembic.ini upgrade head
```

## Common diagnosis

- `409 IDEMPOTENCY_KEY_REUSED`: the same logical key was sent with a different operation or body. Reconcile the existing command; do not invent a replacement retry key for an ambiguous response.
- `409 STALE_ARTIFACT_MANIFEST`: refresh the run and review the new server hash. Never approve the previous hash.
- `401 INVALID_DEVELOPMENT_IDENTITY`: supply valid non-production tenant/principal headers.
- `503 DATABASE_UNAVAILABLE` or failing `/readyz`: inspect PostgreSQL health and migration logs; `/healthz` alone is insufficient.
- `500 INTERNAL_SERVER_ERROR`: use its correlation ID to find the structured log record. The response intentionally omits internals.

## Verification before handoff

Run the commands in the README verification section and `scripts/http_smoke.py`. Confirm logs contain correlation, tenant, principal, run, step, tool operation, success/failure, latency and retry count without request bodies or secrets.
