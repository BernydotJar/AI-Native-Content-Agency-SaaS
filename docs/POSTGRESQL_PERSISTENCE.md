# PostgreSQL durable runtime state

## Status and authority boundary

The runtime supports two persistence modes:

- **SQLite** remains the default for development, local smoke tests and explicitly single-replica operation.
- **PostgreSQL** provides shared runs, audit events, browser sessions, authentication-rate state and tenant-scoped memory for multiple application replicas.

PostgreSQL now has two explicit schema modes:

| Mode | Intended identity | Behavior |
|---|---|---|
| `initialize` | migration/operator role | serializes DDL, creates schema version `1` when absent and then validates it |
| `validate` | long-running application role | performs read-only relation/version checks and fails closed; it never creates or alters schema |

`validate` is the application default. The Helm chart and Terraform module reject any other mode for long-running pods. Schema initialization is an explicit operator action through `agency-runtime-schema`; it is not an application-startup side effect.

The repository does not provision a managed PostgreSQL service or production credentials. Role/database creation against a persistent environment remains an infrastructure and human-approval boundary.

## Runtime configuration

| Variable | Purpose | Default |
|---|---|---|
| `AGENCY_DATABASE_URL` | Runtime PostgreSQL URL. Empty selects SQLite. | empty |
| `AGENCY_DATABASE_POOL_MIN_SIZE` | Connections opened eagerly by each process. | `1` |
| `AGENCY_DATABASE_POOL_MAX_SIZE` | Maximum connections owned by each process. | `10` |
| `AGENCY_DATABASE_CONNECT_TIMEOUT_SECONDS` | Connect and pool-checkout timeout. | `15` |
| `AGENCY_POSTGRES_SCHEMA_MODE` | `validate` for application runtime; `initialize` only in the operator command. | `validate` |

The pool validates `1 <= min <= max <= 100` and a timeout from 1 through 300 seconds. Startup fails closed when PostgreSQL is unreachable, the URL contains unsupported options, a required relation is absent or `runtime_schema_meta` does not contain exactly schema version `1`.

URLs may use `postgresql://` or `postgres://`. Only the following query options are accepted:

- `application_name`;
- `sslmode=disable|prefer|require|verify-ca|verify-full`;
- `sslrootcert=/path/to/ca.pem` with `verify-ca` or `verify-full`.

Unknown or duplicate URL options are rejected. `search_path` cannot be supplied through the URL. Every application connection fixes its session path to `pg_catalog, public`; runtime DML resolves only trusted built-ins and the reviewed `public` schema. Runtime and operator commands do not log the URL or password.

## Required role model

Use separate credentials:

### Migration/operator role

The migration role:

- is not a superuser;
- does not have `CREATEDB`, `CREATEROLE`, `REPLICATION` or `BYPASSRLS`;
- owns the application database and runtime objects, or has an equivalent reviewed DDL grant;
- runs `agency-runtime-schema initialize`, offline SQLite migration and restore;
- is not injected into long-running application pods.

### Runtime role

The runtime role:

- is not a superuser;
- does not have `CREATEDB`, `CREATEROLE`, `REPLICATION` or `BYPASSRLS`;
- owns no database, schema, table, sequence, view or materialized view;
- has `CONNECT` without `TEMPORARY` on the database and `USAGE` without `CREATE` on schema `public`;
- cannot assume the migration role;
- has only the DML needed by the current application:

| Object | Runtime privileges |
|---|---|
| `runtime_schema_meta` | `SELECT` |
| `runtime_runs` | `SELECT, INSERT, UPDATE` |
| `audit_events` | `SELECT, INSERT` |
| `audit_events_sequence_seq` | `USAGE, SELECT` |
| `runtime_sessions` | `SELECT, INSERT, UPDATE` |
| `authentication_rate_limits` | `SELECT, INSERT, UPDATE, DELETE` |
| `memories` | `SELECT, INSERT` |

The runtime role must not have `CREATE` on schema `public`, DDL authority, `TRUNCATE`, or permission to update schema metadata.

The exact commands and rollout order are in [PostgreSQL Schema and Runtime Role Runbook](runbooks/postgresql-schema-rollout.md).

## Schema initialization and validation

The packaged command reads a URL from a named environment variable so the secret is not placed in argv:

```bash
export AGENCY_MIGRATION_DATABASE_URL='postgresql://migration-role@db.example/agency?sslmode=verify-full&sslrootcert=/etc/ssl/agency-ca.pem'
agency-runtime-schema initialize \
  --database-url-env AGENCY_MIGRATION_DATABASE_URL
```

After grants are applied, validate with the runtime identity:

```bash
export AGENCY_DATABASE_URL='postgresql://runtime-role@db.example/agency?sslmode=verify-full&sslrootcert=/etc/ssl/agency-ca.pem'
agency-runtime-schema validate \
  --database-url-env AGENCY_DATABASE_URL
```

Successful output is bounded JSON containing status, mode, runtime version and schema version. Known schema failures use safe operator messages; unexpected driver failures expose only the exception type.

Initialization holds the advisory lock, executes DDL, writes schema metadata and applies the complete validation contract in one transaction. An incompatible metadata version therefore rolls back every partial DDL change.

Validation checks these explicit `public` relations:

- `runtime_schema_meta`;
- `runtime_runs`;
- `audit_events`;
- `runtime_sessions`;
- `authentication_rate_limits`;
- `memories`;
- `audit_events_sequence_seq`.

Readiness revalidates the same schema contract. It does not run DDL.

## Driver and pooling

The runtime uses the hash-locked `pg8000` DB-API driver and a bounded repository-owned pool with:

- eager minimum connections;
- a hard maximum;
- checkout timeout;
- connection health check before reuse;
- commit on successful context exit and rollback on failure;
- discard of broken connections;
- deterministic close during shutdown.

Capacity planning must account for every replica: the theoretical application ceiling is `replicas * poolMaxSize`.

## Transaction and concurrency behavior

Each state transition uses a PostgreSQL transaction. Existing controls include:

- optimistic run versions;
- `SELECT ... FOR UPDATE` for contended mutations;
- one transaction for run mutation and its audit event;
- uniqueness constraints for tenant/run IDs, audit IDs, sessions and memories;
- atomic shared authentication-rate buckets;
- tenant IDs in all shared business-state keys and predicates.

A second replica cannot replace a committed Greenlight decision. Browser-session revocation and authentication throttling are shared after commit.

## Kubernetes and Helm

For a PostgreSQL-backed runtime:

```yaml
replicaCount: 2

runtime:
  storage:
    backend: postgresql
    postgresql:
      existingSecret: agency-postgresql-runtime
      databaseUrlKey: database-url
      poolMinSize: 1
      poolMaxSize: 10
      connectTimeoutSeconds: 15
      schemaMode: validate

podDisruptionBudget:
  enabled: true
  minAvailable: 1
```

The referenced Secret must contain the **runtime-role** URL. The chart:

- never templates the secret value;
- emits `AGENCY_POSTGRES_SCHEMA_MODE=validate`;
- rejects `initialize` for application pods;
- does not create a migration Job or inject migration credentials;
- does not mount the SQLite PVC in PostgreSQL mode;
- permits rolling multi-replica deployment only with PostgreSQL.

Run schema initialization and grants as a separately authorized operator step before deploying or upgrading application pods.

## Terraform boundary

Terraform receives Secret names/keys, not database URLs. For PostgreSQL mode:

```hcl
storage_backend                      = "postgresql"
replica_count                        = 2
postgresql_existing_secret           = "agency-postgresql-runtime"
postgresql_database_url_key          = "database-url"
postgresql_pool_min_size             = 1
postgresql_pool_max_size             = 10
postgresql_connect_timeout_seconds   = 15
postgresql_schema_mode               = "validate"
persistence_enabled                  = false
```

The module only configures the long-running release. It intentionally does not create roles, databases, migration secrets or run `initialize`.

## SQLite migration

`scripts/migrate-sqlite-to-postgresql.py` is an offline, one-time data migration. It now validates an already initialized target; it does not create schema.

Sequence:

1. stop application writes;
2. create and verify the SQLite backup;
3. create an empty PostgreSQL database owned by the migration role;
4. run `agency-runtime-schema initialize` with the migration URL;
5. review and apply the runtime grants;
6. run the dry-run migration report;
7. run `--apply` once;
8. validate schema and data with the runtime URL;
9. compare source and destination counts;
10. deploy pods using only the runtime Secret;
11. retain the source backup throughout the approved rollback window.

Dry-run:

```bash
export AGENCY_DATABASE_URL="$AGENCY_MIGRATION_DATABASE_URL"
python3 scripts/migrate-sqlite-to-postgresql.py \
  --sqlite /secure/backup/runtime.sqlite3
```

Apply only after the reviewed backup and cutover approval:

```bash
python3 scripts/migrate-sqlite-to-postgresql.py \
  --sqlite /secure/backup/runtime.sqlite3 \
  --apply
```

The copy runs in one PostgreSQL transaction. Replay against a non-empty target fails before row copying. There is no reverse synchronization utility.

Rollback means stopping the PostgreSQL-backed deployment and restoring the compatible pre-cutover SQLite application/data pair. Writes accepted after cutover require an explicit loss/reconciliation decision.

## Backup and restore

Backup and restore use an operator credential capable of reading or restoring the full schema; the long-running runtime credential is not sufficient and should not be elevated temporarily.

After restore into an empty operator-created database:

1. apply the reviewed runtime grants;
2. run `agency-runtime-schema validate` with the runtime URL;
3. perform isolated application reads;
4. compare counts and recovery-point evidence;
5. change traffic/Secrets only after explicit recovery authorization.

See [Runtime Backup and Restore Runbook](runbooks/runtime-backup-restore.md) and [PostgreSQL Schema and Runtime Role Runbook](runbooks/postgresql-schema-rollout.md).

## Repository verification contract

`./scripts/verify-postgresql-runtime.sh` is designed to prove, in an ephemeral cluster:

- distinct bootstrap, migration and runtime identities;
- runtime `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOREPLICATION`, `NOBYPASSRLS`;
- zero runtime ownership;
- validation failure for absent, wrong-type, missing-column and incompatible schema;
- fixed application `search_path=pg_catalog,public` with URL override rejected;
- runtime denial of `CREATE`, `ALTER`, `DROP`, `TRUNCATE` and metadata mutation;
- complete application behavior under the runtime role;
- SQLite migration and PostgreSQL restore under migration authority;
- restored-state readability under runtime authority.

This describes the gate contract. A result is evidence only after the command is executed against the exact commit and recorded. It is not a claim about a persistent cloud database.

## Production controls still external or incomplete

A production operator still must provide and prove:

- PostgreSQL high availability and failover;
- TLS verification and storage encryption;
- managed secret creation and rotation;
- scheduled encrypted off-host/immutable backups;
- restore exercises in an authorized environment;
- database telemetry and connection-budget alerts;
- capacity, load and soak evidence;
- schema-upgrade reviews beyond version `1`;
- approved maintenance and rollback windows;
- accountable infrastructure/security review.
