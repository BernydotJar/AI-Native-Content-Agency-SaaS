# INC-028 Production Review

| Criterion | Reconstructed-tree evidence | Result |
|---|---|---|
| per-tenant canonical event chain | SQLite and PostgreSQL tests | PASS |
| durable head detects tail deletion | mutation/deletion/reordering tests | PASS |
| legacy backfill deterministic | reopen and migration tests | PASS |
| cross-replica same-tenant serialization | PostgreSQL concurrent append test | PASS |
| admin tampering detected | migration-role mutation test | PASS |
| signed checkpoint verifies | API and installed-image HMAC verification | PASS |
| weak/partial keyring fails startup | primitive/API tests | PASS |
| session quota revision 5 preserved | session and sanitized-429 regressions | PASS |
| schema v9 migration/backup/restore | PostgreSQL 15.18 verifier, 372 tests | PASS |
| non-root OCI package | Buildah package verification | PASS |
| frontend regression | 58 tests, lint, build | PASS |
| exact-head remote jobs | pending rebuilt PR head | PENDING |
| immutable external custody/KMS | unavailable and unauthorized | EXTERNAL BLOCKER |

The cryptographic chain is production-relevant code, but it is not immutable storage or legal non-repudiation. `DENY_RELEASE` and `DENY_APPLY` remain mandatory. No provider, cloud, secret or publication effect occurred.
