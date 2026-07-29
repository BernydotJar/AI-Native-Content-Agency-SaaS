from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Mapping, Optional

from .memory import utc_now
from .publication_media_store import (
    PublicationMediaConflictError,
    PublicationMediaRecord,
    PublicationMediaReservation,
    PublicationMediaStoreError,
    validate_publication_media_identity,
    validate_publication_media_record,
)


class PostgresPublicationMediaStore:
    def __init__(self, database: object, *, clock=utc_now) -> None:
        if not hasattr(database, "pool"):
            raise TypeError("PostgreSQL publication media store requires a runtime database")
        self._database = database
        self._clock = clock

    def create(
        self, record: PublicationMediaRecord, content: bytes
    ) -> PublicationMediaRecord:
        validate_publication_media_record(record, content)
        with self._database.pool.connection() as connection:
            try:
                self._insert(connection, record, content)
            except Exception as error:
                raise PublicationMediaConflictError(
                    "publication media conflicts with existing durable state"
                ) from error
        return record

    def reserve(
        self, record: PublicationMediaRecord, content: bytes
    ) -> PublicationMediaReservation:
        validate_publication_media_record(record, content)
        lock_id = "publication-media:{}:{}".format(
            record.tenant_id, record.binding_digest or record.media_id
        )
        with self._database.pool.connection() as connection:
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))", (lock_id,)
            )
            existing = connection.execute(
                """
                SELECT * FROM public.publication_media_objects
                WHERE media_id = %s
                   OR (tenant_id = %s AND idempotency_digest = %s)
                   OR (tenant_id = %s AND binding_digest = %s)
                ORDER BY CASE
                    WHEN tenant_id = %s AND idempotency_digest = %s THEN 0
                    WHEN tenant_id = %s AND binding_digest = %s THEN 1
                    ELSE 2
                END
                LIMIT 1
                FOR UPDATE
                """,
                (
                    record.media_id,
                    record.tenant_id,
                    record.idempotency_digest or None,
                    record.tenant_id,
                    record.binding_digest or None,
                    record.tenant_id,
                    record.idempotency_digest or None,
                    record.tenant_id,
                    record.binding_digest or None,
                ),
            ).fetchone()
            if existing is not None:
                stored = _record_from_mapping(existing)
                if stored.binding_digest != record.binding_digest:
                    raise PublicationMediaConflictError(
                        "publication media idempotency key conflicts with prior input"
                    )
                stored_content = bytes(existing["content"])
                if stored_content != content:
                    raise PublicationMediaConflictError(
                        "publication media bytes conflict with durable binding"
                    )
                return PublicationMediaReservation(
                    record=stored, created=False, replayed=True
                )
            try:
                self._insert(connection, record, content)
            except Exception as error:
                raise PublicationMediaConflictError(
                    "publication media conflicts with existing durable state"
                ) from error
        return PublicationMediaReservation(record=record, created=True, replayed=False)

    def get(self, tenant_id: str, media_id: str) -> Optional[PublicationMediaRecord]:
        validate_publication_media_identity(tenant_id, media_id)
        with self._database.pool.connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM public.publication_media_objects
                WHERE tenant_id = %s AND media_id = %s
                """,
                (tenant_id, media_id),
            ).fetchone()
        return None if row is None else _record_from_mapping(row)

    def get_content(self, tenant_id: str, media_id: str) -> bytes:
        validate_publication_media_identity(tenant_id, media_id)
        with self._database.pool.connection() as connection:
            row = connection.execute(
                """
                SELECT content FROM public.publication_media_objects
                WHERE tenant_id = %s AND media_id = %s
                """,
                (tenant_id, media_id),
            ).fetchone()
        if row is None:
            raise KeyError("publication media not found")
        return bytes(row["content"])

    def get_public(
        self, public_token_digest: str
    ) -> tuple[PublicationMediaRecord, bytes]:
        if len(public_token_digest) != 64 or any(
            character not in "0123456789abcdef" for character in public_token_digest
        ):
            raise KeyError("publication media not found")
        now = self._clock()
        with self._database.pool.connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM public.publication_media_objects
                WHERE public_token_digest = %s
                  AND revoked_at IS NULL
                  AND expires_at > %s
                """,
                (public_token_digest, now),
            ).fetchone()
        if row is None:
            raise KeyError("publication media not found")
        record = _record_from_mapping(row)
        content = bytes(row["content"])
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
        with self._database.pool.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE public.publication_media_objects
                SET revoked_at = %s, revocation_reason = %s
                WHERE tenant_id = %s AND media_id = %s AND revoked_at IS NULL
                """,
                (revoked_at, reason, tenant_id, media_id),
            )
            if cursor.rowcount != 1:
                raise KeyError("publication media not found")

    def check(self) -> None:
        with self._database.pool.connection() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM public.publication_media_objects"
            ).fetchone()
        if row is None:
            raise RuntimeError("publication media PostgreSQL readiness failed")

    def close(self) -> None:
        return None

    @staticmethod
    def _insert(connection: object, record: PublicationMediaRecord, content: bytes) -> None:
        connection.execute(
            """
            INSERT INTO public.publication_media_objects(
                media_id, tenant_id, run_id, channel_id, content_type,
                byte_size, sha256, width, height, alt_text,
                rights_attested_by, public_token_digest, public_signing_key_id,
                idempotency_digest, binding_digest, content,
                created_at, expires_at, revoked_at, revocation_reason
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
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
                content,
                record.created_at,
                record.expires_at,
                record.revoked_at,
                record.revocation_reason,
            ),
        )


def _iso(value: object) -> str:
    return value.isoformat() if isinstance(value, datetime) else str(value)


def _record_from_mapping(row: Mapping[str, object]) -> PublicationMediaRecord:
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
        created_at=_iso(row["created_at"]),
        expires_at=_iso(row["expires_at"]),
        revoked_at=None if row["revoked_at"] is None else _iso(row["revoked_at"]),
        revocation_reason=str(row["revocation_reason"]),
    )
