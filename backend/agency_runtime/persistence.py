from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta
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


@dataclass(frozen=True)
class SessionIssue:
    session_id: str
    session_token: str
    csrf_token: str
    tenant_id: str
    credential_fingerprint: str
    expires_at: str


@dataclass(frozen=True)
class SessionRecord:
    session_id: str
    tenant_id: str
    credential_fingerprint: str
    created_at: str
    expires_at: str
    revoked_at: Optional[str]


class SessionAuthenticationError(PermissionError):
    pass


class SessionCsrfError(PermissionError):
    pass


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

                CREATE TABLE IF NOT EXISTS runtime_sessions (
                    session_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    session_token_hash TEXT NOT NULL UNIQUE,
                    csrf_token_hash TEXT NOT NULL,
                    credential_fingerprint TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_runtime_sessions_tenant
                    ON runtime_sessions(tenant_id, expires_at DESC);
                CREATE INDEX IF NOT EXISTS idx_runtime_sessions_active
                    ON runtime_sessions(session_token_hash, revoked_at, expires_at);
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

    def create_session(
        self,
        tenant_id: str,
        credential_fingerprint: str,
        ttl_seconds: int,
        request_id: str,
        actor: str,
    ) -> SessionIssue:
        if ttl_seconds < 300 or ttl_seconds > 86400:
            raise ValueError("session ttl must be between 300 and 86400 seconds")
        created_at = self._clock()
        expires_at = (
            datetime.fromisoformat(created_at) + timedelta(seconds=ttl_seconds)
        ).isoformat()
        session_id = "session-{}".format(uuid.uuid4().hex)
        session_token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO runtime_sessions(
                    session_id, tenant_id, session_token_hash, csrf_token_hash,
                    credential_fingerprint, created_at, expires_at, revoked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    session_id,
                    tenant_id,
                    self._token_hash(session_token),
                    self._token_hash(csrf_token),
                    credential_fingerprint,
                    created_at,
                    expires_at,
                ),
            )
            self._append_audit_locked(
                tenant_id,
                AuditWrite(
                    request_id=request_id,
                    action="session.created",
                    resource_type="browser_session",
                    resource_id=session_id,
                    actor=actor,
                    payload={
                        "auth_method": "http_only_cookie",
                        "expires_at": expires_at,
                    },
                ),
            )
        return SessionIssue(
            session_id=session_id,
            session_token=session_token,
            csrf_token=csrf_token,
            tenant_id=tenant_id,
            credential_fingerprint=credential_fingerprint,
            expires_at=expires_at,
        )

    def authenticate_session(self, session_token: str) -> SessionRecord:
        if not session_token:
            raise SessionAuthenticationError("browser session is missing")
        token_hash = self._token_hash(session_token)
        with self._lock:
            row = self._connection.execute(
                """
                SELECT * FROM runtime_sessions
                WHERE session_token_hash = ?
                """,
                (token_hash,),
            ).fetchone()
        if row is None or not hmac.compare_digest(
            token_hash, str(row["session_token_hash"])
        ):
            raise SessionAuthenticationError("browser session is invalid")
        if row["revoked_at"] is not None:
            raise SessionAuthenticationError("browser session is revoked")
        if datetime.fromisoformat(str(row["expires_at"])) <= datetime.fromisoformat(
            self._clock()
        ):
            raise SessionAuthenticationError("browser session is expired")
        return self._row_to_session_record(row)

    def rotate_session_csrf(self, session_id: str) -> SessionIssue:
        csrf_token = secrets.token_urlsafe(32)
        with self._lock, self._connection:
            row = self._connection.execute(
                """
                SELECT * FROM runtime_sessions WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
            if row is None or row["revoked_at"] is not None:
                raise SessionAuthenticationError("browser session is not active")
            if datetime.fromisoformat(str(row["expires_at"])) <= datetime.fromisoformat(
                self._clock()
            ):
                raise SessionAuthenticationError("browser session is expired")
            self._connection.execute(
                """
                UPDATE runtime_sessions SET csrf_token_hash = ? WHERE session_id = ?
                """,
                (self._token_hash(csrf_token), session_id),
            )
        return SessionIssue(
            session_id=str(row["session_id"]),
            session_token="",
            csrf_token=csrf_token,
            tenant_id=str(row["tenant_id"]),
            credential_fingerprint=str(row["credential_fingerprint"]),
            expires_at=str(row["expires_at"]),
        )

    def verify_session_csrf(self, session_id: str, csrf_token: str) -> None:
        if not csrf_token:
            raise SessionCsrfError("CSRF token is required")
        with self._lock:
            row = self._connection.execute(
                """
                SELECT csrf_token_hash, expires_at, revoked_at
                FROM runtime_sessions
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
        if row is None or row["revoked_at"] is not None:
            raise SessionCsrfError("browser session is not active")
        if datetime.fromisoformat(str(row["expires_at"])) <= datetime.fromisoformat(
            self._clock()
        ):
            raise SessionCsrfError("browser session is expired")
        if not hmac.compare_digest(
            self._token_hash(csrf_token), str(row["csrf_token_hash"])
        ):
            raise SessionCsrfError("CSRF token is invalid")

    def revoke_session(
        self,
        tenant_id: str,
        session_id: str,
        request_id: str,
        actor: str,
    ) -> None:
        revoked_at = self._clock()
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """
                UPDATE runtime_sessions
                SET revoked_at = ?
                WHERE tenant_id = ? AND session_id = ? AND revoked_at IS NULL
                """,
                (revoked_at, tenant_id, session_id),
            )
            if cursor.rowcount != 1:
                raise KeyError("active browser session not found")
            self._append_audit_locked(
                tenant_id,
                AuditWrite(
                    request_id=request_id,
                    action="session.revoked",
                    resource_type="browser_session",
                    resource_id=session_id,
                    actor=actor,
                    payload={"revoked_at": revoked_at},
                ),
            )

    def session_count(self, tenant_id: str, include_revoked: bool = False) -> int:
        sql = "SELECT COUNT(*) AS total FROM runtime_sessions WHERE tenant_id = ?"
        parameters: Tuple[object, ...] = (tenant_id,)
        if not include_revoked:
            sql += " AND revoked_at IS NULL AND expires_at > ?"
            parameters = (tenant_id, self._clock())
        with self._lock:
            row = self._connection.execute(sql, parameters).fetchone()
        return int(row["total"])

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _row_to_session_record(row: sqlite3.Row) -> SessionRecord:
        return SessionRecord(
            session_id=str(row["session_id"]),
            tenant_id=str(row["tenant_id"]),
            credential_fingerprint=str(row["credential_fingerprint"]),
            created_at=str(row["created_at"]),
            expires_at=str(row["expires_at"]),
            revoked_at=(
                str(row["revoked_at"]) if row["revoked_at"] is not None else None
            ),
        )

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
