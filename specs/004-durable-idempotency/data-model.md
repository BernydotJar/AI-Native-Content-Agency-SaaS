# Data Model

## Command receipt

Receipts reuse `audit_events` atomically with the mutation.

- `event_id`: deterministic `command-*` digest of tenant, operation and key digest.
- `tenant_id`: authoritative authenticated tenant.
- `action`: committed business mutation (`run.created`, `greenlight.approved`, etc.).
- `resource_id`: committed run ID.
- `payload.idempotency.operation`: bounded operation name.
- `payload.idempotency.request_fingerprint`: SHA-256 stable digest of operation, resource, payload and subject.

The raw key is never persisted.

## Greenlight fencing

- `fencing_token`: positive integer; starts at 1 and increments on revocation.
- `revoked_at`: nullable UTC timestamp.
- `revoked_by`: bounded authenticated actor label.
- `revocation_reason`: bounded human reason.

A Greenlight is effect-authorizing only when approved, unrevoked, exact-ID and current-token checks pass.
