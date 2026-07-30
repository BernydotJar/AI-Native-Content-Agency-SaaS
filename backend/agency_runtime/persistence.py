from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Mapping, Optional, Tuple, Union

from .memory import utc_now
from .audit_integrity import (
    GENESIS_AUDIT_HASH,
    AuditChainCheckpoint,
    AuditIntegrityError,
    audit_event_hash,
)
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
    event_id: str = ""

    def __post_init__(self) -> None:
        require_non_empty(self.request_id, "request_id")
        require_non_empty(self.action, "action")
        require_non_empty(self.resource_type, "resource_type")
        require_non_empty(self.resource_id, "resource_id")
        require_non_empty(self.actor, "actor")
        if self.event_id:
            require_non_empty(self.event_id, "event_id")


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
    previous_hash: str
    event_hash: str


@dataclass(frozen=True)
class SessionIssue:
    session_id: str
    session_token: str
    csrf_token: str
    tenant_id: str
    subject_id: str
    role: str
    key_id: str
    credential_fingerprint: str
    expires_at: str


@dataclass(frozen=True)
class SessionRecord:
    session_id: str
    tenant_id: str
    subject_id: str
    role: str
    key_id: str
    credential_fingerprint: str
    created_at: str
    expires_at: str
    revoked_at: Optional[str]


class SessionAuthenticationError(PermissionError):
    pass


class SessionCsrfError(PermissionError):
    pass


class AuthenticationRateLimitError(PermissionError):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("authentication rate limit exceeded")
        self.retry_after_seconds = max(1, retry_after_seconds)


class AuthenticatedRequestRateLimitError(PermissionError):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("authenticated request rate limit exceeded")
        self.retry_after_seconds = max(1, retry_after_seconds)


class RunStateConflictError(RuntimeError):
    pass


class AuditEventConflictError(RuntimeError):
    """A deterministic audit receipt already exists for this command."""

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
                    payload_json TEXT NOT NULL,
                    previous_hash TEXT NOT NULL DEFAULT '',
                    event_hash TEXT NOT NULL DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_audit_events_tenant_sequence
                    ON audit_events(tenant_id, sequence ASC);
                CREATE INDEX IF NOT EXISTS idx_audit_events_resource
                    ON audit_events(tenant_id, resource_type, resource_id, sequence ASC);

                CREATE TABLE IF NOT EXISTS audit_chain_heads (
                    tenant_id TEXT PRIMARY KEY,
                    event_count INTEGER NOT NULL CHECK (event_count >= 0),
                    head_event_id TEXT NOT NULL,
                    head_hash TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS runtime_sessions (
                    session_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    session_token_hash TEXT NOT NULL UNIQUE,
                    csrf_token_hash TEXT NOT NULL,
                    credential_fingerprint TEXT NOT NULL,
                    subject_id TEXT NOT NULL DEFAULT '',
                    role TEXT NOT NULL DEFAULT 'admin',
                    key_id TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_runtime_sessions_tenant
                    ON runtime_sessions(tenant_id, expires_at DESC);
                CREATE INDEX IF NOT EXISTS idx_runtime_sessions_active
                    ON runtime_sessions(session_token_hash, revoked_at, expires_at);

                CREATE TABLE IF NOT EXISTS authentication_failures (
                    bucket_hash TEXT NOT NULL,
                    occurred_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_authentication_failures_bucket_time
                    ON authentication_failures(bucket_hash, occurred_at ASC);

                CREATE TABLE IF NOT EXISTS authenticated_request_rate_limits (
                    bucket_hash TEXT PRIMARY KEY,
                    window_started_at TEXT NOT NULL,
                    request_count INTEGER NOT NULL CHECK (request_count >= 0)
                );
                """
            )
            self._ensure_session_identity_columns_locked()
            self._ensure_audit_chain_locked()

    def _ensure_audit_chain_locked(self) -> None:
        columns = {
            str(row["name"])
            for row in self._connection.execute(
                "PRAGMA table_info(audit_events)"
            ).fetchall()
        }
        for name in ("previous_hash", "event_hash"):
            if name not in columns:
                self._connection.execute(
                    "ALTER TABLE audit_events ADD COLUMN {} TEXT NOT NULL DEFAULT ''".format(
                        name
                    )
                )
        rows = self._connection.execute(
            "SELECT * FROM audit_events ORDER BY tenant_id ASC, sequence ASC"
        ).fetchall()
        previous_by_tenant: dict[str, str] = {}
        count_by_tenant: dict[str, int] = {}
        head_event_by_tenant: dict[str, str] = {}
        for row in rows:
            tenant_id = str(row["tenant_id"])
            previous_hash = previous_by_tenant.get(tenant_id, GENESIS_AUDIT_HASH)
            payload = json.loads(str(row["payload_json"]))
            expected = audit_event_hash(
                event_id=str(row["event_id"]),
                tenant_id=tenant_id,
                request_id=str(row["request_id"]),
                occurred_at=str(row["occurred_at"]),
                action=str(row["action"]),
                resource_type=str(row["resource_type"]),
                resource_id=str(row["resource_id"]),
                actor=str(row["actor"]),
                payload=payload,
                previous_hash=previous_hash,
            )
            stored_previous = str(row["previous_hash"])
            stored_event = str(row["event_hash"])
            if not stored_previous and not stored_event:
                self._connection.execute(
                    """
                    UPDATE audit_events
                    SET previous_hash = ?, event_hash = ?
                    WHERE sequence = ?
                    """,
                    (previous_hash, expected, int(row["sequence"])),
                )
            elif stored_previous != previous_hash or stored_event != expected:
                raise AuditIntegrityError(
                    "stored SQLite audit chain failed verification"
                )
            previous_by_tenant[tenant_id] = expected
            count_by_tenant[tenant_id] = count_by_tenant.get(tenant_id, 0) + 1
            head_event_by_tenant[tenant_id] = str(row["event_id"])

        stored_heads = {
            str(row["tenant_id"]): row
            for row in self._connection.execute(
                "SELECT * FROM audit_chain_heads"
            ).fetchall()
        }
        if set(stored_heads) - set(count_by_tenant):
            raise AuditIntegrityError("SQLite audit chain head has no events")
        for tenant_id, event_count in count_by_tenant.items():
            expected_head = previous_by_tenant[tenant_id]
            expected_event_id = head_event_by_tenant[tenant_id]
            stored = stored_heads.get(tenant_id)
            if stored is None:
                self._connection.execute(
                    """
                    INSERT INTO audit_chain_heads(
                        tenant_id, event_count, head_event_id, head_hash
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (tenant_id, event_count, expected_event_id, expected_head),
                )
            elif (
                int(stored["event_count"]) != event_count
                or str(stored["head_event_id"]) != expected_event_id
                or str(stored["head_hash"]) != expected_head
            ):
                raise AuditIntegrityError("SQLite audit chain head is invalid")

    def _ensure_session_identity_columns_locked(self) -> None:
        columns = {
            str(row["name"])
            for row in self._connection.execute(
                "PRAGMA table_info(runtime_sessions)"
            ).fetchall()
        }
        additions = {
            "subject_id": "TEXT NOT NULL DEFAULT ''",
            "role": "TEXT NOT NULL DEFAULT 'admin'",
            "key_id": "TEXT NOT NULL DEFAULT ''",
        }
        for name, declaration in additions.items():
            if name not in columns:
                self._connection.execute(
                    "ALTER TABLE runtime_sessions ADD COLUMN {} {}".format(
                        name, declaration
                    )
                )
        self._connection.execute(
            """
            UPDATE runtime_sessions
            SET subject_id = 'tenant:' || tenant_id
            WHERE subject_id = ''
            """
        )
        self._connection.execute(
            """
            UPDATE runtime_sessions
            SET key_id = 'legacy:' || tenant_id
            WHERE key_id = ''
            """
        )

    def _append_audit_locked(self, tenant_id: str, audit: AuditWrite) -> None:
        event_id = audit.event_id or "audit-{}".format(uuid.uuid4().hex)
        occurred_at = self._clock()
        payload_json = canonical_json(audit.payload)
        row = self._connection.execute(
            """
            SELECT event_count, head_hash FROM audit_chain_heads
            WHERE tenant_id = ?
            """,
            (tenant_id,),
        ).fetchone()
        previous_hash = GENESIS_AUDIT_HASH if row is None else str(row["head_hash"])
        previous_count = 0 if row is None else int(row["event_count"])
        event_hash = audit_event_hash(
            event_id=event_id,
            tenant_id=tenant_id,
            request_id=audit.request_id,
            occurred_at=occurred_at,
            action=audit.action,
            resource_type=audit.resource_type,
            resource_id=audit.resource_id,
            actor=audit.actor,
            payload=dict(audit.payload),
            previous_hash=previous_hash,
        )
        self._connection.execute(
            """
            INSERT INTO audit_events(
                event_id, tenant_id, request_id, occurred_at, action,
                resource_type, resource_id, actor, payload_json,
                previous_hash, event_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                tenant_id,
                audit.request_id,
                occurred_at,
                audit.action,
                audit.resource_type,
                audit.resource_id,
                audit.actor,
                payload_json,
                previous_hash,
                event_hash,
            ),
        )
        self._connection.execute(
            """
            INSERT INTO audit_chain_heads(
                tenant_id, event_count, head_event_id, head_hash
            ) VALUES (?, ?, ?, ?)
            ON CONFLICT(tenant_id) DO UPDATE SET
                event_count = excluded.event_count,
                head_event_id = excluded.head_event_id,
                head_hash = excluded.head_hash
            """,
            (tenant_id, previous_count + 1, event_id, event_hash),
        )

    def append_audit(self, tenant_id: str, audit: AuditWrite) -> None:
        require_non_empty(tenant_id, "tenant_id")
        with self._lock, self._connection:
            self._append_audit_locked(tenant_id, audit)

    @contextmanager
    def command_lock(self, lock_id: str) -> Iterator[None]:
        require_non_empty(lock_id, "lock_id")
        with self._lock:
            yield

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
            if audit is not None and audit.event_id and self.audit_event(
                tenant_id, audit.event_id
            ) is not None:
                raise AuditEventConflictError(
                    "command receipt already exists"
                ) from error
            raise ValueError(
                "run already exists for tenant: {}".format(run.run_id)
            ) from error
        return run

    def save(
        self,
        tenant_id: str,
        run: ExecutionRun,
        audit: Optional[AuditWrite] = None,
        expected_status: Optional[str] = None,
    ) -> ExecutionRun:
        document = canonical_json(execution_run_to_document(run))
        try:
            with self._lock, self._connection:
                if expected_status is None:
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
                else:
                    cursor = self._connection.execute(
                        """
                        UPDATE runtime_runs
                        SET status = ?, document_json = ?, updated_at = ?
                        WHERE tenant_id = ? AND run_id = ? AND status = ?
                        """,
                        (
                            run.status.value,
                            document,
                            self._clock(),
                            tenant_id,
                            run.run_id,
                            expected_status,
                        ),
                    )
                if cursor.rowcount != 1:
                    row = self._connection.execute(
                        "SELECT status FROM runtime_runs WHERE tenant_id = ? AND run_id = ?",
                        (tenant_id, run.run_id),
                    ).fetchone()
                    if row is None:
                        raise KeyError("run not found: {}".format(run.run_id))
                    raise RunStateConflictError(
                        "run state changed before persistence: {}".format(run.run_id)
                    )
                if audit is not None:
                    self._append_audit_locked(tenant_id, audit)
        except sqlite3.IntegrityError as error:
            if audit is not None and audit.event_id and self.audit_event(
                tenant_id, audit.event_id
            ) is not None:
                raise AuditEventConflictError(
                    "command receipt already exists"
                ) from error
            raise
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

    def executable_runs(self, limit: int = 100) -> Tuple[Tuple[str, str], ...]:
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT tenant_id, run_id FROM runtime_runs
                WHERE status IN ('queued', 'running')
                ORDER BY updated_at ASC, tenant_id ASC, run_id ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return tuple((str(row["tenant_id"]), str(row["run_id"])) for row in rows)

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

    def verify_audit_chain(self, tenant_id: str) -> AuditChainCheckpoint:
        require_non_empty(tenant_id, "tenant_id")
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM audit_events
                WHERE tenant_id = ?
                ORDER BY sequence ASC
                """,
                (tenant_id,),
            ).fetchall()
        previous_hash = GENESIS_AUDIT_HASH
        head_event_id = ""
        for row in rows:
            payload = json.loads(str(row["payload_json"]))
            stored_previous = str(row["previous_hash"])
            stored_event = str(row["event_hash"])
            if stored_previous != previous_hash:
                raise AuditIntegrityError("audit previous hash linkage is invalid")
            expected = audit_event_hash(
                event_id=str(row["event_id"]),
                tenant_id=tenant_id,
                request_id=str(row["request_id"]),
                occurred_at=str(row["occurred_at"]),
                action=str(row["action"]),
                resource_type=str(row["resource_type"]),
                resource_id=str(row["resource_id"]),
                actor=str(row["actor"]),
                payload=payload,
                previous_hash=previous_hash,
            )
            if stored_event != expected:
                raise AuditIntegrityError("audit event hash is invalid")
            previous_hash = stored_event
            head_event_id = str(row["event_id"])
        with self._lock:
            head = self._connection.execute(
                "SELECT * FROM audit_chain_heads WHERE tenant_id = ?",
                (tenant_id,),
            ).fetchone()
        if not rows:
            if head is not None:
                raise AuditIntegrityError("audit chain head exists without events")
        elif head is None or (
            int(head["event_count"]) != len(rows)
            or str(head["head_event_id"]) != head_event_id
            or str(head["head_hash"]) != previous_hash
        ):
            raise AuditIntegrityError("audit chain head does not match events")
        return AuditChainCheckpoint(
            tenant_id=tenant_id,
            event_count=len(rows),
            head_event_id=head_event_id,
            head_hash=previous_hash,
            verified_at=self._clock(),
        )

    def audit_event(self, tenant_id: str, event_id: str) -> Optional[AuditEvent]:
        require_non_empty(tenant_id, "tenant_id")
        require_non_empty(event_id, "event_id")
        with self._lock:
            row = self._connection.execute(
                """
                SELECT * FROM audit_events
                WHERE tenant_id = ? AND event_id = ?
                """,
                (tenant_id, event_id),
            ).fetchone()
        return None if row is None else self._row_to_audit_event(row)

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
        subject_id: str = "",
        role: str = "admin",
        key_id: str = "",
    ) -> SessionIssue:
        subject_id = subject_id or "tenant:{}".format(tenant_id)
        key_id = key_id or "legacy:{}".format(tenant_id)
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
                    credential_fingerprint, subject_id, role, key_id,
                    created_at, expires_at, revoked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    session_id,
                    tenant_id,
                    self._token_hash(session_token),
                    self._token_hash(csrf_token),
                    credential_fingerprint,
                    subject_id,
                    role,
                    key_id,
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
                        "subject_id": subject_id,
                        "role": role,
                        "key_id": key_id,
                        "expires_at": expires_at,
                    },
                ),
            )
        return SessionIssue(
            session_id=session_id,
            session_token=session_token,
            csrf_token=csrf_token,
            tenant_id=tenant_id,
            subject_id=subject_id,
            role=role,
            key_id=key_id,
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
            subject_id=str(row["subject_id"]),
            role=str(row["role"]),
            key_id=str(row["key_id"]),
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

    def enforce_authentication_rate_limit(
        self,
        bucket_limits: Tuple[Tuple[str, int], ...],
        window_seconds: int,
    ) -> None:
        if not bucket_limits:
            raise ValueError("at least one authentication bucket is required")
        if any(max_failures < 1 for _, max_failures in bucket_limits):
            raise ValueError("max_failures must be positive")
        if window_seconds < 1:
            raise ValueError("window_seconds must be positive")
        now = datetime.fromisoformat(self._clock())
        cutoff = (now - timedelta(seconds=window_seconds)).isoformat()
        with self._lock, self._connection:
            self._connection.execute(
                "DELETE FROM authentication_failures WHERE occurred_at < ?",
                (cutoff,),
            )
            for bucket_hash, max_failures in bucket_limits:
                rows = self._connection.execute(
                    """
                    SELECT occurred_at
                    FROM authentication_failures
                    WHERE bucket_hash = ? AND occurred_at >= ?
                    ORDER BY occurred_at ASC
                    """,
                    (bucket_hash, cutoff),
                ).fetchall()
                if len(rows) >= max_failures:
                    earliest = datetime.fromisoformat(str(rows[0]["occurred_at"]))
                    retry_at = earliest + timedelta(seconds=window_seconds)
                    retry_after = int((retry_at - now).total_seconds()) + 1
                    raise AuthenticationRateLimitError(retry_after)

    def record_authentication_failure(
        self,
        bucket_limits: Tuple[Tuple[str, int], ...],
        window_seconds: int = 300,
    ) -> None:
        if not bucket_limits:
            raise ValueError("at least one authentication bucket is required")
        if any(max_failures < 1 for _, max_failures in bucket_limits):
            raise ValueError("max_failures must be positive")
        if window_seconds < 1:
            raise ValueError("window_seconds must be positive")
        occurred_at = self._clock()
        now = datetime.fromisoformat(occurred_at)
        cutoff = (now - timedelta(seconds=window_seconds)).isoformat()
        with self._lock, self._connection:
            self._connection.execute(
                "DELETE FROM authentication_failures WHERE occurred_at < ?",
                (cutoff,),
            )
            for bucket_hash, max_failures in sorted(bucket_limits):
                rows = self._connection.execute(
                    """
                    SELECT occurred_at FROM authentication_failures
                    WHERE bucket_hash = ? AND occurred_at >= ?
                    ORDER BY occurred_at ASC
                    """,
                    (bucket_hash, cutoff),
                ).fetchall()
                if len(rows) >= max_failures:
                    earliest = datetime.fromisoformat(str(rows[0]["occurred_at"]))
                    retry_at = earliest + timedelta(seconds=window_seconds)
                    retry_after = int((retry_at - now).total_seconds()) + 1
                    raise AuthenticationRateLimitError(retry_after)
            self._connection.executemany(
                "INSERT INTO authentication_failures(bucket_hash, occurred_at) VALUES (?, ?)",
                tuple(
                    (bucket_hash, occurred_at)
                    for bucket_hash, _ in sorted(bucket_limits)
                ),
            )

    def authentication_failure_count(self, bucket_hash: str) -> int:
        with self._lock:
            row = self._connection.execute(
                "SELECT COUNT(*) AS total FROM authentication_failures WHERE bucket_hash = ?",
                (bucket_hash,),
            ).fetchone()
        return int(row["total"])

    def consume_authenticated_request_quota(
        self,
        bucket_limits: Tuple[Tuple[str, int], ...],
        window_seconds: int,
    ) -> None:
        if not bucket_limits:
            raise ValueError("at least one authenticated request bucket is required")
        if any(not bucket_hash for bucket_hash, _ in bucket_limits):
            raise ValueError("authenticated request bucket hash is required")
        if len({bucket_hash for bucket_hash, _ in bucket_limits}) != len(bucket_limits):
            raise ValueError("authenticated request bucket hashes must be unique")
        if any(max_requests < 1 for _, max_requests in bucket_limits):
            raise ValueError("max authenticated requests must be positive")
        if window_seconds < 1:
            raise ValueError("authenticated request window must be positive")

        occurred_at = self._clock()
        now = datetime.fromisoformat(occurred_at)
        cutoff = (now - timedelta(seconds=window_seconds)).isoformat()
        updates: list[Tuple[str, str, int]] = []
        with self._lock, self._connection:
            self._connection.execute(
                "DELETE FROM authenticated_request_rate_limits WHERE window_started_at < ?",
                (cutoff,),
            )
            for bucket_hash, max_requests in sorted(bucket_limits):
                row = self._connection.execute(
                    """
                    SELECT window_started_at, request_count
                    FROM authenticated_request_rate_limits
                    WHERE bucket_hash = ?
                    """,
                    (bucket_hash,),
                ).fetchone()
                if row is None:
                    updates.append((bucket_hash, occurred_at, 1))
                    continue
                window_started = datetime.fromisoformat(str(row["window_started_at"]))
                if window_started + timedelta(seconds=window_seconds) <= now:
                    updates.append((bucket_hash, occurred_at, 1))
                    continue
                if int(row["request_count"]) >= max_requests:
                    retry_at = window_started + timedelta(seconds=window_seconds)
                    retry_after = int((retry_at - now).total_seconds()) + 1
                    raise AuthenticatedRequestRateLimitError(retry_after)
                updates.append(
                    (
                        bucket_hash,
                        str(row["window_started_at"]),
                        int(row["request_count"]) + 1,
                    )
                )

            self._connection.executemany(
                """
                INSERT INTO authenticated_request_rate_limits(
                    bucket_hash, window_started_at, request_count
                ) VALUES (?, ?, ?)
                ON CONFLICT(bucket_hash) DO UPDATE SET
                    window_started_at = excluded.window_started_at,
                    request_count = excluded.request_count
                """,
                updates,
            )

    def authenticated_request_quota_count(self, bucket_hash: str) -> int:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT request_count AS total
                FROM authenticated_request_rate_limits
                WHERE bucket_hash = ?
                """,
                (bucket_hash,),
            ).fetchone()
        return 0 if row is None else int(row["total"])

    def session_count(self, tenant_id: str, include_revoked: bool = False) -> int:
        sql = "SELECT COUNT(*) AS total FROM runtime_sessions WHERE tenant_id = ?"
        parameters: Tuple[object, ...] = (tenant_id,)
        if not include_revoked:
            sql += " AND revoked_at IS NULL AND expires_at > ?"
            parameters = (tenant_id, self._clock())
        with self._lock:
            row = self._connection.execute(sql, parameters).fetchone()
        return int(row["total"])

    def check(self) -> None:
        with self._lock:
            row = self._connection.execute("SELECT 1 AS ready").fetchone()
        if row is None or int(row["ready"]) != 1:
            raise RuntimeError("SQLite readiness query failed")

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
            subject_id=str(row["subject_id"]),
            role=str(row["role"]),
            key_id=str(row["key_id"]),
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
            previous_hash=str(row["previous_hash"]),
            event_hash=str(row["event_hash"]),
        )
