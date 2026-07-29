# Plan

1. Reuse the durable outbound intent/fence/receipt architecture from INC-015.
2. Add channel-specific publication descriptors and exact artifact/media binding.
3. Implement X create-post and Instagram media-container/publish adapters.
4. Add SQLite/PostgreSQL race, replay, unknown-outcome and revocation tests.
5. Expose an admin/operator confirmation that names account, channel and exact output.
6. Keep real provider calls disabled until all mock/package gates pass.
7. Perform explicitly authorized sandbox posts and reconcile their receipts.

## Delivered locally

- SQLite/PostgreSQL schema v3 intent and bounded receipt stores.
- Unique binding authority across different idempotency keys and replicas.
- X and Instagram protocol adapters behind fixed-host MockTransport verification.
- Pending, succeeded, failed, unknown, revoked and idempotent manual reconciliation states.
- Deterministic success-audit repair on compatible replay after persistence failure.
- Disconnect and Greenlight revocation of unused pending authority.
- Admin/session/CSRF API with server-derived approved copy and media references only.
- Destructive two-step UI confirmation and durable receipt notice.
- Critical unknown-outcome metric, alert and incident runbook.
- Default-disabled Helm/Terraform configuration and installed-image MockTransport smoke.
- Runtime-before-store lock ordering that prevents worker/read deadlock after prior inline runs.

Real sandbox posts and receipt reconciliation remain an explicit human/external gate.
