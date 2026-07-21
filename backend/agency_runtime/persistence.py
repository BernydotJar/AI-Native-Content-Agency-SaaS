from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Optional, Tuple, Union

from .memory import utc_now
from .models import ExecutionRun
from .serialization import execution_run_from_document, execution_run_to_document
from .utils import canonical_json, require_non_empty


Clock = Callable[[], str]


@dataclass(frozen=True)
class AuditWrite:
    request_id: str
    action: str
    resource_type: str
    resource_id: str
    actor: str
    payload: Mapping[str, object]

    def __post_init__(self) -> None:
        require_non_empty(self.request_id, "request_id")
        require_non_empty(self.action, "action")
        require_non_empty(self.resource_type, "resource_type")
        require_non_empty(self.resource_id, "resource_id")
        require_non_empty(self.actor, "actor")


@dataclass(frozen=True)
class AuditEvent:
    sequence: int
    event_id: str
    tenant_id: str
    request_id: str
    occurred_at: str
    action: str
    resource_type: str
    resource_id: str
    actor: str
    payload: Mapping[str, object]


class SQLiteRunStore:
    """Tenant-scoped durable run store and append-only audit ledger."""

    def __init__(
        self,
        path: Union[str, Path] = ":memory:",
        clock: Clock = utc_now,
    ) -> None:
        self.path = str(path)
        self._clock = clock
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        if self.path != ":memory:":
            self._connection.execute("PRAGMA journal_mode = WAL")
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runtime_runs (
                    tenant_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    document_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, run_id)
                );

                CREATE INDEX IF NOT EXISTS idx_runtime_runs_tenant_status
                    ON runtime_runs(tenant_id, status, updated_at DESC);

                CREATE TABLE IF NOT EXISTS audit_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    tenant_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    action TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_audit_events_tenant_sequence
                    ON audit_events(tenant_id, sequence ASC);
                CREATE INDEX IF NOT EXISTS idx_audit_events_resource
                    ON audit_events(tenant_id, resource_type, resource_id, sequence ASC);
                """
            )

    def _append_audit_locked(self, tenant_id: str, audit: AuditWrite) -> None:
        self._connection.execute(
            """
            INSERT INTO audit_events(
                event_id,
                tenant_id,
                request_id,
                occurred_at,
                action,
                resource_type,
                resource_id,
                actor,
                payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "audit-{}".format(uuid.uuid4().hex),
                tenant_id,
                audit.request_id,
                self._clock(),
                audit.action,
                audit.resource_type,
                audit.resource_id,
                audit.actor,
                canonical_json(audit.payload),
            ),
        )

    def create(
        self,
        tenant_id: str,
        run: ExecutionRun,
        audit: Optional[AuditWrite] = None,
    ) -> ExecutionRun:
        timestamp = self._clock()
        document = canonical_json(execution_run_to_document(run))
        try:
            with self._lock, self._connection:
                self._connection.execute(
                    """
                    INSERT INTO runtime_runs(
                        tenant_id, run_id, status, document_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tenant_id,
                        run.run_id,
                        run.status.value,
                        document,
                        timestamp,
                        timestamp,
                    ),
                )
                if audit is not None:
                    self._append_audit_locked(tenant_id, audit)
        except sqlite3.IntegrityError as error:
            raise ValueError(
                "run already exists for tenant: {}".format(run.run_id)
            ) from error
        return run

    def save(
        self,
        tenant_id: str,
        run: ExecutionRun,
        audit: Optional[AuditWrite] = None,
    ) -> ExecutionRun:
        document = canonical_json(execution_run_to_document(run))
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """
                UPDATE runtime_runs
                SET status = ?, document_json = ?, updated_at = ?
                WHERE tenant_id = ? AND run_id = ?
                """,
                (
                    run.status.value,
                    document,
                    self._clock(),
                    tenant_id,
                    run.run_id,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError("run not found: {}".format(run.run_id))
            if audit is not None:
                self._append_audit_locked(tenant_id, audit)
        return run

    def get(self, tenant_id: str, run_id: str) -> ExecutionRun:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT document_json
                FROM runtime_runs
                WHERE tenant_id = ? AND run_id = ?
                """,
                (tenant_id, run_id),
            ).fetchone()
        if row is None:
            raise KeyError("run not found: {}".format(run_id))
        return execution_run_from_document(json.loads(row["document_json"]))

    def exists(self, tenant_id: str, run_id: str) -> bool:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT 1 FROM runtime_runs WHERE tenant_id = ? AND run_id = ?
                """,
                (tenant_id, run_id),
            ).fetchone()
        return row is not None

    def count(self, tenant_id: str) -> int:
        with self._lock:
            row = self._connection.execute(
                "SELECT COUNT(*) AS total FROM runtime_runs WHERE tenant_id = ?",
                (tenant_id,),
            ).fetchone()
        return int(row["total"])

    def audit_events(
        self,
        tenant_id: str,
        after_sequence: int = 0,
        limit: int = 100,
    ) -> Tuple[AuditEvent, ...]:
        if after_sequence < 0:
            raise ValueError("after_sequence must not be negative")
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT *
                FROM audit_events
                WHERE tenant_id = ? AND sequence > ?
                ORDER BY sequence ASC
                LIMIT ?
                """,
                (tenant_id, after_sequence, limit),
            ).fetchall()
        return tuple(self._row_to_audit_event(row) for row in rows)

    def audit_count(self, tenant_id: str) -> int:
        with self._lock:
            row = self._connection.execute(
                "SELECT COUNT(*) AS total FROM audit_events WHERE tenant_id = ?",
                (tenant_id,),
            ).fetchone()
        return int(row["total"])

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    @staticmethod
    def _row_to_audit_event(row: sqlite3.Row) -> AuditEvent:
        return AuditEvent(
            sequence=int(row["sequence"]),
            event_id=str(row["event_id"]),
            tenant_id=str(row["tenant_id"]),
            request_id=str(row["request_id"]),
            occurred_at=str(row["occurred_at"]),
            action=str(row["action"]),
            resource_type=str(row["resource_type"]),
            resource_id=str(row["resource_id"]),
            actor=str(row["actor"]),
            payload=json.loads(row["payload_json"]),
        )
