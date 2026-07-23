# Plan

## Delivered readiness slice

1. Add a secret-free X/Instagram configuration registry and authenticated GET-only API.
2. Add exact environment/Secret reference contracts for local, Helm, and Terraform use.
3. Render channel output and five-stage publication readiness in the primary journey.
4. Keep publication mutation routes absent until durable authority exists.
5. Verify API, browser, image package, and infrastructure without external requests.

## Delivered OAuth slice

1. AES-GCM token storage with key IDs, AAD and rotation.
2. Single-use, expiring, tenant/session-bound OAuth state in SQLite/PostgreSQL schema v2.
3. X OAuth 1.0a and Instagram Authorization Code adapters with bounded mock transports.
4. Admin-only start/disconnect, same-session callbacks, encrypted metadata and audit events.
5. Optional server-side token bootstrap and `.env.local`/Secret references.

## Next publication slice

1. Implement X `POST /2/tweets` and Instagram `/media` → `/media_publish` adapters.
2. Add durable publication intent, fence, receipt, and unknown-state reconciliation.
3. Bind publication to exact Greenlight artifact/channel/media authority.
4. Test with local mock transports; do not contact X or Meta in CI.
5. Perform explicitly authorized sandbox posts only after human review.
