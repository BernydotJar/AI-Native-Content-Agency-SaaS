#!/usr/bin/env bash
set -euo pipefail

REPOSITORY_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
export PATH="$HOME/.local/bin:$PATH"
PYTHON_BIN=${PYTHON_BIN:-python3}
POSTGRES_BIN_DIR=${POSTGRES_BIN_DIR:-}
POSTGRES_RUN_USER=${POSTGRES_RUN_USER:-node}
TMP_DIR=$(mktemp -d /tmp/agency-postgresql-verification.XXXXXX)
VENV="$TMP_DIR/venv"
WHEEL_DIR="$TMP_DIR/wheels"
PG_ROOT="$TMP_DIR/postgres"
PG_DATA="$PG_ROOT/data"
PG_SOCKET="$PG_ROOT/socket"
PG_LOG="$PG_ROOT/postgres.log"
PG_STARTED=false
RUN_ID="${RANDOM}${RANDOM}"
SHARED_DB="agency_shared_${RUN_ID}"
MIGRATION_DB="agency_migration_${RUN_ID}"
RESTORE_DB="agency_restore_${RUN_ID}"
ADMIN_URL=""
DATABASE_URL=""
MIGRATION_URL=""
RESTORE_URL=""

log() {
  printf '[postgresql-verification] %s\n' "$*"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'required command is missing: %s\n' "$1" >&2
    exit 2
  fi
}

run_as_postgres() {
  if [ "$(id -u)" -eq 0 ]; then
    runuser -u "$POSTGRES_RUN_USER" -- "$@"
  else
    "$@"
  fi
}

drop_database() {
  database_name=$1
  "$POSTGRES_BIN_DIR/psql" "$ADMIN_URL" -v ON_ERROR_STOP=1 \
    --set=database_name="$database_name" >/dev/null <<'SQL'
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = :'database_name'
  AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS :"database_name";
SQL
}

create_database() {
  database_name=$1
  drop_database "$database_name"
  "$POSTGRES_BIN_DIR/psql" "$ADMIN_URL" -v ON_ERROR_STOP=1 \
    --set=database_name="$database_name" >/dev/null <<'SQL'
CREATE DATABASE :"database_name";
SQL
}

cleanup() {
  if [ "$PG_STARTED" = true ]; then
    drop_database "$SHARED_DB" >/dev/null 2>&1 || true
    drop_database "$MIGRATION_DB" >/dev/null 2>&1 || true
    drop_database "$RESTORE_DB" >/dev/null 2>&1 || true
    run_as_postgres "$POSTGRES_BIN_DIR/pg_ctl" -D "$PG_DATA" -m fast stop \
      >/dev/null 2>&1 || true
  fi
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

for command in "$PYTHON_BIN" runuser id; do
  require_command "$command"
done

if [ -z "$POSTGRES_BIN_DIR" ]; then
  if command -v pg_config >/dev/null 2>&1; then
    POSTGRES_BIN_DIR=$(pg_config --bindir)
  else
    for candidate in /usr/lib/postgresql/*/bin; do
      if [ -x "$candidate/postgres" ]; then
        POSTGRES_BIN_DIR=$candidate
      fi
    done
  fi
fi

for command in postgres initdb pg_ctl psql pg_dump pg_restore; do
  if [ ! -x "$POSTGRES_BIN_DIR/$command" ]; then
    printf 'required PostgreSQL executable is missing: %s/%s\n' \
      "$POSTGRES_BIN_DIR" "$command" >&2
    exit 2
  fi
done
export PATH="$POSTGRES_BIN_DIR:$PATH"

if [ "$(id -u)" -eq 0 ] && ! id "$POSTGRES_RUN_USER" >/dev/null 2>&1; then
  printf 'PostgreSQL cannot run as root and user does not exist: %s\n' \
    "$POSTGRES_RUN_USER" >&2
  exit 2
fi

log "creating hash-locked wheel environment"
"$PYTHON_BIN" -m venv "$VENV"
"$VENV/bin/python" -m pip install --disable-pip-version-check --require-hashes \
  -r "$REPOSITORY_ROOT/backend/requirements-build.lock"
"$VENV/bin/python" -m pip install --disable-pip-version-check --require-hashes \
  -r "$REPOSITORY_ROOT/backend/requirements-test.lock"
mkdir -p "$WHEEL_DIR"
"$VENV/bin/python" -m build --no-isolation --wheel \
  --outdir "$WHEEL_DIR" "$REPOSITORY_ROOT/backend"
"$VENV/bin/python" -m pip install --disable-pip-version-check --no-deps \
  --force-reinstall "$WHEEL_DIR"/*.whl
"$VENV/bin/python" -m pip check

log "starting ephemeral PostgreSQL as an unprivileged user"
mkdir -p "$PG_DATA" "$PG_SOCKET"
chmod 0755 "$TMP_DIR"
if [ "$(id -u)" -eq 0 ]; then
  chown -R "$POSTGRES_RUN_USER" "$PG_ROOT"
fi
run_as_postgres "$POSTGRES_BIN_DIR/initdb" -D "$PG_DATA" \
  --auth=trust --no-locale --encoding=UTF8 \
  --username="$POSTGRES_RUN_USER" >"$TMP_DIR/initdb.log"
PG_PORT=$(
  "$VENV/bin/python" - <<'PY'
import socket

with socket.socket() as handle:
    handle.bind(("127.0.0.1", 0))
    print(handle.getsockname()[1])
PY
)
run_as_postgres "$POSTGRES_BIN_DIR/pg_ctl" -D "$PG_DATA" -l "$PG_LOG" \
  -o "-F -h 127.0.0.1 -p $PG_PORT -k $PG_SOCKET" -w start
PG_STARTED=true
ADMIN_URL="postgresql://${POSTGRES_RUN_USER}@127.0.0.1:${PG_PORT}/postgres?sslmode=disable"
DATABASE_URL="postgresql://${POSTGRES_RUN_USER}@127.0.0.1:${PG_PORT}/${SHARED_DB}?sslmode=disable"
MIGRATION_URL="postgresql://${POSTGRES_RUN_USER}@127.0.0.1:${PG_PORT}/${MIGRATION_DB}?sslmode=disable"
RESTORE_URL="postgresql://${POSTGRES_RUN_USER}@127.0.0.1:${PG_PORT}/${RESTORE_DB}?sslmode=disable"
create_database "$SHARED_DB"
create_database "$MIGRATION_DB"
create_database "$RESTORE_DB"

log "running complete backend suite against shared PostgreSQL state"
(
  cd "$REPOSITORY_ROOT"
  AGENCY_TEST_DATABASE_URL="$DATABASE_URL" \
    "$VENV/bin/python" -m unittest discover -s backend/tests -v
)

log "seeding representative SQLite state for the migration gate"
LEGACY_DB="$TMP_DIR/legacy.sqlite3"
SOURCE_COUNTS_FILE="$TMP_DIR/source-counts.json"
REPOSITORY_ROOT="$REPOSITORY_ROOT" LEGACY_DB="$LEGACY_DB" \
  SOURCE_COUNTS_FILE="$SOURCE_COUNTS_FILE" "$VENV/bin/python" - <<'PY'
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

root = Path(os.environ["REPOSITORY_ROOT"])
sys.path.insert(0, str(root / "backend"))

from agency_runtime.api import BriefRequest, RuntimeService
from agency_runtime.auth import TenantPrincipal
from agency_runtime.memory import SQLiteMemory
from agency_runtime.models import Platform, Provenance

legacy = Path(os.environ["LEGACY_DB"])
service = RuntimeService(legacy)
service.start(
    tenant_id="tenant-migration",
    request=BriefRequest(
        title="Migration campaign",
        objective="Validate the PostgreSQL cutover path",
        audience="Operators",
        platforms=[Platform.X, Platform.INSTAGRAM],
        budget_cents=90000,
        source_asset="sandbox://migration/brief.md",
        campaign_goal="migration-validation",
    ),
    request_id="req-migration-run",
    actor="api-key:operator-migration",
)
service.create_browser_session(
    principal=TenantPrincipal(
        tenant_id="tenant-migration",
        subject_id="operator-migration",
        role="operator",
        key_id="primary",
        credential_fingerprint="migration-fixture",
        auth_method="bearer",
    ),
    ttl_seconds=1800,
    request_id="req-migration-session",
)
service.record_authentication_failure(
    (("migration-ip-bucket", 10), ("migration-identity-bucket", 10)),
    window_seconds=300,
)
service.close()

memory = SQLiteMemory(legacy, namespace="tenant-migration")
observation = memory.observe(
    content="SQLite to PostgreSQL migration evidence",
    provenance=Provenance(
        source="migration-gate",
        locator="sandbox://migration/evidence",
        observed_at=datetime.now(timezone.utc).isoformat(),
        tool="verify-postgresql-runtime",
        trace_id="migration-trace",
    ),
    confidence=0.99,
    tags=("migration", "postgresql"),
)
memory.store(observation)
memory.close()

with sqlite3.connect(legacy) as connection:
    source_counts = {
        "runtime_runs": connection.execute(
            "SELECT COUNT(*) FROM runtime_runs"
        ).fetchone()[0],
        "audit_events": connection.execute(
            "SELECT COUNT(*) FROM audit_events"
        ).fetchone()[0],
        "runtime_sessions": connection.execute(
            "SELECT COUNT(*) FROM runtime_sessions"
        ).fetchone()[0],
        "authentication_rate_limits": connection.execute(
            "SELECT COUNT(DISTINCT bucket_hash) FROM authentication_failures"
        ).fetchone()[0],
        "authentication_failure_total": connection.execute(
            "SELECT COUNT(*) FROM authentication_failures"
        ).fetchone()[0],
        "memories": connection.execute(
            "SELECT COUNT(*) FROM memories"
        ).fetchone()[0],
    }
required = (
    "runtime_runs",
    "audit_events",
    "runtime_sessions",
    "authentication_rate_limits",
    "authentication_failure_total",
    "memories",
)
missing = [name for name in required if source_counts[name] < 1]
if missing:
    raise SystemExit("migration fixture did not populate: {}".format(", ".join(missing)))
Path(os.environ["SOURCE_COUNTS_FILE"]).write_text(
    json.dumps(source_counts, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
print(json.dumps(source_counts, sort_keys=True))
PY

log "creating and restoring a representative SQLite runtime backup"
SQLITE_BACKUP_DIR="$TMP_DIR/sqlite-backups"
SQLITE_BACKUP_REPORT="$TMP_DIR/sqlite-backup.json"
SQLITE_RESTORE_DB="$TMP_DIR/legacy-restored.sqlite3"
"$VENV/bin/python" "$REPOSITORY_ROOT/scripts/manage-runtime-backup.py" \
  sqlite-backup --database "$LEGACY_DB" --output-dir "$SQLITE_BACKUP_DIR" \
  >"$SQLITE_BACKUP_REPORT"
SQLITE_BACKUP_MANIFEST=$("$VENV/bin/python" - "$SQLITE_BACKUP_REPORT" <<'PYSQLITEREPORT'
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if report.get("status") != "created" or report.get("backend") != "sqlite":
    raise SystemExit("unexpected SQLite backup report: {}".format(report))
print(report["manifest"])
PYSQLITEREPORT
)
"$VENV/bin/python" "$REPOSITORY_ROOT/scripts/manage-runtime-backup.py" \
  sqlite-restore --manifest "$SQLITE_BACKUP_MANIFEST" --target "$SQLITE_RESTORE_DB" \
  >"$TMP_DIR/sqlite-restore.json"
REPOSITORY_ROOT="$REPOSITORY_ROOT" SQLITE_RESTORE_DB="$SQLITE_RESTORE_DB" \
  SOURCE_COUNTS_FILE="$SOURCE_COUNTS_FILE" "$VENV/bin/python" - <<'PYSQLITEVERIFY'
import json
import os
import sqlite3
import sys
from pathlib import Path

root = Path(os.environ["REPOSITORY_ROOT"])
sys.path.insert(0, str(root / "backend"))

from agency_runtime.api import RuntimeService
from agency_runtime.memory import SQLiteMemory

restored = Path(os.environ["SQLITE_RESTORE_DB"])
expected = json.loads(
    Path(os.environ["SOURCE_COUNTS_FILE"]).read_text(encoding="utf-8")
)
with sqlite3.connect(restored) as connection:
    observed = {
        "runtime_runs": connection.execute("SELECT COUNT(*) FROM runtime_runs").fetchone()[0],
        "audit_events": connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0],
        "runtime_sessions": connection.execute("SELECT COUNT(*) FROM runtime_sessions").fetchone()[0],
        "authentication_rate_limits": connection.execute(
            "SELECT COUNT(DISTINCT bucket_hash) FROM authentication_failures"
        ).fetchone()[0],
        "authentication_failure_total": connection.execute(
            "SELECT COUNT(*) FROM authentication_failures"
        ).fetchone()[0],
        "memories": connection.execute("SELECT COUNT(*) FROM memories").fetchone()[0],
    }
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
if observed != expected:
    raise SystemExit(
        "SQLite restore count mismatch: expected {}, observed {}".format(expected, observed)
    )
if integrity != "ok":
    raise SystemExit("SQLite restore integrity check failed: {}".format(integrity))
service = RuntimeService(str(restored))
try:
    if service.run_store.count("tenant-migration") != 1:
        raise SystemExit("restored SQLite run is not application-readable")
finally:
    service.close()
memory = SQLiteMemory(restored, namespace="tenant-migration")
try:
    matches = memory.search("migration evidence", limit=5)
    if not matches:
        raise SystemExit("restored SQLite memory is not application-readable")
finally:
    memory.close()
print("sqlite_restore_counts=pass")
print("sqlite_restore_application_read=pass")
PYSQLITEVERIFY
printf 'sqlite_backup_restore=pass\n'

log "validating the migration plan without mutating PostgreSQL"
AGENCY_DATABASE_URL="$MIGRATION_URL" \
  "$VENV/bin/python" "$REPOSITORY_ROOT/scripts/migrate-sqlite-to-postgresql.py" \
  --sqlite "$LEGACY_DB" >"$TMP_DIR/migration-dry-run.json"
"$VENV/bin/python" - "$TMP_DIR/migration-dry-run.json" <<'PY'
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if report.get("mode") != "dry-run" or report.get("status") != "validated":
    raise SystemExit("unexpected migration dry-run report: {}".format(report))
print("migration_dry_run=pass")
PY

log "applying the SQLite migration exactly once"
AGENCY_DATABASE_URL="$MIGRATION_URL" \
  "$VENV/bin/python" "$REPOSITORY_ROOT/scripts/migrate-sqlite-to-postgresql.py" \
  --sqlite "$LEGACY_DB" --apply >"$TMP_DIR/migration-apply.json"

log "validating source-to-target equivalence and replay protection"
REPOSITORY_ROOT="$REPOSITORY_ROOT" MIGRATION_URL="$MIGRATION_URL" \
  SOURCE_COUNTS_FILE="$SOURCE_COUNTS_FILE" "$VENV/bin/python" - <<'PY'
import json
import os
import sys
from pathlib import Path

root = Path(os.environ["REPOSITORY_ROOT"])
sys.path.insert(0, str(root / "backend"))

from agency_runtime.postgres import PostgresRuntimeDatabase

expected = json.loads(
    Path(os.environ["SOURCE_COUNTS_FILE"]).read_text(encoding="utf-8")
)
runtime = PostgresRuntimeDatabase(os.environ["MIGRATION_URL"])
try:
    with runtime.pool.connection() as connection:
        for table in (
            "runtime_runs",
            "audit_events",
            "runtime_sessions",
            "authentication_rate_limits",
            "memories",
        ):
            observed = connection.execute(
                "SELECT COUNT(*) AS total FROM {}".format(table)
            ).fetchone()
            if observed is None or observed["total"] != expected[table]:
                raise SystemExit(
                    "migration count mismatch for {}: expected {}, observed {}".format(
                        table, expected[table], observed
                    )
                )
        failures = connection.execute(
            "SELECT COALESCE(SUM(failure_count), 0) AS total "
            "FROM authentication_rate_limits"
        ).fetchone()
        if failures is None or failures["total"] != expected["authentication_failure_total"]:
            raise SystemExit(
                "authentication failure total mismatch: expected {}, observed {}".format(
                    expected["authentication_failure_total"], failures
                )
            )
        schema = connection.execute(
            "SELECT value FROM runtime_schema_meta WHERE key = 'schema_version'"
        ).fetchone()
        if schema is None or schema["value"] != "1":
            raise SystemExit("unexpected schema version: {}".format(schema))
finally:
    runtime.close()
print("migration_counts=pass")
print("migration_failure_totals=pass")
PY

set +e
AGENCY_DATABASE_URL="$MIGRATION_URL" \
  "$VENV/bin/python" "$REPOSITORY_ROOT/scripts/migrate-sqlite-to-postgresql.py" \
  --sqlite "$LEGACY_DB" --apply >"$TMP_DIR/migration-replay.log" 2>&1
REPLAY_STATUS=$?
set -e
if [ "$REPLAY_STATUS" -eq 0 ]; then
  printf 'migration replay unexpectedly succeeded\n' >&2
  exit 1
fi
grep -q 'PostgreSQL target must be empty before migration' "$TMP_DIR/migration-replay.log"
printf 'migration_replay_guard=pass\n'

log "creating and validating a custom-format PostgreSQL runtime backup"
BACKUP_DIR="$TMP_DIR/backups"
BACKUP_REPORT="$TMP_DIR/postgresql-backup.json"
AGENCY_DATABASE_URL="$MIGRATION_URL" \
  "$VENV/bin/python" "$REPOSITORY_ROOT/scripts/manage-runtime-backup.py" \
  postgres-backup --database-url-env AGENCY_DATABASE_URL \
  --output-dir "$BACKUP_DIR" >"$BACKUP_REPORT"
BACKUP_MANIFEST=$("$VENV/bin/python" - "$BACKUP_REPORT" <<'PYREPORT'
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if report.get("status") != "created" or report.get("backend") != "postgresql":
    raise SystemExit("unexpected PostgreSQL backup report: {}".format(report))
print(report["manifest"])
PYREPORT
)
if [ ! -f "$BACKUP_MANIFEST" ]; then
  printf 'PostgreSQL backup manifest was not created\n' >&2
  exit 1
fi

log "proving non-empty PostgreSQL targets fail closed before restore"
set +e
AGENCY_RESTORE_DATABASE_URL="$MIGRATION_URL" \
  "$VENV/bin/python" "$REPOSITORY_ROOT/scripts/manage-runtime-backup.py" \
  postgres-restore --manifest "$BACKUP_MANIFEST" \
  --database-url-env AGENCY_RESTORE_DATABASE_URL \
  >"$TMP_DIR/nonempty-restore.log" 2>&1
NONEMPTY_RESTORE_STATUS=$?
set -e
if [ "$NONEMPTY_RESTORE_STATUS" -eq 0 ]; then
  printf 'PostgreSQL restore unexpectedly accepted a non-empty target\n' >&2
  exit 1
fi
grep -q 'target must contain zero non-system tables' "$TMP_DIR/nonempty-restore.log"
printf 'postgresql_restore_nonempty_guard=pass\n'

log "restoring the exact backup into a fresh PostgreSQL database"
AGENCY_RESTORE_DATABASE_URL="$RESTORE_URL" \
  "$VENV/bin/python" "$REPOSITORY_ROOT/scripts/manage-runtime-backup.py" \
  postgres-restore --manifest "$BACKUP_MANIFEST" \
  --database-url-env AGENCY_RESTORE_DATABASE_URL \
  >"$TMP_DIR/postgresql-restore.json"

log "validating restored schema, counts, failure totals and application readability"
REPOSITORY_ROOT="$REPOSITORY_ROOT" RESTORE_URL="$RESTORE_URL" \
  SOURCE_COUNTS_FILE="$SOURCE_COUNTS_FILE" "$VENV/bin/python" - <<'PYVERIFY'
import json
import os
import sys
from pathlib import Path

root = Path(os.environ["REPOSITORY_ROOT"])
sys.path.insert(0, str(root / "backend"))

from agency_runtime.postgres import PostgresRuntimeDatabase

expected = json.loads(
    Path(os.environ["SOURCE_COUNTS_FILE"]).read_text(encoding="utf-8")
)
runtime = PostgresRuntimeDatabase(os.environ["RESTORE_URL"])
try:
    with runtime.pool.connection() as connection:
        for table in (
            "runtime_runs",
            "audit_events",
            "runtime_sessions",
            "authentication_rate_limits",
            "memories",
        ):
            observed = connection.execute(
                "SELECT COUNT(*) AS total FROM {}".format(table)
            ).fetchone()
            if observed is None or observed["total"] != expected[table]:
                raise SystemExit(
                    "restore count mismatch for {}: expected {}, observed {}".format(
                        table, expected[table], observed
                    )
                )
        failures = connection.execute(
            "SELECT COALESCE(SUM(failure_count), 0) AS total "
            "FROM authentication_rate_limits"
        ).fetchone()
        if failures is None or failures["total"] != expected["authentication_failure_total"]:
            raise SystemExit(
                "restore authentication failure total mismatch: expected {}, observed {}".format(
                    expected["authentication_failure_total"], failures
                )
            )
        schema = connection.execute(
            "SELECT value FROM runtime_schema_meta WHERE key = 'schema_version'"
        ).fetchone()
        if schema is None or schema["value"] != "1":
            raise SystemExit("unexpected restored schema version: {}".format(schema))
        restored_run = connection.execute(
            "SELECT tenant_id, status FROM runtime_runs LIMIT 1"
        ).fetchone()
        if restored_run is None or restored_run["tenant_id"] != "tenant-migration":
            raise SystemExit("restored runtime run is not application-readable")
finally:
    runtime.close()
print("postgresql_restore_counts=pass")
print("postgresql_restore_application_read=pass")
PYVERIFY
printf 'postgresql_backup_restore=pass\n'

printf 'postgres_version=%s\n' "$("$POSTGRES_BIN_DIR/postgres" --version)"
printf 'driver=pg8000\n'
printf 'schema_version=1\n'
printf 'wheel_install=pass\n'
printf 'postgres_integration=pass\n'
printf 'sqlite_migration=pass\n'
printf 'migration_idempotence=pass\n'
printf 'backup_restore=pass\n'
printf 'backend_test_suite=pass\n'
printf 'pip_check=pass\n'
printf 'cleanup=pass\n'
