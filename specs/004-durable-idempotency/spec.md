# INC-004 — Durable Command Idempotency and Greenlight Fencing

## Problem

Authenticated business mutations currently use deterministic resource IDs but reject duplicate delivery. A client cannot distinguish a safe retry from a conflicting command, concurrent replicas may execute provider work more than once, and an approved Greenlight cannot be revoked before a future effectful adapter acts.

## Purpose

Provide tenant-scoped durable idempotency for run creation and Greenlight approve/reject/revoke commands, exact compatible replay, uniform conflicts, single provider execution, and a persisted revocation/fencing contract. External publication remains disabled.

## Actors and journeys

- **Operator:** submits a campaign brief with an idempotency key and safely retries after timeout.
- **Approver:** decides or revokes Greenlight with a separate idempotency key.
- **Future effect adapter:** must present the exact Greenlight ID, current fencing token, artifact set, channel and budget before acting.
- **Auditor:** sees one committed mutation event and no raw idempotency key.

## Functional requirements

1. `POST /api/v1/runs` and Greenlight approve/reject/revoke require `Idempotency-Key`.
2. Keys are 8–200 bounded safe characters and are never stored or logged raw.
3. The ledger namespace is tenant plus operation plus key digest.
4. The request fingerprint binds operation, resource, payload and authenticated subject.
5. Identical replay returns the original committed run document and HTTP success status.
6. Reusing the same key with a different fingerprint returns stable public `409 idempotency_conflict`.
7. A different key that targets an already-created deterministic run remains a normal resource-state conflict.
8. Mutation and replay receipt are committed in the same SQLite/PostgreSQL transaction.
9. Concurrent replicas execute the orchestrator/package provider at most once for one compatible command.
10. Approvals persist `fencing_token=1` and are active only while not revoked.
11. Greenlight revoke is exact-authorized, idempotent, audited and increments the fencing token.
12. Revocation changes the run to terminal `revoked`, blocks Publisher and does not delete prior evidence.
13. The future-effect guard rejects rejected, revoked, stale-token, wrong-Greenlight, altered-artifact, unauthorized-channel and over-budget requests.
14. Authentication/session issuance is excluded because exact replay would require persisting raw session/CSRF secrets; clients must not silently retry it.
15. No endpoint publishes, spends, renders, contacts a provider or creates external infrastructure.

## Non-functional requirements

- SQLite single-replica and PostgreSQL multi-replica behavior are equivalent.
- Raw idempotency keys, API keys, cookies and CSRF values never enter persistence or audit.
- Public errors do not reveal prior payload, actor, resource state or key digest.
- The ledger remains tenant-scoped and append-only through application interfaces.
- Existing persisted runs without fencing fields deserialize safely.
- Backup/restore and SQLite→PostgreSQL migration preserve command receipts because receipts use the audit ledger.

## States and failures

- `new` → execute once and commit mutation plus receipt.
- `compatible_replay` → return committed resource without provider execution or new audit event.
- `key_conflict` → uniform 409, no mutation.
- `resource_conflict` → uniform 409, no mutation.
- `approved_active` → token 1 authorizes only exact bounded future effect.
- `revoked` → token increments, all prior tokens are fenced.
- `concurrent_claim` → one commit; compatible loser replays, incompatible loser conflicts.

## Security, privacy and tenant boundaries

The event ID is a deterministic digest over tenant, operation and key digest. Audit payload stores only operation and request fingerprint. Tenant authentication remains server-side. Revocation requires `greenlight:revoke`; no client-supplied tenant ID is trusted.

## Accessibility

Any console control added for revocation must be keyboard accessible, visibly focused, semantically labelled and not rely on color alone. API-only errors remain available as text.

## Acceptance criteria

- identical create and decision replay returns byte-equivalent JSON;
- changed payload with the same key returns `idempotency_conflict`;
- audit count and campaign package prove provider work executed once;
- replay survives service restart and PostgreSQL replica boundaries;
- concurrent compatible requests both succeed with one mutation;
- concurrent incompatible requests yield one success and one sanitized 409;
- raw key is absent from database rows, audit output and logs;
- revoke replay is exact and one revocation audit event exists;
- stale fencing token and altered authorization envelope are rejected;
- locked wheel, PostgreSQL, frontend, package, program, secrets and CI remain green.

## Out of scope

- idempotent browser-session secret issuance;
- external provider calls, receipts or callback processing;
- re-approval after revocation;
- production deployment, cloud apply, spending or publication.
