# INC-029 Independent Review — Versioned API Contract

Date: 2026-07-30
Graph revision: 2
State at review: `running`

## Producer result

- Added `PublicErrorResponse`, `ValidationErrorItem`, and `ValidationErrorResponse` as strict Pydantic models.
- Every OpenAPI operation declares the same 400/401/403/404/409/413/422/429/500/503 schema contracts.
- Added deterministic `contracts/openapi-v1.json` generated from the production FastAPI app.
- Added `scripts/verify-api-contract.py` with read-only drift verification and explicit reviewed `--write` mode.
- Source, installed wheel, and OCI package regenerate the same contract.

## Contract evidence

- OpenAPI: 3.1.0.
- API version: 0.7.0.
- Paths: 30.
- Operations: 31.
- Schemas: 14.
- Standard error declarations: 310.
- Canonical contract SHA-256: `c9f0532e19bd5a8bad074f51c7fa7404e1eae76805ffa8659c2997ea51af68e9`.
- Unversioned schema paths are exactly `/healthz` and `/readyz`; all business paths use `/api/v1`.

## Runtime evidence

Representative 400, 401, 403, 404, 409, 413, 422, 429, 500, and 503 responses validate against the public models. The tests prove:

- request IDs appear in both body and `X-Request-ID`;
- validation output includes only bounded `location` and `type` values;
- permission names, rejected values, exception types, stack traces, and private failure details are absent;
- rate-limited responses preserve `Retry-After`;
- verifier negatives reject an unversioned business path and a missing standard response.

## Localized repairs

1. Revision 1: a generic 500 response included correlation in the body but omitted `X-Request-ID` when exception handling bypassed normal middleware finalization. All handlers now emit the header explicitly while preserving safe headers.
2. Revision 2: adding the installed-wheel CI gate changed `package.json` and the workflow, invalidating their compliance inventory hashes. The exact evidence hashes and review timestamp were renewed; release compliance remains `DENY_RELEASE`.

Only `INC-029` was invalidated by either repair. Unrelated node evidence remained active.

## Critic and security review

PASS locally. The snapshot prevents accidental path, operation ID, response, and schema drift. It contains no credential fixtures. `--write` changes bytes but grants no breaking-change approval. No provider, deployment, secret, cloud, spend, or publication effect is enabled.

## Open gates

A clean implementation commit, exact-tree supply-chain evidence, exact-head CI, remote artifact inspection, merge authority, and close-gate remain pending.
