# PostgreSQL Schema and Runtime Role Runbook

Status: implementation contract; exact-commit execution evidence pending for `INC-012`
Application schema: `1`
Persistent-environment role/database mutation: human-gated

## Purpose

This runbook separates schema authority from application runtime authority. It prevents long-running API replicas from owning database objects or creating/upgrading schema during startup.

The roles are:

- **platform/bootstrap administrator**: creates login roles and the database, then leaves the application path;
- **migration role**: owns the application database and schema objects, runs explicit schema initialization/migration/restore;
- **runtime role**: owns no objects, runs only application DML and read-only schema validation.

Do not place the platform or migration URL in application Deployment Secrets.

## Preconditions and human gates

Before touching a persistent environment, record:

```yaml
change_id:
environment:
database_host:
database_name:
current_application_commit:
target_application_commit:
current_schema_version:
target_schema_version:
backup_manifest:
rollback_window:
migration_operator:
security_reviewer:
release_reviewer:
write_freeze_approved_by:
secret_cutover_approved_by:
```

Explicit approval is required for:

- creating or altering persistent database roles;
- creating a persistent database;
- executing schema DDL;
- changing an application Secret or traffic;
- destructive restore, data deletion or accepted data loss;
- production rollout.

The repository agent may validate this sequence only against disposable/local databases unless separate environment authorization is provided.

## Secret and URL handling

Keep URLs in named environment variables. Never put passwords in command arguments, files committed to Git, shell history examples or logs.

Recommended variable names:

```bash
AGENCY_MIGRATION_DATABASE_URL
AGENCY_DATABASE_URL
AGENCY_RESTORE_DATABASE_URL
```

`AGENCY_DATABASE_URL` is always the non-owner runtime credential in a deployed application.

## Role creation template

Run this through an approved secret-aware database administration process. Replace identifiers using safe PostgreSQL identifier handling; do not interpolate untrusted text into SQL.

```sql
CREATE ROLE agency_migrator
  LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

CREATE ROLE agency_runtime
  LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

CREATE DATABASE agency OWNER agency_migrator;
REVOKE CONNECT, TEMPORARY ON DATABASE agency FROM PUBLIC;
GRANT CONNECT ON DATABASE agency TO agency_runtime;
```

After connecting to the application database as the migration role:

```sql
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO agency_runtime;
```

Credential creation, password policy, rotation and storage are provider-specific and outside the repository.

## Initial schema rollout

### 1. Verify an empty/new target

Do not initialize over an unknown database. Confirm the database name, owner, environment and approved recovery point. Preserve any existing target instead of cleaning it in place.

### 2. Initialize with migration authority

```bash
agency-runtime-schema initialize \
  --database-url-env AGENCY_MIGRATION_DATABASE_URL
```

Expected bounded output:

```json
{"mode":"initialize","runtime_version":"0.7.0","schema_version":"1","status":"pass"}
```

The command serializes DDL with an advisory transaction lock and validates before commit. An incompatible metadata version must preserve its original value and leave no partially created runtime table.

### 3. Apply runtime grants

Run as the migration role:

```sql
REVOKE ALL ON TABLE public.runtime_schema_meta FROM PUBLIC;
REVOKE ALL ON TABLE public.runtime_runs FROM PUBLIC;
REVOKE ALL ON TABLE public.audit_events FROM PUBLIC;
REVOKE ALL ON TABLE public.runtime_sessions FROM PUBLIC;
REVOKE ALL ON TABLE public.authentication_rate_limits FROM PUBLIC;
REVOKE ALL ON TABLE public.memories FROM PUBLIC;
REVOKE ALL ON SEQUENCE public.audit_events_sequence_seq FROM PUBLIC;

GRANT SELECT ON TABLE public.runtime_schema_meta TO agency_runtime;
GRANT SELECT, INSERT, UPDATE ON TABLE public.runtime_runs TO agency_runtime;
GRANT SELECT, INSERT ON TABLE public.audit_events TO agency_runtime;
GRANT SELECT, INSERT, UPDATE ON TABLE public.runtime_sessions TO agency_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE
  ON TABLE public.authentication_rate_limits TO agency_runtime;
GRANT SELECT, INSERT ON TABLE public.memories TO agency_runtime;
GRANT USAGE, SELECT ON SEQUENCE public.audit_events_sequence_seq TO agency_runtime;

ALTER DEFAULT PRIVILEGES FOR ROLE agency_migrator IN SCHEMA public
  REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE agency_migrator IN SCHEMA public
  REVOKE ALL ON SEQUENCES FROM PUBLIC;
```

Do not grant blanket ownership, `ALL PRIVILEGES`, schema `CREATE`, table `TRUNCATE` or schema-metadata mutation to the runtime role. The application fixes each connection to `search_path=pg_catalog,public`; do not add a role-named schema or allow URL/session overrides that change object resolution.

Every future schema change must review whether new objects require a new exact runtime grant. Default privileges deliberately do not grant future DML automatically.

### 4. Validate with runtime authority

```bash
agency-runtime-schema validate \
  --database-url-env AGENCY_DATABASE_URL
```

Failure for an absent relation, sequence or unsupported version is a release blocker. Do not switch the application to `initialize` to bypass it.

### 5. Verify role properties

Through an approved administration connection:

```sql
SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls
FROM pg_catalog.pg_roles
WHERE rolname IN ('agency_migrator', 'agency_runtime');
```

The runtime row must be false for every capability flag.

Verify ownership:

```sql
SELECT n.nspname, c.relname, c.relkind, r.rolname AS owner
FROM pg_catalog.pg_class c
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
JOIN pg_catalog.pg_roles r ON r.oid = c.relowner
WHERE r.rolname = 'agency_runtime';
```

Expected application-object rows: zero.

### 6. Deploy application pods

The chart must render:

```yaml
- name: AGENCY_POSTGRES_SCHEMA_MODE
  value: validate
```

The referenced PostgreSQL Secret contains the runtime URL only. The chart rejects `schemaMode: initialize`.

## SQLite-to-PostgreSQL cutover

1. approve and enforce a write freeze;
2. create and verify the SQLite backup;
3. initialize the empty PostgreSQL schema as above;
4. apply exact runtime grants;
5. run migration dry-run using the migration URL;
6. review source/target report;
7. run `--apply` once using the migration URL;
8. reapply/review grants if the migration introduced objects;
9. validate through the runtime URL;
10. compare counts and representative application reads;
11. deploy runtime pods with `validate` and runtime Secret;
12. reopen writes only after the release reviewer accepts evidence.

The migration utility does not initialize schema and does not perform reverse synchronization.

## Restore sequence

Restore uses a new, empty database owned by the migration role:

1. create the isolated restore database;
2. restore with `AGENCY_RESTORE_DATABASE_URL` using migration/restore authority;
3. apply exact runtime grants;
4. validate schema with the runtime URL;
5. perform isolated application reads and count comparison;
6. record the selected recovery point and any expected data-loss window;
7. switch an application Secret or traffic only after explicit recovery approval.

Never elevate the runtime credential temporarily for restore.

## Upgrade sequence for a future schema version

Schema version `1` has no online upgrade mechanism. A future version requires:

- a new bounded specification and ADR;
- forward and rollback compatibility analysis;
- representative data migration tests;
- runtime-grant diff;
- backup and isolated restore proof;
- maintenance/availability plan;
- migration command executed before application rollout;
- application pods remaining in `validate` mode.

Do not add DDL back to normal startup as an upgrade shortcut.

## Rollback

Application rollback and data rollback are different decisions.

### Before traffic or write reopening

Roll back by stopping the new application, restoring the previous immutable image/configuration and retaining the new database for diagnosis. If the previous application is compatible with schema version `1`, no data rollback is implied.

### After writes on the new target

Do not silently revert to an older SQLite/database snapshot. Record:

- writes accepted after cutover;
- expected loss/reconciliation impact;
- recovery-point choice;
- approver;
- tenant/customer communication requirement.

A destructive restore or loss acceptance is human-gated.

## Failure handling

Stop the rollout when:

- runtime validation reports a missing relation/sequence;
- schema version is absent or unsupported;
- runtime owns any application object;
- runtime can execute DDL, `TRUNCATE` or schema metadata update;
- migration credentials appear in the Deployment;
- backup/restore evidence is missing;
- runtime application reads fail;
- grants differ from the reviewed matrix.

Do not resolve these failures by granting ownership, using a superuser URL in the application, setting `initialize` in Helm, weakening readiness or editing schema metadata manually without a reviewed migration.

## Repository evidence command

The intended disposable proof is:

```bash
./scripts/verify-postgresql-runtime.sh
```

It is expected to exercise distinct roles, absent/incompatible/incomplete schema guards, DDL denial, complete backend behavior, migration, backup and restore. This runbook does not claim that result until it is executed against the exact commit and recorded in program evidence.
