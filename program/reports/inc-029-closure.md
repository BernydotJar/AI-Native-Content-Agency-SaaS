# INC-029 Closure — Versioned API Contract

Date: 2026-07-31
Graph revision: 1

## Final implementation

- Canonical OpenAPI 3.1 contract remains byte-deterministic at `contracts/openapi-v1.json`.
- Every business route is restricted to `/api/v1` or `/api/v1/...`; adversarial `/api/v10` and `/api/v1beta` paths fail validation.
- HTTP 422 declares both runtime envelopes: bounded `ValidationErrorResponse` and safe domain `PublicErrorResponse`.
- Runtime tests prove request correlation, sanitization, quota headers and both 422 shapes.

## Verification

- Clean installed-wheel verification: 380 tests PASS.
- Exact-head GitHub Actions run `30656597259`: 8/8 required jobs PASS on `a6bd73468e3f530afdb17fff70d69dc45bb994a4`.
- Review findings repaired: 2.
- Review threads resolved: 2.
- No provider, publication, model, secret, deployment or cloud effect occurred during verification.

## Publication

PR #38 was squash-merged into `main` as `12332e4653f9db2949a5936dd1765cbd4436ff4c`.
The resulting tree is `f983588c1dbe8537895f4fafb757b7e8344506e2`, identical to the exact-head tree that passed CI.

Release and deployment authority remain governed separately.
