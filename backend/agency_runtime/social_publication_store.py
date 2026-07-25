from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Mapping, Optional, Tuple

from .memory import utc_now
from .utils import canonical_json

_CHANNEL = re.compile(r"^(x|instagram)$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,255}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_STATUSES = frozenset({"pending", "succeeded", "unknown", "failed", "revoked"})


class SocialPublicationStoreError(RuntimeError):
    pass


class SocialPublicationConflictError(SocialPublicationStoreError):
    pass


class SocialPublicationStateError(SocialPublicationStoreError):
    pass


@dataclass(frozen=True)
class SocialPublicationIntent:
    intent_id: str
    tenant_id: str
    channel_id: str
    account_id: str
    run_id: str
    artifact_id: str
    artifact_hash: str
    content_hash: str
    media_url_hash: Optional[str]
    media_hash: Optional[str]
    confirmation_hash: Optional[str]
    greenlight_id: str
    greenlight_fencing_token: int
    budget_cents: int
    idempotency_digest: str
    binding_digest: str
    status: str
    execution_fencing_token: int
    provider_container_id: Optional[str]
    provider_post_id: Optional[str]
    receipt: Mapping[str, object]
    failure_reason: str
    created_at: str
    updated_at: str
    completed_at: Optional[str]
    revoked_at: Optional[str]


@dataclass(frozen=True)
class SocialPublicationReservation:
    intent: SocialPublicationIntent
    executable: bool
    replayed: bool


class SQLiteSocialPublicationStore:
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
                CREATE TABLE IF NOT EXISTS social_publication_intents (
                    intent_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    artifact_id TEXT NOT NULL,
                    artifact_hash TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    media_url_hash TEXT,
                    media_hash TEXT,
                    confirmation_hash TEXT,
                    greenlight_id TEXT NOT NULL,
                    greenlight_fencing_token INTEGER NOT NULL,
                    budget_cents INTEGER NOT NULL,
                    idempotency_digest TEXT NOT NULL,
                    binding_digest TEXT NOT NULL,
                    status TEXT NOT NULL,
                    execution_fencing_token INTEGER NOT NULL,
                    provider_container_id TEXT,
                    provider_post_id TEXT,
                    receipt_json TEXT NOT NULL,
                    failure_reason TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    revoked_at TEXT,
                    UNIQUE (tenant_id, idempotency_digest),
                    UNIQUE (tenant_id, binding_digest)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS uq_social_publication_binding
                    ON social_publication_intents(tenant_id, binding_digest);
                CREATE INDEX IF NOT EXISTS idx_social_publication_run
                    ON social_publication_intents(tenant_id, run_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_social_publication_account
                    ON social_publication_intents(
                        tenant_id, channel_id, account_id, status, updated_at DESC
                    );
                """
            )
            columns = {
                str(row["name"])
                for row in self._connection.execute(
                    "PRAGMA table_info(social_publication_intents)"
                ).fetchall()
            }
            if "confirmation_hash" not in columns:
                self._connection.execute(
                    "ALTER TABLE social_publication_intents "
                    "ADD COLUMN confirmation_hash TEXT"
                )

    def reserve(self, intent: SocialPublicationIntent) -> SocialPublicationReservation:
        validate_intent(intent, require_pending=True)
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                existing = self._connection.execute(
                    """
                    SELECT * FROM social_publication_intents
                    WHERE tenant_id = ?
                      AND (idempotency_digest = ? OR binding_digest = ?)
                    ORDER BY CASE WHEN idempotency_digest = ? THEN 0 ELSE 1 END
                    LIMIT 1
                    """,
                    (
                        intent.tenant_id,
                        intent.idempotency_digest,
                        intent.binding_digest,
                        intent.idempotency_digest,
                    ),
                ).fetchone()
                if existing is not None:
                    record = intent_from_mapping(dict(existing))
                    if (
                        record.idempotency_digest == intent.idempotency_digest
                        and record.binding_digest != intent.binding_digest
                    ):
                        raise SocialPublicationConflictError(
                            "publication idempotency key conflicts with a prior binding"
                        )
                    if record.binding_digest != intent.binding_digest:
                        raise SocialPublicationConflictError(
                            "publication binding conflicts with a prior intent"
                        )
                    self._connection.commit()
                    return SocialPublicationReservation(
                        record,
                        executable=False,
                        replayed=record.status == "succeeded",
                    )
                self._connection.execute(
                    """
                    INSERT INTO social_publication_intents(
                        intent_id, tenant_id, channel_id, account_id, run_id,
                        artifact_id, artifact_hash, content_hash, media_url_hash,
                        media_hash, confirmation_hash, greenlight_id,
                        greenlight_fencing_token, budget_cents, idempotency_digest,
                        binding_digest, status,
                        execution_fencing_token, provider_container_id,
                        provider_post_id, receipt_json, failure_reason, created_at,
                        updated_at, completed_at, revoked_at
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    intent_values(intent),
                )
                self._connection.commit()
                return SocialPublicationReservation(intent, True, False)
            except Exception:
                self._connection.rollback()
                raise

    def get(self, tenant_id: str, intent_id: str) -> SocialPublicationIntent:
        validate_identity(tenant_id, intent_id)
        with self._lock:
            row = self._connection.execute(
                """
                SELECT * FROM social_publication_intents
                WHERE tenant_id = ? AND intent_id = ?
                """,
                (tenant_id, intent_id),
            ).fetchone()
        if row is None:
            raise KeyError("social publication intent not found")
        return intent_from_mapping(dict(row))

    def record_container(
        self, tenant_id: str, intent_id: str, fence: int, container_id: str
    ) -> SocialPublicationIntent:
        return self._transition(
            tenant_id,
            intent_id,
            fence,
            status="pending",
            provider_container_id=container_id,
        )

    def complete(
        self,
        tenant_id: str,
        intent_id: str,
        fence: int,
        provider_post_id: str,
        receipt: Mapping[str, object],
    ) -> SocialPublicationIntent:
        return self._transition(
            tenant_id,
            intent_id,
            fence,
            status="succeeded",
            provider_post_id=provider_post_id,
            receipt=receipt,
            completed=True,
        )

    def mark_unknown(
        self, tenant_id: str, intent_id: str, fence: int, reason: str
    ) -> SocialPublicationIntent:
        return self._transition(
            tenant_id, intent_id, fence, status="unknown", failure_reason=reason
        )

    def mark_failed(
        self, tenant_id: str, intent_id: str, fence: int, reason: str
    ) -> SocialPublicationIntent:
        return self._transition(
            tenant_id, intent_id, fence, status="failed", failure_reason=reason
        )

    def reconcile_success(
        self,
        tenant_id: str,
        intent_id: str,
        provider_post_id: str,
        receipt: Mapping[str, object],
    ) -> SocialPublicationIntent:
        validate_identity(tenant_id, intent_id)
        validate_provider_id(provider_post_id)
        validate_receipt(receipt)
        now = self._clock()
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """
                UPDATE social_publication_intents
                SET status = 'succeeded', provider_post_id = ?, receipt_json = ?,
                    failure_reason = '', completed_at = ?, updated_at = ?
                WHERE tenant_id = ? AND intent_id = ? AND status = 'unknown'
                """,
                (
                    provider_post_id,
                    canonical_json(receipt),
                    now,
                    now,
                    tenant_id,
                    intent_id,
                ),
            )
            if cursor.rowcount != 1:
                row = self._connection.execute(
                    """
                    SELECT * FROM social_publication_intents
                    WHERE tenant_id = ? AND intent_id = ?
                    """,
                    (tenant_id, intent_id),
                ).fetchone()
                if row is not None:
                    existing = intent_from_mapping(dict(row))
                    if reconciliation_matches(existing, provider_post_id, receipt):
                        return existing
                raise SocialPublicationStateError(
                    "only an unknown publication can be reconciled"
                )
        return self.get(tenant_id, intent_id)

    def revoke_unused(
        self,
        tenant_id: str,
        *,
        channel_id: Optional[str] = None,
        account_id: Optional[str] = None,
        run_id: Optional[str] = None,
        reason: str,
    ) -> int:
        if not _IDENTIFIER.fullmatch(tenant_id):
            raise ValueError("tenant_id is invalid")
        if channel_id is not None and not _CHANNEL.fullmatch(channel_id):
            raise ValueError("channel_id is invalid")
        if account_id is not None and not _IDENTIFIER.fullmatch(account_id):
            raise ValueError("account_id is invalid")
        if run_id is not None and not _IDENTIFIER.fullmatch(run_id):
            raise ValueError("run_id is invalid")
        validate_reason(reason)
        clauses = ["tenant_id = ?", "status = 'pending'"]
        where_values: list[object] = [tenant_id]
        for column, value in (
            ("channel_id", channel_id),
            ("account_id", account_id),
            ("run_id", run_id),
        ):
            if value is not None:
                clauses.append("{} = ?".format(column))
                where_values.append(value)
        now = self._clock()
        values = [reason, now, now, *where_values]
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """
                UPDATE social_publication_intents
                SET status = 'revoked', failure_reason = ?,
                    revoked_at = ?, updated_at = ?
                WHERE {}
                """.format(" AND ".join(clauses)),
                tuple(values),
            )
            return int(cursor.rowcount)

    def list_for_run(
        self, tenant_id: str, run_id: str
    ) -> Tuple[SocialPublicationIntent, ...]:
        validate_identity(tenant_id, run_id)
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM social_publication_intents
                WHERE tenant_id = ? AND run_id = ?
                ORDER BY created_at ASC, intent_id ASC
                """,
                (tenant_id, run_id),
            ).fetchall()
        return tuple(intent_from_mapping(dict(row)) for row in rows)

    def _transition(
        self,
        tenant_id: str,
        intent_id: str,
        fence: int,
        *,
        status: str,
        provider_container_id: Optional[str] = None,
        provider_post_id: Optional[str] = None,
        receipt: Optional[Mapping[str, object]] = None,
        failure_reason: str = "",
        completed: bool = False,
    ) -> SocialPublicationIntent:
        validate_identity(tenant_id, intent_id)
        if fence < 1:
            raise ValueError("publication fence must be positive")
        if status not in _STATUSES:
            raise ValueError("publication status is invalid")
        if provider_container_id is not None:
            validate_provider_id(provider_container_id)
        if provider_post_id is not None:
            validate_provider_id(provider_post_id)
        if receipt is not None:
            validate_receipt(receipt)
        if failure_reason:
            validate_reason(failure_reason)
        now = self._clock()
        assignments = ["status = ?", "updated_at = ?"]
        values: list[object] = [status, now]
        if provider_container_id is not None:
            assignments.append("provider_container_id = ?")
            values.append(provider_container_id)
        if provider_post_id is not None:
            assignments.append("provider_post_id = ?")
            values.append(provider_post_id)
        if receipt is not None:
            assignments.append("receipt_json = ?")
            values.append(canonical_json(receipt))
        if failure_reason or status in {"succeeded", "pending"}:
            assignments.append("failure_reason = ?")
            values.append(failure_reason)
        if completed:
            assignments.append("completed_at = ?")
            values.append(now)
        values.extend((tenant_id, intent_id, fence))
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """
                UPDATE social_publication_intents SET {}
                WHERE tenant_id = ? AND intent_id = ?
                  AND status = 'pending' AND execution_fencing_token = ?
                """.format(", ".join(assignments)),
                tuple(values),
            )
            if cursor.rowcount != 1:
                raise SocialPublicationStateError(
                    "publication intent is not pending for this fence"
                )
        return self.get(tenant_id, intent_id)

    def check(self) -> None:
        with self._lock:
            row = self._connection.execute(
                "SELECT COUNT(*) AS total FROM social_publication_intents"
            ).fetchone()
        if row is None:
            raise RuntimeError("social publication SQLite readiness failed")

    def close(self) -> None:
        with self._lock:
            self._connection.close()


def intent_values(intent: SocialPublicationIntent) -> tuple[object, ...]:
    return (
        intent.intent_id,
        intent.tenant_id,
        intent.channel_id,
        intent.account_id,
        intent.run_id,
        intent.artifact_id,
        intent.artifact_hash,
        intent.content_hash,
        intent.media_url_hash,
        intent.media_hash,
        intent.confirmation_hash,
        intent.greenlight_id,
        intent.greenlight_fencing_token,
        intent.budget_cents,
        intent.idempotency_digest,
        intent.binding_digest,
        intent.status,
        intent.execution_fencing_token,
        intent.provider_container_id,
        intent.provider_post_id,
        canonical_json(intent.receipt),
        intent.failure_reason,
        intent.created_at,
        intent.updated_at,
        intent.completed_at,
        intent.revoked_at,
    )


def intent_from_mapping(row: Mapping[str, object]) -> SocialPublicationIntent:
    raw_receipt = row.get("receipt_json", {})
    receipt = (
        raw_receipt
        if isinstance(raw_receipt, Mapping)
        else json.loads(str(raw_receipt))
    )
    if not isinstance(receipt, Mapping):
        raise SocialPublicationStoreError("stored publication receipt is invalid")
    return SocialPublicationIntent(
        intent_id=str(row["intent_id"]),
        tenant_id=str(row["tenant_id"]),
        channel_id=str(row["channel_id"]),
        account_id=str(row["account_id"]),
        run_id=str(row["run_id"]),
        artifact_id=str(row["artifact_id"]),
        artifact_hash=str(row["artifact_hash"]),
        content_hash=str(row["content_hash"]),
        media_url_hash=(
            None if row.get("media_url_hash") is None else str(row["media_url_hash"])
        ),
        media_hash=None if row.get("media_hash") is None else str(row["media_hash"]),
        confirmation_hash=(
            None
            if row.get("confirmation_hash") is None
            else str(row["confirmation_hash"])
        ),
        greenlight_id=str(row["greenlight_id"]),
        greenlight_fencing_token=int(row["greenlight_fencing_token"]),
        budget_cents=int(row["budget_cents"]),
        idempotency_digest=str(row["idempotency_digest"]),
        binding_digest=str(row["binding_digest"]),
        status=str(row["status"]),
        execution_fencing_token=int(row["execution_fencing_token"]),
        provider_container_id=(
            None
            if row.get("provider_container_id") is None
            else str(row["provider_container_id"])
        ),
        provider_post_id=(
            None if row.get("provider_post_id") is None else str(row["provider_post_id"])
        ),
        receipt=dict(receipt),
        failure_reason=str(row.get("failure_reason", "")),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        completed_at=(
            None if row.get("completed_at") is None else str(row["completed_at"])
        ),
        revoked_at=None if row.get("revoked_at") is None else str(row["revoked_at"]),
    )


def validate_intent(intent: SocialPublicationIntent, *, require_pending: bool) -> None:
    for value in (
        intent.intent_id,
        intent.tenant_id,
        intent.account_id,
        intent.run_id,
        intent.artifact_id,
        intent.greenlight_id,
    ):
        if not _IDENTIFIER.fullmatch(value):
            raise ValueError("publication intent identity is invalid")
    if not _CHANNEL.fullmatch(intent.channel_id):
        raise ValueError("publication channel is invalid")
    for digest in (
        intent.artifact_hash,
        intent.content_hash,
        intent.idempotency_digest,
        intent.binding_digest,
    ):
        if not _SHA256.fullmatch(digest):
            raise ValueError("publication digest is invalid")
    for optional in (
        intent.media_url_hash, intent.media_hash, intent.confirmation_hash
    ):
        if optional is not None and not _SHA256.fullmatch(optional):
            raise ValueError("publication optional digest is invalid")
    if intent.greenlight_fencing_token < 0 or intent.budget_cents < 0:
        raise ValueError("publication authority values are invalid")
    if intent.status not in _STATUSES:
        raise ValueError("publication status is invalid")
    if require_pending and (
        intent.status != "pending" or intent.execution_fencing_token < 1
    ):
        raise ValueError(
            "new publication intent must be pending with a positive fence"
        )
    validate_receipt(intent.receipt)


def validate_identity(tenant_id: str, identifier: str) -> None:
    if not _IDENTIFIER.fullmatch(tenant_id) or not _IDENTIFIER.fullmatch(identifier):
        raise ValueError("publication identity is invalid")


def validate_provider_id(value: str) -> None:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError("provider publication ID is invalid")


def validate_reason(reason: str) -> None:
    if (
        not reason
        or len(reason) > 128
        or any(ord(character) < 32 or ord(character) == 127 for character in reason)
    ):
        raise ValueError("publication reason is invalid")


def validate_receipt(receipt: Mapping[str, object]) -> None:
    encoded = canonical_json(receipt)
    if len(encoded.encode("utf-8")) > 8192:
        raise ValueError("publication receipt is too large")


def reconciliation_matches(
    intent: SocialPublicationIntent,
    provider_post_id: str,
    receipt: Mapping[str, object],
) -> bool:
    expected_binding = receipt.get("reconciliation_binding_digest")
    observed_binding = intent.receipt.get("reconciliation_binding_digest")
    return (
        intent.status == "succeeded"
        and intent.provider_post_id == provider_post_id
        and isinstance(expected_binding, str)
        and isinstance(observed_binding, str)
        and _SHA256.fullmatch(expected_binding) is not None
        and observed_binding == expected_binding
    )
