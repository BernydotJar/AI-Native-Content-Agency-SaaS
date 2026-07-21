#!/usr/bin/env python3
"""Create and restore checksummed SQLite/PostgreSQL runtime backups."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import uuid
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, quote, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_SCHEMA = "agency-runtime-backup.v1"
TOOL_NAME = "manage-runtime-backup"
ALLOWED_POSTGRES_OPTIONS = {"application_name", "sslmode", "sslrootcert"}
ALLOWED_SSL_MODES = {"disable", "prefer", "require", "verify-ca", "verify-full"}
MAX_MANIFEST_BYTES = 64 * 1024
DEFAULT_COMMAND_TIMEOUT_SECONDS = 3600
MAX_COMMAND_TIMEOUT_SECONDS = 24 * 60 * 60
MANIFEST_FIELDS = {
    "schema_version",
    "backend",
    "created_at",
    "backup_file",
    "bytes",
    "sha256",
    "validation",
    "source_identifier_sha256",
    "tool",
}
VALIDATION_BY_BACKEND = {
    "sqlite": "integrity_check_ok",
    "postgresql": "pg_restore_list_ok",
}
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
ENVIRONMENT_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")


class BackupError(RuntimeError):
    """A fail-closed backup or restore validation error."""


def tool_version() -> str:
    path = ROOT / "backend/agency_runtime/version.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for statement in tree.body:
        if not isinstance(statement, ast.Assign):
            continue
        if any(
            isinstance(target, ast.Name) and target.id == "VERSION"
            for target in statement.targets
        ):
            value = ast.literal_eval(statement.value)
            if isinstance(value, str):
                return value
    raise BackupError("runtime version metadata is unavailable")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def ensure_directory(path: Path) -> Path:
    if path.is_symlink():
        raise BackupError("output directory must not be a symlink")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not path.is_dir():
        raise BackupError("output path is not a directory")
    return path.resolve()


def sqlite_uri(path: Path) -> str:
    return "file:{}?mode=ro".format(quote(str(path.resolve()), safe="/"))


def sqlite_integrity(path: Path) -> None:
    if not path.is_file():
        raise BackupError("SQLite backup file is missing")
    try:
        with sqlite3.connect(sqlite_uri(path), uri=True) as connection:
            rows = connection.execute("PRAGMA integrity_check").fetchall()
    except sqlite3.Error as error:
        raise BackupError("SQLite integrity validation failed") from error
    if rows != [("ok",)]:
        raise BackupError("SQLite integrity validation did not return ok")


def fsync_file(path: Path) -> None:
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
        fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_text(path: Path, content: str) -> None:
    destination = path.parent
    if destination.exists():
        if destination.is_symlink() or not destination.is_dir():
            raise BackupError("metrics directory must be a regular directory")
    else:
        destination.mkdir(mode=0o700, parents=True, exist_ok=False)
        os.chmod(destination, 0o700)
    resolved = destination / path.name
    if resolved.is_symlink():
        raise BackupError("metrics file must not be a symlink")
    temporary = resolved.with_name(f".{resolved.name}.{uuid.uuid4().hex}.tmp")
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, resolved)
        os.chmod(resolved, 0o600)
        fsync_directory(destination)
    finally:
        temporary.unlink(missing_ok=True)


def write_backup_metrics(metrics_path: Path | str, manifest_path: Path | str) -> None:
    path = Path(manifest_path)
    if path.is_symlink() or not path.is_file():
        raise BackupError("backup manifest must be an existing regular file")
    if path.stat().st_size > MAX_MANIFEST_BYTES:
        raise BackupError("backup manifest exceeds the maximum size")
    try:
        candidate = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BackupError("backup manifest is not valid JSON") from error
    backend = candidate.get("backend") if isinstance(candidate, dict) else None
    if backend not in VALIDATION_BY_BACKEND:
        raise BackupError("backup manifest backend is unsupported")
    manifest, _ = load_and_verify_manifest(path, expected_backend=str(backend))
    created_at = datetime.fromisoformat(
        str(manifest["created_at"]).replace("Z", "+00:00")
    )
    timestamp = int(created_at.timestamp())
    content = "\n".join(
        (
            "# HELP agency_backup_last_success_timestamp_seconds "
            "Unix timestamp of the last validated backup.",
            "# TYPE agency_backup_last_success_timestamp_seconds gauge",
            'agency_backup_last_success_timestamp_seconds{{backend="{}"}} {}'.format(
                backend, timestamp
            ),
            "# HELP agency_backup_artifact_bytes Size of the last validated backup artifact.",
            "# TYPE agency_backup_artifact_bytes gauge",
            'agency_backup_artifact_bytes{{backend="{}"}} {}'.format(
                backend, manifest["bytes"]
            ),
            "# HELP agency_backup_success Last backup command success marker.",
            "# TYPE agency_backup_success gauge",
            'agency_backup_success{{backend="{}"}} 1'.format(backend),
            "",
        )
    )
    atomic_text(Path(metrics_path), content)


def backup_stem(backend: str, now: datetime) -> str:
    if now.tzinfo is None:
        raise BackupError("backup timestamp must be timezone-aware")
    timestamp = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"agency-{backend}-{timestamp}-{uuid.uuid4().hex[:12]}"


def build_manifest(
    *,
    backend: str,
    backup_path: Path,
    source_identifier_sha256: str,
    now: datetime,
) -> dict[str, Any]:
    if not HEX_64.fullmatch(source_identifier_sha256):
        raise BackupError("source identifier digest is invalid")
    return {
        "schema_version": MANIFEST_SCHEMA,
        "backend": backend,
        "created_at": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "backup_file": backup_path.name,
        "bytes": backup_path.stat().st_size,
        "sha256": sha256_file(backup_path),
        "validation": VALIDATION_BY_BACKEND[backend],
        "source_identifier_sha256": source_identifier_sha256,
        "tool": {"name": TOOL_NAME, "version": tool_version()},
    }


def create_sqlite_backup(
    database: Path | str,
    output_dir: Path | str,
    *,
    now: datetime | None = None,
) -> Path:
    source = Path(database)
    if source.is_symlink() or not source.is_file():
        raise BackupError("SQLite source must be an existing regular file")
    destination = ensure_directory(Path(output_dir))
    created_at = now or utc_now()
    stem = backup_stem("sqlite", created_at)
    final_backup = destination / f"{stem}.sqlite3"
    temporary_backup = destination / f".{stem}.tmp"
    manifest_path = destination / f"{stem}.manifest.json"

    try:
        os.close(os.open(temporary_backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
        with sqlite3.connect(sqlite_uri(source), uri=True) as source_connection:
            source_connection.execute("PRAGMA query_only = ON")
            with sqlite3.connect(temporary_backup) as target_connection:
                source_connection.backup(target_connection, pages=1000, sleep=0.01)
        sqlite_integrity(temporary_backup)
        fsync_file(temporary_backup)
        os.replace(temporary_backup, final_backup)
        os.chmod(final_backup, 0o600)
        fsync_directory(destination)
        manifest = build_manifest(
            backend="sqlite",
            backup_path=final_backup,
            source_identifier_sha256=sha256_text(f"sqlite:{source.resolve()}"),
            now=created_at,
        )
        atomic_json(manifest_path, manifest)
        return manifest_path
    except BackupError:
        final_backup.unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)
        raise
    except (OSError, sqlite3.Error) as error:
        final_backup.unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)
        raise BackupError("SQLite backup creation failed") from error
    finally:
        temporary_backup.unlink(missing_ok=True)


def parse_timestamp(value: Any) -> None:
    if not isinstance(value, str):
        raise BackupError("backup manifest created_at must be a string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise BackupError("backup manifest created_at is invalid") from error
    if parsed.tzinfo is None:
        raise BackupError("backup manifest created_at must include a timezone")


def load_and_verify_manifest(
    manifest_path: Path | str,
    *,
    expected_backend: str,
) -> tuple[dict[str, Any], Path]:
    path = Path(manifest_path)
    if path.is_symlink() or not path.is_file():
        raise BackupError("backup manifest must be an existing regular file")
    if path.stat().st_size > MAX_MANIFEST_BYTES:
        raise BackupError("backup manifest exceeds the maximum size")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BackupError("backup manifest is not valid JSON") from error
    if not isinstance(manifest, dict):
        raise BackupError("backup manifest must be a JSON object")
    missing = sorted(MANIFEST_FIELDS - set(manifest))
    unexpected = sorted(set(manifest) - MANIFEST_FIELDS)
    if missing:
        raise BackupError(f"backup manifest missing fields: {', '.join(missing)}")
    if unexpected:
        raise BackupError(f"backup manifest has unexpected fields: {', '.join(unexpected)}")
    if manifest["schema_version"] != MANIFEST_SCHEMA:
        raise BackupError("backup manifest schema version is unsupported")
    if manifest["backend"] != expected_backend:
        raise BackupError("backup manifest backend does not match restore operation")
    if manifest["validation"] != VALIDATION_BY_BACKEND.get(expected_backend):
        raise BackupError("backup manifest validation marker is invalid")
    parse_timestamp(manifest["created_at"])

    backup_name = manifest["backup_file"]
    if (
        not isinstance(backup_name, str)
        or len(backup_name.encode("utf-8")) > 255
        or Path(backup_name).name != backup_name
    ):
        raise BackupError("backup_file must be a basename next to the manifest")
    backup_path = path.parent / backup_name
    if backup_path.is_symlink() or not backup_path.is_file():
        raise BackupError("backup file must be an existing regular file")
    size = manifest["bytes"]
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise BackupError("backup manifest bytes must be a positive integer")
    if backup_path.stat().st_size != size:
        raise BackupError("backup size mismatch")
    checksum = manifest["sha256"]
    if not isinstance(checksum, str) or not HEX_64.fullmatch(checksum):
        raise BackupError("backup manifest checksum is invalid")
    if sha256_file(backup_path) != checksum:
        raise BackupError("backup checksum mismatch")
    source_hash = manifest["source_identifier_sha256"]
    if not isinstance(source_hash, str) or not HEX_64.fullmatch(source_hash):
        raise BackupError("backup source identifier digest is invalid")
    tool = manifest["tool"]
    if not isinstance(tool, dict) or set(tool) != {"name", "version"}:
        raise BackupError("backup manifest tool metadata is invalid")
    if (
        tool["name"] != TOOL_NAME
        or not isinstance(tool["version"], str)
        or not SEMVER.fullmatch(tool["version"])
    ):
        raise BackupError("backup manifest tool metadata is unsupported")
    return manifest, backup_path


def restore_sqlite_backup(
    manifest_path: Path | str,
    target: Path | str,
    *,
    replace: bool = False,
) -> dict[str, Any]:
    manifest, backup_path = load_and_verify_manifest(
        manifest_path, expected_backend="sqlite"
    )
    sqlite_integrity(backup_path)
    target_path = Path(target)
    if target_path.is_symlink():
        raise BackupError("SQLite restore target must not be a symlink")
    if target_path.exists() and not replace:
        raise BackupError("SQLite restore target already exists; explicit replace is required")
    sidecars = [Path(f"{target_path}-wal"), Path(f"{target_path}-shm")]
    if any(path.exists() for path in sidecars):
        raise BackupError("SQLite restore target has an active sidecar; stop the application first")
    parent = ensure_directory(target_path.parent)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".agency-restore-", dir=parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    os.chmod(temporary, 0o600)
    installed = False
    try:
        with sqlite3.connect(sqlite_uri(backup_path), uri=True) as source_connection:
            source_connection.execute("PRAGMA query_only = ON")
            with sqlite3.connect(temporary) as target_connection:
                source_connection.backup(target_connection, pages=1000, sleep=0.01)
        sqlite_integrity(temporary)
        fsync_file(temporary)
        os.replace(temporary, target_path)
        installed = True
        os.chmod(target_path, 0o600)
        fsync_directory(parent)
    except (OSError, sqlite3.Error) as error:
        if installed:
            raise BackupError(
                "SQLite restore was installed but its durability flush failed; inspect the target"
            ) from error
        raise BackupError("SQLite restore failed before atomic replacement") from error
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "status": "restored",
        "backend": "sqlite",
        "target": str(target_path),
        "sha256": manifest["sha256"],
    }


def postgres_environment(connection_url: str) -> tuple[dict[str, str], str]:
    try:
        parsed = urlsplit(connection_url)
    except ValueError as error:
        raise BackupError("PostgreSQL connection URL is invalid") from error
    if parsed.scheme not in {"postgresql", "postgres"}:
        raise BackupError("PostgreSQL connection URL must use postgresql:// or postgres://")
    if parsed.fragment:
        raise BackupError("PostgreSQL connection URL must not contain a fragment")
    if not parsed.username:
        raise BackupError("PostgreSQL connection URL must include a username")
    query: dict[str, str] = {}
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key in query:
            raise BackupError("PostgreSQL connection URL contains a duplicate option")
        query[key] = value
    if set(query) - ALLOWED_POSTGRES_OPTIONS:
        raise BackupError("unsupported PostgreSQL connection URL option")
    sslmode = query.get("sslmode", "prefer").lower()
    if sslmode not in ALLOWED_SSL_MODES:
        raise BackupError("unsupported PostgreSQL sslmode")
    sslrootcert = query.get("sslrootcert")
    if sslrootcert and sslmode not in {"verify-ca", "verify-full"}:
        raise BackupError("sslrootcert requires verify-ca or verify-full")
    try:
        port = parsed.port or 5432
    except ValueError as error:
        raise BackupError("PostgreSQL connection URL contains an invalid port") from error
    username = unquote(parsed.username)
    database = unquote(parsed.path.lstrip("/")) or username
    host = parsed.hostname or "localhost"
    password = unquote(parsed.password) if parsed.password is not None else ""
    application_name = query.get("application_name") or "ai-native-agency-backup"
    components = (username, database, host, password, application_name, sslrootcert or "")
    if any(any(ord(character) < 32 or ord(character) == 127 for character in value) for value in components):
        raise BackupError("PostgreSQL connection URL contains a control character")

    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("PG")
    }
    environment.update(
        {
            "PGHOST": host,
            "PGPORT": str(port),
            "PGUSER": username,
            "PGDATABASE": database,
            "PGSSLMODE": sslmode,
            "PGAPPNAME": application_name,
            "PGCONNECT_TIMEOUT": "15",
            "PGPASSFILE": os.devnull,
        }
    )
    if password:
        environment["PGPASSWORD"] = password
    else:
        environment.pop("PGPASSWORD", None)
    if sslrootcert:
        environment["PGSSLROOTCERT"] = sslrootcert
    else:
        environment.pop("PGSSLROOTCERT", None)
    source_identifier = f"postgresql:{username}@{host}:{port}/{database}"
    return environment, sha256_text(source_identifier)


def connection_from_environment(name: str) -> tuple[dict[str, str], str]:
    if not ENVIRONMENT_NAME.fullmatch(name):
        raise BackupError("database URL environment variable name is invalid")
    value = os.environ.get(name)
    if not value:
        raise BackupError("database URL environment variable is not configured")
    return postgres_environment(value)


def postgres_backup_command(output_path: Path) -> list[str]:
    return [
        "pg_dump",
        "--format=custom",
        "--no-owner",
        "--no-privileges",
        "--file",
        str(output_path),
    ]


def postgres_restore_command(database: str) -> list[str]:
    return [
        "pg_restore",
        "--exit-on-error",
        "--single-transaction",
        "--no-owner",
        "--no-privileges",
        "--dbname",
        database,
    ]


def redact_output(value: str, environment: Mapping[str, str]) -> str:
    redacted = value
    password = environment.get("PGPASSWORD")
    if password:
        redacted = redacted.replace(password, "[REDACTED]")
    return redacted.strip()[:2000]


def command_timeout_seconds(environment: Mapping[str, str]) -> int:
    raw = environment.get(
        "AGENCY_BACKUP_COMMAND_TIMEOUT_SECONDS",
        str(DEFAULT_COMMAND_TIMEOUT_SECONDS),
    )
    try:
        timeout = int(raw)
    except (TypeError, ValueError) as error:
        raise BackupError("backup command timeout must be an integer") from error
    if timeout < 1 or timeout > MAX_COMMAND_TIMEOUT_SECONDS:
        raise BackupError(
            "backup command timeout must be between 1 and {} seconds".format(
                MAX_COMMAND_TIMEOUT_SECONDS
            )
        )
    return timeout


def run_command(command: Sequence[str], environment: Mapping[str, str]) -> str:
    actual_command = list(command)
    try:
        result = subprocess.run(
            actual_command,
            env=dict(environment),
            capture_output=True,
            text=True,
            check=False,
            timeout=command_timeout_seconds(environment),
        )
    except subprocess.TimeoutExpired as error:
        raise BackupError(
            f"{actual_command[0]} exceeded the configured command timeout"
        ) from error
    except FileNotFoundError as error:
        raise BackupError(f"required PostgreSQL tool is unavailable: {actual_command[0]}") from error
    if result.returncode != 0:
        detail = redact_output(result.stderr or result.stdout, environment)
        suffix = f": {detail}" if detail else ""
        raise BackupError(
            f"{actual_command[0]} failed with exit code {result.returncode}{suffix}"
        )
    return result.stdout


def postgres_query(environment: Mapping[str, str], query: str) -> str:
    return run_command(
        [
            "psql",
            "--no-psqlrc",
            "--tuples-only",
            "--no-align",
            "--set=ON_ERROR_STOP=1",
            "--command",
            query,
        ],
        environment,
    ).strip()


def runtime_schema_version(environment: Mapping[str, str]) -> str:
    return postgres_query(
        environment,
        "SELECT value FROM public.runtime_schema_meta WHERE key = 'schema_version';",
    )


def non_system_table_count(environment: Mapping[str, str]) -> int:
    output = postgres_query(
        environment,
        "SELECT COUNT(*) FROM pg_catalog.pg_tables "
        "WHERE schemaname NOT IN ('pg_catalog', 'information_schema');",
    )
    try:
        return int(output)
    except ValueError as error:
        raise BackupError("PostgreSQL table-count validation returned an invalid result") from error


def create_postgresql_backup(
    database_url_environment: str,
    output_dir: Path | str,
    *,
    now: datetime | None = None,
) -> Path:
    environment, source_hash = connection_from_environment(database_url_environment)
    if runtime_schema_version(environment) != "1":
        raise BackupError("PostgreSQL runtime schema version is unsupported for backup")
    destination = ensure_directory(Path(output_dir))
    created_at = now or utc_now()
    stem = backup_stem("postgresql", created_at)
    final_backup = destination / f"{stem}.dump"
    temporary_backup = destination / f".{stem}.tmp"
    manifest_path = destination / f"{stem}.manifest.json"
    try:
        run_command(postgres_backup_command(temporary_backup), environment)
        listing = run_command(["pg_restore", "--list", str(temporary_backup)], environment)
        if "runtime_schema_meta" not in listing:
            raise BackupError("PostgreSQL backup does not contain runtime schema metadata")
        if not temporary_backup.is_file() or temporary_backup.stat().st_size <= 0:
            raise BackupError("PostgreSQL backup file was not created")
        os.chmod(temporary_backup, 0o600)
        fsync_file(temporary_backup)
        os.replace(temporary_backup, final_backup)
        fsync_directory(destination)
        manifest = build_manifest(
            backend="postgresql",
            backup_path=final_backup,
            source_identifier_sha256=source_hash,
            now=created_at,
        )
        atomic_json(manifest_path, manifest)
        return manifest_path
    except BackupError:
        final_backup.unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)
        raise
    except OSError as error:
        final_backup.unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)
        raise BackupError("PostgreSQL backup creation failed") from error
    finally:
        temporary_backup.unlink(missing_ok=True)


def restore_postgresql_backup(
    manifest_path: Path | str,
    database_url_environment: str,
) -> dict[str, Any]:
    manifest, backup_path = load_and_verify_manifest(
        manifest_path, expected_backend="postgresql"
    )
    environment, _ = connection_from_environment(database_url_environment)
    table_count = non_system_table_count(environment)
    if table_count != 0:
        raise BackupError("PostgreSQL restore target must contain zero non-system tables")
    run_command(
        postgres_restore_command(environment["PGDATABASE"]) + [str(backup_path)],
        environment,
    )
    if runtime_schema_version(environment) != "1":
        raise BackupError("restored PostgreSQL runtime schema version is invalid")
    restored_tables = non_system_table_count(environment)
    if restored_tables <= 0:
        raise BackupError("PostgreSQL restore produced no runtime tables")
    return {
        "status": "restored",
        "backend": "postgresql",
        "tables": restored_tables,
        "sha256": manifest["sha256"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    sqlite_backup = commands.add_parser("sqlite-backup")
    sqlite_backup.add_argument("--database", type=Path, required=True)
    sqlite_backup.add_argument("--output-dir", type=Path, required=True)
    sqlite_backup.add_argument("--metrics-file", type=Path)

    sqlite_restore = commands.add_parser("sqlite-restore")
    sqlite_restore.add_argument("--manifest", type=Path, required=True)
    sqlite_restore.add_argument("--target", type=Path, required=True)
    sqlite_restore.add_argument("--replace", action="store_true")

    postgres_backup = commands.add_parser("postgres-backup")
    postgres_backup.add_argument(
        "--database-url-env", default="AGENCY_DATABASE_URL"
    )
    postgres_backup.add_argument("--output-dir", type=Path, required=True)
    postgres_backup.add_argument("--metrics-file", type=Path)

    postgres_restore = commands.add_parser("postgres-restore")
    postgres_restore.add_argument("--manifest", type=Path, required=True)
    postgres_restore.add_argument(
        "--database-url-env", default="AGENCY_RESTORE_DATABASE_URL"
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        if arguments.command == "sqlite-backup":
            manifest = create_sqlite_backup(arguments.database, arguments.output_dir)
            if arguments.metrics_file is not None:
                write_backup_metrics(arguments.metrics_file, manifest)
            result: Mapping[str, Any] = {
                "status": "created",
                "backend": "sqlite",
                "manifest": str(manifest),
                "metrics_file": (
                    str(arguments.metrics_file)
                    if arguments.metrics_file is not None
                    else None
                ),
            }
        elif arguments.command == "sqlite-restore":
            result = restore_sqlite_backup(
                arguments.manifest, arguments.target, replace=arguments.replace
            )
        elif arguments.command == "postgres-backup":
            manifest = create_postgresql_backup(
                arguments.database_url_env, arguments.output_dir
            )
            if arguments.metrics_file is not None:
                write_backup_metrics(arguments.metrics_file, manifest)
            result = {
                "status": "created",
                "backend": "postgresql",
                "manifest": str(manifest),
                "metrics_file": (
                    str(arguments.metrics_file)
                    if arguments.metrics_file is not None
                    else None
                ),
            }
        else:
            result = restore_postgresql_backup(
                arguments.manifest, arguments.database_url_env
            )
    except BackupError as error:
        print("backup_status=fail", file=sys.stderr)
        print(f"error={error}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
