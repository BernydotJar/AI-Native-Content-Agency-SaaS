# INC-028 Requirements — Audit Ledger Integrity

## Problem

`F-012` identifies that the transactional audit ledger can be modified by a database owner without deterministic tamper evidence. The ledger is not hash chained, and there is no signed checkpoint that an operator can export independently.

## Required behavior

1. Every audit event stores a 64-hex previous hash and event hash.
2. The chain is independent per tenant and begins with a defined all-zero genesis hash.
3. The event hash covers a versioned canonical document containing every persisted audit field except database sequence, plus the previous hash.
4. SQLite and PostgreSQL append the chain atomically in the same transaction as the domain mutation.
5. PostgreSQL serializes only the affected tenant chain and remains correct across replicas.
6. Existing SQLite and PostgreSQL rows are backfilled deterministically in tenant/sequence order during migration.
7. A verifier recomputes every link and fails closed on field mutation, deletion, insertion, reordering or broken linkage.
8. Authenticated `audit:read` users can request a bounded integrity checkpoint containing event count, head event ID, head hash and verification timestamp.
9. Checkpoints are HMAC-SHA256 signed with an externalized keyring and include the active key ID. Partial, ambiguous or weak key configuration fails startup.
10. No signing key, raw signature key material or unrestricted tenant data enters logs, metrics, audit payloads or Terraform state.
11. PostgreSQL advances to schema v9; migration, least-privilege grants, backup/restore and SQLite migration preserve chain fields.
12. Local runner, Helm and Terraform support only Secret references for checkpoint keys.
13. Package and exact-head CI prove integrity verification, tamper detection and zero external effects.

## External boundary

This increment does not claim immutable off-host storage, transparency logging, KMS/HSM custody, production key rotation, retention approval or legal non-repudiation. Those remain explicit production/human gates under INC-005 and INC-011.
