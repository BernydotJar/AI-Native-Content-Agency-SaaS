# INC-030 Independent Review — Runtime Schema Compatibility

Date: 2026-07-30
Graph revision: 0
State at review: `running`

## Producer result

- Added canonical schema history `contracts/runtime-schema-history.json` for versions 1 through 9.
- Every version is bound to a real historical Git commit whose source declares the recorded `POSTGRES_SCHEMA_VERSION`.
- Added one verifier that extracts historical `backend/` source with `git archive` and executes that source in isolated temporary environments.
- SQLite cases create one historical tenant audit event, then the current runtime upgrades the database and verifies event preservation plus the current audit chain.
- PostgreSQL cases create one isolated database per version, write the same historical event, upgrade with current migration authority, verify v9 data/chain, and drop the database.
- The enclosing PostgreSQL harness separately revalidates current migration/runtime role separation and least-privilege grants.

## Matrix evidence

- Historical versions: 9/9 contiguous.
- SQLite upgrades: v1, v2, v3, v4, v5, v6, v7, v8, v9 PASS.
- PostgreSQL upgrades: v1, v2, v3, v4, v5, v6, v7, v8, v9 PASS.
- Installed current wheel is used for upgrade and verification gates.
- Unknown/gapped, duplicate, future, and wrong-source manifests fail closed.
- PostgreSQL full suite: 379/379 PASS; schema v9, SQLite migration, replay guard, least privilege, backup and restore PASS.
- Locked-wheel suite: 379 PASS with only the existing 27 PostgreSQL-only skips outside the PostgreSQL job.

## Critic and security review

PASS locally. The verifier does not synthesize historical schemas, rewrite Git history, connect to production, or retain databases. Full history is fetched only by the CI jobs that execute the matrix, and exact PR-head checkout remains asserted. Administrative PostgreSQL authority is limited to the ephemeral harness; current runtime least privilege remains independently verified.

## Open gates

A clean implementation commit, clean-tree supply-chain provenance, exact-head CI, retained artifact inspection, merge authority, and close-gate remain pending.
