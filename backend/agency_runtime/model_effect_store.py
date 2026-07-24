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

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$")
_PROVIDER = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")
_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_HOST = re.compile(r"^[a-z0-9][a-z0-9.-]{0,252}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_STATUSES = frozenset({"pending", "succeeded", "unknown", "failed", "revoked"})
_MAX_OUTPUT_BYTES = 1024 * 1024
_MAX_RECEIPT_BYTES = 16 * 1024


class ModelEffectStoreError(RuntimeError):
    pass


class ModelEffectConflictError(ModelEffectStoreError):
    pass


class ModelEffectStateError(ModelEffectStoreError):
    pass


@dataclass(frozen=True)
class ModelEffectIntent:
    effect_id: str
    tenant_id: str
    run_id: str
    station: str
    source_artifact_id: str
    source_artifact_hash: str
    instruction_hash: str
    provider_id: str
    model: str
    endpoint_host: str
    request_sha256: str
    max_output_tokens: int
    max_cost_micros: int
    idempotency_digest: str
    binding_digest: str
    status: str
    execution_fencing_token: int
    output_text: str
    output_sha256: str
    receipt: Mapping[str, object]
    failure_reason: str
    created_at: str
    updated_at: str
    completed_at: Optional[str]
    revoked_at: Optional[str]


@dataclass(frozen=True)
class ModelEffectReservation:
    intent: ModelEffectIntent
    executable: bool
    replayed: bool


class SQLiteModelEffectStore:
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
                CREATE TABLE IF NOT EXISTS model_effect_intents (
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
                    max_output_tokens INTEGER NOT NULL,
                    max_cost_micros INTEGER NOT NULL,
                    idempotency_digest TEXT NOT NULL,
                    binding_digest TEXT NOT NULL,
                    status TEXT NOT NULL,
                    execution_fencing_token INTEGER NOT NULL,
                    output_text TEXT NOT NULL,
                    output_sha256 TEXT NOT NULL,
                    receipt_json TEXT NOT NULL,
                    failure_reason TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    revoked_at TEXT,
                    UNIQUE (tenant_id, idempotency_digest),
                    UNIQUE (tenant_id, binding_digest)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS uq_model_effect_binding
                    ON model_effect_intents(tenant_id, binding_digest);
                CREATE INDEX IF NOT EXISTS idx_model_effect_run
                    ON model_effect_intents(tenant_id, run_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_model_effect_status
                    ON model_effect_intents(tenant_id, status, updated_at DESC);
                """
            )

    def reserve(self, intent: ModelEffectIntent) -> ModelEffectReservation:
        validate_intent(intent, require_pending=True)
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                existing = self._connection.execute(
                    """
                    SELECT * FROM model_effect_intents
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
                        raise ModelEffectConflictError(
                            "model effect idempotency key conflicts with a prior binding"
                        )
                    if record.binding_digest != intent.binding_digest:
                        raise ModelEffectConflictError(
                            "model effect binding conflicts with a prior intent"
                        )
                    self._connection.commit()
                    return ModelEffectReservation(
                        record,
                        executable=False,
                        replayed=record.status == "succeeded",
                    )
                self._connection.execute(
                    """
                    INSERT INTO model_effect_intents(
                        effect_id, tenant_id, run_id, station, source_artifact_id,
                        source_artifact_hash, instruction_hash, provider_id, model,
                        endpoint_host, request_sha256, max_output_tokens,
                        max_cost_micros, idempotency_digest, binding_digest, status,
                        execution_fencing_token, output_text, output_sha256,
                        receipt_json, failure_reason, created_at, updated_at,
                        completed_at, revoked_at
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    intent_values(intent),
                )
                self._connection.commit()
                return ModelEffectReservation(intent, True, False)
            except Exception:
                self._connection.rollback()
                raise

    def get(self, tenant_id: str, effect_id: str) -> ModelEffectIntent:
        validate_identity(tenant_id, effect_id)
        with self._lock:
            row = self._connection.execute(
                """
                SELECT * FROM model_effect_intents
                WHERE tenant_id = ? AND effect_id = ?
                """,
                (tenant_id, effect_id),
            ).fetchone()
        if row is None:
            raise KeyError("model effect intent not found")
        return intent_from_mapping(dict(row))

    def complete(
        self,
        tenant_id: str,
        effect_id: str,
        fence: int,
        output_text: str,
        receipt: Mapping[str, object],
    ) -> ModelEffectIntent:
        validate_output(output_text)
        validate_receipt(receipt)
        return self._transition(
            tenant_id,
            effect_id,
            fence,
            status="succeeded",
            output_text=output_text,
            output_sha256=_sha256(output_text),
            receipt=receipt,
            completed=True,
        )

    def mark_unknown(
        self, tenant_id: str, effect_id: str, fence: int, reason: str
    ) -> ModelEffectIntent:
        return self._transition(
            tenant_id, effect_id, fence, status="unknown", failure_reason=reason
        )

    def mark_failed(
        self, tenant_id: str, effect_id: str, fence: int, reason: str
    ) -> ModelEffectIntent:
        return self._transition(
            tenant_id, effect_id, fence, status="failed", failure_reason=reason
        )

    def reconcile_success(
        self,
        tenant_id: str,
        effect_id: str,
        output_text: str,
        receipt: Mapping[str, object],
    ) -> ModelEffectIntent:
        validate_identity(tenant_id, effect_id)
        validate_output(output_text)
        validate_receipt(receipt)
        output_sha256 = _sha256(output_text)
        now = self._clock()
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """
                UPDATE model_effect_intents
                SET status = 'succeeded', output_text = ?, output_sha256 = ?,
                    receipt_json = ?, failure_reason = '', completed_at = ?,
                    updated_at = ?
                WHERE tenant_id = ? AND effect_id = ? AND status = 'unknown'
                """,
                (
                    output_text,
                    output_sha256,
                    canonical_json(receipt),
                    now,
                    now,
                    tenant_id,
                    effect_id,
                ),
            )
            if cursor.rowcount != 1:
                row = self._connection.execute(
                    """
                    SELECT * FROM model_effect_intents
                    WHERE tenant_id = ? AND effect_id = ?
                    """,
                    (tenant_id, effect_id),
                ).fetchone()
                if row is not None:
                    existing = intent_from_mapping(dict(row))
                    if reconciliation_matches(existing, output_sha256, receipt):
                        return existing
                raise ModelEffectStateError(
                    "only an unknown model effect can be reconciled"
                )
        return self.get(tenant_id, effect_id)

    def revoke_unused(self, tenant_id: str, *, run_id: str, reason: str) -> int:
        validate_identity(tenant_id, run_id)
        validate_reason(reason)
        now = self._clock()
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """
                UPDATE model_effect_intents
                SET status = 'revoked', execution_fencing_token = execution_fencing_token + 1,
                    failure_reason = ?, revoked_at = ?, updated_at = ?
                WHERE tenant_id = ? AND run_id = ? AND status = 'pending'
                """,
                (reason, now, now, tenant_id, run_id),
            )
            return int(cursor.rowcount)

    def list_for_run(
        self, tenant_id: str, run_id: str
    ) -> Tuple[ModelEffectIntent, ...]:
        validate_identity(tenant_id, run_id)
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM model_effect_intents
                WHERE tenant_id = ? AND run_id = ?
                ORDER BY created_at ASC, effect_id ASC
                """,
                (tenant_id, run_id),
            ).fetchall()
        return tuple(intent_from_mapping(dict(row)) for row in rows)

    def _transition(
        self,
        tenant_id: str,
        effect_id: str,
        fence: int,
        *,
        status: str,
        output_text: Optional[str] = None,
        output_sha256: Optional[str] = None,
        receipt: Optional[Mapping[str, object]] = None,
        failure_reason: str = "",
        completed: bool = False,
    ) -> ModelEffectIntent:
        validate_identity(tenant_id, effect_id)
        if fence < 1:
            raise ValueError("model effect fence must be positive")
        if status not in _STATUSES:
            raise ValueError("model effect status is invalid")
        if output_text is not None:
            validate_output(output_text)
        if output_sha256 is not None and not _SHA256.fullmatch(output_sha256):
            raise ValueError("model effect output digest is invalid")
        if receipt is not None:
            validate_receipt(receipt)
        if failure_reason:
            validate_reason(failure_reason)
        now = self._clock()
        assignments = ["status = ?", "updated_at = ?"]
        values: list[object] = [status, now]
        if output_text is not None:
            assignments.append("output_text = ?")
            values.append(output_text)
        if output_sha256 is not None:
            assignments.append("output_sha256 = ?")
            values.append(output_sha256)
        if receipt is not None:
            assignments.append("receipt_json = ?")
            values.append(canonical_json(receipt))
        if failure_reason or status == "succeeded":
            assignments.append("failure_reason = ?")
            values.append(failure_reason)
        if completed:
            assignments.append("completed_at = ?")
            values.append(now)
        values.extend((tenant_id, effect_id, fence))
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """
                UPDATE model_effect_intents SET {}
                WHERE tenant_id = ? AND effect_id = ?
                  AND status = 'pending' AND execution_fencing_token = ?
                """.format(", ".join(assignments)),
                tuple(values),
            )
            if cursor.rowcount != 1:
                raise ModelEffectStateError(
                    "model effect intent is not pending for this fence"
                )
        return self.get(tenant_id, effect_id)

    def check(self) -> None:
        with self._lock:
            row = self._connection.execute(
                "SELECT COUNT(*) AS total FROM model_effect_intents"
            ).fetchone()
        if row is None:
            raise RuntimeError("model effect SQLite readiness failed")

    def close(self) -> None:
        with self._lock:
            self._connection.close()


def intent_values(intent: ModelEffectIntent) -> tuple[object, ...]:
    return (
        intent.effect_id,
        intent.tenant_id,
        intent.run_id,
        intent.station,
        intent.source_artifact_id,
        intent.source_artifact_hash,
        intent.instruction_hash,
        intent.provider_id,
        intent.model,
        intent.endpoint_host,
        intent.request_sha256,
        intent.max_output_tokens,
        intent.max_cost_micros,
        intent.idempotency_digest,
        intent.binding_digest,
        intent.status,
        intent.execution_fencing_token,
        intent.output_text,
        intent.output_sha256,
        canonical_json(intent.receipt),
        intent.failure_reason,
        intent.created_at,
        intent.updated_at,
        intent.completed_at,
        intent.revoked_at,
    )


def intent_from_mapping(row: Mapping[str, object]) -> ModelEffectIntent:
    raw_receipt = row.get("receipt_json", {})
    receipt = raw_receipt if isinstance(raw_receipt, Mapping) else json.loads(str(raw_receipt))
    if not isinstance(receipt, Mapping):
        raise ModelEffectStoreError("stored model effect receipt is invalid")
    return ModelEffectIntent(
        effect_id=str(row["effect_id"]),
        tenant_id=str(row["tenant_id"]),
        run_id=str(row["run_id"]),
        station=str(row["station"]),
        source_artifact_id=str(row["source_artifact_id"]),
        source_artifact_hash=str(row["source_artifact_hash"]),
        instruction_hash=str(row["instruction_hash"]),
        provider_id=str(row["provider_id"]),
        model=str(row["model"]),
        endpoint_host=str(row["endpoint_host"]),
        request_sha256=str(row["request_sha256"]),
        max_output_tokens=int(row["max_output_tokens"]),
        max_cost_micros=int(row["max_cost_micros"]),
        idempotency_digest=str(row["idempotency_digest"]),
        binding_digest=str(row["binding_digest"]),
        status=str(row["status"]),
        execution_fencing_token=int(row["execution_fencing_token"]),
        output_text=str(row.get("output_text", "")),
        output_sha256=str(row.get("output_sha256", "")),
        receipt=dict(receipt),
        failure_reason=str(row.get("failure_reason", "")),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        completed_at=None if row.get("completed_at") is None else str(row["completed_at"]),
        revoked_at=None if row.get("revoked_at") is None else str(row["revoked_at"]),
    )


def validate_intent(intent: ModelEffectIntent, *, require_pending: bool) -> None:
    for value in (
        intent.effect_id,
        intent.tenant_id,
        intent.run_id,
        intent.station,
        intent.source_artifact_id,
    ):
        if not _IDENTIFIER.fullmatch(value):
            raise ValueError("model effect identity is invalid")
    for digest in (
        intent.source_artifact_hash,
        intent.instruction_hash,
        intent.request_sha256,
        intent.idempotency_digest,
        intent.binding_digest,
    ):
        if not _SHA256.fullmatch(digest):
            raise ValueError("model effect digest is invalid")
    if not _PROVIDER.fullmatch(intent.provider_id):
        raise ValueError("model effect provider is invalid")
    if not _MODEL.fullmatch(intent.model):
        raise ValueError("model effect model is invalid")
    if not _HOST.fullmatch(intent.endpoint_host):
        raise ValueError("model effect endpoint host is invalid")
    if intent.max_output_tokens < 1 or intent.max_output_tokens > 8192:
        raise ValueError("model effect token cap is invalid")
    if intent.max_cost_micros < 0 or intent.max_cost_micros > 10_000_000_000:
        raise ValueError("model effect cost cap is invalid")
    if intent.status not in _STATUSES or (require_pending and intent.status != "pending"):
        raise ValueError("model effect status is invalid")
    if intent.execution_fencing_token < 1:
        raise ValueError("model effect fence is invalid")
    if intent.output_text:
        validate_output(intent.output_text)
    if intent.output_sha256 and not _SHA256.fullmatch(intent.output_sha256):
        raise ValueError("model effect output digest is invalid")
    validate_receipt(intent.receipt)
    if intent.failure_reason:
        validate_reason(intent.failure_reason)


def validate_identity(tenant_id: str, effect_id: str) -> None:
    if not _IDENTIFIER.fullmatch(tenant_id) or not _IDENTIFIER.fullmatch(effect_id):
        raise ValueError("model effect identity is invalid")


def validate_output(output_text: str) -> None:
    if not output_text or len(output_text.encode("utf-8")) > _MAX_OUTPUT_BYTES:
        raise ValueError("model effect output is invalid")


def validate_receipt(receipt: Mapping[str, object]) -> None:
    if len(canonical_json(receipt).encode("utf-8")) > _MAX_RECEIPT_BYTES:
        raise ValueError("model effect receipt is too large")


def validate_reason(reason: str) -> None:
    if not reason or len(reason.encode("utf-8")) > 256 or not re.fullmatch(
        r"[a-z0-9][a-z0-9_.:-]{0,255}", reason
    ):
        raise ValueError("model effect reason is invalid")


def reconciliation_matches(
    intent: ModelEffectIntent, output_sha256: str, receipt: Mapping[str, object]
) -> bool:
    expected = receipt.get("reconciliation_binding_digest")
    observed = intent.receipt.get("reconciliation_binding_digest")
    return (
        intent.status == "succeeded"
        and intent.output_sha256 == output_sha256
        and isinstance(expected, str)
        and _SHA256.fullmatch(expected) is not None
        and observed == expected
    )


def _sha256(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()
