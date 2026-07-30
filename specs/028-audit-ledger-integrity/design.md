# INC-028 Design — Audit Ledger Integrity

## Chain

Each tenant has a logical chain. The genesis previous hash is 64 zeroes. The event hash is SHA-256 over canonical JSON:

`["audit-event-v1", event_id, tenant_id, request_id, occurred_at, action, resource_type, resource_id, actor, payload, previous_hash]`

The database sequence is excluded because PostgreSQL allocates it globally; order is nevertheless bound through the previous hash and event ID. Verification walks tenant rows in sequence order and compares both links and hashes.

## Append concurrency

SQLite uses its existing store lock and transaction.

PostgreSQL obtains `pg_advisory_xact_lock(hashtextextended("audit-chain:" + tenant_id, 0))`, reads the current tenant head, computes the new hash and inserts in the same transaction. Different tenants remain concurrent.

## Migration

SQLite adds nullable/default chain columns, then backfills every tenant in sequence order before allowing append or verification.

PostgreSQL schema v9 adds the columns and performs equivalent deterministic backfill under migration authority. Runtime validation requires non-null 64-hex values.

## Signed checkpoint

A strict keyring maps bounded key IDs to exact 32-byte base64url keys and selects one active key. The checkpoint canonical document includes schema, tenant ID, event count, head event ID/hash and verified timestamp. The response includes `key_id` and base64url HMAC-SHA256 signature.

The keyring is required only to expose the checkpoint endpoint; partial configuration fails startup. Regular audit append remains available without signing configuration, while readiness discloses whether signed checkpoints are configured.

## Failure model

- mutation/deletion/reordering/link mismatch: verifier raises integrity error;
- missing active key or weak/invalid key: startup fails;
- retired checkpoint key: historical signature cannot be independently verified until the old key is restored;
- database owner can rewrite the entire chain: signed exported checkpoints allow comparison, but immutable off-host custody remains external.
