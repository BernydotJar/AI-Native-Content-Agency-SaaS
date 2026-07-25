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
INCOMPATIBLE_DB="agency_incompatible_${RUN_ID}"
MIGRATION_ROLE="agency_migrator_${RUN_ID}"
RUNTIME_ROLE="agency_runtime_${RUN_ID}"
ADMIN_URL=""
SHARED_MIGRATION_URL=""
DATABASE_URL=""
MIGRATION_URL=""
MIGRATION_RUNTIME_URL=""
RESTORE_URL=""
RESTORE_RUNTIME_URL=""
INCOMPATIBLE_URL=""

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
  "$POSTGRES_BIN_DIR/psql" "$ADMIN_URL" --no-psqlrc -v ON_ERROR_STOP=1 \
    --set=database_name="$database_name" >/dev/null <<'SQL'
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = :'database_name'
  AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS :"database_name";
SQL
}

drop_role() {
  role_name=$1
  "$POSTGRES_BIN_DIR/psql" "$ADMIN_URL" --no-psqlrc -v ON_ERROR_STOP=1 \
    --set=role_name="$role_name" >/dev/null <<'SQL'
DROP ROLE IF EXISTS :"role_name";
SQL
}

create_database() {
  database_name=$1
  owner_name=$2
  drop_database "$database_name"
  "$POSTGRES_BIN_DIR/psql" "$ADMIN_URL" --no-psqlrc -v ON_ERROR_STOP=1 \
    --set=database_name="$database_name" \
    --set=owner_name="$owner_name" \
    --set=runtime_role="$RUNTIME_ROLE" >/dev/null <<'SQL'
CREATE DATABASE :"database_name" OWNER :"owner_name";
REVOKE CONNECT, TEMPORARY ON DATABASE :"database_name" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"database_name" TO :"runtime_role";
SQL
}

prepare_runtime_schema_access() {
  migration_url=$1
  "$POSTGRES_BIN_DIR/psql" "$migration_url" --no-psqlrc -v ON_ERROR_STOP=1 \
    --set=runtime_role="$RUNTIME_ROLE" >/dev/null <<'SQL'
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO :"runtime_role";
SQL
}

grant_runtime_privileges() {
  migration_url=$1
  "$POSTGRES_BIN_DIR/psql" "$migration_url" --no-psqlrc -v ON_ERROR_STOP=1 \
    --set=migration_role="$MIGRATION_ROLE" \
    --set=runtime_role="$RUNTIME_ROLE" >/dev/null <<'SQL'
REVOKE ALL ON TABLE public.runtime_schema_meta FROM PUBLIC;
REVOKE ALL ON TABLE public.runtime_runs FROM PUBLIC;
REVOKE ALL ON TABLE public.audit_events FROM PUBLIC;
REVOKE ALL ON TABLE public.runtime_sessions FROM PUBLIC;
REVOKE ALL ON TABLE public.authentication_rate_limits FROM PUBLIC;
REVOKE ALL ON TABLE public.memories FROM PUBLIC;
REVOKE ALL ON TABLE public.social_oauth_states FROM PUBLIC;
REVOKE ALL ON TABLE public.social_connections FROM PUBLIC;
REVOKE ALL ON TABLE public.social_publication_intents FROM PUBLIC;
REVOKE ALL ON TABLE public.publication_media_objects FROM PUBLIC;
REVOKE ALL ON TABLE public.model_effect_intents FROM PUBLIC;
REVOKE ALL ON SEQUENCE public.audit_events_sequence_seq FROM PUBLIC;

GRANT SELECT ON TABLE public.runtime_schema_meta TO :"runtime_role";
GRANT SELECT, INSERT, UPDATE ON TABLE public.runtime_runs TO :"runtime_role";
GRANT SELECT, INSERT ON TABLE public.audit_events TO :"runtime_role";
GRANT SELECT, INSERT, UPDATE ON TABLE public.runtime_sessions TO :"runtime_role";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.authentication_rate_limits TO :"runtime_role";
GRANT SELECT, INSERT ON TABLE public.memories TO :"runtime_role";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.social_oauth_states TO :"runtime_role";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.social_connections TO :"runtime_role";
GRANT SELECT, INSERT, UPDATE ON TABLE public.social_publication_intents TO :"runtime_role";
GRANT SELECT, INSERT, UPDATE ON TABLE public.publication_media_objects TO :"runtime_role";
GRANT SELECT, INSERT, UPDATE ON TABLE public.model_effect_intents TO :"runtime_role";
GRANT USAGE, SELECT ON SEQUENCE public.audit_events_sequence_seq TO :"runtime_role";

ALTER DEFAULT PRIVILEGES FOR ROLE :"migration_role" IN SCHEMA public
  REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE :"migration_role" IN SCHEMA public
  REVOKE ALL ON SEQUENCES FROM PUBLIC;
SQL
}

expect_runtime_denied() {
  operation=$1
  statement=$2
  log_file="$TMP_DIR/runtime-denied-${operation}.log"
  set +e
  "$POSTGRES_BIN_DIR/psql" "$DATABASE_URL" --no-psqlrc -v ON_ERROR_STOP=1 \
    --command "$statement" >"$log_file" 2>&1
  status=$?
  set -e
  if [ "$status" -eq 0 ]; then
    printf 'runtime PostgreSQL role unexpectedly completed %s\n' "$operation" >&2
    exit 1
  fi
  if ! grep -Eqi 'permission denied|must be owner' "$log_file"; then
    printf 'runtime PostgreSQL %s denial was not a permission failure\n' "$operation" >&2
    exit 1
  fi
  printf 'postgresql_runtime_%s_denied=pass\n' "$operation"
}

expect_runtime_grant_ineffective() {
  log_file="$TMP_DIR/runtime-grant-escalation.log"
  set +e
  "$POSTGRES_BIN_DIR/psql" "$DATABASE_URL" --no-psqlrc -v ON_ERROR_STOP=1 \
    --command "GRANT UPDATE ON public.runtime_schema_meta TO PUBLIC" \
    >"$log_file" 2>&1
  status=$?
  set -e
  if [ "$status" -ne 0 ]; then
    if ! grep -Eqi 'permission denied|must be owner' "$log_file"; then
      printf 'runtime PostgreSQL grant escalation failed for an unexpected reason\n' >&2
      exit 1
    fi
  elif ! grep -Eqi 'no privileges were granted' "$log_file"; then
    printf 'runtime PostgreSQL grant escalation returned success without the expected denial warning\n' >&2
    exit 1
  fi
  public_update_grants=$("$POSTGRES_BIN_DIR/psql" "$SHARED_MIGRATION_URL" \
    --no-psqlrc --tuples-only --no-align --set=ON_ERROR_STOP=1 --command "
SELECT COUNT(*)
FROM information_schema.table_privileges
WHERE table_schema = 'public'
  AND table_name = 'runtime_schema_meta'
  AND grantee = 'PUBLIC'
  AND privilege_type = 'UPDATE';
")
  if [ "$public_update_grants" != "0" ]; then
    printf 'runtime PostgreSQL role changed PUBLIC privileges unexpectedly\n' >&2
    exit 1
  fi
  printf 'postgresql_runtime_grant_escalation_denied=pass\n'
}

cleanup() {
  if [ "$PG_STARTED" = true ]; then
    drop_database "$SHARED_DB" >/dev/null 2>&1 || true
    drop_database "$MIGRATION_DB" >/dev/null 2>&1 || true
    drop_database "$RESTORE_DB" >/dev/null 2>&1 || true
    drop_database "$INCOMPATIBLE_DB" >/dev/null 2>&1 || true
    drop_role "$RUNTIME_ROLE" >/dev/null 2>&1 || true
    drop_role "$MIGRATION_ROLE" >/dev/null 2>&1 || true
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

log "creating distinct migration and runtime login roles"
"$POSTGRES_BIN_DIR/psql" "$ADMIN_URL" --no-psqlrc -v ON_ERROR_STOP=1 \
  --set=migration_role="$MIGRATION_ROLE" \
  --set=runtime_role="$RUNTIME_ROLE" >/dev/null <<'SQL'
CREATE ROLE :"migration_role"
  LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE :"runtime_role"
  LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
SQL

SHARED_MIGRATION_URL="postgresql://${MIGRATION_ROLE}@127.0.0.1:${PG_PORT}/${SHARED_DB}?sslmode=disable"
DATABASE_URL="postgresql://${RUNTIME_ROLE}@127.0.0.1:${PG_PORT}/${SHARED_DB}?sslmode=disable"
MIGRATION_URL="postgresql://${MIGRATION_ROLE}@127.0.0.1:${PG_PORT}/${MIGRATION_DB}?sslmode=disable"
MIGRATION_RUNTIME_URL="postgresql://${RUNTIME_ROLE}@127.0.0.1:${PG_PORT}/${MIGRATION_DB}?sslmode=disable"
RESTORE_URL="postgresql://${MIGRATION_ROLE}@127.0.0.1:${PG_PORT}/${RESTORE_DB}?sslmode=disable"
RESTORE_RUNTIME_URL="postgresql://${RUNTIME_ROLE}@127.0.0.1:${PG_PORT}/${RESTORE_DB}?sslmode=disable"
INCOMPATIBLE_URL="postgresql://${MIGRATION_ROLE}@127.0.0.1:${PG_PORT}/${INCOMPATIBLE_DB}?sslmode=disable"
create_database "$SHARED_DB" "$MIGRATION_ROLE"
create_database "$MIGRATION_DB" "$MIGRATION_ROLE"
create_database "$RESTORE_DB" "$MIGRATION_ROLE"
create_database "$INCOMPATIBLE_DB" "$MIGRATION_ROLE"
prepare_runtime_schema_access "$SHARED_MIGRATION_URL"
prepare_runtime_schema_access "$MIGRATION_URL"
prepare_runtime_schema_access "$RESTORE_URL"

log "proving validate mode fails closed before schema initialization"
set +e
AGENCY_DATABASE_URL="$DATABASE_URL" \
  "$VENV/bin/agency-runtime-schema" validate \
  --database-url-env AGENCY_DATABASE_URL >"$TMP_DIR/schema-absent.log" 2>&1
SCHEMA_ABSENT_STATUS=$?
set -e
if [ "$SCHEMA_ABSENT_STATUS" -eq 0 ]; then
  printf 'runtime schema validation unexpectedly initialized an absent schema\n' >&2
  exit 1
fi
grep -q 'PostgreSQL runtime schema is incomplete' "$TMP_DIR/schema-absent.log"
printf 'postgresql_schema_absent_guard=pass\n'

log "proving incompatible initialization rolls back partial DDL"
"$POSTGRES_BIN_DIR/psql" "$INCOMPATIBLE_URL" --no-psqlrc -v ON_ERROR_STOP=1 \
  >/dev/null <<'SQL'
CREATE TABLE public.runtime_schema_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
INSERT INTO public.runtime_schema_meta(key, value)
VALUES ('schema_version', '999');
SQL
set +e
AGENCY_MIGRATION_DATABASE_URL="$INCOMPATIBLE_URL" \
  "$VENV/bin/agency-runtime-schema" initialize \
  --database-url-env AGENCY_MIGRATION_DATABASE_URL \
  >"$TMP_DIR/schema-initialize-incompatible.log" 2>&1
INCOMPATIBLE_INITIALIZE_STATUS=$?
set -e
if [ "$INCOMPATIBLE_INITIALIZE_STATUS" -eq 0 ]; then
  printf 'incompatible schema initialization unexpectedly succeeded\n' >&2
  exit 1
fi
grep -q 'unsupported PostgreSQL runtime schema version' \
  "$TMP_DIR/schema-initialize-incompatible.log"
INCOMPATIBLE_ROLLBACK_STATE=$("$POSTGRES_BIN_DIR/psql" "$INCOMPATIBLE_URL" \
  --no-psqlrc --tuples-only --no-align --set=ON_ERROR_STOP=1 --command "
SELECT COALESCE(to_regclass('public.runtime_runs')::text, 'missing') || '|' || value
FROM public.runtime_schema_meta
WHERE key = 'schema_version';
")
if [ "$INCOMPATIBLE_ROLLBACK_STATE" != "missing|999" ]; then
  printf 'incompatible initialization left partial schema state: %s\n' \
    "$INCOMPATIBLE_ROLLBACK_STATE" >&2
  exit 1
fi
printf 'postgresql_schema_initialize_rollback=pass\n'

log "initializing shared schema with migration authority"
AGENCY_MIGRATION_DATABASE_URL="$SHARED_MIGRATION_URL" \
  "$VENV/bin/agency-runtime-schema" initialize \
  --database-url-env AGENCY_MIGRATION_DATABASE_URL \
  >"$TMP_DIR/schema-initialize.json"
grant_runtime_privileges "$SHARED_MIGRATION_URL"
AGENCY_DATABASE_URL="$DATABASE_URL" \
  "$VENV/bin/agency-runtime-schema" validate \
  --database-url-env AGENCY_DATABASE_URL \
  >"$TMP_DIR/schema-validate.json"
printf 'postgresql_schema_validate=pass\n'

log "proving application connections use a fixed safe search path"
REPOSITORY_ROOT="$REPOSITORY_ROOT" DATABASE_URL="$DATABASE_URL" \
  "$VENV/bin/python" - <<'PYSEARCHPATH'
import os
import sys
from pathlib import Path

root = Path(os.environ["REPOSITORY_ROOT"])
sys.path.insert(0, str(root / "backend"))

from agency_runtime.postgres import PostgresRuntimeDatabase

runtime = PostgresRuntimeDatabase(os.environ["DATABASE_URL"], schema_mode="validate")
try:
    with runtime.pool.connection() as connection:
        row = connection.execute("SHOW search_path").fetchone()
        if row is None or str(row["search_path"]).replace(" ", "") != "pg_catalog,public":
            raise SystemExit("unexpected runtime search_path: {}".format(row))

        database_privileges = connection.execute(
            """
            SELECT
              has_database_privilege(current_user, current_database(), 'CONNECT') AS connect,
              has_database_privilege(current_user, current_database(), 'TEMP') AS temporary
            """
        ).fetchone()
        if database_privileges != {"connect": True, "temporary": False}:
            raise SystemExit(
                "unexpected runtime database privileges: {}".format(database_privileges)
            )

        schema_privileges = connection.execute(
            """
            SELECT
              has_schema_privilege(current_user, 'public', 'USAGE') AS usage,
              has_schema_privilege(current_user, 'public', 'CREATE') AS create
            """
        ).fetchone()
        if schema_privileges != {"usage": True, "create": False}:
            raise SystemExit(
                "unexpected runtime schema privileges: {}".format(schema_privileges)
            )

        expected_table_privileges = {
            "runtime_schema_meta": {"SELECT"},
            "runtime_runs": {"SELECT", "INSERT", "UPDATE"},
            "audit_events": {"SELECT", "INSERT"},
            "runtime_sessions": {"SELECT", "INSERT", "UPDATE"},
            "authentication_rate_limits": {"SELECT", "INSERT", "UPDATE", "DELETE"},
            "memories": {"SELECT", "INSERT"},
            "social_oauth_states": {"SELECT", "INSERT", "UPDATE", "DELETE"},
            "social_connections": {"SELECT", "INSERT", "UPDATE", "DELETE"},
            "social_publication_intents": {"SELECT", "INSERT", "UPDATE"},
            "publication_media_objects": {"SELECT", "INSERT", "UPDATE"},
            "model_effect_intents": {"SELECT", "INSERT", "UPDATE"},
        }
        all_table_privileges = {
            "SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"
        }
        for table, expected in expected_table_privileges.items():
            for privilege in all_table_privileges:
                observed = connection.execute(
                    "SELECT has_table_privilege(current_user, %s, %s) AS allowed",
                    ("public.{}".format(table), privilege),
                ).fetchone()
                if observed is None or bool(observed["allowed"]) != (privilege in expected):
                    raise SystemExit(
                        "unexpected runtime privilege {} on {}: {}".format(
                            privilege, table, observed
                        )
                    )

        for privilege, expected in {"USAGE": True, "SELECT": True, "UPDATE": False}.items():
            observed = connection.execute(
                "SELECT has_sequence_privilege(current_user, %s, %s) AS allowed",
                ("public.audit_events_sequence_seq", privilege),
            ).fetchone()
            if observed is None or bool(observed["allowed"]) != expected:
                raise SystemExit(
                    "unexpected runtime sequence privilege {}: {}".format(
                        privilege, observed
                    )
                )
finally:
    runtime.close()
print("postgresql_runtime_search_path=pass")
print("postgresql_runtime_grant_matrix=pass")
PYSEARCHPATH

log "proving incompatible and incomplete schemas fail closed"
"$POSTGRES_BIN_DIR/psql" "$SHARED_MIGRATION_URL" --no-psqlrc -v ON_ERROR_STOP=1 \
  --command "UPDATE public.runtime_schema_meta SET value = '999' WHERE key = 'schema_version'" \
  >/dev/null
set +e
AGENCY_DATABASE_URL="$DATABASE_URL" \
  "$VENV/bin/agency-runtime-schema" validate \
  --database-url-env AGENCY_DATABASE_URL >"$TMP_DIR/schema-incompatible.log" 2>&1
SCHEMA_INCOMPATIBLE_STATUS=$?
set -e
"$POSTGRES_BIN_DIR/psql" "$SHARED_MIGRATION_URL" --no-psqlrc -v ON_ERROR_STOP=1 \
  --command "UPDATE public.runtime_schema_meta SET value = '5' WHERE key = 'schema_version'" \
  >/dev/null
if [ "$SCHEMA_INCOMPATIBLE_STATUS" -eq 0 ]; then
  printf 'runtime schema validation unexpectedly accepted an incompatible version\n' >&2
  exit 1
fi
grep -q 'unsupported PostgreSQL runtime schema version' "$TMP_DIR/schema-incompatible.log"
printf 'postgresql_schema_incompatible_guard=pass\n'

"$POSTGRES_BIN_DIR/psql" "$SHARED_MIGRATION_URL" --no-psqlrc -v ON_ERROR_STOP=1 \
  --command "ALTER TABLE public.memories RENAME TO memories_schema_probe" >/dev/null
set +e
AGENCY_DATABASE_URL="$DATABASE_URL" \
  "$VENV/bin/agency-runtime-schema" validate \
  --database-url-env AGENCY_DATABASE_URL >"$TMP_DIR/schema-incomplete.log" 2>&1
SCHEMA_INCOMPLETE_STATUS=$?
set -e
if [ "$SCHEMA_INCOMPLETE_STATUS" -eq 0 ]; then
  printf 'runtime schema validation unexpectedly accepted an incomplete schema\n' >&2
  exit 1
fi
grep -q 'table:memories:missing' "$TMP_DIR/schema-incomplete.log"
printf 'postgresql_schema_incomplete_guard=pass\n'

"$POSTGRES_BIN_DIR/psql" "$SHARED_MIGRATION_URL" --no-psqlrc -v ON_ERROR_STOP=1 \
  --command "CREATE VIEW public.memories AS SELECT 1 AS placeholder" >/dev/null
set +e
AGENCY_DATABASE_URL="$DATABASE_URL" \
  "$VENV/bin/agency-runtime-schema" validate \
  --database-url-env AGENCY_DATABASE_URL >"$TMP_DIR/schema-wrong-type.log" 2>&1
SCHEMA_WRONG_TYPE_STATUS=$?
set -e
"$POSTGRES_BIN_DIR/psql" "$SHARED_MIGRATION_URL" --no-psqlrc -v ON_ERROR_STOP=1 \
  --command "DROP VIEW public.memories" >/dev/null
"$POSTGRES_BIN_DIR/psql" "$SHARED_MIGRATION_URL" --no-psqlrc -v ON_ERROR_STOP=1 \
  --command "ALTER TABLE public.memories_schema_probe RENAME TO memories" >/dev/null
if [ "$SCHEMA_WRONG_TYPE_STATUS" -eq 0 ]; then
  printf 'runtime schema validation unexpectedly accepted a wrong-type relation\n' >&2
  exit 1
fi
grep -q 'table:memories:wrong_type' "$TMP_DIR/schema-wrong-type.log"
printf 'postgresql_schema_relation_type_guard=pass\n'

"$POSTGRES_BIN_DIR/psql" "$SHARED_MIGRATION_URL" --no-psqlrc -v ON_ERROR_STOP=1 \
  --command "ALTER TABLE public.memories RENAME COLUMN content TO content_schema_probe" \
  >/dev/null
set +e
AGENCY_DATABASE_URL="$DATABASE_URL" \
  "$VENV/bin/agency-runtime-schema" validate \
  --database-url-env AGENCY_DATABASE_URL >"$TMP_DIR/schema-missing-column.log" 2>&1
SCHEMA_MISSING_COLUMN_STATUS=$?
set -e
"$POSTGRES_BIN_DIR/psql" "$SHARED_MIGRATION_URL" --no-psqlrc -v ON_ERROR_STOP=1 \
  --command "ALTER TABLE public.memories RENAME COLUMN content_schema_probe TO content" \
  >/dev/null
if [ "$SCHEMA_MISSING_COLUMN_STATUS" -eq 0 ]; then
  printf 'runtime schema validation unexpectedly accepted a missing column\n' >&2
  exit 1
fi
grep -q 'column:memories.content:missing' "$TMP_DIR/schema-missing-column.log"
printf 'postgresql_schema_column_guard=pass\n'

log "proving the application database identity is least-privilege"
RUNTIME_ROLE_FACTS=$("$POSTGRES_BIN_DIR/psql" "$ADMIN_URL" --no-psqlrc \
  --tuples-only --no-align --set=ON_ERROR_STOP=1 \
  --set=runtime_role="$RUNTIME_ROLE" <<'SQL'
SELECT rolsuper::text || '|' || rolcreatedb::text || '|' ||
       rolcreaterole::text || '|' || rolreplication::text || '|' ||
       rolbypassrls::text
FROM pg_catalog.pg_roles
WHERE rolname = :'runtime_role';
SQL
)
if [ "$RUNTIME_ROLE_FACTS" != "false|false|false|false|false" ]; then
  printf 'runtime PostgreSQL role is overprivileged: observed %s\n' \
    "$RUNTIME_ROLE_FACTS" >&2
  exit 1
fi
printf 'postgresql_runtime_role_attributes=pass\n'

RUNTIME_OWNED_OBJECTS=$("$POSTGRES_BIN_DIR/psql" "$SHARED_MIGRATION_URL" \
  --no-psqlrc --tuples-only --no-align --set=ON_ERROR_STOP=1 \
  --set=runtime_role="$RUNTIME_ROLE" <<'SQL'
WITH runtime_role AS (
  SELECT oid FROM pg_catalog.pg_roles WHERE rolname = :'runtime_role'
)
SELECT
  (SELECT COUNT(*) FROM pg_catalog.pg_database, runtime_role
   WHERE datdba = runtime_role.oid) +
  (SELECT COUNT(*) FROM pg_catalog.pg_namespace, runtime_role
   WHERE nspowner = runtime_role.oid) +
  (SELECT COUNT(*) FROM pg_catalog.pg_class, runtime_role
   WHERE relowner = runtime_role.oid
     AND relkind IN ('r', 'p', 'S', 'v', 'm', 'f'));
SQL
)
if [ "$RUNTIME_OWNED_OBJECTS" != "0" ]; then
  printf 'runtime PostgreSQL role owns database/schema/runtime objects: %s\n' \
    "$RUNTIME_OWNED_OBJECTS" >&2
  exit 1
fi
printf 'postgresql_runtime_role_ownership=pass\n'

expect_runtime_denied create_table \
  "CREATE TABLE public.runtime_forbidden_probe(id integer)"
expect_runtime_denied create_temp_table \
  "CREATE TEMP TABLE runtime_forbidden_temp_probe(id integer)"
expect_runtime_denied alter_table \
  "ALTER TABLE public.runtime_runs ADD COLUMN forbidden_probe integer"
expect_runtime_denied drop_table \
  "DROP TABLE public.memories"
expect_runtime_denied truncate_table \
  "TRUNCATE TABLE public.runtime_runs"
expect_runtime_denied schema_meta_update \
  "UPDATE public.runtime_schema_meta SET value = '999' WHERE key = 'schema_version'"
expect_runtime_grant_ineffective
expect_runtime_denied set_migration_role \
  "SET ROLE \"$MIGRATION_ROLE\""
printf 'postgresql_runtime_ddl_denied=pass\n'

log "running complete backend suite against shared PostgreSQL state"
(
  cd "$REPOSITORY_ROOT"
  AGENCY_TEST_DATABASE_URL="$DATABASE_URL" \
  AGENCY_TEST_MIGRATION_DATABASE_URL="$SHARED_MIGRATION_URL" \
  AGENCY_POSTGRES_SCHEMA_MODE=validate \
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
    subject_id="operator-migration",
    idempotency_key="migration-fixture-run-0001",
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

log "initializing the SQLite migration target with migration authority"
AGENCY_MIGRATION_DATABASE_URL="$MIGRATION_URL" \
  "$VENV/bin/agency-runtime-schema" initialize \
  --database-url-env AGENCY_MIGRATION_DATABASE_URL \
  >"$TMP_DIR/migration-schema-initialize.json"

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
grant_runtime_privileges "$MIGRATION_URL"
AGENCY_DATABASE_URL="$MIGRATION_RUNTIME_URL" \
  "$VENV/bin/agency-runtime-schema" validate \
  --database-url-env AGENCY_DATABASE_URL \
  >"$TMP_DIR/migration-schema-validate.json"

log "validating source-to-target equivalence and replay protection"
REPOSITORY_ROOT="$REPOSITORY_ROOT" MIGRATION_RUNTIME_URL="$MIGRATION_RUNTIME_URL" \
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
runtime = PostgresRuntimeDatabase(
    os.environ["MIGRATION_RUNTIME_URL"], schema_mode="validate"
)
try:
    with runtime.pool.connection() as connection:
        for table in (
            "runtime_runs",
            "audit_events",
            "runtime_sessions",
            "authentication_rate_limits",
            "memories",
            "social_oauth_states",
            "social_connections",
            "social_publication_intents",
            "model_effect_intents",
        ):
            observed = connection.execute(
                "SELECT COUNT(*) AS total FROM {}".format(table)
            ).fetchone()
            if observed is None or observed["total"] != expected.get(table, 0):
                raise SystemExit(
                    "migration count mismatch for {}: expected {}, observed {}".format(
                        table, expected.get(table, 0), observed
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
        if schema is None or schema["value"] != "5":
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
  --output-dir "$BACKUP_DIR" \
  --metrics-file "$TMP_DIR/postgresql-backup.prom" >"$BACKUP_REPORT"
grep -q 'agency_backup_last_success_timestamp_seconds{backend="postgresql"}' \
  "$TMP_DIR/postgresql-backup.prom"
grep -q 'agency_backup_success{backend="postgresql"} 1' \
  "$TMP_DIR/postgresql-backup.prom"
if [ "$(stat -c '%a' "$TMP_DIR/postgresql-backup.prom")" != "600" ]; then
  printf 'PostgreSQL backup metric file is not private\n' >&2
  exit 1
fi
printf 'backup_freshness_metrics=pass\n'
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
grant_runtime_privileges "$RESTORE_URL"
AGENCY_DATABASE_URL="$RESTORE_RUNTIME_URL" \
  "$VENV/bin/agency-runtime-schema" validate \
  --database-url-env AGENCY_DATABASE_URL \
  >"$TMP_DIR/restore-schema-validate.json"

log "validating restored schema, counts, failure totals and application readability"
REPOSITORY_ROOT="$REPOSITORY_ROOT" RESTORE_RUNTIME_URL="$RESTORE_RUNTIME_URL" \
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
runtime = PostgresRuntimeDatabase(
    os.environ["RESTORE_RUNTIME_URL"], schema_mode="validate"
)
try:
    with runtime.pool.connection() as connection:
        for table in (
            "runtime_runs",
            "audit_events",
            "runtime_sessions",
            "authentication_rate_limits",
            "memories",
            "social_oauth_states",
            "social_connections",
            "social_publication_intents",
            "model_effect_intents",
        ):
            observed = connection.execute(
                "SELECT COUNT(*) AS total FROM {}".format(table)
            ).fetchone()
            if observed is None or observed["total"] != expected.get(table, 0):
                raise SystemExit(
                    "restore count mismatch for {}: expected {}, observed {}".format(
                        table, expected.get(table, 0), observed
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
        if schema is None or schema["value"] != "5":
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
printf 'schema_version=6\n'
printf 'wheel_install=pass\n'
printf 'postgres_integration=pass\n'
printf 'sqlite_migration=pass\n'
printf 'migration_idempotence=pass\n'
printf 'backup_restore=pass\n'
printf 'backend_test_suite=pass\n'
printf 'pip_check=pass\n'
printf 'cleanup=pass\n'
