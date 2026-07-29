# ADR 0002: Structured observability and transactional audit ledger

- Status: accepted
- Date: 2026-07-21

## Context

The authenticated runtime had durable run state but lacked request correlation, operational metrics, structured logs, and an exportable audit history. Logging request bodies or using tenant/run identifiers as metric labels would create confidentiality and cardinality risks. Writing audit events after committing run state could also leave an irreversible decision without corresponding evidence.

## Decision

1. Correlate every HTTP response with a validated or generated `X-Request-ID`.
2. Emit JSON completion logs using route templates and no headers, query strings, bodies, or credential values.
3. Expose dependency-free Prometheus metrics with low-cardinality labels only.
4. Keep metrics process-local and use the durable ledger for business evidence.
5. Append `run.created` and `greenlight.approved|rejected` records in the same SQLite transaction as the associated run mutation.
6. Scope all ledger queries by authenticated tenant and return cursor-based pages.
7. Identify the calling credential only by a truncated SHA-256 fingerprint.
8. Expose `/metrics` without tenant authentication because it contains no tenant labels or content and is intended for cluster-internal scraping.
9. Add Prometheus scrape annotations through Helm, without coupling the chart to a specific operator CRD.

## Consequences

### Positive

- Operators can correlate API responses, logs, metrics, and durable audit records.
- Successful state changes cannot occur without their mutation audit record.
- Metrics avoid tenant cardinality and disclosure.
- The implementation requires no external telemetry backend or credentials.

### Trade-offs

- Metrics reset on restart.
- Logs are stdout JSON but are not shipped by this repository.
- The audit ledger is application-append-only, not cryptographically immutable.
- `/metrics` should remain cluster-internal through ingress and network policy configuration.
- Distributed tracing and OpenTelemetry export remain unimplemented.
