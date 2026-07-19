# Control Plane API v1

The canonical machine-readable contract is [`backend/openapi.json`](../../backend/openapi.json). This page explains behavior; it does not replace OpenAPI.

## Local identity and headers

Protected local/development requests require:

```http
X-Tenant-ID: local-dev
X-Principal-ID: local-operator
```

Every mutable request also requires a unique `Idempotency-Key` matching the documented character/length contract. An optional valid `X-Correlation-ID` is returned; otherwise the server creates one.

Development headers are deliberately rejected by production configuration. They are identifiers, not a production authentication mechanism.

## Operations

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/healthz` | Process liveness; does not prove database readiness. |
| `GET` | `/readyz` | Database dependency readiness. |
| `GET` | `/api/v1/identity` | Return the strict `v1` tenant and principal contract supplied by the active identity adapter. |
| `POST` | `/api/v1/missions` | Create a tenant-scoped mission idempotently. |
| `POST` | `/api/v1/missions/{mission_id}/runs` | Execute the bounded sandbox workflow and persist its Greenlight wait state. |
| `GET` | `/api/v1/runs/{run_id}` | Poll/reconnect to persisted steps, artifacts, evidence, events, audit and approval. |
| `POST` | `/api/v1/runs/{run_id}/approvals` | Approve or reject the exact current artifact manifest. |

All request models reject unknown fields. Every application response and request body uses `schema_version: "v1"`; timestamps use the OpenAPI `date-time` format. Agent roles/statuses and run statuses are closed enums in the canonical contract, and Greenlight policy is the literal `greenlight.v1`.

Inspect the development identity contract without creating state:

```bash
curl -sS http://127.0.0.1:8000/api/v1/identity \
  -H 'X-Tenant-ID: local-dev' \
  -H 'X-Principal-ID: local-operator'
```

The response nests strict `TenantIdentityResponse` and `PrincipalIdentityResponse` objects. It is identity context, not proof of production authentication; cloud dev still requires Cloud Run IAM.

## Example flow

Create a mission:

```bash
curl -sS http://127.0.0.1:8000/api/v1/missions \
  -H 'Content-Type: application/json' \
  -H 'X-Tenant-ID: local-dev' \
  -H 'X-Principal-ID: local-operator' \
  -H 'Idempotency-Key: mission-example-001' \
  --data '{"schema_version":"v1","title":"Evidence-led launch","objective":"Explain reversible AI experiments","audience":"Engineering leaders","platforms":["x","facebook"],"budget_cents":0,"source_asset":"sandbox://docs/example","campaign_goal":"awareness"}'
```

Use the returned `mission_id` to start the run:

```bash
curl -sS http://127.0.0.1:8000/api/v1/missions/MISSION_ID/runs \
  -H 'Content-Type: application/json' \
  -H 'X-Tenant-ID: local-dev' \
  -H 'X-Principal-ID: local-operator' \
  -H 'Idempotency-Key: run-example-001' \
  --data '{"schema_version":"v1"}'
```

The returned run should be `awaiting_greenlight`. Copy its server-produced `artifact_manifest_hash` exactly; do not compute or alter it in the browser. Approve only that manifest:

```bash
curl -sS http://127.0.0.1:8000/api/v1/runs/RUN_ID/approvals \
  -H 'Content-Type: application/json' \
  -H 'X-Tenant-ID: local-dev' \
  -H 'X-Principal-ID: local-operator' \
  -H 'Idempotency-Key: approval-example-001' \
  --data '{"schema_version":"v1","decision":"approved","reviewer":"local-operator","note":"Sandbox package only","artifact_manifest_hash":"64_LOWERCASE_HEX_CHARACTERS","policy_version":"greenlight.v1"}'
```

Use `decision: "rejected"` to block Publisher. Neither decision performs external publication or ad spend.

The returned `approval` object includes the same `idempotency_key` supplied in the command header. The backend stores that key directly on the approval row and in the `run.approval` audit payload. Migration `0003_approval_idempotency` backfills a legacy approval only when exactly one durable command record can identify it; unsafe or missing provenance stops the migration.

Idempotency guarantees one durable command response and rejects incompatible replay. Current `run.start` provider execution is an inline sandbox boundary, not an exactly-once external-effect protocol: simultaneous identical starts can perform deterministic sandbox work twice before one transaction wins. External/effectful adapters are disabled until durable key ownership precedes provider execution.

## Idempotency behavior

- Same tenant + key + operation + canonical payload: original response is returned.
- Same tenant + key with another operation or payload: `409` structured conflict.
- Concurrent approval decisions: at most one transition/approval row commits.
- A request interrupted before a committed response is retried with the same key.
- The approval row has a tenant/key uniqueness constraint in addition to one-decision-per-run.

## Errors

Errors use this envelope:

```json
{
  "schema_version": "v1",
  "error": {
    "code": "MACHINE_READABLE_CODE",
    "message": "Safe operator-facing summary",
    "correlation_id": "corr-...",
    "details": {}
  }
}
```

Validation details omit submitted values. Logs omit request/approval bodies, authorization material and full prompts.

## Contract drift

After changing routes or Pydantic contracts, regenerate both canonical artifacts:

```bash
cd backend
uv run python -m control_plane.openapi --output openapi.json
cd ..
python3 scripts/generate_ts_contracts.py
npm run check:api-contract
```

`src/api/contracts.ts` is generated from `backend/openapi.json`; edit the Pydantic contract, not that TypeScript file. CI checks the OpenAPI snapshot, regenerates the TypeScript in memory, and validates required headers, patterns, enums, references, timestamp formats and policy literals. A breaking semantic change requires a new version rather than silently changing `v1`.
