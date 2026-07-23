# Plan

## Delivered readiness slice

1. Add a secret-free X/Instagram configuration registry and authenticated GET-only API.
2. Add exact environment/Secret reference contracts for local, Helm, and Terraform use.
3. Render channel output and five-stage publication readiness in the primary journey.
4. Keep OAuth and publication mutation routes absent.
5. Verify API, browser, image package, and infrastructure without external requests.

## Next implementation slice

1. Implement encrypted tenant integration credential storage and key rotation.
2. Add OAuth start/callback/disconnect routes with expiring state and replay tests.
3. Persist connected account metadata without returning tokens.
4. Implement X `POST /2/tweets` and Instagram `/media` → `/media_publish` adapters.
5. Add durable publication intent, fence, receipt, and unknown-state reconciliation.
6. Bind publication to exact Greenlight artifact/channel authority.
7. Test with local mock transports; do not contact X or Meta in CI.
8. Perform explicitly authorized sandbox posts only after human review.
