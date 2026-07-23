# Plan

1. Version run/agent durable states and lease metadata.
2. Persist queued run plus command receipt atomically.
3. Implement worker claim, heartbeat, station checkpoint and terminal completion.
4. Add crash, lease-expiry, duplicate-worker and cancellation tests.
5. Expose bounded polling or SSE with tenant authorization.
6. Update topology from observed states only.
7. Package worker and operator runbook without cloud deployment.

## Delivered implementation

- `Prefer: respond-async` persists and returns a queued run with `202 Accepted`.
- In-process workers use the durable SQLite/PostgreSQL store as the queue authority.
- Per-run locks, expiring leases and monotonic fences serialize checkpoints.
- Seven stations expose processing and ready checkpoints before Greenlight.
- The SPA polls only while the persisted run is queued/running.
- Chromium observes all seven stations and fourteen backend checkpoint values.
- Existing synchronous API/CLI behavior remains available for compatibility.
