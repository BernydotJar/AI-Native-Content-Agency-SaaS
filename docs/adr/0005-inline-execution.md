# ADR 0005 — Inline execution before queues

- Decision: Keep the bounded sandbox workflow inline for V1.
- Status: Accepted
- Context: Current deterministic work is short and has no retryable external side effect.
- Alternatives: Inline; local worker; Cloud Tasks; Pub/Sub.
- Evidence: A queue would introduce leases, duplicate delivery, dead letters, cancellation, and cost without a consumer need.
- Chosen option: Persist each command result transactionally and document that an interruption before commit must be retried idempotently.
- Trade-offs: Simple and testable; no mid-step resume and request timeouts cap future work.
- Consequences: Cloud Tasks/Pub/Sub/outbox remain absent.
- Review trigger: A run can exceed request timeout or activates a retryable provider operation.
- Date: 2026-07-18
- Owner: Orchestrator
