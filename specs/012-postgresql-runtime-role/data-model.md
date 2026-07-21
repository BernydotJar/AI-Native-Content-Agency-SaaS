# Schema Authority Model

## Modes

- `initialize`: migration/bootstrap authority; creates/upgrades supported schema in a transaction and then validates.
- `validate`: runtime authority; reads metadata/required-object catalog only and performs no DDL.

## Roles in the ephemeral proof

- cluster bootstrap role: creates disposable roles/database only; never used by application tests;
- migration role: LOGIN, owns disposable database/public schema/runtime objects, no superuser/createdb/createrole;
- runtime role: LOGIN, no superuser/createdb/createrole/replication/bypassrls, owns nothing, has CONNECT without TEMPORARY, schema USAGE without CREATE, exact table DML and exact sequence usage.

## Required schema evidence

- `runtime_schema_meta.schema_version = 1`;
- every required runtime table exists in `public` with the correct relation type and required columns;
- required sequence access exists where schema uses identity/serial;
- each application connection fixes `search_path` to `pg_catalog, public`;
- no runtime-owned object exists.
