#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from agency_runtime.postgres import PostgresRuntimeDatabase, _datetime
from agency_runtime.utils import canonical_json

TABLES = (
    "runtime_runs",
    "audit_events",
    "runtime_sessions",
    "authentication_failures",
    "memories",
)
TARGET_TABLES = (
    "runtime_runs",
    "audit_events",
    "runtime_sessions",
    "authentication_rate_limits",
    "memories",
)


def source_connection(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError("SQLite database does not exist: {}".format(path))
    connection = sqlite3.connect("file:{}?mode=ro".format(path), uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def source_tables(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {str(row["name"]) for row in rows}


def rows(connection: sqlite3.Connection, table: str) -> list[sqlite3.Row]:
    if table not in source_tables(connection):
        return []
    return connection.execute("SELECT * FROM {}".format(table)).fetchall()


def source_counts(connection: sqlite3.Connection) -> dict[str, int]:
    available = source_tables(connection)
    return {
        table: (
            int(connection.execute("SELECT COUNT(*) FROM {}".format(table)).fetchone()[0])
            if table in available
            else 0
        )
        for table in TABLES
    }


def target_counts(database: PostgresRuntimeDatabase) -> dict[str, int]:
    with database.pool.connection() as connection:
        return {
            table: int(
                connection.execute(
                    "SELECT COUNT(*) AS total FROM {}".format(table)
                ).fetchone()["total"]
            )
            for table in TARGET_TABLES
        }


def parsed_json(value: object, *, expected: type) -> Any:
    parsed = json.loads(str(value))
    if not isinstance(parsed, expected):
        raise ValueError("expected {} JSON".format(expected.__name__))
    return parsed


def require_empty_target(counts: Mapping[str, int]) -> None:
    populated = {table: count for table, count in counts.items() if count}
    if populated:
        raise RuntimeError(
            "PostgreSQL target must be empty before migration: {}".format(
                json.dumps(populated, sort_keys=True)
            )
        )


def migrate_runs(
    source: sqlite3.Connection, target: Any
) -> int:
    records = rows(source, "runtime_runs")
    for row in records:
        target.execute(
            """
            INSERT INTO runtime_runs(
                tenant_id, run_id, status, document_json, version,
                created_at, updated_at
            ) VALUES (%s, %s, %s, CAST(%s AS jsonb), 1, %s, %s)
            """,
            (
                row["tenant_id"],
                row["run_id"],
                row["status"],
                canonical_json(parsed_json(row["document_json"], expected=dict)),
                _datetime(str(row["created_at"])),
                _datetime(str(row["updated_at"])),
            ),
        )
    return len(records)


def migrate_audit(
    source: sqlite3.Connection, target: Any
) -> int:
    records = rows(source, "audit_events")
    for row in records:
        target.execute(
            """
            INSERT INTO audit_events(
                sequence, event_id, tenant_id, request_id, occurred_at, action,
                resource_type, resource_id, actor, payload_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CAST(%s AS jsonb))
            """,
            (
                row["sequence"],
                row["event_id"],
                row["tenant_id"],
                row["request_id"],
                _datetime(str(row["occurred_at"])),
                row["action"],
                row["resource_type"],
                row["resource_id"],
                row["actor"],
                canonical_json(parsed_json(row["payload_json"], expected=dict)),
            ),
        )
    target.execute(
        """
        SELECT setval(
            pg_get_serial_sequence('audit_events', 'sequence'),
            COALESCE((SELECT MAX(sequence) FROM audit_events), 1),
            EXISTS (SELECT 1 FROM audit_events)
        )
        """
    )
    return len(records)


def migrate_sessions(
    source: sqlite3.Connection, target: Any
) -> int:
    records = rows(source, "runtime_sessions")
    columns = {
        str(row["name"])
        for row in source.execute("PRAGMA table_info(runtime_sessions)").fetchall()
    }
    for row in records:
        tenant_id = str(row["tenant_id"])
        subject_id = (
            str(row["subject_id"])
            if "subject_id" in columns and row["subject_id"]
            else "tenant:{}".format(tenant_id)
        )
        role = (
            str(row["role"])
            if "role" in columns and row["role"]
            else "admin"
        )
        key_id = (
            str(row["key_id"])
            if "key_id" in columns and row["key_id"]
            else "legacy:{}".format(tenant_id)
        )
        target.execute(
            """
            INSERT INTO runtime_sessions(
                session_id, tenant_id, session_token_hash, csrf_token_hash,
                credential_fingerprint, subject_id, role, key_id,
                created_at, expires_at, revoked_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                row["session_id"],
                tenant_id,
                row["session_token_hash"],
                row["csrf_token_hash"],
                row["credential_fingerprint"],
                subject_id,
                role,
                key_id,
                _datetime(str(row["created_at"])),
                _datetime(str(row["expires_at"])),
                (
                    _datetime(str(row["revoked_at"]))
                    if row["revoked_at"] is not None
                    else None
                ),
            ),
        )
    return len(records)


def migrate_rate_limits(
    source: sqlite3.Connection, target: Any
) -> tuple[int, int]:
    records = rows(source, "authentication_failures")
    grouped: dict[str, list[str]] = {}
    for row in records:
        grouped.setdefault(str(row["bucket_hash"]), []).append(
            str(row["occurred_at"])
        )
    for bucket_hash, occurred_values in grouped.items():
        target.execute(
            """
            INSERT INTO authentication_rate_limits(
                bucket_hash, window_started_at, failure_count
            ) VALUES (%s, %s, %s)
            """,
            (
                bucket_hash,
                min(_datetime(value) for value in occurred_values),
                len(occurred_values),
            ),
        )
    return len(records), len(grouped)


def migrate_memories(
    source: sqlite3.Connection, target: Any
) -> int:
    records = rows(source, "memories")
    if not records:
        return 0
    columns = {
        str(row["name"])
        for row in source.execute("PRAGMA table_info(memories)").fetchall()
    }
    for row in records:
        namespace = (
            str(row["namespace"])
            if "namespace" in columns and row["namespace"]
            else "default"
        )
        target.execute(
            """
            INSERT INTO memories(
                namespace, memory_id, observation_id, content, provenance_json,
                confidence, tags_json, observed_at, stored_at
            ) VALUES (%s, %s, %s, %s, CAST(%s AS jsonb), %s, CAST(%s AS jsonb), %s, %s)
            """,
            (
                namespace,
                row["memory_id"],
                row["observation_id"],
                row["content"],
                canonical_json(parsed_json(row["provenance_json"], expected=dict)),
                row["confidence"],
                canonical_json(parsed_json(row["tags_json"], expected=list)),
                _datetime(str(row["observed_at"])),
                _datetime(str(row["stored_at"])),
            ),
        )
    return len(records)


def verify_migration(
    source_summary: Mapping[str, int],
    target_summary: Mapping[str, int],
    migrated_failure_events: int,
    database: PostgresRuntimeDatabase,
) -> None:
    mappings = {
        "runtime_runs": "runtime_runs",
        "audit_events": "audit_events",
        "runtime_sessions": "runtime_sessions",
        "memories": "memories",
    }
    mismatches = {
        source_table: {
            "source": source_summary[source_table],
            "target": target_summary[target_table],
        }
        for source_table, target_table in mappings.items()
        if source_summary[source_table] != target_summary[target_table]
    }
    with database.pool.connection() as connection:
        row = connection.execute(
            "SELECT COALESCE(SUM(failure_count), 0) AS total FROM authentication_rate_limits"
        ).fetchone()
    target_failure_events = int(row["total"])
    if target_failure_events != migrated_failure_events:
        mismatches["authentication_failures"] = {
            "source": migrated_failure_events,
            "target": target_failure_events,
        }
    if mismatches:
        raise RuntimeError(
            "migration count verification failed: {}".format(
                json.dumps(mismatches, sort_keys=True)
            )
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate an AI Native Content Agency SQLite database to an empty PostgreSQL database."
    )
    parser.add_argument("--sqlite", required=True, type=Path)
    parser.add_argument(
        "--postgres-url-env",
        default="AGENCY_DATABASE_URL",
        help="Environment variable containing the postgresql:// URL.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the migration. Without this flag only a read-only plan is printed.",
    )
    args = parser.parse_args()

    postgres_url = os.environ.get(args.postgres_url_env, "").strip()
    if not postgres_url:
        raise ValueError(
            "{} must contain the PostgreSQL connection URL".format(
                args.postgres_url_env
            )
        )

    source = source_connection(args.sqlite.resolve())
    database = PostgresRuntimeDatabase(postgres_url, min_size=1, max_size=2)
    try:
        source_summary = source_counts(source)
        before = target_counts(database)
        require_empty_target(before)
        plan = {
            "mode": "apply" if args.apply else "dry-run",
            "status": "pending" if args.apply else "validated",
            "sqlite": str(args.sqlite.resolve()),
            "source_counts": source_summary,
            "target_counts_before": before,
            "raw_secrets_migrated": False,
        }
        if not args.apply:
            print(json.dumps(plan, indent=2, sort_keys=True))
            return 0

        with database.pool.connection() as target:
            target.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                ("ai-native-content-agency-sqlite-migration-v1",),
            )
            require_empty_target(
                {
                    table: int(
                        target.execute(
                            "SELECT COUNT(*) AS total FROM {}".format(table)
                        ).fetchone()["total"]
                    )
                    for table in TARGET_TABLES
                }
            )
            migrated = {
                "runtime_runs": migrate_runs(source, target),
                "audit_events": migrate_audit(source, target),
                "runtime_sessions": migrate_sessions(source, target),
                "memories": migrate_memories(source, target),
            }
            failure_events, failure_buckets = migrate_rate_limits(source, target)
            migrated["authentication_failure_events"] = failure_events
            migrated["authentication_rate_limit_buckets"] = failure_buckets

        after = target_counts(database)
        verify_migration(source_summary, after, failure_events, database)
        result = {
            **plan,
            "status": "pass",
            "migrated": migrated,
            "target_counts_after": after,
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    finally:
        source.close()
        database.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print("migration failed: {}".format(error), file=sys.stderr)
        sys.exit(1)
