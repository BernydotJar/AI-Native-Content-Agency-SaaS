from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Callable, Union

from .memory import utc_now
from .models import ExecutionRun
from .serialization import execution_run_from_document, execution_run_to_document
from .utils import canonical_json


Clock = Callable[[], str]


class SQLiteRunStore:
    """Tenant-scoped durable store for complete execution and approval state."""

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
                """
            )

    def create(self, tenant_id: str, run: ExecutionRun) -> ExecutionRun:
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
        except sqlite3.IntegrityError as error:
            raise ValueError(
                "run already exists for tenant: {}".format(run.run_id)
            ) from error
        return run

    def save(self, tenant_id: str, run: ExecutionRun) -> ExecutionRun:
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

    def close(self) -> None:
        with self._lock:
            self._connection.close()
