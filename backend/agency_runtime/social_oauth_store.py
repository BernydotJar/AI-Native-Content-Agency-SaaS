from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Callable, Mapping, Optional, Tuple

from .memory import utc_now
from .social_oauth import EncryptedSocialValue
from .utils import canonical_json


Clock = Callable[[], str]
_CHANNEL = re.compile(r"^(x|instagram)$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,255}$")


class SocialOAuthStoreError(RuntimeError):
    pass


class SocialOAuthStateUnavailableError(SocialOAuthStoreError):
    pass


@dataclass(frozen=True)
class SocialOAuthStateRecord:
    state_id: str
    tenant_id: str
    session_id: str
    channel_id: str
    state_digest: str
    provider_token_digest: Optional[str]
    encrypted_payload: EncryptedSocialValue
    created_at: str
    expires_at: str
    consumed_at: Optional[str]


@dataclass(frozen=True)
class SocialConnectionRecord:
    tenant_id: str
    channel_id: str
    account_id: str
    account_username: str
    encrypted_tokens: EncryptedSocialValue
    scopes: Tuple[str, ...]
    token_expires_at: Optional[str]
    connected_at: str
    updated_at: str


class SQLiteSocialOAuthStore:
    def __init__(self, database_path: str | Path, *, clock: Clock = utc_now) -> None:
        self._clock = clock
        self._connection = sqlite3.connect(
            str(database_path), timeout=30, check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA secure_delete = ON")
        self._lock = RLock()
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        with self._lock, self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS social_oauth_states (
                    state_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    state_digest TEXT NOT NULL UNIQUE,
                    provider_token_digest TEXT,
                    encrypted_payload TEXT NOT NULL,
                    key_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    consumed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_social_oauth_states_lookup
                    ON social_oauth_states(
                        tenant_id, session_id, channel_id, state_digest, consumed_at
                    );
                CREATE TABLE IF NOT EXISTS social_connections (
                    tenant_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    account_username TEXT NOT NULL,
                    encrypted_tokens TEXT NOT NULL,
                    key_id TEXT NOT NULL,
                    scopes_json TEXT NOT NULL,
                    token_expires_at TEXT,
                    connected_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, channel_id)
                );
                """
            )

    def create_state(self, record: SocialOAuthStateRecord) -> None:
        _validate_state(record)
        with self._lock, self._connection:
            self._connection.execute(
                """
                DELETE FROM social_oauth_states
                WHERE tenant_id = ? AND session_id = ? AND channel_id = ?
                  AND consumed_at IS NULL
                """,
                (record.tenant_id, record.session_id, record.channel_id),
            )
            try:
                self._connection.execute(
                    """
                    INSERT INTO social_oauth_states(
                        state_id, tenant_id, session_id, channel_id,
                        state_digest, provider_token_digest,
                        encrypted_payload, key_id, created_at, expires_at, consumed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        record.state_id,
                        record.tenant_id,
                        record.session_id,
                        record.channel_id,
                        record.state_digest,
                        record.provider_token_digest,
                        record.encrypted_payload.ciphertext,
                        record.encrypted_payload.key_id,
                        record.created_at,
                        record.expires_at,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise SocialOAuthStoreError("social OAuth state could not be created") from error

    def consume_state(
        self,
        *,
        tenant_id: str,
        session_id: str,
        channel_id: str,
        state_digest: str,
        provider_token_digest: Optional[str],
    ) -> SocialOAuthStateRecord:
        _validate_lookup(
            tenant_id, session_id, channel_id, state_digest, provider_token_digest
        )
        consumed_at = self._clock()
        with self._lock, self._connection:
            row = self._connection.execute(
                """
                SELECT * FROM social_oauth_states
                WHERE tenant_id = ? AND session_id = ? AND channel_id = ?
                  AND state_digest = ?
                  AND ((provider_token_digest IS NULL AND ? IS NULL)
                       OR provider_token_digest = ?)
                  AND consumed_at IS NULL AND expires_at > ?
                """,
                (
                    tenant_id,
                    session_id,
                    channel_id,
                    state_digest,
                    provider_token_digest,
                    provider_token_digest,
                    consumed_at,
                ),
            ).fetchone()
            if row is None:
                raise SocialOAuthStateUnavailableError(
                    "social OAuth state is unavailable"
                )
            cursor = self._connection.execute(
                """
                UPDATE social_oauth_states SET consumed_at = ?
                WHERE state_id = ? AND consumed_at IS NULL
                """,
                (consumed_at, row["state_id"]),
            )
            if cursor.rowcount != 1:
                raise SocialOAuthStateUnavailableError(
                    "social OAuth state is unavailable"
                )
            return _state_from_mapping({**dict(row), "consumed_at": consumed_at})

    def upsert_connection(self, record: SocialConnectionRecord) -> None:
        _validate_connection(record)
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO social_connections(
                    tenant_id, channel_id, account_id, account_username,
                    encrypted_tokens, key_id, scopes_json, token_expires_at,
                    connected_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, channel_id) DO UPDATE SET
                    account_id = excluded.account_id,
                    account_username = excluded.account_username,
                    encrypted_tokens = excluded.encrypted_tokens,
                    key_id = excluded.key_id,
                    scopes_json = excluded.scopes_json,
                    token_expires_at = excluded.token_expires_at,
                    connected_at = excluded.connected_at,
                    updated_at = excluded.updated_at
                """,
                (
                    record.tenant_id,
                    record.channel_id,
                    record.account_id,
                    record.account_username,
                    record.encrypted_tokens.ciphertext,
                    record.encrypted_tokens.key_id,
                    canonical_json(list(record.scopes)),
                    record.token_expires_at,
                    record.connected_at,
                    record.updated_at,
                ),
            )

    def get_connection(
        self, tenant_id: str, channel_id: str
    ) -> Optional[SocialConnectionRecord]:
        _validate_tenant_channel(tenant_id, channel_id)
        with self._lock:
            row = self._connection.execute(
                """
                SELECT * FROM social_connections
                WHERE tenant_id = ? AND channel_id = ?
                """,
                (tenant_id, channel_id),
            ).fetchone()
        return None if row is None else _connection_from_mapping(dict(row))

    def list_connections(self, tenant_id: str) -> Tuple[SocialConnectionRecord, ...]:
        if not _IDENTIFIER.fullmatch(tenant_id):
            raise ValueError("tenant_id is invalid")
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM social_connections
                WHERE tenant_id = ? ORDER BY channel_id ASC
                """,
                (tenant_id,),
            ).fetchall()
        return tuple(_connection_from_mapping(dict(row)) for row in rows)

    def delete_connection(self, tenant_id: str, channel_id: str) -> bool:
        _validate_tenant_channel(tenant_id, channel_id)
        with self._lock, self._connection:
            row = self._connection.execute(
                """
                SELECT encrypted_tokens
                FROM social_connections
                WHERE tenant_id = ? AND channel_id = ?
                """,
                (tenant_id, channel_id),
            ).fetchone()
            if row is None:
                return False
            self._connection.execute(
                """
                UPDATE social_connections
                SET encrypted_tokens = ?, account_id = ?, account_username = ?,
                    scopes_json = '[]', token_expires_at = NULL, updated_at = ?
                WHERE tenant_id = ? AND channel_id = ?
                """,
                (
                    "0" * max(32, len(str(row["encrypted_tokens"]))),
                    "deleted-account",
                    "deleted-account",
                    self._clock(),
                    tenant_id,
                    channel_id,
                ),
            )
            cursor = self._connection.execute(
                """
                DELETE FROM social_connections
                WHERE tenant_id = ? AND channel_id = ?
                """,
                (tenant_id, channel_id),
            )
            return cursor.rowcount == 1

    def connection_count(self, tenant_id: str) -> int:
        if not _IDENTIFIER.fullmatch(tenant_id):
            raise ValueError("tenant_id is invalid")
        with self._lock:
            row = self._connection.execute(
                "SELECT COUNT(*) AS total FROM social_connections WHERE tenant_id = ?",
                (tenant_id,),
            ).fetchone()
        return int(row["total"])

    def check(self) -> None:
        with self._lock:
            row = self._connection.execute(
                "SELECT COUNT(*) AS total FROM social_connections"
            ).fetchone()
        if row is None:
            raise RuntimeError("social OAuth SQLite readiness failed")

    def close(self) -> None:
        with self._lock:
            self._connection.close()


def _validate_state(record: SocialOAuthStateRecord) -> None:
    _validate_lookup(
        record.tenant_id,
        record.session_id,
        record.channel_id,
        record.state_digest,
        record.provider_token_digest,
    )
    if not _IDENTIFIER.fullmatch(record.state_id):
        raise ValueError("state_id is invalid")
    if not record.encrypted_payload.ciphertext or not _IDENTIFIER.fullmatch(
        record.encrypted_payload.key_id
    ):
        raise ValueError("encrypted OAuth payload is invalid")
    created = datetime.fromisoformat(record.created_at)
    expires = datetime.fromisoformat(record.expires_at)
    if expires <= created or record.consumed_at is not None:
        raise ValueError("social OAuth state lifetime is invalid")


def _validate_connection(record: SocialConnectionRecord) -> None:
    _validate_tenant_channel(record.tenant_id, record.channel_id)
    for label, value in (
        ("account_id", record.account_id),
        ("account_username", record.account_username),
    ):
        if not _IDENTIFIER.fullmatch(value):
            raise ValueError("{} is invalid".format(label))
    if not record.encrypted_tokens.ciphertext or not _IDENTIFIER.fullmatch(
        record.encrypted_tokens.key_id
    ):
        raise ValueError("encrypted social tokens are invalid")
    if not record.scopes or len(record.scopes) > 32 or any(
        not isinstance(scope, str) or not scope or len(scope) > 128
        for scope in record.scopes
    ):
        raise ValueError("social scopes are invalid")
    datetime.fromisoformat(record.connected_at)
    datetime.fromisoformat(record.updated_at)
    if record.token_expires_at is not None:
        datetime.fromisoformat(record.token_expires_at)


def _validate_lookup(
    tenant_id: str,
    session_id: str,
    channel_id: str,
    state_digest: str,
    provider_token_digest: Optional[str],
) -> None:
    if not _IDENTIFIER.fullmatch(tenant_id) or not _IDENTIFIER.fullmatch(session_id):
        raise ValueError("social OAuth identity is invalid")
    if not _CHANNEL.fullmatch(channel_id) or not _SHA256.fullmatch(state_digest):
        raise ValueError("social OAuth state lookup is invalid")
    if provider_token_digest is not None and not _SHA256.fullmatch(
        provider_token_digest
    ):
        raise ValueError("provider token digest is invalid")


def _validate_tenant_channel(tenant_id: str, channel_id: str) -> None:
    if not _IDENTIFIER.fullmatch(tenant_id) or not _CHANNEL.fullmatch(channel_id):
        raise ValueError("social connection identity is invalid")


def _state_from_mapping(row: Mapping[str, object]) -> SocialOAuthStateRecord:
    return SocialOAuthStateRecord(
        state_id=str(row["state_id"]),
        tenant_id=str(row["tenant_id"]),
        session_id=str(row["session_id"]),
        channel_id=str(row["channel_id"]),
        state_digest=str(row["state_digest"]),
        provider_token_digest=(
            None
            if row["provider_token_digest"] is None
            else str(row["provider_token_digest"])
        ),
        encrypted_payload=EncryptedSocialValue(
            key_id=str(row["key_id"]), ciphertext=str(row["encrypted_payload"])
        ),
        created_at=str(row["created_at"]),
        expires_at=str(row["expires_at"]),
        consumed_at=(
            None if row["consumed_at"] is None else str(row["consumed_at"])
        ),
    )


def _connection_from_mapping(row: Mapping[str, object]) -> SocialConnectionRecord:
    raw_scopes = row["scopes_json"]
    scopes = raw_scopes if isinstance(raw_scopes, list) else json.loads(str(raw_scopes))
    if not isinstance(scopes, list) or not all(isinstance(item, str) for item in scopes):
        raise SocialOAuthStoreError("stored social scopes are invalid")
    return SocialConnectionRecord(
        tenant_id=str(row["tenant_id"]),
        channel_id=str(row["channel_id"]),
        account_id=str(row["account_id"]),
        account_username=str(row["account_username"]),
        encrypted_tokens=EncryptedSocialValue(
            key_id=str(row["key_id"]), ciphertext=str(row["encrypted_tokens"])
        ),
        scopes=tuple(scopes),
        token_expires_at=(
            None if row["token_expires_at"] is None else str(row["token_expires_at"])
        ),
        connected_at=str(row["connected_at"]),
        updated_at=str(row["updated_at"]),
    )


class PostgresSocialOAuthStore:
    def __init__(self, database: object, *, clock: Clock = utc_now) -> None:
        if not hasattr(database, "pool"):
            raise TypeError("PostgreSQL social OAuth store requires a runtime database")
        self._database = database
        self._clock = clock

    def create_state(self, record: SocialOAuthStateRecord) -> None:
        _validate_state(record)
        with self._database.pool.connection() as connection:
            connection.execute(
                """
                DELETE FROM public.social_oauth_states
                WHERE tenant_id = %s AND session_id = %s AND channel_id = %s
                  AND consumed_at IS NULL
                """,
                (record.tenant_id, record.session_id, record.channel_id),
            )
            try:
                connection.execute(
                    """
                    INSERT INTO public.social_oauth_states(
                        state_id, tenant_id, session_id, channel_id,
                        state_digest, provider_token_digest,
                        encrypted_payload, key_id, created_at, expires_at, consumed_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL)
                    """,
                    (
                        record.state_id,
                        record.tenant_id,
                        record.session_id,
                        record.channel_id,
                        record.state_digest,
                        record.provider_token_digest,
                        record.encrypted_payload.ciphertext,
                        record.encrypted_payload.key_id,
                        record.created_at,
                        record.expires_at,
                    ),
                )
            except Exception as error:
                raise SocialOAuthStoreError(
                    "social OAuth state could not be created"
                ) from error

    def consume_state(
        self,
        *,
        tenant_id: str,
        session_id: str,
        channel_id: str,
        state_digest: str,
        provider_token_digest: Optional[str],
    ) -> SocialOAuthStateRecord:
        _validate_lookup(
            tenant_id, session_id, channel_id, state_digest, provider_token_digest
        )
        consumed_at = self._clock()
        with self._database.pool.connection() as connection:
            row = connection.execute(
                """
                UPDATE public.social_oauth_states
                SET consumed_at = %s
                WHERE tenant_id = %s AND session_id = %s AND channel_id = %s
                  AND state_digest = %s
                  AND ((provider_token_digest IS NULL AND %s::text IS NULL)
                       OR provider_token_digest = %s::text)
                  AND consumed_at IS NULL AND expires_at > %s
                RETURNING state_id, tenant_id, session_id, channel_id,
                          state_digest, provider_token_digest, encrypted_payload,
                          key_id, created_at, expires_at, consumed_at
                """,
                (
                    consumed_at,
                    tenant_id,
                    session_id,
                    channel_id,
                    state_digest,
                    provider_token_digest,
                    provider_token_digest,
                    consumed_at,
                ),
            ).fetchone()
        if row is None:
            raise SocialOAuthStateUnavailableError("social OAuth state is unavailable")
        return _state_from_mapping(row)

    def upsert_connection(self, record: SocialConnectionRecord) -> None:
        _validate_connection(record)
        with self._database.pool.connection() as connection:
            connection.execute(
                """
                INSERT INTO public.social_connections(
                    tenant_id, channel_id, account_id, account_username,
                    encrypted_tokens, key_id, scopes_json, token_expires_at,
                    connected_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
                ON CONFLICT(tenant_id, channel_id) DO UPDATE SET
                    account_id = excluded.account_id,
                    account_username = excluded.account_username,
                    encrypted_tokens = excluded.encrypted_tokens,
                    key_id = excluded.key_id,
                    scopes_json = excluded.scopes_json,
                    token_expires_at = excluded.token_expires_at,
                    connected_at = excluded.connected_at,
                    updated_at = excluded.updated_at
                """,
                (
                    record.tenant_id,
                    record.channel_id,
                    record.account_id,
                    record.account_username,
                    record.encrypted_tokens.ciphertext,
                    record.encrypted_tokens.key_id,
                    canonical_json(list(record.scopes)),
                    record.token_expires_at,
                    record.connected_at,
                    record.updated_at,
                ),
            )

    def get_connection(
        self, tenant_id: str, channel_id: str
    ) -> Optional[SocialConnectionRecord]:
        _validate_tenant_channel(tenant_id, channel_id)
        with self._database.pool.connection() as connection:
            row = connection.execute(
                """
                SELECT tenant_id, channel_id, account_id, account_username,
                       encrypted_tokens, key_id, scopes_json, token_expires_at,
                       connected_at, updated_at
                FROM public.social_connections
                WHERE tenant_id = %s AND channel_id = %s
                """,
                (tenant_id, channel_id),
            ).fetchone()
        return None if row is None else _connection_from_mapping(row)

    def list_connections(self, tenant_id: str) -> Tuple[SocialConnectionRecord, ...]:
        if not _IDENTIFIER.fullmatch(tenant_id):
            raise ValueError("tenant_id is invalid")
        with self._database.pool.connection() as connection:
            rows = connection.execute(
                """
                SELECT tenant_id, channel_id, account_id, account_username,
                       encrypted_tokens, key_id, scopes_json, token_expires_at,
                       connected_at, updated_at
                FROM public.social_connections
                WHERE tenant_id = %s ORDER BY channel_id ASC
                """,
                (tenant_id,),
            ).fetchall()
        return tuple(_connection_from_mapping(row) for row in rows)

    def delete_connection(self, tenant_id: str, channel_id: str) -> bool:
        _validate_tenant_channel(tenant_id, channel_id)
        with self._database.pool.connection() as connection:
            row = connection.execute(
                """
                SELECT encrypted_tokens
                FROM public.social_connections
                WHERE tenant_id = %s AND channel_id = %s
                FOR UPDATE
                """,
                (tenant_id, channel_id),
            ).fetchone()
            if row is None:
                return False
            connection.execute(
                """
                UPDATE public.social_connections
                SET encrypted_tokens = %s, account_id = 'deleted-account',
                    account_username = 'deleted-account', scopes_json = '[]'::jsonb,
                    token_expires_at = NULL, updated_at = %s
                WHERE tenant_id = %s AND channel_id = %s
                """,
                (
                    "0" * max(32, len(str(row["encrypted_tokens"]))),
                    self._clock(),
                    tenant_id,
                    channel_id,
                ),
            )
            cursor = connection.execute(
                """
                DELETE FROM public.social_connections
                WHERE tenant_id = %s AND channel_id = %s
                """,
                (tenant_id, channel_id),
            )
            return cursor.rowcount == 1

    def connection_count(self, tenant_id: str) -> int:
        if not _IDENTIFIER.fullmatch(tenant_id):
            raise ValueError("tenant_id is invalid")
        with self._database.pool.connection() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM public.social_connections WHERE tenant_id = %s
                """,
                (tenant_id,),
            ).fetchone()
        return int(row["total"])

    def clear_tenant(self, tenant_id: str) -> None:
        if not _IDENTIFIER.fullmatch(tenant_id):
            raise ValueError("tenant_id is invalid")
        with self._database.pool.connection() as connection:
            connection.execute(
                "DELETE FROM public.social_oauth_states WHERE tenant_id = %s",
                (tenant_id,),
            )
            connection.execute(
                "DELETE FROM public.social_connections WHERE tenant_id = %s",
                (tenant_id,),
            )

    def check(self) -> None:
        with self._database.pool.connection() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM public.social_connections"
            ).fetchone()
        if row is None:
            raise RuntimeError("social OAuth PostgreSQL readiness failed")

    def close(self) -> None:
        return None
