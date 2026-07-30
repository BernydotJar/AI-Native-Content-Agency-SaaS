# INC-028 Role-Separated Review

Date: 2026-07-30
Graph revision: 4
Decision: PASS for local review; exact-head CI pending.

## Producer

Implemented versioned per-tenant SHA-256 audit chains, durable chain heads, deterministic SQLite/PostgreSQL backfill, schema v9, cross-replica same-tenant serialization, fail-closed verification, strict HMAC checkpoint keyring and a tenant-scoped signed checkpoint endpoint for `audit:read` identities.

## Critic / Red Team

The critic exercised:

- mutation of action/actor/payload;
- deletion of the tail event;
- sequence reordering;
- legacy rows without hashes;
- concurrent appends from two PostgreSQL stores;
- administrative tampering outside the runtime role;
- weak, padded, duplicate, partial and missing keyring configuration;
- checkpoint document tampering and retired-key absence;
- tenant isolation and safe API errors;
- Secret leakage through health, readiness, Helm render and Terraform state.

All scenarios fail closed or verify as expected. A durable head makes tail truncation detectable. Different tenants maintain independent genesis chains.

## Fixer

Four Graph Harness repairs were localized to INC-028:

1. padded base64url was accepted; exact unpadded canonical encoding is now required;
2. derived hashes were accidentally attached to `AuditWrite`; callers now provide no hashes and persisted `AuditEvent` carries them;
3. one compatibility test and restore assertion still wrote schema v8; both now preserve schema v9;
4. API tests assumed `/me` wrote audit events; fixtures now create real audited mutations.

No unrelated node or evidence was invalidated.

## Security and Privacy Reviewer

- Chain hashes cover every persisted audit field except global database sequence, while linkage and event ID bind order.
- `audit_chain_heads` protects against tail deletion and is updated in the same transaction.
- PostgreSQL advisory locks serialize only the tenant chain being written.
- Checkpoint keys are exact 32-byte externalized secrets; readiness exposes only configured state and active key ID.
- API errors do not reflect tampered database content or key material.
- A database owner can still rewrite all rows and heads; independent signed checkpoint custody is necessary to detect that rewrite.
- No immutable storage, KMS/HSM custody or legal non-repudiation is claimed.

## Independent Verifier

- focused integrity/API/SQLite tests PASS;
- locked wheel: 371 PASS, 27 PostgreSQL-only skips;
- PostgreSQL 15.18: 366 PASS, schema v9, multi-replica chain, migration, least privilege and backup/restore PASS;
- non-root OCI package: signed checkpoint HMAC independently verified;
- K3s/Helm/Terraform: Secret refs and plan/apply/destroy PASS; key material absent from state;
- frontend: 58 PASS; lint and production build PASS;
- program, graph, governance, compliance and operability validators PASS.

## Limitations

Exact-head CI is pending. Production key provisioning/rotation, immutable off-host checkpoint retention, KMS/HSM custody, release, deployment and legal acceptance are human/external gates.
