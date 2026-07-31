# Audit Ledger Integrity Runbook

## Purpose

Every tenant audit stream is a versioned SHA-256 chain. Each event stores `previous_hash` and `event_hash`; `audit_chain_heads` stores the event count and current head. The head makes tail deletion detectable. SQLite and PostgreSQL update the event and head in the same transaction.

Signed checkpoints allow an authenticated `audit:read` user to export a compact receipt:

- schema version;
- tenant ID;
- event count;
- head event ID;
- head hash;
- verification timestamp;
- active key ID;
- HMAC-SHA256 signature.

## Configuration

Checkpoint signing is optional. Configure both variables or neither:

- `AGENCY_AUDIT_CHECKPOINT_SIGNING_KEYS_JSON`
- `AGENCY_AUDIT_CHECKPOINT_ACTIVE_KEY_ID`

The JSON maps bounded key IDs to canonical unpadded base64url encoding of exactly 32 bytes. Local development may use environment variables. Helm and Terraform accept only a pre-provisioned Secret name and its two data-key names; raw key material must not enter values, Git or Terraform state.

## Verification

1. Authenticate as an identity with `audit:read`.
2. Request `GET /api/v1/audit-events/integrity`.
3. Reconstruct the canonical checkpoint document without `key_id` and `signature`.
4. Verify HMAC-SHA256 with the key named by `key_id`.
5. Compare `event_count`, `head_event_id` and `head_hash` with the prior independently retained checkpoint.

HTTP 503 `audit_integrity_verification_failed` means the database chain or head does not verify. Stop release/deployment activity, preserve the database and logs, and investigate under incident-response authority. Do not silently rebuild or overwrite the chain.

## Key rotation

1. Add a new exact 32-byte key under a new ID while retaining old keys.
2. Update the active key ID.
3. Roll the workload and verify readiness exposes only the new ID, not material.
4. Export and independently verify a checkpoint signed by the new key.
5. Retain old keys for the required checkpoint verification and audit-retention period.
6. Remove an old key only after accountable security/retention approval.

Production Secret mutation, KMS/HSM custody and rotation are human-gated operations.

## Migration and recovery

Schema v9 backfills existing events in tenant/sequence order and creates a head per tenant. Migration fails if pre-existing hashes or heads disagree with recomputation. SQLite-to-PostgreSQL migration recomputes and verifies hashes rather than trusting copied values. Backup/restore must preserve both `audit_events` and `audit_chain_heads` and run chain verification after restore.

## Security boundary

A database owner can still rewrite every row and head. Independently retained signed checkpoints make such rewrites detectable by comparison, but this repository does not provide immutable off-host custody, transparency logs, KMS/HSM non-exportable keys or legal non-repudiation. Those remain external production controls under INC-005 and INC-011.
