from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Optional

from .memory import utc_now


Clock = callable
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,255}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_CHANNEL = re.compile(r"^instagram$")
_MAX_ALT_TEXT_BYTES = 2_000
_MAX_CONTENT_BYTES = 8 * 1024 * 1024


class PublicationMediaStoreError(RuntimeError):
    pass


class PublicationMediaConflictError(PublicationMediaStoreError):
    pass


@dataclass(frozen=True)
class PublicationMediaRecord:
    media_id: str
    tenant_id: str
    run_id: str
    channel_id: str
    content_type: str
    byte_size: int
    sha256: str
    width: int
    height: int
    alt_text: str
    rights_attested_by: str
    public_token_digest: str
    public_signing_key_id: str
    created_at: str
    expires_at: str
    revoked_at: Optional[str]
    idempotency_digest: str = ""
    binding_digest: str = ""
    revocation_reason: str = ""


@dataclass(frozen=True)
class PublicationMediaReservation:
    record: PublicationMediaRecord
    created: bool
    replayed: bool


class SQLitePublicationMediaStore:
    def __init__(self, database_path: str | Path, *, clock=utc_now) -> None:
        self._clock = clock
        self._connection = sqlite3.connect(
            str(database_path), timeout=30, check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA secure_delete = ON")
        self._lock = RLock()
        self._initialize()

    def _initialize(self) -> None:
        with self._lock, self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS publication_media_objects (
                    media_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    byte_size INTEGER NOT NULL,
                    sha256 TEXT NOT NULL,
                    width INTEGER NOT NULL,
                    height INTEGER NOT NULL,
                    alt_text TEXT NOT NULL,
                    rights_attested_by TEXT NOT NULL,
                    public_token_digest TEXT NOT NULL UNIQUE,
                    public_signing_key_id TEXT NOT NULL DEFAULT 'legacy',
                    idempotency_digest TEXT,
                    binding_digest TEXT,
                    content BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT,
                    revocation_reason TEXT NOT NULL DEFAULT '',
                    UNIQUE (tenant_id, idempotency_digest),
                    UNIQUE (tenant_id, binding_digest),
                    UNIQUE (tenant_id, run_id, channel_id, sha256)
                );
                CREATE INDEX IF NOT EXISTS idx_publication_media_tenant_run
                    ON publication_media_objects(tenant_id, run_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_publication_media_public_lookup
                    ON publication_media_objects(public_token_digest, expires_at, revoked_at);
                """
            )
            columns = {
                str(row[1])
                for row in self._connection.execute(
                    "PRAGMA table_info(publication_media_objects)"
                ).fetchall()
            }
            if "public_signing_key_id" not in columns:
                self._connection.execute(
                    "ALTER TABLE publication_media_objects "
                    "ADD COLUMN public_signing_key_id TEXT NOT NULL DEFAULT 'legacy'"
                )

    def create(
        self, record: PublicationMediaRecord, content: bytes
    ) -> PublicationMediaRecord:
        validate_publication_media_record(record, content)
        with self._lock, self._connection:
            try:
                self._insert(record, content)
            except sqlite3.IntegrityError as error:
                raise PublicationMediaConflictError(
                    "publication media conflicts with existing durable state"
                ) from error
        return record

    def reserve(
        self, record: PublicationMediaRecord, content: bytes
    ) -> PublicationMediaReservation:
        validate_publication_media_record(record, content)
        with self._lock, self._connection:
            existing = self._find_existing(record)
            if existing is not None:
                if existing.binding_digest != record.binding_digest:
                    raise PublicationMediaConflictError(
                        "publication media idempotency key conflicts with prior input"
                    )
                stored_content = self._content_for(existing.media_id)
                if stored_content != content:
                    raise PublicationMediaConflictError(
                        "publication media bytes conflict with durable binding"
                    )
                return PublicationMediaReservation(
                    record=existing, created=False, replayed=True
                )
            try:
                self._insert(record, content)
            except sqlite3.IntegrityError as error:
                # A concurrent writer may have inserted the same binding. Resolve once
                # from durable state instead of creating a duplicate object.
                existing = self._find_existing(record)
                if existing is None or existing.binding_digest != record.binding_digest:
                    raise PublicationMediaConflictError(
                        "publication media conflicts with existing durable state"
                    ) from error
                if self._content_for(existing.media_id) != content:
                    raise PublicationMediaConflictError(
                        "publication media bytes conflict with durable binding"
                    ) from error
                return PublicationMediaReservation(
                    record=existing, created=False, replayed=True
                )
            return PublicationMediaReservation(record=record, created=True, replayed=False)

    def get(self, tenant_id: str, media_id: str) -> Optional[PublicationMediaRecord]:
        validate_publication_media_identity(tenant_id, media_id)
        with self._lock:
            row = self._connection.execute(
                """
                SELECT * FROM publication_media_objects
                WHERE tenant_id = ? AND media_id = ?
                """,
                (tenant_id, media_id),
            ).fetchone()
        return None if row is None else _record_from_row(row)

    def get_content(self, tenant_id: str, media_id: str) -> bytes:
        record = self.get(tenant_id, media_id)
        if record is None:
            raise KeyError("publication media not found")
        with self._lock:
            return self._content_for(media_id)

    def get_public(
        self, public_token_digest: str
    ) -> tuple[PublicationMediaRecord, bytes]:
        if not _SHA256.fullmatch(public_token_digest):
            raise KeyError("publication media not found")
        now = self._clock()
        with self._lock:
            row = self._connection.execute(
                """
                SELECT * FROM publication_media_objects
                WHERE public_token_digest = ?
                  AND revoked_at IS NULL
                  AND expires_at > ?
                """,
                (public_token_digest, now),
            ).fetchone()
            if row is None:
                raise KeyError("publication media not found")
            content = bytes(row["content"])
        record = _record_from_row(row)
        if hashlib.sha256(content).hexdigest() != record.sha256:
            raise PublicationMediaStoreError(
                "publication media bytes do not match durable hash"
            )
        return record, content

    def revoke(self, tenant_id: str, media_id: str, reason: str) -> None:
        validate_publication_media_identity(tenant_id, media_id)
        if not reason or len(reason.encode("utf-8")) > 512:
            raise ValueError("publication media revocation reason is invalid")
        revoked_at = self._clock()
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """
                UPDATE publication_media_objects
                SET revoked_at = ?, revocation_reason = ?
                WHERE tenant_id = ? AND media_id = ? AND revoked_at IS NULL
                """,
                (revoked_at, reason, tenant_id, media_id),
            )
            if cursor.rowcount != 1:
                raise KeyError("publication media not found")

    def check(self) -> None:
        with self._lock:
            row = self._connection.execute(
                "SELECT COUNT(*) AS total FROM publication_media_objects"
            ).fetchone()
        if row is None:
            raise RuntimeError("publication media SQLite readiness failed")

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _insert(self, record: PublicationMediaRecord, content: bytes) -> None:
        self._connection.execute(
            """
            INSERT INTO publication_media_objects(
                media_id, tenant_id, run_id, channel_id, content_type,
                byte_size, sha256, width, height, alt_text,
                rights_attested_by, public_token_digest, public_signing_key_id,
                idempotency_digest, binding_digest, content,
                created_at, expires_at, revoked_at, revocation_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.media_id,
                record.tenant_id,
                record.run_id,
                record.channel_id,
                record.content_type,
                record.byte_size,
                record.sha256,
                record.width,
                record.height,
                record.alt_text,
                record.rights_attested_by,
                record.public_token_digest,
                record.public_signing_key_id,
                record.idempotency_digest or None,
                record.binding_digest or None,
                sqlite3.Binary(content),
                record.created_at,
                record.expires_at,
                record.revoked_at,
                record.revocation_reason,
            ),
        )

    def _find_existing(
        self, record: PublicationMediaRecord
    ) -> Optional[PublicationMediaRecord]:
        clauses = ["media_id = ?"]
        values: list[object] = [record.media_id]
        if record.idempotency_digest:
            clauses.append("(tenant_id = ? AND idempotency_digest = ?)")
            values.extend((record.tenant_id, record.idempotency_digest))
        if record.binding_digest:
            clauses.append("(tenant_id = ? AND binding_digest = ?)")
            values.extend((record.tenant_id, record.binding_digest))
        row = self._connection.execute(
            "SELECT * FROM publication_media_objects WHERE " + " OR ".join(clauses),
            tuple(values),
        ).fetchone()
        return None if row is None else _record_from_row(row)

    def _content_for(self, media_id: str) -> bytes:
        row = self._connection.execute(
            "SELECT content FROM publication_media_objects WHERE media_id = ?",
            (media_id,),
        ).fetchone()
        if row is None:
            raise KeyError("publication media not found")
        return bytes(row["content"])


def validate_publication_media_record(record: PublicationMediaRecord, content: bytes) -> None:
    validate_publication_media_identity(record.tenant_id, record.media_id)
    for name, value in (
        ("run_id", record.run_id),
        ("rights_attested_by", record.rights_attested_by),
    ):
        if not _IDENTIFIER.fullmatch(value):
            raise ValueError("{} is invalid".format(name))
    if not _CHANNEL.fullmatch(record.channel_id):
        raise ValueError("publication media channel is invalid")
    if record.content_type != "image/jpeg":
        raise ValueError("publication media content type is invalid")
    if not content or len(content) > _MAX_CONTENT_BYTES or record.byte_size != len(content):
        raise ValueError("publication media byte size is invalid")
    if not _SHA256.fullmatch(record.sha256) or hashlib.sha256(content).hexdigest() != record.sha256:
        raise ValueError("publication media hash is invalid")
    if not _SHA256.fullmatch(record.public_token_digest):
        raise ValueError("publication media token digest is invalid")
    if not _IDENTIFIER.fullmatch(record.public_signing_key_id):
        raise ValueError("publication media signing key identifier is invalid")
    for optional_digest in (record.idempotency_digest, record.binding_digest):
        if optional_digest and not _SHA256.fullmatch(optional_digest):
            raise ValueError("publication media command digest is invalid")
    if record.width <= 0 or record.height <= 0:
        raise ValueError("publication media dimensions are invalid")
    if not record.alt_text.strip() or len(record.alt_text.encode("utf-8")) > _MAX_ALT_TEXT_BYTES:
        raise ValueError("publication media alt text is invalid")
    created = datetime.fromisoformat(record.created_at)
    expires = datetime.fromisoformat(record.expires_at)
    if expires <= created:
        raise ValueError("publication media expiry is invalid")
    if record.revoked_at is not None:
        datetime.fromisoformat(record.revoked_at)


def validate_publication_media_identity(tenant_id: str, media_id: str) -> None:
    if not _IDENTIFIER.fullmatch(tenant_id) or not _IDENTIFIER.fullmatch(media_id):
        raise ValueError("publication media identity is invalid")


def _record_from_row(row: sqlite3.Row) -> PublicationMediaRecord:
    return PublicationMediaRecord(
        media_id=str(row["media_id"]),
        tenant_id=str(row["tenant_id"]),
        run_id=str(row["run_id"]),
        channel_id=str(row["channel_id"]),
        content_type=str(row["content_type"]),
        byte_size=int(row["byte_size"]),
        sha256=str(row["sha256"]),
        width=int(row["width"]),
        height=int(row["height"]),
        alt_text=str(row["alt_text"]),
        rights_attested_by=str(row["rights_attested_by"]),
        public_token_digest=str(row["public_token_digest"]),
        public_signing_key_id=str(row["public_signing_key_id"]),
        idempotency_digest=(
            "" if row["idempotency_digest"] is None else str(row["idempotency_digest"])
        ),
        binding_digest=(
            "" if row["binding_digest"] is None else str(row["binding_digest"])
        ),
        created_at=str(row["created_at"]),
        expires_at=str(row["expires_at"]),
        revoked_at=None if row["revoked_at"] is None else str(row["revoked_at"]),
        revocation_reason=str(row["revocation_reason"]),
    )
