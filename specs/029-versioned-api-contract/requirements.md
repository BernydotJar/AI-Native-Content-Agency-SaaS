# INC-029 Requirements — Versioned API Contract

## Goal

Publish and continuously verify one canonical OpenAPI contract for the installed `/api/v1` runtime without enabling deployment, providers, spend, or release.

## Requirements

1. The contract is generated deterministically from the production FastAPI application and committed as `contracts/openapi-v1.json`.
2. Business endpoints are versioned under `/api/v1`; only the explicitly allowlisted operational endpoints `/healthz` and `/readyz` may be public and unversioned in the schema.
3. OpenAPI exposes one common structured error schema containing `code`, `detail`, and `request_id`, plus a validation-error schema with bounded sanitized locations/types.
4. Every operation declares the common 400, 401, 403, 404, 409, 413, 422, 429, 500, and 503 response contracts.
5. Runtime tests prove representative responses conform to the committed schemas and preserve request correlation without leaking internal exceptions or authorization details.
6. A verifier fails closed on any contract drift, unversioned business path, missing error response, unstable operation identifier, or application/version mismatch.
7. The installed locked wheel and production package expose the same contract.
8. Exact-head CI passes with zero external effects.

## Non-goals

- no backward-incompatible API change;
- no provider, social, model, cloud, or publication effect;
- no deployment or release;
- no branch-protection change;
- no secret mutation.
