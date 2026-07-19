# Control Plane Incident Runbook

## Safety first

The current product has no live publication or advertising adapter. Preserve that boundary during incident response: do not add credentials, bypass Greenlight, edit database state by hand, or enable a public invoker to restore availability.

## Triage

1. Record the UTC time, environment, service revision/image digest, correlation ID, run ID, tenant ID only when operationally necessary, and observed status code.
2. Check `/healthz`. A failure indicates process/container failure.
3. Check `/readyz`. Liveness with readiness failure indicates the database or migration boundary.
4. Query the run through the normal tenant-scoped API. Do not infer state from browser storage; it contains only an opaque run ID.
5. Inspect structured logs by correlation/run ID. Never paste authorization headers, ADC material, database credentials, request bodies, or full prompts into an issue.
6. Check the current deployment revision, database migration head, and Terraform drift separately.

## Common cases

### Database unavailable

- Keep `/healthz` interpretation separate from `/readyz`.
- Verify PostgreSQL health, Cloud SQL instance state and proxy/connector readiness.
- Confirm the runtime identity still has Cloud SQL Client/User scopes and the IAM database user exists.
- Do not switch to SQLite in cloud or enable schema auto-create.
- Restore the dependency, rerun readiness, then retry the original command with the same idempotency key.

### Command response was interrupted

- Retry with the same tenant, operation, idempotency key and exact payload.
- If the response replays, use its persisted resource.
- If it returns an incompatible-key conflict, stop: do not generate a new key until the operator confirms which intent is authoritative.

### Stale artifact manifest

- Do not override the conflict or edit the stored hash.
- Reload the run and compare the current manifest/policy.
- Any legitimate artifact change requires Risk review and a new human decision on the new exact hash.

### Concurrent or duplicate approval

- Reload the run and audit events.
- Compatible calls with the same tenant/key/payload must return the same committed response. A second incompatible decision or different-key decision must remain rejected.
- Escalate any observation of two approval rows or two Publisher transitions as a critical integrity incident.

### Concurrent or duplicate run start

- Retry only with the original tenant, idempotency key and exact payload; do not invent a new key after an ambiguous transport failure.
- Two simultaneous compatible calls must return the same run and produce one `run.started` audit event, one command record, seven tool-evidence rows and seven sandbox tool telemetry records.
- Treat two run IDs or more than seven provider/tool calls as an idempotency integrity incident. Keep external providers disabled, preserve the database and correlation IDs, and inspect transaction/advisory-lock errors before retrying.
- A same-key waiter that exceeds the PostgreSQL five-second transaction-local lock bound returns redacted `503 DATABASE_UNAVAILABLE`. Inspect the holder by correlation ID; retry only the unchanged command after the holder has committed or rolled back.

### UI appears ahead of backend

- Use Refresh or reload the saved run ID.
- Integrated mode never advances locally. If timers or simulated transitions appear, verify `VITE_RUNTIME_MODE`; `demo` is isolated and must be visibly labeled.
- Do not copy demo run IDs/artifacts into the control-plane database.

### Migration failure

- Stop the app revision from accepting writes if a partially applied migration is possible.
- Inspect `alembic current`, `alembic heads`, migration logs and the database schema.
- Do not run a destructive downgrade against shared/cloud data without a human gate and verified backup.
- Prefer rolling the app back to a schema-compatible image while a forward repair migration is reviewed.

## Containment and rollback

- Cloud Run: routine rollback may use only the immediate predecessor from the reviewed pre-apply report. Prove it still resolves and matches `app:rollback-current`, then deploy that digest—not the tag—through a new saved-plan/evaluator sequence. Keep IAM/ingress unchanged; older digests are outside the guaranteed window.
- Application: preserve idempotency/audit rows and database snapshots; never delete runs to make a test pass.
- Terraform: do not run `destroy`, delete a project, disable deletion protection, or apply an unreviewed new plan. Create a saved remedial plan and repeat critique/evaluator gates.
- Database: use documented backup/restore only after the human destructive-data gate. A code rollback is not automatically a schema rollback.

## Recovery verification

1. `/healthz` and `/readyz` pass.
2. A tenant-scoped existing run is readable after a new process/revision starts.
3. Wrong-tenant and unauthenticated reads still fail.
4. A sandbox mission/run reaches Greenlight and records zero external effects.
5. Exact-manifest rejection or approval behaves idempotently.
6. Logs contain correlation/run/tool/decision context without sensitive payloads.
7. The second Terraform plan reports no unexpected change when cloud infrastructure is in scope.

Record the evidence and residual risk in `agent/evidence-register.jsonl` and the tracking issue. Never mark recovery based only on a green health endpoint.
