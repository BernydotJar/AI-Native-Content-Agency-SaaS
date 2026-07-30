# INC-029 Design — Versioned API Contract

## Authority

FastAPI remains the runtime authority. The repository stores a canonical JSON projection generated from the exact production app configuration with deterministic local identities and no external providers.

## Error contract

`PublicErrorResponse` defines `code`, `detail`, and `request_id`. `ValidationErrorResponse` extends it with bounded `errors` entries containing only sanitized `location` and `type`. The application OpenAPI generator injects these schemas and standard error responses into every operation while preserving FastAPI request/response models.

## Drift verification

`scripts/verify-api-contract.py` regenerates the contract, compares canonical bytes with `contracts/openapi-v1.json`, and verifies:

- API title/version;
- exact allowlist for unversioned operational paths;
- stable unique `operationId` values;
- common error references for all operations;
- no provider execution routes outside governed authorities;
- no raw secret-bearing examples.

The verifier supports an explicit `--write` mode for intentional reviewed contract updates; normal CI is read-only.

## Runtime verification

Backend tests exercise 400/401/403/404/409/413/422/429/500/503 responses and validate the common fields, correlation ID, sanitized validation details, and absence of internal exception/permission leakage.

## Distribution

The verifier runs against source and the installed hash-locked wheel. The production package smoke fetches `/openapi.json` and compares its SHA-256 to the committed contract.
