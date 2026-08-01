# INC-030 Closure — Runtime Schema Compatibility Matrix

Date: 2026-07-31
Graph revision: 2

## Final contract

- Versions 1 through 9 are bound to full 40-character commits and canonical retained refs `runtime-schema-v1` through `runtime-schema-v9`.
- CI explicitly fetches those refs and the verifier rejects missing, moved or noncanonical refs.
- SQLite and PostgreSQL historical writers are executed from each retained commit; the current installed wheel upgrades to schema v9 and verifies event and audit-chain preservation.
- All preservation checks raise explicitly and remain active under `PYTHONOPTIMIZE=1`.

## Verification and review

- Clean local: 384 installed-wheel tests and 384 PostgreSQL tests PASS.
- Exact-head GitHub Actions run `30660276585`: 8/8 required jobs PASS on `47244792abe9f5740b1853e2f7973d2b8bc9e2c3`.
- Remote findings repaired: 2 (durable history refs; optimization-safe invariants).
- Review threads resolved: 2.
- External effects: 0.

## Publication

PR #39 was squash-merged as `fe75c5f563e97cda38f4fe0a7c05f9c455000474`.
The merged tree is `3cb641d61411c19fe305d9144d10edf768ac6931`.

This closure proves compatibility tooling and delivery gates. It does not execute or authorize a production database migration.
