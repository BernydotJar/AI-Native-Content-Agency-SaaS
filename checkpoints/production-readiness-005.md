# Production Readiness Checkpoint 005

## Increment

Add operational observability and durable tenant-scoped audit evidence without introducing sensitive telemetry or external dependencies.

## Delivered

- Validated/generated `X-Request-ID` on every HTTP response.
- JSON completion logs with request ID, route template, status, duration, and optional tenant ID.
- Explicit exclusion of authorization headers, raw paths, query strings, bodies, and credentials from application logs.
- Prometheus `/metrics` endpoint with low-cardinality labels and no tenant/run/content identifiers.
- Counters for HTTP requests, durations, persisted runs, and durable Greenlight decisions.
- Transactional `audit_events` ledger stored with run mutations.
- Tenant-scoped `/api/v1/audit-events` cursor pagination.
- Audit actions for run creation and approved/rejected Greenlights.
- Credential fingerprint actor instead of raw bearer token.
- Helm Prometheus scrape annotations.
- Operations runbook and ADR 0002.
- Corrected runtime compatibility contract from Python `>=3.9` to `>=3.10` after inspecting installed dependency metadata.

## Verification evidence

- Python: 25/25 tests pass.
- Frontend: 28/28 tests pass.
- Oxlint: zero findings.
- Vite build: pass.
- Helm lint/template: pass, metrics annotations rendered.
- Structured-log test confirms bearer key and query secret are absent.
- Metrics test confirms tenant IDs, credentials, and query values are absent.
- Audit test confirms duplicate run conflict does not create a false mutation event.
- Audit test confirms tenant isolation and survival across service restart.
- Package verification covers request correlation, run creation, Greenlight approval, sandbox package, ledger export, and metrics.

## Remaining program work

- Frontend still uses its browser simulation rather than the authenticated API.
- Metrics reset with the process; no OpenTelemetry or remote exporter exists.
- Audit records lack retention policy, hash chaining, immutable export, and SIEM integration.
- User-level identity and RBAC remain absent.
- SQLite remains single-node.
