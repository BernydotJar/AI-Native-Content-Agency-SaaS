# `postgresql-schema-mode.v1`

Allowed values: `initialize`, `validate`.

`initialize` may execute the reviewed schema DDL and must end by applying the same validation contract.

`validate` is read-only with respect to schema/data. It must fail when metadata is absent, schema version differs or a required object is missing. It must not fall back to initialize.

Environment:

- runtime: `AGENCY_POSTGRES_SCHEMA_MODE=validate`; application construction rejects `initialize` before connecting;
- migration command: explicit `initialize` plus a named URL environment variable;
- invalid/missing production configuration fails closed according to documented defaults.
