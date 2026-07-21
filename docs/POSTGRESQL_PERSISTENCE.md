# PostgreSQL durable runtime state

## Status

The runtime supports two persistence modes:

- **SQLite** remains the default for single-process development, local smoke tests and one-replica deployments.
- **PostgreSQL** is the shared-state backend for multiple application replicas. It is selected only when `AGENCY_DATABASE_URL` is non-empty.

The PostgreSQL path stores execution runs, the append-only audit ledger, browser sessions, authentication rate-limit buckets and tenant-scoped memories in one database. It does not provision PostgreSQL, manage backups or implement database failover.

## Runtime configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `AGENCY_DATABASE_URL` | PostgreSQL URL. An empty value selects SQLite. | empty |
| `AGENCY_POSTGRES_POOL_MIN_SIZE` | Connections opened eagerly by each application process. | `1` |
| `AGENCY_POSTGRES_POOL_MAX_SIZE` | Maximum connections owned by each application process. | `5` |
| `AGENCY_POSTGRES_CONNECT_TIMEOUT_SECONDS` | Connection and pool-checkout timeout. | `15` |

The pool validates `1 <= min <= max <= 100` and a timeout from 1 through 300 seconds. Startup fails closed if PostgreSQL is unreachable, the URL contains unsupported options or the runtime schema version is not exactly the supported version.

Connection URLs may use `postgresql://` or `postgres://`. The driver accepts only these query options:

- `application_name`
- `sslmode=disable|prefer|require|verify-ca|verify-full`
- `sslrootcert=/path/to/ca.pem` with `verify-ca` or `verify-full`

Unknown or duplicate URL options are rejected. Secrets are never written to logs by the runtime. Production URLs should use TLS verification and a least-privilege database role.

## Driver and pooling

The runtime uses `pg8000` through Python DB-API. `pg8000` and its transitive packages are pinned in the hash-locked Python dependency graph. The application owns a small bounded pool per process with:

- eager creation of the minimum connection count;
- a hard maximum connection count;
- a checkout timeout;
- health checks before reuse;
- commit on successful context exit and rollback on failure;
- discard of broken connections;
- deterministic close during application shutdown.

Capacity planning must account for every replica: the theoretical application connection ceiling is `replicas * poolMaxSize`.

## Schema and consistency

Schema initialization is serialized with a PostgreSQL advisory transaction lock. The runtime records schema version `1` in `runtime_schema_meta`. It inserts the version only when absent and refuses to overwrite an unknown version, which prevents a newer schema from being silently downgraded.

The backend uses PostgreSQL transactions for each state transition. Important concurrency controls include:

- optimistic run versions for updates;
- `SELECT ... FOR UPDATE` before Greenlight decisions and other contended mutations;
- a single transaction for a run mutation and its audit event;
- uniqueness constraints for tenant/run IDs, audit event IDs, sessions and memories;
- row-level locking for shared authentication-rate buckets;
- tenant IDs in every shared business-state primary key or lookup predicate.

A second replica cannot overwrite a committed Greenlight decision. Browser-session revocation and authentication throttling are visible across replicas immediately after commit.

## Kubernetes and Helm

The chart selects the backend with `runtime.storage.backend`:

```yaml
replicaCount: 2

runtime:
  storage:
    backend: postgresql
    postgresql:
      existingSecret: agency-postgresql
      secretKey: database-url
      poolMinSize: 1
      poolMaxSize: 5
      connectTimeoutSeconds: 15

podDisruptionBudget:
  enabled: true
  minAvailable: 1
```

The referenced Secret must already exist and contain the database URL. The chart does not template the Secret value. PostgreSQL mode does not create or mount the SQLite PVC. SQLite mode rejects more than one replica, while a PodDisruptionBudget requires PostgreSQL and at least two replicas.

The deployment uses a rolling update only for PostgreSQL. SQLite keeps a one-replica `Recreate` strategy to avoid concurrent writers to the same local database.

## Terraform boundary

Terraform accepts the name and key of an existing Kubernetes Secret. It does not accept the database URL itself, so that value is not incorporated into Terraform configuration or state.

For PostgreSQL mode, set:

```hcl
runtime_storage_backend              = "postgresql"
replica_count                        = 2
postgresql_existing_secret           = "agency-postgresql"
postgresql_secret_key                = "database-url"
postgresql_pool_min_size             = 1
postgresql_pool_max_size             = 5
postgresql_connect_timeout_seconds   = 15
pod_disruption_budget_enabled        = true
pod_disruption_budget_min_available  = 1
```

The module validates backend selection, replica count, pool bounds, timeout, Secret name/key and PodDisruptionBudget bounds before planning.

## SQLite migration

`scripts/migrate-sqlite-to-postgresql.py` is a one-time, offline migration utility. It migrates:

- `runtime_runs`;
- `audit_events`;
- `runtime_sessions`;
- grouped authentication failures into `authentication_rate_limits`;
- `memories`.

The source database is opened read-only. The destination schema is initialized through the normal runtime schema path and must otherwise be empty. The command defaults to dry-run:

```bash
export AGENCY_DATABASE_URL='postgresql://agency@db.example/agency?sslmode=verify-full'
python scripts/migrate-sqlite-to-postgresql.py --sqlite /secure/backup/runtime.sqlite3
```

Apply only after reviewing the dry-run report and taking verified backups:

```bash
python scripts/migrate-sqlite-to-postgresql.py \
  --sqlite /secure/backup/runtime.sqlite3 \
  --apply
```

The migration runs in one PostgreSQL transaction. A replay against a non-empty target fails before copying rows. This is intentional fail-closed behavior, not an online or repeatable synchronization mechanism.

Recommended cutover sequence:

1. stop application writes;
2. create and verify a SQLite backup;
3. create an empty PostgreSQL database with the intended role and TLS policy;
4. run the dry-run;
5. run `--apply` once;
6. compare source and destination counts;
7. deploy with `AGENCY_DATABASE_URL` from the approved Secret;
8. retain the source backup through the rollback window.

Rollback means stopping the PostgreSQL-backed deployment and restoring the pre-cutover SQLite deployment and backup. There is no reverse migration utility.

## Local verification

The repository gate builds and installs the backend wheel from hash-locked dependencies, starts PostgreSQL as a non-root local process, executes the complete backend test suite against shared state, performs dry-run and applied migration checks, validates source-to-target counts and confirms replay protection:

```bash
./scripts/verify-postgresql-runtime.sh
```

The gate is daemonless with respect to containers and removes its virtual environment, databases, PostgreSQL process and temporary directory on exit.

## Operational requirements not implemented here

A production operator must provide:

- PostgreSQL high availability and tested restore procedures;
- encryption in transit and at rest;
- credential rotation and least-privilege roles;
- database monitoring, capacity limits and connection-budget alerts;
- schema upgrade planning beyond version `1`;
- a maintenance window for the SQLite cutover;
- load and soak testing at the intended replica and concurrency levels.
