# ADR 0009 — Defer distributed tracing until a multi-service runtime exists

- Status: accepted
- Date: 2026-07-21
- Owner: WS-09

## Context

The selected runtime is one FastAPI process with local deterministic agents and one SQLite or PostgreSQL persistence boundary. It emits structured request logs, bounded request IDs, counters, cumulative latency histograms, health and readiness signals. External model, browser, media, publication and advertising adapters remain disabled.

Adding an OpenTelemetry SDK and collector now would create a new telemetry transport, retention and privacy surface without a real cross-service causal path to diagnose. A collector manifest or empty trace backend would not be evidence of useful tracing.

## Decision

Do not add distributed tracing to the current single-service deterministic sandbox. Continue using:

- `X-Request-ID` correlation across HTTP logs, audit events and public errors;
- bounded route/method/status metrics and latency histograms;
- explicit dependency/readiness checks;
- versioned SLO, alert and runbook contracts.

Distributed tracing becomes mandatory before enabling any production architecture with a separately deployed worker, effectful provider adapter, queue, browser/video service or other cross-process request path.

The future implementation must use W3C Trace Context and OpenTelemetry, define sampling and redaction, prohibit tenant/content/credential values in span attributes, document retention and exporter failure behavior, and demonstrate traces in an authorized staging environment.

## Consequences

- `OPS-003` has an explicit reviewed decision instead of an unimplemented implied requirement.
- No claim is made that distributed tracing or a collector is currently deployed or observed.
- Request IDs remain the authoritative local correlation mechanism.
- Activating a multi-service or external-effect architecture without revisiting this ADR is a release blocker.
