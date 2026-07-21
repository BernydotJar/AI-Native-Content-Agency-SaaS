# ADR 0008 — Durable command idempotency and Greenlight fencing

- Status: accepted for INC-004
- Date: 2026-07-21
- Runtime: `backend/agency_runtime`

## Context

Run creation and Greenlight decisions are deterministic, but delivery retries previously returned conflicts and concurrent replicas could repeat the local provider work. Approved Greenlights also lacked a durable revocation/fencing state suitable for a future effectful adapter.

## Decision

Use the existing transactional audit ledger as the durable command receipt:

- a deterministic `event_id` binds tenant, operation and a SHA-256 digest of the idempotency key;
- the request fingerprint binds operation, resource, authenticated subject and canonical payload;
- the audit payload stores the operation, fingerprint and exact committed response document;
- the raw idempotency key is never stored, logged or returned;
- mutation and receipt commit in one SQLite/PostgreSQL transaction;
- PostgreSQL serializes concurrent compatible commands with a dedicated session-level advisory lock outside the application pool transaction;
- compatible replay returns the original response and does not increment mutation metrics;
- incompatible key reuse returns uniform `idempotency_conflict`.

Greenlight approval starts at fencing token `1`. Revocation preserves the decision and artifact evidence, increments the token, records the authenticated subject and reason, moves the run to `revoked`, and blocks the Publisher. A future adapter must present the current Greenlight ID, token, exact artifact IDs/hashes, channel and bounded budget.

## Consequences

- Compatible retries survive restart and PostgreSQL replica boundaries.
- Concurrent provider/package work executes once for a command.
- The audit ledger grows faster because it contains a replay snapshot. Capacity, retention, immutable export and compaction remain operational work.
- Browser-session creation is not silently retryable: exact replay would require recoverable session/CSRF secrets, violating the existing credential boundary.
- A process crash before the transactional receipt may repeat deterministic local sandbox work. No external side effect exists today. A future effectful provider requires its own durable outbox, provider idempotency token, receipt and revocation contract before activation.
- Client-supplied `reviewer` text is not authoritative; persisted decision/revocation identity comes from the authenticated subject.
