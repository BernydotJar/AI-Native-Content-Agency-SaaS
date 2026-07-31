# INC-030 Design — Runtime Schema Compatibility Audit

## Canonical history

`contracts/runtime-schema-history.json` records versions 1–9, their exact source commits, and the feature introduced at each boundary. This is a compatibility support declaration, not generated release notes.

## Historical execution

The verifier uses `git archive` to extract only `backend/` from each recorded commit into a temporary directory. It executes that historical package with the current hash-locked test interpreter. This avoids editable-import contamination and proves the repository can reproduce the declared source.

SQLite creates one historical audit event, then the current installed runtime opens the same file, performs its idempotent migrations, verifies the event, and validates the per-tenant hash chain.

PostgreSQL uses one isolated ephemeral database per historical version. Historical `PostgresRuntimeDatabase(..., schema_mode="initialize")` creates the old schema and writes one event. Current v9 migration authority initializes/upgrades it; current runtime validation and audit-chain verification must pass. Databases and extracted sources are destroyed after the gate.

## CI boundary

The `verify` and `postgresql-shared-state` jobs fetch full history because the compatibility matrix explicitly requires recorded historical commits. Exact source checkout remains asserted after fetch. No network call occurs after checkout, and no external runtime is contacted.
