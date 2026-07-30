# Versioned API Contract

The authoritative public application contract is `contracts/openapi-v1.json`. It is generated from the production FastAPI application, not maintained by hand.

## Verify

```bash
API_CONTRACT_PYTHON_BIN=.venv/bin/python npm run validate:api-contract
```

The selected interpreter must contain the hash-locked backend runtime dependencies. CI sets it to the Python environment containing the installed wheel; the verifier never installs dependencies implicitly.

The command fails when runtime OpenAPI differs byte-for-byte from the committed canonical projection, when a business path is not under `/api/v1`, when an `operationId` is missing or duplicated, or when an operation omits the standard structured error responses.

Intentional compatible changes require review of the generated diff:

```bash
python3 scripts/verify-api-contract.py --write
git diff -- contracts/openapi-v1.json
python3 scripts/verify-api-contract.py
```

A breaking contract change additionally requires the explicit human gate recorded by Graph Harness; `--write` is not approval.

## Error envelope

Every operation documents these statuses: `400`, `401`, `403`, `404`, `409`, `413`, `422`, `429`, `500`, and `503`.

The common envelope is:

```json
{
  "code": "stable_machine_code",
  "detail": "safe public detail",
  "request_id": "correlation-id"
}
```

Validation failures add at most 20 sanitized entries containing only `location` and `type`. Rejected values, internal exception text, permissions, credentials, and stack traces are not part of the public contract.

## Distribution evidence

The hash-locked wheel verifier regenerates the contract from the installed package with `API_CONTRACT_USE_INSTALLED=1`. The OCI package smoke fetches `/openapi.json`, canonicalizes it, and requires exact equality with the committed contract. These checks perform no external effects.
