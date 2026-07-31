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
