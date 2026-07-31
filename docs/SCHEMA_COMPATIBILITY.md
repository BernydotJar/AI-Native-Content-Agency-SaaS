# Runtime Schema Compatibility

`contracts/runtime-schema-history.json` declares the supported PostgreSQL schema lineage from v1 through v9. Each version is bound to an exact Git commit and the capability introduced at that boundary.

## SQLite matrix

```bash
SCHEMA_COMPATIBILITY_PYTHON_BIN=.venv/bin/python npm run validate:schema-compatibility
```

For every declared version, the verifier extracts the exact historical `backend/`, creates a database with that implementation, writes a tenant-scoped audit event, and opens the file with the current runtime. The event and current audit chain must verify.

## PostgreSQL matrix

The PostgreSQL production-readiness harness invokes the same verifier with its ephemeral administrative URL. Each historical implementation creates an isolated database and event; the installed current wheel upgrades it to v9 and verifies the preserved event and chain. Every database is dropped after its case.

The enclosing harness separately proves current migration/runtime authority separation and the non-owner runtime grant set. The historical matrix does not grant broader production privileges.

## History requirement

The verifier fails if a declared commit is unavailable. CI therefore uses `fetch-depth: 0` only for the `verify` and `postgresql-shared-state` jobs that execute historical evidence. Exact pull-request head checkout is still asserted before any gate.

No production database, cloud target, credential, provider, or external effect is used.
