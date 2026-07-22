# Plan

1. Fix protocol and model assumptions from official provider documentation.
2. Separate public provider contracts from private execution configuration.
3. Write RED contracts for disabled-by-default behavior and exact HTTP shapes.
4. Implement bounded clients with strict host, timeout and size policy.
5. Parse provider responses into a common result and sanitized receipt.
6. Publish only safe gateway status through the existing GET-only provider endpoint.
7. Keep inference routes and automatic run integration absent.
8. Move `httpx` into hash-locked runtime dependencies and reconcile licenses.
9. Verify wheel, PostgreSQL, frontend, Chromium and non-root package.
10. Record the durable outbound intent/receipt requirement as the next gated increment.
11. Defer real credentials, egress, spend and final E2E until explicitly authorized.
