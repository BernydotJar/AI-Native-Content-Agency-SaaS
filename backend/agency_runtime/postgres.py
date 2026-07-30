from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import ssl
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterator, Mapping, Optional, Sequence, Tuple
from urllib.parse import parse_qsl, unquote, urlsplit

from pg8000 import dbapi

from .memory import utc_now
from .models import (
    ExecutionRun,
    MemoryObservation,
    MemoryRecord,
    MemorySearchResult,
    Provenance,
)
from .persistence import (
    AuditEvent,
    AuditEventConflictError,
    AuditWrite,
    AuthenticationRateLimitError,
    RunStateConflictError,
    SessionAuthenticationError,
    SessionCsrfError,
    SessionIssue,
    SessionRecord,
)
from .serialization import execution_run_from_document, execution_run_to_document
from .utils import canonical_json, require_confidence, require_non_empty, stable_id

Clock = Callable[[], str]
POSTGRES_SCHEMA_VERSION = "7"
SCHEMA_VERSION = POSTGRES_SCHEMA_VERSION
POSTGRES_SCHEMA_MODES = frozenset({"initialize", "validate"})
POSTGRES_REQUIRED_TABLES = (
    "runtime_schema_meta",
    "runtime_runs",
    "audit_events",
    "runtime_sessions",
    "authentication_rate_limits",
    "memories",
    "social_oauth_states",
    "social_connections",
    "social_publication_intents",
    "publication_media_objects",
    "model_effect_intents",
)
POSTGRES_REQUIRED_SEQUENCES = ("audit_events_sequence_seq",)
POSTGRES_REQUIRED_COLUMNS = {
    "runtime_schema_meta": frozenset({"key", "value"}),
    "runtime_runs": frozenset(
        {
            "tenant_id",
            "run_id",
            "status",
            "document_json",
            "version",
            "created_at",
            "updated_at",
        }
    ),
    "audit_events": frozenset(
        {
            "sequence",
            "event_id",
            "tenant_id",
            "request_id",
            "occurred_at",
            "action",
            "resource_type",
            "resource_id",
            "actor",
            "payload_json",
        }
    ),
    "runtime_sessions": frozenset(
        {
            "session_id",
            "tenant_id",
            "session_token_hash",
            "csrf_token_hash",
            "credential_fingerprint",
            "subject_id",
            "role",
            "key_id",
            "created_at",
            "expires_at",
            "revoked_at",
        }
    ),
    "authentication_rate_limits": frozenset(
        {"bucket_hash", "window_started_at", "failure_count"}
    ),
    "memories": frozenset(
        {
            "namespace",
            "memory_id",
            "observation_id",
            "content",
            "provenance_json",
            "confidence",
            "tags_json",
            "observed_at",
            "stored_at",
        }
    ),
    "social_oauth_states": frozenset(
        {
            "state_id",
            "tenant_id",
            "session_id",
            "channel_id",
            "state_digest",
            "provider_token_digest",
            "encrypted_payload",
            "key_id",
            "created_at",
            "expires_at",
            "consumed_at",
        }
    ),
    "social_connections": frozenset(
        {
            "tenant_id",
            "channel_id",
            "account_id",
            "account_username",
            "encrypted_tokens",
            "key_id",
            "scopes_json",
            "token_expires_at",
            "connected_at",
            "updated_at",
        }
    ),
    "social_publication_intents": frozenset(
        {
            "intent_id",
            "tenant_id",
            "channel_id",
            "account_id",
            "run_id",
            "artifact_id",
            "artifact_hash",
            "content_hash",
            "media_url_hash",
            "media_hash",
            "confirmation_hash",
            "greenlight_id",
            "greenlight_fencing_token",
            "budget_cents",
            "idempotency_digest",
            "binding_digest",
            "status",
            "execution_fencing_token",
            "provider_container_id",
            "provider_post_id",
            "receipt_json",
            "failure_reason",
            "created_at",
            "updated_at",
            "completed_at",
            "revoked_at",
        }
    ),
    "publication_media_objects": frozenset(
        {
            "media_id",
            "tenant_id",
            "run_id",
            "channel_id",
            "content_type",
            "byte_size",
            "sha256",
            "width",
            "height",
            "alt_text",
            "rights_attested_by",
            "public_token_digest",
            "public_signing_key_id",
            "idempotency_digest",
            "binding_digest",
            "content",
            "created_at",
            "expires_at",
            "revoked_at",
            "revocation_reason",
        }
    ),
    "model_effect_intents": frozenset(
        {
            "effect_id",
            "tenant_id",
            "run_id",
            "station",
            "source_artifact_id",
            "source_artifact_hash",
            "instruction_hash",
            "provider_id",
            "model",
            "endpoint_host",
            "request_sha256",
            "max_output_tokens",
            "max_cost_micros",
            "idempotency_digest",
            "binding_digest",
            "status",
            "execution_fencing_token",
            "output_text",
            "output_sha256",
            "receipt_json",
            "failure_reason",
            "created_at",
            "updated_at",
            "completed_at",
            "revoked_at",
        }
    ),
}
_ALLOWED_CONNECTION_OPTIONS = {"application_name", "sslmode", "sslrootcert"}


class PostgresSchemaError(RuntimeError):
    """Safe schema-state failure suitable for startup and operator reporting."""


def normalize_postgres_schema_mode(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("PostgreSQL schema mode must be a string")
    normalized = value.strip().lower()
    if normalized not in POSTGRES_SCHEMA_MODES:
        raise ValueError("PostgreSQL schema mode must be initialize or validate")
    return normalized


def _datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _iso(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _json_object(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, Mapping):
            return parsed
    raise ValueError("expected a JSON object from PostgreSQL")


def _json_sequence(value: object) -> Sequence[object]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return parsed
    raise ValueError("expected a JSON array from PostgreSQL")


def _connection_options(conninfo: str, timeout_seconds: float) -> dict[str, object]:
    parsed = urlsplit(conninfo)
    if parsed.scheme not in {"postgresql", "postgres"}:
        raise ValueError("PostgreSQL connection URL must use postgresql:// or postgres://")
    if parsed.fragment:
        raise ValueError("PostgreSQL connection URL must not contain a fragment")
    if not parsed.username:
        raise ValueError("PostgreSQL connection URL must include a username")

    query: dict[str, str] = {}
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key in query:
            raise ValueError(
                "PostgreSQL connection URL contains duplicate option: {}".format(key)
            )
        query[key] = value
    unsupported = sorted(set(query) - _ALLOWED_CONNECTION_OPTIONS)
    if unsupported:
        raise ValueError(
            "unsupported PostgreSQL connection URL option(s): {}".format(
                ", ".join(unsupported)
            )
        )

    sslmode = query.get("sslmode", "prefer").lower()
    sslrootcert = query.get("sslrootcert")
    if sslmode == "disable":
        if sslrootcert:
            raise ValueError("sslrootcert cannot be used with sslmode=disable")
        ssl_context: object = False
    elif sslmode == "prefer":
        if sslrootcert:
            raise ValueError(
                "sslrootcert requires sslmode=verify-ca or sslmode=verify-full"
            )
        ssl_context = None
    elif sslmode == "require":
        if sslrootcert:
            raise ValueError(
                "sslrootcert requires sslmode=verify-ca or sslmode=verify-full"
            )
        ssl_context = True
    elif sslmode in {"verify-ca", "verify-full"}:
        context = ssl.create_default_context(cafile=sslrootcert or None)
        context.check_hostname = sslmode == "verify-full"
        ssl_context = context
    else:
        raise ValueError(
            "unsupported PostgreSQL sslmode; use disable, prefer, require, "
            "verify-ca or verify-full"
        )

    try:
        port = parsed.port or 5432
    except ValueError as error:
        raise ValueError("PostgreSQL connection URL contains an invalid port") from error
    username = unquote(parsed.username)
    database = unquote(parsed.path.lstrip("/")) or username
    options: dict[str, object] = {
        "user": username,
        "host": parsed.hostname or "localhost",
        "port": port,
        "database": database,
        "timeout": timeout_seconds,
        "ssl_context": ssl_context,
        "application_name": query.get(
            "application_name", "ai-native-content-agency"
        ),
    }
    if parsed.password is not None:
        options["password"] = unquote(parsed.password)
    return options


def _connect_database_url(conninfo: str, timeout_seconds: float = 15.0) -> Any:
    """Open one pg8000 connection with a fixed safe object-resolution path."""

    connection = dbapi.connect(**_connection_options(conninfo, timeout_seconds))
    try:
        cursor = connection.cursor()
        try:
            cursor.execute("SET search_path TO pg_catalog, public")
        finally:
            cursor.close()
        connection.commit()
        return connection
    except BaseException:
        try:
            connection.close()
        except Exception:
            pass
        raise


def _quote_identifier(value: str) -> str:
    if not value or "\x00" in value:
        raise ValueError("PostgreSQL identifier must be non-empty and contain no NUL")
    return '"{}"'.format(value.replace('"', '""'))


class _MappingResult:
    def __init__(self, cursor: Any) -> None:
        self._cursor = cursor
        self._columns = tuple(str(item[0]) for item in (cursor.description or ()))

    @property
    def rowcount(self) -> int:
        return int(self._cursor.rowcount)

    def fetchone(self) -> Optional[dict[str, Any]]:
        row = self._cursor.fetchone()
        if row is None:
            return None
        return dict(zip(self._columns, row))

    def fetchall(self) -> list[dict[str, Any]]:
        return [dict(zip(self._columns, row)) for row in self._cursor.fetchall()]


class _MappingConnection:
    def __init__(self, raw: Any) -> None:
        self._raw = raw

    def execute(
        self, statement: str, parameters: Sequence[object] = ()
    ) -> _MappingResult:
        cursor = self._raw.cursor()
        cursor.execute(statement, tuple(parameters))
        return _MappingResult(cursor)


class ConnectionPool:
    """Bounded DB-API pool with eager minimum size and checkout timeout."""

    def __init__(
        self,
        *,
        conninfo: str,
        min_size: int,
        max_size: int,
        timeout: float,
    ) -> None:
        self._conninfo = conninfo
        self._max_size = max_size
        self._timeout = timeout
        self._condition = threading.Condition()
        self._idle: list[Any] = []
        self._total = 0
        self._closed = False

        created: list[Any] = []
        try:
            for _ in range(min_size):
                created.append(_connect_database_url(conninfo, timeout))
        except BaseException:
            for connection in created:
                try:
                    connection.close()
                except Exception:
                    pass
            raise
        self._idle.extend(created)
        self._total = len(created)

    def _ping(self, connection: Any) -> None:
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
            if row is None or int(row[0]) != 1:
                raise RuntimeError("PostgreSQL connection health check failed")
        finally:
            try:
                cursor.close()
            finally:
                connection.rollback()

    def _discard(self, connection: Any) -> None:
        try:
            connection.close()
        except Exception:
            pass
        with self._condition:
            self._total -= 1
            self._condition.notify()

    def _checkout(self) -> Any:
        deadline = time.monotonic() + self._timeout
        while True:
            create = False
            with self._condition:
                if self._closed:
                    raise RuntimeError("PostgreSQL connection pool is closed")
                if self._idle:
                    connection = self._idle.pop()
                elif self._total < self._max_size:
                    self._total += 1
                    create = True
                    connection = None
                else:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError(
                            "PostgreSQL connection pool checkout timed out"
                        )
                    self._condition.wait(remaining)
                    continue

            if create:
                try:
                    connection = _connect_database_url(self._conninfo, self._timeout)
                except BaseException:
                    with self._condition:
                        self._total -= 1
                        self._condition.notify()
                    raise
            try:
                self._ping(connection)
            except BaseException:
                self._discard(connection)
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        "PostgreSQL connection pool could not obtain a healthy connection"
                    )
                continue
            with self._condition:
                closed = self._closed
            if closed:
                self._discard(connection)
                raise RuntimeError("PostgreSQL connection pool is closed")
            return connection

    def _release(self, connection: Any, *, broken: bool) -> None:
        if broken:
            self._discard(connection)
            return
        with self._condition:
            if self._closed:
                self._total -= 1
                close_connection = True
            else:
                self._idle.append(connection)
                self._condition.notify()
                close_connection = False
        if close_connection:
            try:
                connection.close()
            except Exception:
                pass

    @contextmanager
    def connection(self) -> Iterator[_MappingConnection]:
        raw = self._checkout()
        broken = False
        try:
            try:
                yield _MappingConnection(raw)
            except BaseException:
                try:
                    raw.rollback()
                except Exception:
                    broken = True
                raise
            else:
                try:
                    raw.commit()
                except BaseException:
                    broken = True
                    try:
                        raw.rollback()
                    except Exception:
                        pass
                    raise
        finally:
            self._release(raw, broken=broken)

    def close(self) -> None:
        with self._condition:
            if self._closed:
                return
            self._closed = True
            idle = self._idle
            self._idle = []
            self._total -= len(idle)
            self._condition.notify_all()
        for connection in idle:
            try:
                connection.close()
            except Exception:
                pass


class PostgresRuntimeDatabase:
    """Shared PostgreSQL state for runs, memory, sessions, audit and abuse counters."""

    def __init__(
        self,
        conninfo: str,
        *,
        min_size: int = 1,
        max_size: int = 10,
        connect_timeout_seconds: float = 15.0,
        schema_mode: str = "validate",
        clock: Clock = utc_now,
    ) -> None:
        normalized = conninfo.strip()
        if not normalized.startswith(("postgresql://", "postgres://")):
            raise ValueError("PostgreSQL connection URL must use postgresql:// or postgres://")
        if min_size < 1:
            raise ValueError("PostgreSQL pool min size must be positive")
        if max_size < min_size or max_size > 100:
            raise ValueError("PostgreSQL pool max size must be between min size and 100")
        if connect_timeout_seconds < 1 or connect_timeout_seconds > 300:
            raise ValueError(
                "PostgreSQL connect timeout must be between 1 and 300 seconds"
            )
        normalized_schema_mode = normalize_postgres_schema_mode(schema_mode)
        self._clock = clock
        self._conninfo = normalized
        self._connect_timeout_seconds = connect_timeout_seconds
        self.schema_mode = normalized_schema_mode
        self._closed = False
        pool = ConnectionPool(
            conninfo=normalized,
            min_size=min_size,
            max_size=max_size,
            timeout=connect_timeout_seconds,
        )
        self.pool = pool
        try:
            if normalized_schema_mode == "initialize":
                self._initialize_schema()
            else:
                self._validate_schema()
        except Exception:
            self._closed = True
            pool.close()
            raise

    @property
    def clock(self) -> Clock:
        return self._clock

    def _initialize_schema(self) -> None:
        statements = (
            """
            CREATE TABLE IF NOT EXISTS public.runtime_schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS public.runtime_runs (
                tenant_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                status TEXT NOT NULL,
                document_json JSONB NOT NULL,
                version BIGINT NOT NULL DEFAULT 1,
                created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL,
                PRIMARY KEY (tenant_id, run_id)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_runtime_runs_tenant_status
                ON public.runtime_runs(tenant_id, status, updated_at DESC)
            """,
            """
            CREATE TABLE IF NOT EXISTS public.audit_events (
                sequence BIGSERIAL PRIMARY KEY,
                event_id TEXT NOT NULL UNIQUE,
                tenant_id TEXT NOT NULL,
                request_id TEXT NOT NULL,
                occurred_at TIMESTAMPTZ NOT NULL,
                action TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                actor TEXT NOT NULL,
                payload_json JSONB NOT NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_audit_events_tenant_sequence
                ON public.audit_events(tenant_id, sequence ASC)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_audit_events_resource
                ON public.audit_events(tenant_id, resource_type, resource_id, sequence ASC)
            """,
            """
            CREATE TABLE IF NOT EXISTS public.runtime_sessions (
                session_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                session_token_hash TEXT NOT NULL UNIQUE,
                csrf_token_hash TEXT NOT NULL,
                credential_fingerprint TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                role TEXT NOT NULL,
                key_id TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                revoked_at TIMESTAMPTZ
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_runtime_sessions_tenant
                ON public.runtime_sessions(tenant_id, expires_at DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_runtime_sessions_active
                ON public.runtime_sessions(session_token_hash, revoked_at, expires_at)
            """,
            """
            CREATE TABLE IF NOT EXISTS public.authentication_rate_limits (
                bucket_hash TEXT PRIMARY KEY,
                window_started_at TIMESTAMPTZ NOT NULL,
                failure_count INTEGER NOT NULL CHECK (failure_count >= 0)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS public.memories (
                namespace TEXT NOT NULL,
                memory_id TEXT NOT NULL,
                observation_id TEXT NOT NULL,
                content TEXT NOT NULL,
                provenance_json JSONB NOT NULL,
                confidence DOUBLE PRECISION NOT NULL
                    CHECK (confidence >= 0 AND confidence <= 1),
                tags_json JSONB NOT NULL,
                observed_at TIMESTAMPTZ NOT NULL,
                stored_at TIMESTAMPTZ NOT NULL,
                PRIMARY KEY (namespace, memory_id),
                UNIQUE (namespace, observation_id)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_memories_namespace_confidence
                ON public.memories(namespace, confidence DESC, stored_at DESC)
            """,
            """
            CREATE TABLE IF NOT EXISTS public.social_oauth_states (
                state_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                channel_id TEXT NOT NULL CHECK (channel_id IN ('x', 'instagram')),
                state_digest TEXT NOT NULL UNIQUE,
                provider_token_digest TEXT,
                encrypted_payload TEXT NOT NULL,
                key_id TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                consumed_at TIMESTAMPTZ
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_social_oauth_states_lookup
                ON public.social_oauth_states(
                    tenant_id, session_id, channel_id, state_digest, consumed_at
                )
            """,
            """
            CREATE TABLE IF NOT EXISTS public.social_connections (
                tenant_id TEXT NOT NULL,
                channel_id TEXT NOT NULL CHECK (channel_id IN ('x', 'instagram')),
                account_id TEXT NOT NULL,
                account_username TEXT NOT NULL,
                encrypted_tokens TEXT NOT NULL,
                key_id TEXT NOT NULL,
                scopes_json JSONB NOT NULL,
                token_expires_at TIMESTAMPTZ,
                connected_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL,
                PRIMARY KEY (tenant_id, channel_id)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_social_connections_tenant_updated
                ON public.social_connections(tenant_id, updated_at DESC)
            """,
            """
            CREATE TABLE IF NOT EXISTS public.social_publication_intents (
                intent_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                channel_id TEXT NOT NULL CHECK (channel_id IN ('x', 'instagram')),
                account_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                artifact_id TEXT NOT NULL,
                artifact_hash TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                media_url_hash TEXT,
                media_hash TEXT,
                confirmation_hash TEXT,
                greenlight_id TEXT NOT NULL,
                greenlight_fencing_token BIGINT NOT NULL CHECK (greenlight_fencing_token >= 0),
                budget_cents BIGINT NOT NULL CHECK (budget_cents >= 0),
                idempotency_digest TEXT NOT NULL,
                binding_digest TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('pending', 'succeeded', 'unknown', 'failed', 'revoked')),
                execution_fencing_token BIGINT NOT NULL CHECK (execution_fencing_token > 0),
                provider_container_id TEXT,
                provider_post_id TEXT,
                receipt_json JSONB NOT NULL,
                failure_reason TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL,
                completed_at TIMESTAMPTZ,
                revoked_at TIMESTAMPTZ,
                UNIQUE (tenant_id, idempotency_digest),
                UNIQUE (tenant_id, binding_digest)
            )
            """,
            """
            ALTER TABLE public.social_publication_intents
                ADD COLUMN IF NOT EXISTS confirmation_hash TEXT
            """,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_social_publication_binding
                ON public.social_publication_intents(tenant_id, binding_digest)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_social_publication_run
                ON public.social_publication_intents(tenant_id, run_id, updated_at DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_social_publication_account
                ON public.social_publication_intents(
                    tenant_id, channel_id, account_id, status, updated_at DESC
                )
            """,
            """
            CREATE TABLE IF NOT EXISTS public.publication_media_objects (
                media_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                channel_id TEXT NOT NULL CHECK (channel_id = 'instagram'),
                content_type TEXT NOT NULL CHECK (content_type = 'image/jpeg'),
                byte_size BIGINT NOT NULL CHECK (byte_size > 0 AND byte_size <= 8388608),
                sha256 TEXT NOT NULL,
                width INTEGER NOT NULL CHECK (width >= 320 AND width <= 1440),
                height INTEGER NOT NULL CHECK (height >= 320 AND height <= 1440),
                alt_text TEXT NOT NULL,
                rights_attested_by TEXT NOT NULL,
                public_token_digest TEXT NOT NULL UNIQUE,
                public_signing_key_id TEXT NOT NULL DEFAULT 'legacy',
                idempotency_digest TEXT,
                binding_digest TEXT,
                content BYTEA NOT NULL,
                created_at TIMESTAMPTZ NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                revoked_at TIMESTAMPTZ,
                revocation_reason TEXT NOT NULL DEFAULT '',
                UNIQUE (tenant_id, idempotency_digest),
                UNIQUE (tenant_id, binding_digest),
                UNIQUE (tenant_id, run_id, channel_id, sha256)
            )
            """,
            """
            ALTER TABLE public.publication_media_objects
                ADD COLUMN IF NOT EXISTS public_signing_key_id TEXT NOT NULL DEFAULT 'legacy'
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_publication_media_tenant_run
                ON public.publication_media_objects(tenant_id, run_id, created_at DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_publication_media_public_lookup
                ON public.publication_media_objects(
                    public_token_digest, expires_at, revoked_at
                )
            """,
            """
            CREATE TABLE IF NOT EXISTS public.model_effect_intents (
                effect_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                station TEXT NOT NULL,
                source_artifact_id TEXT NOT NULL,
                source_artifact_hash TEXT NOT NULL,
                instruction_hash TEXT NOT NULL,
                provider_id TEXT NOT NULL,
                model TEXT NOT NULL,
                endpoint_host TEXT NOT NULL,
                request_sha256 TEXT NOT NULL,
                max_output_tokens BIGINT NOT NULL CHECK (max_output_tokens > 0),
                max_cost_micros BIGINT NOT NULL CHECK (max_cost_micros >= 0),
                idempotency_digest TEXT NOT NULL,
                binding_digest TEXT NOT NULL,
                status TEXT NOT NULL CHECK (
                    status IN ('pending', 'succeeded', 'unknown', 'failed', 'revoked')
                ),
                execution_fencing_token BIGINT NOT NULL CHECK (execution_fencing_token > 0),
                output_text TEXT NOT NULL,
                output_sha256 TEXT NOT NULL,
                receipt_json JSONB NOT NULL,
                failure_reason TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL,
                completed_at TIMESTAMPTZ,
                revoked_at TIMESTAMPTZ,
                UNIQUE (tenant_id, idempotency_digest),
                UNIQUE (tenant_id, binding_digest)
            )
            """,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_model_effect_binding
                ON public.model_effect_intents(tenant_id, binding_digest)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_model_effect_run
                ON public.model_effect_intents(tenant_id, run_id, updated_at DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_model_effect_status
                ON public.model_effect_intents(tenant_id, status, updated_at DESC)
            """,
        )
        with self.pool.connection() as connection:
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                ("ai-native-content-agency-schema",),
            )
            for statement in statements:
                connection.execute(statement)
            connection.execute(
                """
                INSERT INTO public.runtime_schema_meta(key, value)
                VALUES ('schema_version', %s)
                ON CONFLICT (key) DO NOTHING
                """,
                (SCHEMA_VERSION,),
            )
            connection.execute(
                """
                UPDATE public.runtime_schema_meta
                SET value = %s
                WHERE key = 'schema_version' AND value IN ('1', '2', '3', '4', '5', '6')
                """,
                (SCHEMA_VERSION,),
            )
            self._validate_schema_connection(connection)

    def _validate_schema_connection(self, connection: _MappingConnection) -> None:
        invalid: list[str] = []
        expected_relkinds = {
            "table": frozenset({"r", "p"}),
            "sequence": frozenset({"S"}),
        }
        for relation_type, names in (
            ("table", POSTGRES_REQUIRED_TABLES),
            ("sequence", POSTGRES_REQUIRED_SEQUENCES),
        ):
            for name in names:
                row = connection.execute(
                    """
                    SELECT relation.relkind AS kind
                    FROM pg_catalog.pg_class AS relation
                    JOIN pg_catalog.pg_namespace AS namespace
                      ON namespace.oid = relation.relnamespace
                    WHERE namespace.nspname = %s AND relation.relname = %s
                    """,
                    ("public", name),
                ).fetchone()
                if row is None:
                    invalid.append("{}:{}:missing".format(relation_type, name))
                elif str(row["kind"]) not in expected_relkinds[relation_type]:
                    invalid.append("{}:{}:wrong_type".format(relation_type, name))
                elif relation_type == "table":
                    columns = connection.execute(
                        """
                        SELECT attribute.attname AS column_name
                        FROM pg_catalog.pg_attribute AS attribute
                        JOIN pg_catalog.pg_class AS relation
                          ON relation.oid = attribute.attrelid
                        JOIN pg_catalog.pg_namespace AS namespace
                          ON namespace.oid = relation.relnamespace
                        WHERE namespace.nspname = %s
                          AND relation.relname = %s
                          AND attribute.attnum > 0
                          AND NOT attribute.attisdropped
                        """,
                        ("public", name),
                    ).fetchall()
                    observed_columns = {str(item["column_name"]) for item in columns}
                    for column in sorted(
                        POSTGRES_REQUIRED_COLUMNS[name] - observed_columns
                    ):
                        invalid.append("column:{}.{}:missing".format(name, column))
        if invalid:
            raise PostgresSchemaError(
                "PostgreSQL runtime schema is incomplete: {}".format(
                    ", ".join(sorted(invalid))
                )
            )
        row = connection.execute(
            """
            SELECT value
            FROM public.runtime_schema_meta
            WHERE key = 'schema_version'
            """
        ).fetchone()
        actual_version = None if row is None else str(row["value"])
        if actual_version != POSTGRES_SCHEMA_VERSION:
            raise PostgresSchemaError(
                "unsupported PostgreSQL runtime schema version: {} (expected {})".format(
                    actual_version or "missing", POSTGRES_SCHEMA_VERSION
                )
            )

    def _validate_schema(self) -> None:
        with self.pool.connection() as connection:
            self._validate_schema_connection(connection)

    def check(self) -> None:
        self._validate_schema()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.pool.close()


class PostgresRunStore:
    """Tenant-scoped shared run/session/audit/rate-limit store."""

    def __init__(self, database: PostgresRuntimeDatabase) -> None:
        self.database = database
        self._clock = database.clock

    def _append_audit(
        self,
        connection: _MappingConnection,
        tenant_id: str,
        audit: AuditWrite,
    ) -> None:
        connection.execute(
            """
            INSERT INTO audit_events(
                event_id, tenant_id, request_id, occurred_at, action,
                resource_type, resource_id, actor, payload_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CAST(%s AS jsonb))
            """,
            (
                audit.event_id or "audit-{}".format(uuid.uuid4().hex),
                tenant_id,
                audit.request_id,
                _datetime(self._clock()),
                audit.action,
                audit.resource_type,
                audit.resource_id,
                audit.actor,
                canonical_json(dict(audit.payload)),
            ),
        )

    def append_audit(self, tenant_id: str, audit: AuditWrite) -> None:
        require_non_empty(tenant_id, "tenant_id")
        with self.database.pool.connection() as connection:
            self._append_audit(connection, tenant_id, audit)

    @contextmanager
    def command_lock(self, lock_id: str) -> Iterator[None]:
        require_non_empty(lock_id, "lock_id")
        raw = _connect_database_url(
            self.database._conninfo, self.database._connect_timeout_seconds
        )
        connection = _MappingConnection(raw)
        try:
            connection.execute(
                "SELECT pg_catalog.pg_advisory_lock("
                "pg_catalog.hashtextextended(%s, 0)) AS locked",
                (lock_id,),
            )
            raw.commit()
            try:
                yield
            finally:
                row = connection.execute(
                    "SELECT pg_catalog.pg_advisory_unlock("
                    "pg_catalog.hashtextextended(%s, 0)) AS unlocked",
                    (lock_id,),
                ).fetchone()
                raw.commit()
                if row is None or bool(row["unlocked"]) is not True:
                    raise RuntimeError("PostgreSQL command lock was not held")
        finally:
            raw.close()

    def create(
        self,
        tenant_id: str,
        run: ExecutionRun,
        audit: Optional[AuditWrite] = None,
    ) -> ExecutionRun:
        timestamp = _datetime(self._clock())
        try:
            with self.database.pool.connection() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO runtime_runs(
                        tenant_id, run_id, status, document_json, version,
                        created_at, updated_at
                    ) VALUES (%s, %s, %s, CAST(%s AS jsonb), 1, %s, %s)
                    ON CONFLICT (tenant_id, run_id) DO NOTHING
                    """,
                    (
                        tenant_id,
                        run.run_id,
                        run.status.value,
                        canonical_json(execution_run_to_document(run)),
                        timestamp,
                        timestamp,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ValueError(
                        "run already exists for tenant: {}".format(run.run_id)
                    )
                if audit is not None:
                    self._append_audit(connection, tenant_id, audit)
        except dbapi.IntegrityError as error:
            if audit is not None and audit.event_id and self.audit_event(
                tenant_id, audit.event_id
            ) is not None:
                raise AuditEventConflictError(
                    "command receipt already exists"
                ) from error
            raise
        return run

    def save(
        self,
        tenant_id: str,
        run: ExecutionRun,
        audit: Optional[AuditWrite] = None,
        expected_status: Optional[str] = None,
    ) -> ExecutionRun:
        try:
            with self.database.pool.connection() as connection:
                if expected_status is None:
                    cursor = connection.execute(
                        """
                        UPDATE runtime_runs
                        SET status = %s, document_json = CAST(%s AS jsonb),
                            version = version + 1, updated_at = %s
                        WHERE tenant_id = %s AND run_id = %s
                        """,
                        (
                            run.status.value,
                            canonical_json(execution_run_to_document(run)),
                            _datetime(self._clock()),
                            tenant_id,
                            run.run_id,
                        ),
                    )
                else:
                    cursor = connection.execute(
                        """
                        UPDATE runtime_runs
                        SET status = %s, document_json = CAST(%s AS jsonb),
                            version = version + 1, updated_at = %s
                        WHERE tenant_id = %s AND run_id = %s AND status = %s
                        """,
                        (
                            run.status.value,
                            canonical_json(execution_run_to_document(run)),
                            _datetime(self._clock()),
                            tenant_id,
                            run.run_id,
                            expected_status,
                        ),
                    )
                if cursor.rowcount != 1:
                    exists = connection.execute(
                        "SELECT status FROM runtime_runs WHERE tenant_id = %s AND run_id = %s",
                        (tenant_id, run.run_id),
                    ).fetchone()
                    if exists is None:
                        raise KeyError("run not found: {}".format(run.run_id))
                    raise RunStateConflictError(
                        "run state changed before persistence: {}".format(run.run_id)
                    )
                if audit is not None:
                    self._append_audit(connection, tenant_id, audit)
        except dbapi.IntegrityError as error:
            if audit is not None and audit.event_id and self.audit_event(
                tenant_id, audit.event_id
            ) is not None:
                raise AuditEventConflictError(
                    "command receipt already exists"
                ) from error
            raise
        return run

    def get(self, tenant_id: str, run_id: str) -> ExecutionRun:
        with self.database.pool.connection() as connection:
            row = connection.execute(
                """
                SELECT document_json FROM runtime_runs
                WHERE tenant_id = %s AND run_id = %s
                """,
                (tenant_id, run_id),
            ).fetchone()
        if row is None:
            raise KeyError("run not found: {}".format(run_id))
        return execution_run_from_document(_json_object(row["document_json"]))

    def exists(self, tenant_id: str, run_id: str) -> bool:
        with self.database.pool.connection() as connection:
            row = connection.execute(
                "SELECT 1 FROM runtime_runs WHERE tenant_id = %s AND run_id = %s",
                (tenant_id, run_id),
            ).fetchone()
        return row is not None

    def count(self, tenant_id: str) -> int:
        with self.database.pool.connection() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM runtime_runs WHERE tenant_id = %s",
                (tenant_id,),
            ).fetchone()
        return int(row["total"])

    def executable_runs(self, limit: int = 100) -> Tuple[Tuple[str, str], ...]:
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")
        with self.database.pool.connection() as connection:
            rows = connection.execute(
                """
                SELECT tenant_id, run_id FROM runtime_runs
                WHERE status IN ('queued', 'running')
                ORDER BY updated_at ASC, tenant_id ASC, run_id ASC
                LIMIT %s
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
        with self.database.pool.connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM audit_events
                WHERE tenant_id = %s AND sequence > %s
                ORDER BY sequence ASC
                LIMIT %s
                """,
                (tenant_id, after_sequence, limit),
            ).fetchall()
        return tuple(self._row_to_audit_event(row) for row in rows)

    def audit_event(self, tenant_id: str, event_id: str) -> Optional[AuditEvent]:
        require_non_empty(tenant_id, "tenant_id")
        require_non_empty(event_id, "event_id")
        with self.database.pool.connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM audit_events
                WHERE tenant_id = %s AND event_id = %s
                """,
                (tenant_id, event_id),
            ).fetchone()
        return None if row is None else self._row_to_audit_event(row)

    def audit_count(self, tenant_id: str) -> int:
        with self.database.pool.connection() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM audit_events WHERE tenant_id = %s",
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
        created_at = _datetime(self._clock())
        expires_at = created_at + timedelta(seconds=ttl_seconds)
        session_id = "session-{}".format(uuid.uuid4().hex)
        session_token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        with self.database.pool.connection() as connection:
            connection.execute(
                """
                INSERT INTO runtime_sessions(
                    session_id, tenant_id, session_token_hash, csrf_token_hash,
                    credential_fingerprint, subject_id, role, key_id,
                    created_at, expires_at, revoked_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL)
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
            self._append_audit(
                connection,
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
                        "expires_at": expires_at.isoformat(),
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
            expires_at=expires_at.isoformat(),
        )

    def authenticate_session(self, session_token: str) -> SessionRecord:
        if not session_token:
            raise SessionAuthenticationError("browser session is missing")
        token_hash = self._token_hash(session_token)
        with self.database.pool.connection() as connection:
            row = connection.execute(
                "SELECT * FROM runtime_sessions WHERE session_token_hash = %s",
                (token_hash,),
            ).fetchone()
        if row is None or not hmac.compare_digest(
            token_hash, str(row["session_token_hash"])
        ):
            raise SessionAuthenticationError("browser session is invalid")
        if row["revoked_at"] is not None:
            raise SessionAuthenticationError("browser session is revoked")
        if row["expires_at"] <= _datetime(self._clock()):
            raise SessionAuthenticationError("browser session is expired")
        return self._row_to_session_record(row)

    def rotate_session_csrf(self, session_id: str) -> SessionIssue:
        csrf_token = secrets.token_urlsafe(32)
        with self.database.pool.connection() as connection:
            row = connection.execute(
                "SELECT * FROM runtime_sessions WHERE session_id = %s FOR UPDATE",
                (session_id,),
            ).fetchone()
            if row is None or row["revoked_at"] is not None:
                raise SessionAuthenticationError("browser session is not active")
            if row["expires_at"] <= _datetime(self._clock()):
                raise SessionAuthenticationError("browser session is expired")
            connection.execute(
                "UPDATE runtime_sessions SET csrf_token_hash = %s WHERE session_id = %s",
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
            expires_at=_iso(row["expires_at"]),
        )

    def verify_session_csrf(self, session_id: str, csrf_token: str) -> None:
        if not csrf_token:
            raise SessionCsrfError("CSRF token is required")
        with self.database.pool.connection() as connection:
            row = connection.execute(
                """
                SELECT csrf_token_hash, expires_at, revoked_at
                FROM runtime_sessions WHERE session_id = %s
                """,
                (session_id,),
            ).fetchone()
        if row is None or row["revoked_at"] is not None:
            raise SessionCsrfError("browser session is not active")
        if row["expires_at"] <= _datetime(self._clock()):
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
        revoked_at = _datetime(self._clock())
        with self.database.pool.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE runtime_sessions SET revoked_at = %s
                WHERE tenant_id = %s AND session_id = %s AND revoked_at IS NULL
                """,
                (revoked_at, tenant_id, session_id),
            )
            if cursor.rowcount != 1:
                raise KeyError("active browser session not found")
            self._append_audit(
                connection,
                tenant_id,
                AuditWrite(
                    request_id=request_id,
                    action="session.revoked",
                    resource_type="browser_session",
                    resource_id=session_id,
                    actor=actor,
                    payload={"revoked_at": revoked_at.isoformat()},
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
        now = _datetime(self._clock())
        with self.database.pool.connection() as connection:
            for bucket_hash, max_failures in sorted(bucket_limits):
                row = connection.execute(
                    """
                    SELECT window_started_at, failure_count
                    FROM authentication_rate_limits
                    WHERE bucket_hash = %s
                    FOR UPDATE
                    """,
                    (bucket_hash,),
                ).fetchone()
                if row is None:
                    continue
                window_started = row["window_started_at"]
                if window_started + timedelta(seconds=window_seconds) <= now:
                    connection.execute(
                        "DELETE FROM authentication_rate_limits WHERE bucket_hash = %s",
                        (bucket_hash,),
                    )
                    continue
                if int(row["failure_count"]) >= max_failures:
                    retry_at = window_started + timedelta(seconds=window_seconds)
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
        occurred_at = _datetime(self._clock())
        with self.database.pool.connection() as connection:
            for bucket_hash, max_failures in sorted(bucket_limits):
                connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (bucket_hash,),
                )
                row = connection.execute(
                    """
                    SELECT window_started_at, failure_count
                    FROM authentication_rate_limits
                    WHERE bucket_hash = %s
                    FOR UPDATE
                    """,
                    (bucket_hash,),
                ).fetchone()
                if row is None:
                    connection.execute(
                        """
                        INSERT INTO authentication_rate_limits(
                            bucket_hash, window_started_at, failure_count
                        ) VALUES (%s, %s, 1)
                        """,
                        (bucket_hash, occurred_at),
                    )
                    continue
                window_started = row["window_started_at"]
                if window_started + timedelta(seconds=window_seconds) <= occurred_at:
                    connection.execute(
                        """
                        UPDATE authentication_rate_limits
                        SET window_started_at = %s, failure_count = 1
                        WHERE bucket_hash = %s
                        """,
                        (occurred_at, bucket_hash),
                    )
                    continue
                if int(row["failure_count"]) >= max_failures:
                    retry_at = window_started + timedelta(seconds=window_seconds)
                    retry_after = int((retry_at - occurred_at).total_seconds()) + 1
                    raise AuthenticationRateLimitError(retry_after)
                connection.execute(
                    """
                    UPDATE authentication_rate_limits
                    SET failure_count = failure_count + 1
                    WHERE bucket_hash = %s
                    """,
                    (bucket_hash,),
                )

    def authentication_failure_count(self, bucket_hash: str) -> int:
        with self.database.pool.connection() as connection:
            row = connection.execute(
                """
                SELECT failure_count AS total FROM authentication_rate_limits
                WHERE bucket_hash = %s
                """,
                (bucket_hash,),
            ).fetchone()
        return 0 if row is None else int(row["total"])

    def session_count(self, tenant_id: str, include_revoked: bool = False) -> int:
        if include_revoked:
            sql = "SELECT COUNT(*) AS total FROM runtime_sessions WHERE tenant_id = %s"
            parameters: Tuple[object, ...] = (tenant_id,)
        else:
            sql = """
                SELECT COUNT(*) AS total FROM runtime_sessions
                WHERE tenant_id = %s AND revoked_at IS NULL AND expires_at > %s
            """
            parameters = (tenant_id, _datetime(self._clock()))
        with self.database.pool.connection() as connection:
            row = connection.execute(sql, parameters).fetchone()
        return int(row["total"])

    def check(self) -> None:
        self.database.check()

    def close(self) -> None:
        self.database.close()

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _row_to_session_record(row: Mapping[str, object]) -> SessionRecord:
        return SessionRecord(
            session_id=str(row["session_id"]),
            tenant_id=str(row["tenant_id"]),
            subject_id=str(row["subject_id"]),
            role=str(row["role"]),
            key_id=str(row["key_id"]),
            credential_fingerprint=str(row["credential_fingerprint"]),
            created_at=_iso(row["created_at"]),
            expires_at=_iso(row["expires_at"]),
            revoked_at=(
                _iso(row["revoked_at"]) if row["revoked_at"] is not None else None
            ),
        )

    @staticmethod
    def _row_to_audit_event(row: Mapping[str, object]) -> AuditEvent:
        return AuditEvent(
            sequence=int(row["sequence"]),
            event_id=str(row["event_id"]),
            tenant_id=str(row["tenant_id"]),
            request_id=str(row["request_id"]),
            occurred_at=_iso(row["occurred_at"]),
            action=str(row["action"]),
            resource_type=str(row["resource_type"]),
            resource_id=str(row["resource_id"]),
            actor=str(row["actor"]),
            payload=_json_object(row["payload_json"]),
        )


class PostgresMemory:
    """Shared Observe/Store/Search/Recall memory partitioned by tenant namespace."""

    def __init__(
        self,
        database: PostgresRuntimeDatabase,
        *,
        namespace: str,
        clock: Optional[Clock] = None,
    ) -> None:
        self.database = database
        self._clock = clock or database.clock
        self.namespace = namespace.strip().lower()
        if not self.namespace:
            raise ValueError("namespace must not be empty")

    def observe(
        self,
        content: str,
        provenance: Provenance,
        confidence: float,
        tags: Sequence[str] = (),
    ) -> MemoryObservation:
        require_confidence(confidence)
        normalized_content = content.strip()
        if not normalized_content:
            raise ValueError("content must not be empty")
        normalized_tags = tuple(
            sorted({tag.strip().lower() for tag in tags if tag and tag.strip()})
        )
        observed_at = self._clock()
        observation_id = stable_id(
            "obs",
            self.namespace,
            normalized_content,
            provenance,
            confidence,
            normalized_tags,
            observed_at,
        )
        return MemoryObservation(
            observation_id=observation_id,
            content=normalized_content,
            provenance=provenance,
            confidence=confidence,
            tags=normalized_tags,
            observed_at=observed_at,
        )

    def store(self, observation: MemoryObservation) -> MemoryRecord:
        memory_id = stable_id("mem", self.namespace, observation.observation_id)
        stored_at = _datetime(self._clock())
        provenance = json.loads(canonical_json(observation.provenance))
        with self.database.pool.connection() as connection:
            connection.execute(
                """
                INSERT INTO memories(
                    namespace, memory_id, observation_id, content, provenance_json,
                    confidence, tags_json, observed_at, stored_at
                ) VALUES (
                    %s, %s, %s, %s, CAST(%s AS jsonb), %s,
                    CAST(%s AS jsonb), %s, %s
                )
                ON CONFLICT (namespace, observation_id) DO NOTHING
                """,
                (
                    self.namespace,
                    memory_id,
                    observation.observation_id,
                    observation.content,
                    canonical_json(provenance),
                    observation.confidence,
                    canonical_json(list(observation.tags)),
                    _datetime(observation.observed_at),
                    stored_at,
                ),
            )
        return self.recall(memory_id)

    def search(
        self,
        query: str,
        limit: int = 10,
        min_confidence: float = 0.0,
    ) -> Tuple[MemorySearchResult, ...]:
        require_confidence(min_confidence)
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        tokens = tuple(
            dict.fromkeys(token for token in query.lower().split() if token.strip())
        )
        if not tokens:
            raise ValueError("query must not be empty")
        clauses = ["namespace = %s", "confidence >= %s"]
        parameters: list[object] = [self.namespace, min_confidence]
        for token in tokens:
            clauses.append("(content ILIKE %s OR tags_json::text ILIKE %s)")
            wildcard = "%{}%".format(token)
            parameters.extend((wildcard, wildcard))
        parameters.append(limit)
        sql = """
            SELECT * FROM memories
            WHERE {}
            ORDER BY confidence DESC, stored_at DESC, memory_id ASC
            LIMIT %s
        """.format(" AND ".join(clauses))
        with self.database.pool.connection() as connection:
            rows = connection.execute(sql, tuple(parameters)).fetchall()
        results = []
        for row in rows:
            record = self._row_to_record(row)
            content = record.content.lower()
            tags = set(record.tags)
            matched = sum(1 for token in tokens if token in content or token in tags)
            exact_tag_bonus = 0.1 if any(token in tags for token in tokens) else 0.0
            score = min(
                1.0,
                record.confidence * 0.55
                + (matched / len(tokens)) * 0.35
                + exact_tag_bonus,
            )
            results.append(MemorySearchResult(record=record, score=round(score, 4)))
        return tuple(sorted(results, key=lambda item: (-item.score, item.record.memory_id)))

    def recall(self, memory_id: str) -> MemoryRecord:
        with self.database.pool.connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM memories
                WHERE namespace = %s AND memory_id = %s
                """,
                (self.namespace, memory_id),
            ).fetchone()
        if row is None:
            raise KeyError("memory not found: {}".format(memory_id))
        return self._row_to_record(row)

    def count(self) -> int:
        with self.database.pool.connection() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM memories WHERE namespace = %s",
                (self.namespace,),
            ).fetchone()
        return int(row["total"])

    def close(self) -> None:
        return None

    @staticmethod
    def _row_to_record(row: Mapping[str, object]) -> MemoryRecord:
        provenance_data = _json_object(row["provenance_json"])
        return MemoryRecord(
            memory_id=str(row["memory_id"]),
            content=str(row["content"]),
            provenance=Provenance(**provenance_data),
            confidence=float(row["confidence"]),
            tags=tuple(str(item) for item in _json_sequence(row["tags_json"])),
            observed_at=_iso(row["observed_at"]),
            stored_at=_iso(row["stored_at"]),
        )
