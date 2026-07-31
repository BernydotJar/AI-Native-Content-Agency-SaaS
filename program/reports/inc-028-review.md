# INC-028 Role-Separated Review

Date: 2026-07-31
Graph revision: 0 (reconstructed on merged quota base)
Decision: PASS for local technical review; exact-head CI and PR review pending.

## Producer

Implemented versioned per-tenant SHA-256 audit chains, durable chain heads, deterministic SQLite/PostgreSQL backfill, schema v9, cross-replica same-tenant serialization, fail-closed verification, a strict rotatable HMAC checkpoint keyring and a tenant-scoped signed checkpoint endpoint for `audit:read` identities.

The reconstructed API preserves the quota revision-5 ordering: authenticated quota is consumed before identity is published to request logging, and browser-session creation consumes the same principal/tenant buckets.

## Critic / Red Team

Coverage includes:

- mutation of action, actor and payload;
- deletion, reordering and broken linkage;
- legacy rows without hashes;
- concurrent PostgreSQL appends;
- administrator tampering outside the runtime role;
- weak, padded, duplicate, partial and absent keyring configuration;
- checkpoint/document tampering and missing retired keys;
- tenant isolation and sanitized API failures;
- session quota coverage and 429-log privacy from INC-027 revision 5;
- absence of signing material from health, readiness and package output.

All executable scenarios fail closed or verify as expected. A transactional durable head detects tail truncation. Tenants retain independent genesis chains.

## Historical localized repairs retained

The implementation contains the four earlier localized repairs:

1. canonical unpadded base64url is mandatory;
2. callers cannot supply derived audit hashes;
3. schema/restore fixtures preserve schema v9;
4. API tests create real audited mutations instead of assuming reads append events.

The reconstruction introduced no conflict and preserved the two quota review repairs merged in PR #36.

## Independent verification on the reconstructed tree

- locked installed wheel: 372 tests PASS; 27 PostgreSQL-only skips;
- PostgreSQL 15.18: 372 tests PASS; schema v9; multi-replica chain, migration, least privilege, SQLite/PostgreSQL backup and restore PASS;
- non-root OCI package: audit checkpoint, durable audit, quota and default-disabled provider guards PASS;
- frontend: 58 tests PASS; zero lint findings; production build PASS;
- program, Graph Harness, repository governance, compliance and operability validators PASS;
- release decision: `DENY_RELEASE`; external effects: `0`.

## Limitations

Exact-head CI, PR review and ordered merge remain pending. Production signing-key provisioning/rotation, immutable off-host checkpoint retention, KMS/HSM custody, release, deployment and legal acceptance remain separate human/external gates.


## PR #37 review repair — revision 1

The rebuilt PR review found three valid correctness gaps:

1. PostgreSQL checkpoint verification could read events and the durable head across two READ COMMITTED snapshots while another replica appended;
2. SQLite-to-PostgreSQL migration verified surviving row hashes but did not compare a schema-v9 source head before rebuilding the target head, which could launder detectable tail deletion;
3. SQLite/PostgreSQL restore paths validated file/schema shape but did not cryptographically verify restored event chains before returning `status: restored`.

The localized repair:

- acquires the same tenant-scoped transaction advisory lock for PostgreSQL verification as for append;
- prepares and validates the complete source chain plus exact source heads before executing any target audit insert;
- verifies chain linkage, event hashes, tenant sets and durable heads before SQLite installation and after copy;
- enumerates restored PostgreSQL tenants and invokes the runtime verifier before reporting success;
- converts driver/connection failures to a sanitized restore error and always closes the validation pool.

New regressions prove verifier lock blocking, migration rejection before target writes, valid-checksum SQLite corruption rejection and PostgreSQL restore failure propagation. Development wheel and PostgreSQL suites pass 375 tests. No unrelated node was invalidated and no external effect occurred.
