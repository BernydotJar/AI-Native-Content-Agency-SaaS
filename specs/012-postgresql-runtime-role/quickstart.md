# Quickstart

```bash
export AGENCY_MIGRATION_DATABASE_URL='postgresql://...'
agency-runtime-schema initialize --database-url-env AGENCY_MIGRATION_DATABASE_URL

export AGENCY_DATABASE_URL='postgresql://...'
export AGENCY_POSTGRES_SCHEMA_MODE=validate
agency-runtime-api
```

Never mount `AGENCY_MIGRATION_DATABASE_URL` into the long-running runtime workload. Persistent role creation, grants or schema migration require explicit human/database authorization.
