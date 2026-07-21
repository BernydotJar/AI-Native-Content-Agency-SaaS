# Runtime Backup and Restore Runbook

Status: executable repository runbook
Version: `agency-runtime-backup.v1`
Last verified locally: 2026-07-21
Production restore authority: human-gated

## Evidence boundary

This runbook covers the application state stored by the selected runtime in SQLite or PostgreSQL. The repository gate demonstrates that representative runs, audit events, browser sessions, authentication-rate buckets and tenant memories survive backup and restore and remain readable by the application.

It does **not** demonstrate scheduled backups, encrypted off-host retention, point-in-time recovery, managed-database failover, cross-region disaster recovery, production RPO/RTO, or a restore inside an authorized staging/production environment. Those remain deployment controls.

## Backup artifact contract

Every successful backup produces two files in the same directory:

- a backend-specific data file (`.sqlite3` or PostgreSQL custom-format `.dump`);
- a `*.manifest.json` file using schema `agency-runtime-backup.v1`.

The manifest records:

- backend;
- UTC creation time;
- data-file basename and size;
- SHA-256 of the exact data file;
- backend validation marker;
- an opaque SHA-256 source identifier;
- tool name and semantic version.

The manifest intentionally contains no database URL, password, campaign content, tenant ID or filesystem source path. Manifests larger than 64 KiB, unknown fields and traversal basenames are rejected. SHA-256 detects accidental or unauthorized byte changes only when the manifest itself is trusted; it is not a digital signature. Store the pair under approved encryption, access control, retention and immutable/audited storage policy.

All generated files use mode `0600`. Creation and SQLite replacement use same-directory atomic rename plus file/directory `fsync`.

## SQLite backup

SQLite backup uses `sqlite3.Connection.backup`, not a copy of the live main file. This captures a consistent committed view even when the source uses WAL.

```bash
python3 scripts/manage-runtime-backup.py sqlite-backup \
  --database /var/lib/agency/runtime.sqlite3 \
  --output-dir /secure/agency-backups
```

The command:

1. requires an existing regular source file and rejects a symlink;
2. opens the source read-only;
3. writes a private temporary database in the destination directory;
4. runs `PRAGMA integrity_check`;
5. flushes and atomically installs the data file;
6. writes and flushes the strict manifest.

A successful command emits one JSON object with `status=created`, `backend=sqlite` and the manifest path.

## SQLite restore drill

Restore into a new path first:

```bash
python3 scripts/manage-runtime-backup.py sqlite-restore \
  --manifest /secure/agency-backups/agency-sqlite-....manifest.json \
  --target /var/lib/agency-restore-test/runtime.sqlite3
```

Before mutation, the tool verifies strict manifest fields, backend, size, checksum and SQLite integrity. It then creates a private temporary database, verifies it and atomically moves it into place.

The target must not exist by default. Replacing a persistent target requires all of the following:

1. explicit incident/change approval;
2. application writes stopped;
3. verified recovery point selected;
4. current target preserved according to the incident plan;
5. no `-wal` or `-shm` sidecar present;
6. explicit `--replace`:

```bash
python3 scripts/manage-runtime-backup.py sqlite-restore \
  --manifest /secure/agency-backups/agency-sqlite-....manifest.json \
  --target /var/lib/agency/runtime.sqlite3 \
  --replace
```

`--replace` is destructive-data authority, not a routine deployment flag. The tool refuses an active sidecar even with this flag; stop the process cleanly first.

After restore, verify:

```bash
python3 agency.py demo --db /var/lib/agency/runtime.sqlite3 --json
```

For a real recovery, use read-only application/API inspection appropriate to the selected tenant and confirm run, audit and memory counts against the incident recovery point before reopening writes.

## PostgreSQL backup

Prerequisites:

- `pg_dump`, `pg_restore` and `psql` from a supported PostgreSQL client distribution;
- a connection URL in an environment variable;
- a runtime schema version accepted by the application (`1` for version `0.7.0`);
- least-privilege access that can read the complete runtime database.

```bash
export AGENCY_DATABASE_URL='postgresql://agency@db.example/agency?sslmode=verify-full&sslrootcert=/etc/ssl/agency-ca.pem'
python3 scripts/manage-runtime-backup.py postgres-backup \
  --database-url-env AGENCY_DATABASE_URL \
  --output-dir /secure/agency-backups
```

The URL is parsed into a controlled libpq environment; it is never placed in a process argument or output. Existing `PG*` variables are discarded, `PGPASSFILE` is set to the null device to prevent ambient `.pgpass` authority, and the tool sets the exact host, port, user, database, TLS mode, root certificate, application name and connection timeout. Only `application_name`, `sslmode` and `sslrootcert` URL options are accepted. PostgreSQL subprocesses default to a 3,600-second timeout; `AGENCY_BACKUP_COMMAND_TIMEOUT_SECONDS` may set a reviewed value from 1 to 86,400 seconds.

The command verifies runtime schema version `1`, creates a custom-format dump with owner/ACL exclusion and validates the archive with `pg_restore --list` before writing the manifest.

## PostgreSQL restore drill

The operator creates the restore database and grants the intended role outside this tool. The target must contain zero non-system tables.

```bash
export AGENCY_RESTORE_DATABASE_URL='postgresql://agency_restore@db.example/agency_restore?sslmode=verify-full&sslrootcert=/etc/ssl/agency-ca.pem'
python3 scripts/manage-runtime-backup.py postgres-restore \
  --manifest /secure/agency-backups/agency-postgresql-....manifest.json \
  --database-url-env AGENCY_RESTORE_DATABASE_URL
```

Restore uses `pg_restore --single-transaction --exit-on-error --no-owner --no-privileges`. It does not create/drop a database and does not clean a non-empty target. After restore it verifies runtime schema version and the presence of runtime tables.

Then point an isolated application instance at the restored database and verify:

- `/readyz` reports PostgreSQL shared state;
- representative tenant runs are readable;
- audit sequence/counts match the recovery point;
- sessions/rate-limit rows exist as expected, while expired sessions remain unusable;
- representative tenant memories are searchable;
- no production traffic or effectful adapter is enabled.

The repository executes this same-scope drill with:

```bash
./scripts/verify-postgresql-runtime.sh
```

That gate creates ephemeral source/restore databases, proves a non-empty target is rejected, compares every representative table count and authentication-failure total, and reads restored state through `PostgresRuntimeDatabase`. It also runs the SQLite drill against a representative runtime fixture.

## Recovery and rollback decision record

Before any persistent restore, record:

```yaml
incident_or_change_id:
approved_by:
backend:
source_manifest:
manifest_sha256:
recovery_point_utc:
expected_data_loss_window:
target_environment:
application_commit:
schema_version:
writes_stopped_at:
pre_restore_backup:
verification_owner:
rollback_condition:
```

Application rollback should prefer an immutable prior image digest that remains compatible with schema version `1`. Data rollback is separate and must never be inferred from an application rollback.

For SQLite-to-PostgreSQL cutover, rollback means stopping the PostgreSQL-backed deployment and restoring the verified pre-cutover SQLite application/data pair. There is no reverse synchronization utility; writes accepted after cutover would otherwise be lost.

For PostgreSQL incidents, forward repair or restore into an isolated new database is preferred. Replacing the authoritative production database, changing DNS/Secrets, terminating sessions, or discarding newer data requires explicit human authorization.

## Retention, encryption and deletion

The repository tool does not schedule, encrypt, upload or delete backups. A production environment must define and independently review:

- encryption in transit and at rest, including key ownership and rotation;
- separate backup credentials and least privilege;
- off-host/immutable copies and geographic requirements;
- RPO/RTO and backup frequency derived from measured workload;
- retention periods, legal hold and deletion approval;
- restore-test cadence and evidence retention;
- monitoring for stale/missing backups and failed drills;
- customer/tenant data handling and jurisdiction.

Do not automate destructive deletion until the retention/privacy policy and accountable reviewer are recorded.

## Failure handling

Treat any of these as a failed backup/restore gate:

- missing or malformed manifest;
- unknown manifest field;
- basename traversal;
- size/checksum mismatch;
- SQLite integrity failure;
- unsupported PostgreSQL URL/TLS option;
- missing PostgreSQL client tool;
- source schema mismatch;
- non-empty PostgreSQL target;
- restore command failure;
- post-restore schema/count/application-read failure.

Do not alter a manifest, disable checksum/integrity checks or add `--clean` to make a failed restore pass. Preserve the command result and sanitized logs, classify the blocker and select another verified recovery point or repair the cause.
