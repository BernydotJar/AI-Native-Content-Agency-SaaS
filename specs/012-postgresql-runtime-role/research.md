# Research

The active PostgreSQL gate initializes an ephemeral cluster with the `initdb` bootstrap role and uses that same role in application URLs. The adapter creates schema during database construction. Therefore current green tests demonstrate functionality but not least privilege.

PostgreSQL ownership and privileges are distinct: granting SELECT/INSERT/UPDATE/DELETE and sequence USAGE is sufficient for current DML, while CREATE on schema, table ownership, TRUNCATE and role/database creation can remain denied. `CREATE TABLE IF NOT EXISTS` still belongs to schema-management authority and must not run in runtime validation mode.

The safe rollout is migration-before-runtime: migration job uses the schema owner, commits the supported schema, applies exact grants, exits, and runtime starts with `validate`. Missing or incompatible schema must prevent readiness rather than trigger opportunistic DDL.
