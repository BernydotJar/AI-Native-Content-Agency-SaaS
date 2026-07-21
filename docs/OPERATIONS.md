# Runtime Operations

## Operational endpoints

| Endpoint | Authentication | Purpose |
|---|---|---|
| `GET /healthz` | none | Process liveness and sandbox-mode declaration. |
| `GET /readyz` | none | Readiness; returns `503` when tenant authentication is absent. |
| `GET /metrics` | none | Prometheus text exposition with low-cardinality, non-tenant labels. |
| `POST /api/v1/sessions` | one-time tenant credential | Creates an HttpOnly browser session and returns an in-memory CSRF token. |
| `GET /api/v1/sessions/current` | HttpOnly cookie | Restores the browser session and rotates CSRF. |
| `DELETE /api/v1/sessions/current` | cookie + CSRF | Revokes the durable browser session. |
| `GET /api/v1/audit-events` | bearer or HttpOnly session | Durable, tenant-scoped mutation ledger with cursor pagination. |

`/metrics` intentionally contains no tenant ID, run ID, request ID, objective, reviewer, credential fingerprint, or user content. It is designed for cluster-internal scraping. The Helm chart emits standard Prometheus pod annotations when `observability.metrics.enabled=true`.

## Request correlation

Every HTTP response includes `X-Request-ID`.

- Incoming IDs are accepted only when they match a bounded safe character set and length.
- Invalid or absent IDs are replaced with an opaque `req-<uuid>` value.
- Mutation audit records retain the same request ID.
- Clients should supply a new request ID per logical request and include it in support reports.

## Structured HTTP logs

The `agency_runtime.http` logger writes one JSON object per completed request with:

- `event`;
- `request_id`;
- HTTP method;
- route template, never raw path parameters or query string;
- status code;
- duration in milliseconds;
- authenticated tenant ID when available.

The logger does not write headers, bearer credentials, request bodies, response bodies, query strings, campaign content, or Greenlight notes. Logs are emitted to stdout through the process logging configuration.

## Prometheus metrics

Current metrics:

- `agency_runtime_info`;
- `agency_http_requests_total`;
- `agency_http_request_duration_seconds_sum`;
- `agency_http_request_duration_seconds_count`;
- `agency_runs_started_total`;
- `agency_greenlight_decisions_total`;
- `agency_browser_sessions_total`.

HTTP labels are limited to method, FastAPI route template, and status. Greenlight labels contain only `approved` or `rejected`.

These counters are process-local and reset when the pod restarts. Durable business evidence belongs in the audit ledger, not in metrics.

## Browser sessions

Production defaults are `HttpOnly`, `SameSite=Strict`, `Secure=true`, and an eight-hour TTL. Configure them with `AGENCY_SESSION_COOKIE_NAME`, `AGENCY_SESSION_COOKIE_SECURE`, and `AGENCY_SESSION_TTL_SECONDS`. Disable `Secure` only for isolated local HTTP smoke tests.

Session and CSRF values are stored as SHA-256 hashes. Mutations authenticated by cookie require `X-CSRF-Token`; bearer clients do not. Session recovery rotates the CSRF token. Login rate limiting, MFA and user-level identity are not yet implemented.

## Durable audit ledger

Run creation and Greenlight decisions are written to `audit_events` in the same SQLite transaction that creates or updates the run. A failed duplicate request does not produce a successful mutation event.

Each event includes:

- monotonically increasing sequence;
- opaque event ID;
- tenant ID;
- request ID;
- timestamp;
- action;
- resource type and ID;
- credential fingerprint actor, never the raw credential;
- action-specific payload.

The API returns only the authenticated tenant's events. Pagination uses `after_sequence` and `limit`:

```bash
curl -H "Authorization: Bearer $AGENCY_API_KEY" \
  "http://127.0.0.1:8080/api/v1/audit-events?after_sequence=0&limit=100"
```

The current ledger is append-only through application interfaces but is not cryptographically signed or exported to immutable storage. Retention, legal hold, tamper-evident hashing, and external SIEM export remain future production controls.

## Alerting baseline

Recommended initial alerts:

- readiness failures for more than five minutes;
- elevated `5xx` rate by route;
- sustained latency growth on run creation or Greenlight decisions;
- pod restart loops;
- PVC capacity pressure;
- absence of expected audit events after successful mutation metrics.

No alert should include campaign content or credential material.
