# INC-030 Requirements — Runtime Schema Compatibility Audit

## Goal

Prove that every supported historical runtime schema version can be upgraded by the current code without data loss or privilege broadening.

## Requirements

1. Maintain one canonical version history for PostgreSQL schema versions 1 through 9, bound to exact Git commits and introduced capabilities.
2. Verify the history is contiguous, each commit exists, and each historical source declares the recorded version.
3. For SQLite, execute each historical implementation against a fresh database, write tenant-scoped audit evidence, open it with the current runtime, and prove data preservation plus valid v9 audit chaining.
4. For PostgreSQL, execute each historical implementation against an isolated database, write tenant-scoped audit evidence, upgrade with the current migration authority, and prove schema v9, data preservation, and a valid chain; the same PostgreSQL gate separately revalidates the current least-privilege runtime role.
5. Reject unknown, future, missing, reordered, or duplicate versions.
6. Preserve the migration/runtime authority split; no production database, credential, cloud target, or persistent infrastructure may be used.
7. Run the matrix from the hash-locked installed wheel and exact full Git history in CI.
8. Exact-head CI passes with zero external effects.
