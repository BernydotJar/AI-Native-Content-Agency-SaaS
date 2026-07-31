#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import quote, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "contracts/runtime-schema-history.json"
HEX_COMMIT = re.compile(r"^[0-9a-f]{40}$")
HISTORY_REF = re.compile(r"^refs/tags/runtime-schema-v([1-9][0-9]*)$")
DECLARATION = re.compile(r'^POSTGRES_SCHEMA_VERSION = "([0-9]+)"$', re.MULTILINE)
MANIFEST_SCHEMA = "agency-runtime-schema-history.v2"


@dataclass(frozen=True)
class SchemaVersion:
    version: int
    commit: str
    ref: str
    resolved_commit: str
    capability: str


def run(
    command: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    cwd: Path = ROOT,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        list(command), cwd=cwd, env=None if env is None else dict(env),
        capture_output=True, text=True, check=False, timeout=120,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError("command failed ({}): {}".format(" ".join(command), detail))
    return completed


def git_text(*arguments: str) -> str:
    return run(("git", *arguments)).stdout.strip()


def load_manifest(path: Path = MANIFEST) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("schema history must be a JSON object")
    return value


def validate_manifest(
    value: Mapping[str, Any], *, resolve_commits: bool = True
) -> tuple[SchemaVersion, ...]:
    if set(value) != {"schema_version", "current_version", "versions"}:
        raise ValueError("schema history fields are invalid")
    if value.get("schema_version") != MANIFEST_SCHEMA:
        raise ValueError("schema history format is unsupported")
    current = value.get("current_version")
    records = value.get("versions")
    if not isinstance(current, int) or current < 1:
        raise ValueError("current_version must be a positive integer")
    if not isinstance(records, list) or not records:
        raise ValueError("versions must be a non-empty array")

    observed: list[int] = []
    seen_commits: set[str] = set()
    versions: list[SchemaVersion] = []
    for index, item in enumerate(records, start=1):
        if not isinstance(item, dict) or set(item) != {
            "version", "commit", "ref", "capability"
        }:
            raise ValueError(f"version record {index} fields are invalid")
        version = item["version"]
        commit = item["commit"]
        ref = item["ref"]
        capability = item["capability"]
        if not isinstance(version, int) or version < 1:
            raise ValueError(f"version record {index} has invalid version")
        if not isinstance(commit, str) or not HEX_COMMIT.fullmatch(commit):
            raise ValueError(f"version {version} has invalid commit")
        if commit in seen_commits:
            raise ValueError(f"duplicate historical commit: {commit}")
        if not isinstance(ref, str) or not HISTORY_REF.fullmatch(ref):
            raise ValueError(f"version {version} has invalid history ref")
        if ref != f"refs/tags/runtime-schema-v{version}":
            raise ValueError(f"version {version} history ref is not canonical")
        if not isinstance(capability, str) or not capability.strip() or len(capability) > 200:
            raise ValueError(f"version {version} has invalid capability")
        observed.append(version)
        seen_commits.add(commit)
        resolved = commit
        if resolve_commits:
            try:
                resolved = git_text("rev-parse", f"{ref}^{{commit}}")
            except RuntimeError as error:
                raise ValueError(
                    f"canonical history ref {ref} is unavailable; fetch runtime-schema tags"
                ) from error
            if resolved != commit:
                raise ValueError(
                    f"canonical history ref {ref} resolves to {resolved}, expected {commit}"
                )
            source = git_text("show", f"{resolved}:backend/agency_runtime/postgres.py")
            match = DECLARATION.search(source)
            declared = None if match is None else int(match.group(1))
            if declared != version:
                raise ValueError(
                    f"historical commit {commit} declares schema {declared}, expected {version}"
                )
        versions.append(SchemaVersion(version, commit, ref, resolved, capability.strip()))

    expected = list(range(1, current + 1))
    if observed != expected:
        raise ValueError(
            f"schema versions must be contiguous and ordered: expected {expected}, found {observed}"
        )
    if versions[-1].version != current:
        raise ValueError("current_version does not match the last version record")
    return tuple(versions)


def extract_backend(version: SchemaVersion, destination: Path) -> Path:
    archive = destination / f"schema-v{version.version}.tar"
    source = destination / f"schema-v{version.version}"
    source.mkdir(parents=True, exist_ok=True)
    run((
        "git", "archive", "--format=tar", f"--output={archive}",
        version.resolved_commit, "backend",
    ))
    run(("tar", "-xf", str(archive), "-C", str(source)))
    archive.unlink()
    return source / "backend"


def child_environment(python_path: Path | None, **values: str) -> dict[str, str]:
    environment = dict(os.environ)
    if python_path is None:
        environment.pop("PYTHONPATH", None)
    else:
        environment["PYTHONPATH"] = str(python_path)
    environment.update(values)
    return environment


HISTORICAL_SQLITE_WRITER = r'''
import os
from agency_runtime.persistence import SQLiteRunStore, AuditWrite
version = int(os.environ["SCHEMA_VERSION_UNDER_TEST"])
store = SQLiteRunStore(os.environ["SCHEMA_DATABASE_PATH"])
try:
    store.append_audit(
        "schema-compat-tenant",
        AuditWrite(
            request_id="schema-compat-v{}".format(version),
            action="schema.compatibility.created",
            resource_type="schema_version",
            resource_id="v{}".format(version),
            actor="schema-compatibility-auditor",
            payload={"version": version},
        ),
    )
finally:
    store.close()
'''

CURRENT_SQLITE_VERIFIER = r'''
import os
from agency_runtime.persistence import SQLiteRunStore

def require(condition, message):
    if not condition:
        raise RuntimeError(message)

version = int(os.environ["SCHEMA_VERSION_UNDER_TEST"])
store = SQLiteRunStore(os.environ["SCHEMA_DATABASE_PATH"])
try:
    events = store.audit_events("schema-compat-tenant", 0, 10)
    require(len(events) == 1, "historical SQLite event cardinality changed")
    event = events[0]
    require(event.action == "schema.compatibility.created", "historical SQLite action changed")
    require(event.resource_id == "v{}".format(version), "historical SQLite resource changed")
    require(event.payload == {"version": version}, "historical SQLite payload changed")
    checkpoint = store.verify_audit_chain("schema-compat-tenant")
    require(checkpoint.event_count == 1, "historical SQLite checkpoint count changed")
    require(checkpoint.head_event_id == event.event_id, "historical SQLite checkpoint event changed")
    require(checkpoint.head_hash == event.event_hash, "historical SQLite checkpoint hash changed")
finally:
    store.close()
'''

HISTORICAL_POSTGRES_WRITER = r'''
import os
from agency_runtime.persistence import AuditWrite
from agency_runtime.postgres import PostgresRunStore, PostgresRuntimeDatabase
version = int(os.environ["SCHEMA_VERSION_UNDER_TEST"])
database = PostgresRuntimeDatabase(
    os.environ["SCHEMA_DATABASE_URL"], min_size=1, max_size=2, schema_mode="initialize"
)
store = PostgresRunStore(database)
try:
    store.append_audit(
        "schema-compat-tenant",
        AuditWrite(
            request_id="schema-compat-v{}".format(version),
            action="schema.compatibility.created",
            resource_type="schema_version",
            resource_id="v{}".format(version),
            actor="schema-compatibility-auditor",
            payload={"version": version},
        ),
    )
finally:
    store.close()
'''

CURRENT_POSTGRES_UPGRADER = r'''
import os
from agency_runtime.postgres import PostgresRuntimeDatabase
runtime = PostgresRuntimeDatabase(
    os.environ["SCHEMA_DATABASE_URL"], min_size=1, max_size=2, schema_mode="initialize"
)
runtime.close()
'''

CURRENT_POSTGRES_VERIFIER = r'''
import os
from agency_runtime.postgres import PostgresRunStore, PostgresRuntimeDatabase

def require(condition, message):
    if not condition:
        raise RuntimeError(message)

version = int(os.environ["SCHEMA_VERSION_UNDER_TEST"])
database = PostgresRuntimeDatabase(
    os.environ["SCHEMA_DATABASE_URL"], min_size=1, max_size=2, schema_mode="validate"
)
store = PostgresRunStore(database)
try:
    events = store.audit_events("schema-compat-tenant", 0, 10)
    require(len(events) == 1, "historical PostgreSQL event cardinality changed")
    event = events[0]
    require(event.action == "schema.compatibility.created", "historical PostgreSQL action changed")
    require(event.resource_id == "v{}".format(version), "historical PostgreSQL resource changed")
    require(event.payload == {"version": version}, "historical PostgreSQL payload changed")
    checkpoint = store.verify_audit_chain("schema-compat-tenant")
    require(checkpoint.event_count == 1, "historical PostgreSQL checkpoint count changed")
    require(checkpoint.head_event_id == event.event_id, "historical PostgreSQL checkpoint event changed")
    require(checkpoint.head_hash == event.event_hash, "historical PostgreSQL checkpoint hash changed")
finally:
    store.close()
'''


def current_python_path() -> Path | None:
    if os.environ.get("SCHEMA_COMPATIBILITY_USE_INSTALLED") == "1":
        return None
    return ROOT / "backend"


def run_sqlite_matrix(versions: Sequence[SchemaVersion], python: str) -> None:
    with tempfile.TemporaryDirectory(prefix="agency-schema-compat-sqlite-") as tmp:
        root = Path(tmp)
        for version in versions:
            historical_backend = extract_backend(version, root)
            database = root / f"schema-v{version.version}.sqlite3"
            values = {
                "SCHEMA_DATABASE_PATH": str(database),
                "SCHEMA_VERSION_UNDER_TEST": str(version.version),
            }
            run(
                (python, "-c", HISTORICAL_SQLITE_WRITER),
                env=child_environment(historical_backend, **values),
            )
            run(
                (python, "-c", CURRENT_SQLITE_VERIFIER),
                env=child_environment(current_python_path(), **values),
            )
            print(f"sqlite_schema_upgrade_v{version.version}=pass")


def database_url(base: str, database: str) -> str:
    parsed = urlsplit(base)
    if parsed.scheme not in {"postgresql", "postgres"} or not parsed.hostname:
        raise ValueError("PostgreSQL admin URL is invalid")
    if not parsed.username:
        raise ValueError("PostgreSQL admin URL requires a username")
    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    credentials = quote(parsed.username, safe="")
    if parsed.password is not None:
        credentials += ":" + quote(parsed.password, safe="")
    netloc = credentials + "@" + host
    if parsed.port is not None:
        netloc += f":{parsed.port}"
    return urlunsplit((parsed.scheme, netloc, "/" + database, parsed.query, ""))


def admin_execute(url: str, statement: str) -> None:
    from agency_runtime.postgres import _connect_database_url

    connection = _connect_database_url(url, timeout_seconds=15)
    try:
        connection.autocommit = True
        cursor = connection.cursor()
        cursor.execute(statement)
        cursor.close()
    finally:
        connection.close()


def run_postgres_matrix(
    versions: Sequence[SchemaVersion], python: str, admin_url: str, prefix: str
) -> None:
    parsed = urlsplit(admin_url)
    if not parsed.username:
        raise ValueError("PostgreSQL admin URL requires a username")
    with tempfile.TemporaryDirectory(prefix="agency-schema-compat-postgres-") as tmp:
        root = Path(tmp)
        for version in versions:
            historical_backend = extract_backend(version, root)
            name = f"{prefix}_v{version.version}"
            url = database_url(admin_url, name)
            admin_execute(admin_url, f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
            admin_execute(admin_url, f'CREATE DATABASE "{name}" OWNER "{parsed.username}"')
            values = {
                "SCHEMA_DATABASE_URL": url,
                "SCHEMA_VERSION_UNDER_TEST": str(version.version),
            }
            try:
                run(
                    (python, "-c", HISTORICAL_POSTGRES_WRITER),
                    env=child_environment(historical_backend, **values),
                )
                run(
                    (python, "-c", CURRENT_POSTGRES_UPGRADER),
                    env=child_environment(current_python_path(), **values),
                )
                run(
                    (python, "-c", CURRENT_POSTGRES_VERIFIER),
                    env=child_environment(current_python_path(), **values),
                )
                print(f"postgresql_schema_upgrade_v{version.version}=pass")
            finally:
                admin_execute(admin_url, f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def current_declared_version(python: str) -> int:
    completed = run(
        (
            python,
            "-c",
            "from agency_runtime.postgres import POSTGRES_SCHEMA_VERSION; print(POSTGRES_SCHEMA_VERSION)",
        ),
        env=child_environment(current_python_path()),
    )
    return int(completed.stdout.strip())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Execute the historical runtime schema compatibility matrix."
    )
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--postgres-admin-url", default="")
    parser.add_argument("--postgres-database-prefix", default="agency_schema_compat")
    parser.add_argument("--skip-sqlite", action="store_true")
    args = parser.parse_args()

    versions = validate_manifest(load_manifest(args.manifest))
    current = current_declared_version(args.python)
    if current != versions[-1].version:
        raise ValueError(
            f"current runtime schema is {current}, history ends at {versions[-1].version}"
        )
    if not args.skip_sqlite:
        run_sqlite_matrix(versions, args.python)
    if args.postgres_admin_url:
        if not re.fullmatch(r"[a-z][a-z0-9_]{2,40}", args.postgres_database_prefix):
            raise ValueError("PostgreSQL database prefix is invalid")
        run_postgres_matrix(
            versions,
            args.python,
            args.postgres_admin_url,
            args.postgres_database_prefix,
        )

    print("schema_compatibility=pass")
    print(f"current_schema_version={current}")
    print(f"historical_versions={len(versions)}")
    print(f"sqlite_matrix={'skipped' if args.skip_sqlite else 'pass'}")
    print(f"postgresql_matrix={'pass' if args.postgres_admin_url else 'not_requested'}")
    print("external_effects=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"schema compatibility verification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
