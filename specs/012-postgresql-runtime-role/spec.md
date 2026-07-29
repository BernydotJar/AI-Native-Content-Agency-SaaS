# 012 — PostgreSQL Migration/Runtime Authority Separation

Status: in_progress
Owner: Security Reviewer / Data Engineer

## Problem

The selected PostgreSQL adapter can initialize its schema using the same connection that serves application traffic. Existing integration tests use the bootstrap PostgreSQL superuser. This violates least privilege and leaves an application compromise with schema/database authority. A green PostgreSQL test does not demonstrate a production-like non-owner runtime role.

## Purpose

Separate schema bootstrap/migration authority from runtime authority, make runtime startup fail closed when schema is missing or incompatible, and demonstrate that a non-superuser/no-owner runtime role can perform every supported product operation while being unable to create, alter, drop or truncate schema objects.

## Actors and journeys

- **Migration operator/job:** uses a dedicated migration credential to initialize or upgrade the runtime schema before rollout.
- **Runtime pod/process:** connects with a non-owner role, validates schema version without DDL and serves application operations.
- **Security reviewer:** proves the runtime role is not superuser, owns no database/schema/table/sequence and lacks schema CREATE/DDL/TRUNCATE authority.
- **Release reviewer:** rejects a deployment whose runtime credential can bootstrap schema or whose schema mode is implicit.
- **Incident responder:** can identify whether a startup failure is connection, missing schema or incompatible schema without exposing credentials.

## Functional requirements

1. PostgreSQL startup accepts an explicit schema mode: `initialize` or `validate`.
2. `initialize` executes schema creation/upgrades and is intended only for migration authority.
3. `validate` performs no DDL and requires the exact supported schema version.
4. Missing metadata/table or incompatible schema in `validate` fails startup before serving traffic.
5. FastAPI/runtime reads `AGENCY_POSTGRES_SCHEMA_MODE` but accepts only `validate`; `initialize` is exclusive to the packaged operator command. Helm/Terraform enforce the same application boundary.
6. A packaged operator command initializes/validates schema using a database URL held in a named environment variable, never an argv/log value.
7. The PostgreSQL verifier creates distinct login roles for migration and runtime and a database/schema owned by migration authority.
8. Runtime gets only CONNECT, schema USAGE, table SELECT/INSERT/UPDATE/DELETE and required sequence privileges.
9. Runtime is not superuser, cannot create databases/roles, owns no database/schema/table/sequence, lacks schema CREATE and database TEMPORARY, and cannot assume the migration role.
10. Runtime cannot CREATE TABLE, ALTER TABLE, DROP TABLE or TRUNCATE a runtime table.
11. Runtime can execute runs, sessions, rate limits, audit, memories, Greenlight and recovery/readiness behavior across instances.
12. Migration replay and SQLite→PostgreSQL migration continue using migration authority.
13. Operator docs define rollout order, credential boundary, grants, rollback and human gates.

## Non-functional requirements

- no persistent/external database is touched by repository verification;
- schema-mode validation is deterministic and uses parameterized SQL where values are dynamic;
- role/identifier SQL in the verifier uses generated bounded identifiers and server-side quoting;
- credentials/URLs are not printed;
- runtime validation opens no long-lived transaction and makes no external call;
- existing SQLite behavior is unchanged;
- full backup/restore, tenant isolation and supply-chain gates remain valid.

## Invariants

- a runtime connection in `validate` mode issues zero CREATE/ALTER/DROP/TRUNCATE/GRANT/REVOKE statements;
- initialize holds its advisory lock through DDL, metadata insertion and validation so failure rolls back the full transaction;
- migration credentials are never required by the application runtime;
- runtime role cannot grant itself more authority;
- schema validation checks authoritative metadata, relation types and required columns, not only connection success;
- application connections fix `search_path` to `pg_catalog, public` and reject URL control of object resolution;
- readiness cannot report ready on missing/incompatible schema;
- production Helm never silently selects `initialize`;
- changing schema version requires an explicit migration increment and compatibility/rollback review.

## States and failures

- `schema_absent` → migration command required; runtime validate fails closed;
- `schema_current` → runtime validate succeeds;
- `schema_incompatible` → both runtime startup and readiness fail with safe operational error;
- `migration_failed` → transaction rolls back; runtime remains on previous compatible schema or unavailable;
- `insufficient_runtime_grant` → application operation fails in ephemeral verification and release is denied;
- `excess_runtime_grant` → negative privilege test fails and release is denied.

## Security/privacy/tenant boundaries

The migration role is highly privileged and must not be mounted into runtime pods. The runtime role remains a database-wide application credential; tenant isolation continues through composite keys/tenant-leading predicates and tests. PostgreSQL RLS is not added in this increment and remains defense-in-depth future work. Database URLs/passwords are restricted secrets and must remain server-side.

## Acceptance criteria

- the verifier first fails when the current bootstrap role is treated as runtime;
- explicit initialize creates schema and explicit validate never executes DDL;
- incompatible initialize preserves the prior metadata version and leaves no partial runtime relation;
- validate mode rejects absent, wrong-type, missing-column and incompatible schema in tests;
- runtime connections prove the fixed safe search path and reject a caller-supplied `search_path` option;
- runtime-role privilege inventory proves all forbidden capabilities false and no ownership;
- negative DDL, temporary-object, privilege-escalation and schema-metadata operations fail with permission errors and leave schema/data intact;
- all 78+ backend/PostgreSQL tests pass under the non-owner role;
- migration, replay, backup/restore and cross-instance denial evidence pass;
- Helm schema/render uses `validate` by default and rejects invalid schema mode;
- program/security docs and exact evidence are updated;
- zero open CRITICAL/HIGH code findings remain in this slice.

## Out of scope

- executing role creation/rotation on an external or persistent database;
- managed cloud IAM database authentication;
- PostgreSQL RLS policies;
- online multi-version migrations or zero-downtime schema expansion/contraction beyond current version;
- destructive downgrade;
- production apply/deployment/merge;
- durable API idempotency and external integrations.
