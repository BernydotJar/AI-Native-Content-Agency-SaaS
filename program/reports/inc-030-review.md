# INC-030 Independent Review — Runtime Schema Compatibility

Date: 2026-07-31
Graph revision: 0
State at review: `running`

## Producer result

- Added canonical `contracts/runtime-schema-history.json` for versions 1 through 9.
- Every version is bound to a real historical Git commit whose source declares that exact `POSTGRES_SCHEMA_VERSION`.
- Historical source is extracted with `git archive`; schemas are not reimplemented or synthesized in the verifier.
- SQLite and PostgreSQL each write a real historical audit event, then the installed current wheel upgrades the store to schema v9 and verifies event and audit-chain preservation.
- Unknown, gapped, duplicate, future and wrong-source manifests fail closed.

## Fresh verification on merged API-contract base

- Base: `12332e4653f9db2949a5936dd1765cbd4436ff4c`.
- SQLite historical upgrades v1–v9: 9/9 PASS.
- PostgreSQL historical upgrades v1–v9: 9/9 PASS.
- Installed-wheel suite: 383 tests PASS.
- PostgreSQL 15.18 suite: 383/383 PASS.
- Schema v9 initialize/validate, migration, replay guard, least privilege and backup/restore: PASS.
- API contract revision 1 remains PASS.
- Frontend: 58 tests, lint and production build PASS.
- Program, Graph Harness, compliance, operability and actionlint: PASS.

## Critic and security review

The verifier requires full Git history, checks the source declaration at each recorded commit, uses isolated temporary databases and deletes every PostgreSQL database after its case. Administrative authority exists only inside the ephemeral verification harness. It does not connect to a production database, alter persistent infrastructure, rewrite history or execute a downgrade.

No provider, model, publication, secret, deployment or paid effect is enabled by this increment.

## Open gates

Clean-tree evidence, exact-head GitHub Actions, remote review and squash merge remain pending. A real production migration remains a separate human gate even after this node closes.

## Revision 1 — retained history refs

PR review identified that early schema commits were reachable only through incidental feature branches. The repair creates canonical non-release tags `runtime-schema-v1` through `runtime-schema-v9`, records full 40-character SHAs, and requires every tag to resolve exactly to its declared commit. CI explicitly fetches only those canonical history refs before running the matrix. Missing, noncanonical or moved refs fail closed.

## Revision 2 — optimization-safe invariants

Re-review identified that Python `assert` statements inside the SQLite/PostgreSQL verification snippets could disappear under `PYTHONOPTIMIZE`. All cardinality, action, resource, payload and checkpoint invariants now use explicit checks that raise `RuntimeError`. A regression runs the historical matrix with `PYTHONOPTIMIZE=1`; the full installed-wheel suite now contains 384 tests.
