# Runtime Operations

## Operational endpoints

| Endpoint | Authentication | Required permission | Purpose |
|---|---|---|---|
| `GET /healthz` | none | none | Process liveness, sandbox declaration, and whether individual identity is configured. |
| `GET /readyz` | none | none | Readiness, identity mode, durable-store state, and active rate-limit parameters. |
| `GET /metrics` | none | none | Prometheus text exposition with low-cardinality labels. |
| `POST /api/v1/sessions` | one-time bearer credential | valid active identity | Creates an HttpOnly browser session and returns an in-memory CSRF token. |
| `GET /api/v1/sessions/current` | HttpOnly cookie | active identity | Restores the browser session and rotates CSRF. |
| `DELETE /api/v1/sessions/current` | cookie + CSRF | active identity | Revokes the durable browser session. |
| `GET /api/v1/me` | bearer or cookie | `identity:read` | Returns tenant, subject, role, key ID, permissions, and authentication method. |
| `GET /api/v1/audit-events` | bearer or cookie | `audit:read` | Durable, tenant-scoped mutation ledger with cursor pagination. |
| `POST /api/v1/runs` | bearer or cookie + CSRF | `runs:create` | Starts a governed sandbox run. |
| `GET /api/v1/runs/{run_id}` | bearer or cookie | `runs:read` | Reads a tenant-scoped run. |
| `POST /api/v1/runs/{run_id}/greenlight/*` | bearer or cookie + CSRF | `greenlight:decide` | Approves or rejects exact reviewed artifacts. |

`/metrics` intentionally contains no tenant ID, subject ID, key ID, run ID, request ID, objective, reviewer, credential fingerprint, or user content. It is designed for cluster-internal scraping. The Helm chart emits standard Prometheus pod annotations when `observability.metrics.enabled=true`.

## Individual identity and RBAC

Production configuration uses `AGENCY_IDENTITY_CREDENTIALS_JSON`, an array of records:

```json
[
  {
    "tenant_id": "tenant-alpha",
    "subject_id": "operator@example.com",
    "role": "operator",
    "key_id": "operator-v2",
    "api_key": "replace-with-secret-material-at-least-24-characters",
    "active": true
  }
]
```

Roles are intentionally fixed and fail closed:

| Role | Permissions |
|---|---|
| `viewer` | `identity:read`, `runs:read`, `audit:read` |
| `operator` | viewer permissions plus `runs:create` |
| `approver` | viewer permissions plus `greenlight:decide` |
| `admin` | all current permissions |

A `key_id` is unique within a tenant. Multiple active key IDs may identify the same subject during a controlled rotation window. To rotate a key:

1. Add a new active record with a new `key_id`.
2. Deploy and migrate clients to the new credential.
3. Mark the old record `active=false` or remove it.
4. Redeploy/restart the runtime.

After step 4, the old bearer credential fails and every browser session derived from its old `key_id`/fingerprint is rejected. Raw API keys, session tokens, and CSRF values are never stored in SQLite; only SHA-256-derived values are persisted. Sessions created before version 0.6 with a 16-character credential fingerprint remain valid only while their mapped legacy key remains active; newly issued sessions store the full digest.

`AGENCY_TENANT_API_KEYS_JSON` remains as a migration-only tenant-level administrator mapping. The Helm production chart allows its Secret key to be omitted, but requires individual identity configuration. Do not use the legacy mapping for new deployments.

This is application-managed identity, not a complete enterprise identity platform. SSO, MFA, account recovery, lifecycle provisioning, device policy, and managed IdP integration remain open controls.

## Authentication abuse controls

Failed authentication attempts are stored durably as opaque bucket hashes:

- `AGENCY_LOGIN_MAX_FAILURES` limits one credential fingerprint; default `5`.
- `AGENCY_LOGIN_SOURCE_MAX_FAILURES` limits password-spray attempts across different credentials from one source; default `50` and must be greater than or equal to the credential threshold.
- `AGENCY_LOGIN_WINDOW_SECONDS` defines the rolling window; default `300`.

A blocked request returns `429` and `Retry-After`. Successful authentication does not reveal or persist raw credential material. Old failures expire from SQLite when the next authentication check runs.

Source attribution depends on Uvicorn proxy handling. Set `FORWARDED_ALLOW_IPS` only to known reverse-proxy addresses or CIDRs. Never use `*` unless a trusted edge strips client-supplied forwarding headers. The application limiter complements, but does not replace, ingress/WAF rate limits and distributed abuse detection.

## Browser sessions

Production defaults are `HttpOnly`, `SameSite=Strict`, `Secure=true`, and an eight-hour TTL. Configure them with `AGENCY_SESSION_COOKIE_NAME`, `AGENCY_SESSION_COOKIE_SECURE`, and `AGENCY_SESSION_TTL_SECONDS`. Disable `Secure` only for isolated local HTTP smoke tests.

Mutations authenticated by cookie require `X-CSRF-Token`; bearer clients do not. Session recovery rotates the CSRF token. Sessions retain tenant, subject, role, key ID, and credential fingerprint so deactivating a key invalidates its existing sessions.

## Request correlation

Every HTTP response includes `X-Request-ID`.

- Incoming IDs are accepted only when they match a bounded safe character set and length.
- Invalid or absent IDs are replaced with an opaque `req-<uuid>` value.
- Mutation audit records retain the same request ID.
- Clients should supply a new request ID per logical request and include it in support reports.

## Structured HTTP logs

The `agency_runtime.http` logger writes one JSON object per completed request with:

- event;
- request ID;
- HTTP method;
- route template, never raw path parameters or query string;
- status code;
- duration in milliseconds;
- authenticated tenant ID when available.

The logger does not write headers, bearer credentials, request/response bodies, query strings, campaign content, Greenlight notes, subject IDs, or key IDs. Logs are emitted to stdout through the process logging configuration.

## Prometheus metrics

Current metrics:

- `agency_runtime_info`;
- `agency_http_requests_total`;
- `agency_http_request_duration_seconds_sum`;
- `agency_http_request_duration_seconds_count`;
- `agency_runs_started_total`;
- `agency_greenlight_decisions_total`;
- `agency_browser_sessions_total`;
- `agency_authentication_attempts_total` with only `succeeded`, `failed`, or `rate_limited` outcomes.

HTTP labels are limited to method, FastAPI route template, and status. Greenlight labels contain only `approved` or `rejected`. Authentication metrics never include identity or source labels.

These counters are process-local and reset when the pod restarts. Durable business evidence belongs in the audit ledger; durable abuse counters belong in SQLite.

## Durable audit ledger

Session creation, run creation, and Greenlight decisions are written to `audit_events` in the same SQLite transaction as the corresponding state change. A failed duplicate request does not produce a successful mutation event.

Each event includes:

- monotonically increasing sequence;
- opaque event ID;
- tenant ID;
- request ID;
- timestamp;
- action;
- resource type and ID;
- actor in the form `api-key:<subject_id>` or `browser-session:<subject_id>`;
- action-specific payload.

The API returns only the authenticated tenant's events. `viewer`, `operator`, `approver`, and `admin` all currently receive `audit:read`; narrow that policy before exposing sensitive tenant audit data to broader user populations. Pagination uses `after_sequence` and `limit`:

```bash
curl -H "Authorization: Bearer $AGENCY_API_KEY" \
  "http://127.0.0.1:8080/api/v1/audit-events?after_sequence=0&limit=100"
```

The current ledger is append-only through application interfaces but is not cryptographically signed or exported to immutable storage. Retention, legal hold, subject pseudonymization, tamper-evident hashing, and external SIEM export remain future production controls.

## PostgreSQL schema and role boundary

PostgreSQL application pods use `AGENCY_POSTGRES_SCHEMA_MODE=validate`. They require a pre-initialized schema and a non-owner runtime URL; readiness checks the required relations and schema version without running DDL.

Schema initialization, SQLite migration and restore use a separate migration/operator URL through the packaged command:

```bash
agency-runtime-schema initialize --database-url-env AGENCY_MIGRATION_DATABASE_URL
agency-runtime-schema validate --database-url-env AGENCY_DATABASE_URL
```

The runtime role must own no application objects and must not have schema `CREATE`, DDL, `TRUNCATE` or schema-metadata mutation. The deployment chart rejects `initialize` for long-running pods and never injects migration credentials. Follow [PostgreSQL Schema and Runtime Role Runbook](runbooks/postgresql-schema-rollout.md) before a PostgreSQL rollout or restore. Persistent role, schema, Secret or traffic changes remain human-gated.

The repository implementation and verifier contract are present, but `INC-012` is not considered verified until the exact-commit PostgreSQL, Helm, Terraform, package and regression gates are executed and recorded.

## Backup, restore and data rollback

`scripts/manage-runtime-backup.py` creates strict, checksummed `agency-runtime-backup.v1` artifacts for SQLite and PostgreSQL. SQLite uses the online backup API and atomic restore; PostgreSQL uses custom-format `pg_dump`, validates with `pg_restore --list`, refuses non-empty targets and restores in one transaction. Connection URLs remain in named environment variables and passwords are removed from tool errors.

The deterministic repository drill is part of:

```bash
./scripts/verify-postgresql-runtime.sh
```

It restores representative SQLite and PostgreSQL state, compares run/audit/session/rate-limit/memory counts and proves application-level readability. This is local ephemeral recovery evidence, not an encrypted scheduled backup service or production/staging disaster-recovery exercise.

Use [Runtime Backup and Restore Runbook](runbooks/runtime-backup-restore.md) for commands, manifests, security boundaries, rollback separation and exact human gates. Any replacement of persistent data, database cutover, deletion or loss-acceptance decision requires explicit human approval.

## Alerting baseline

Recommended initial alerts:

- readiness failures for more than five minutes;
- elevated authentication `failed` or `rate_limited` outcomes;
- elevated `5xx` rate by route;
- sustained latency growth on run creation or Greenlight decisions;
- pod restart loops;
- PVC capacity pressure;
- absence of expected audit events after successful mutation metrics.

No alert should include campaign content, credential material, subject ID, or key ID.
