# Plan

1. Version run/agent durable states and lease metadata.
2. Persist queued run plus command receipt atomically.
3. Implement worker claim, heartbeat, station checkpoint and terminal completion.
4. Add crash, lease-expiry, duplicate-worker and cancellation tests.
5. Expose bounded polling or SSE with tenant authorization.
6. Update topology from observed states only.
7. Package worker and operator runbook without cloud deployment.
