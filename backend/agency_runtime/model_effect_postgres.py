from __future__ import annotations

from typing import Mapping, Tuple

from .memory import utc_now
from .model_effect_store import (
    ModelEffectConflictError,
    ModelEffectIntent,
    ModelEffectReservation,
    ModelEffectStateError,
    intent_from_mapping,
    intent_values,
    reconciliation_matches,
    validate_identity,
    validate_intent,
    validate_output,
    validate_reason,
    validate_receipt,
)
from .utils import canonical_json


class PostgresModelEffectStore:
    def __init__(self, database: object, *, clock=utc_now) -> None:
        if not hasattr(database, "pool"):
            raise TypeError("PostgreSQL model effect store requires a runtime database")
        self._database = database
        self._clock = clock

    def reserve(self, intent: ModelEffectIntent) -> ModelEffectReservation:
        validate_intent(intent, require_pending=True)
        lock_ids = sorted(
            (
                "model-effect:{}:binding:{}".format(
                    intent.tenant_id, intent.binding_digest
                ),
                "model-effect:{}:idempotency:{}".format(
                    intent.tenant_id, intent.idempotency_digest
                ),
            )
        )
        with self._database.pool.connection() as connection:
            for lock_id in lock_ids:
                connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))", (lock_id,)
                )
            existing = connection.execute(
                """
                SELECT * FROM public.model_effect_intents
                WHERE tenant_id = %s
                  AND (idempotency_digest = %s OR binding_digest = %s)
                ORDER BY CASE WHEN idempotency_digest = %s THEN 0 ELSE 1 END
                LIMIT 1
                FOR UPDATE
                """,
                (
                    intent.tenant_id,
                    intent.idempotency_digest,
                    intent.binding_digest,
                    intent.idempotency_digest,
                ),
            ).fetchone()
            if existing is not None:
                record = intent_from_mapping(existing)
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
                return ModelEffectReservation(
                    record,
                    executable=False,
                    replayed=record.status == "succeeded",
                )
            connection.execute(
                """
                INSERT INTO public.model_effect_intents(
                    effect_id, tenant_id, run_id, station, source_artifact_id,
                    source_artifact_hash, instruction_hash, provider_id, model,
                    endpoint_host, request_sha256, max_output_tokens,
                    max_cost_micros, idempotency_digest, binding_digest, status,
                    execution_fencing_token, output_text, output_sha256,
                    receipt_json, failure_reason, created_at, updated_at,
                    completed_at, revoked_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    CAST(%s AS jsonb), %s, %s, %s, %s, %s
                )
                """,
                intent_values(intent),
            )
        return ModelEffectReservation(intent, True, False)

    def get(self, tenant_id: str, effect_id: str) -> ModelEffectIntent:
        validate_identity(tenant_id, effect_id)
        with self._database.pool.connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM public.model_effect_intents
                WHERE tenant_id = %s AND effect_id = %s
                """,
                (tenant_id, effect_id),
            ).fetchone()
        if row is None:
            raise KeyError("model effect intent not found")
        return intent_from_mapping(row)

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
        with self._database.pool.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE public.model_effect_intents
                SET status = 'succeeded', output_text = %s,
                    output_sha256 = %s, receipt_json = CAST(%s AS jsonb),
                    failure_reason = '', completed_at = %s, updated_at = %s
                WHERE tenant_id = %s AND effect_id = %s AND status = 'unknown'
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
                row = connection.execute(
                    """
                    SELECT * FROM public.model_effect_intents
                    WHERE tenant_id = %s AND effect_id = %s
                    FOR UPDATE
                    """,
                    (tenant_id, effect_id),
                ).fetchone()
                if row is not None:
                    existing = intent_from_mapping(row)
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
        with self._database.pool.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE public.model_effect_intents
                SET status = 'revoked',
                    execution_fencing_token = execution_fencing_token + 1,
                    failure_reason = %s, revoked_at = %s, updated_at = %s
                WHERE tenant_id = %s AND run_id = %s AND status = 'pending'
                """,
                (reason, now, now, tenant_id, run_id),
            )
            return int(cursor.rowcount)

    def list_for_run(
        self, tenant_id: str, run_id: str
    ) -> Tuple[ModelEffectIntent, ...]:
        validate_identity(tenant_id, run_id)
        with self._database.pool.connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM public.model_effect_intents
                WHERE tenant_id = %s AND run_id = %s
                ORDER BY created_at ASC, effect_id ASC
                """,
                (tenant_id, run_id),
            ).fetchall()
        return tuple(intent_from_mapping(row) for row in rows)

    def _transition(
        self,
        tenant_id: str,
        effect_id: str,
        fence: int,
        *,
        status: str,
        output_text: str | None = None,
        output_sha256: str | None = None,
        receipt: Mapping[str, object] | None = None,
        failure_reason: str = "",
        completed: bool = False,
    ) -> ModelEffectIntent:
        validate_identity(tenant_id, effect_id)
        if fence < 1:
            raise ValueError("model effect fence must be positive")
        if status not in {"pending", "succeeded", "unknown", "failed", "revoked"}:
            raise ValueError("model effect status is invalid")
        if output_text is not None:
            validate_output(output_text)
        if output_sha256 is not None and len(output_sha256) != 64:
            raise ValueError("model effect output digest is invalid")
        if receipt is not None:
            validate_receipt(receipt)
        if failure_reason:
            validate_reason(failure_reason)
        now = self._clock()
        assignments = ["status = %s", "updated_at = %s"]
        values: list[object] = [status, now]
        if output_text is not None:
            assignments.append("output_text = %s")
            values.append(output_text)
        if output_sha256 is not None:
            assignments.append("output_sha256 = %s")
            values.append(output_sha256)
        if receipt is not None:
            assignments.append("receipt_json = CAST(%s AS jsonb)")
            values.append(canonical_json(receipt))
        if failure_reason or status == "succeeded":
            assignments.append("failure_reason = %s")
            values.append(failure_reason)
        if completed:
            assignments.append("completed_at = %s")
            values.append(now)
        values.extend((tenant_id, effect_id, fence))
        with self._database.pool.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE public.model_effect_intents SET {}
                WHERE tenant_id = %s AND effect_id = %s
                  AND status = 'pending' AND execution_fencing_token = %s
                """.format(", ".join(assignments)),
                tuple(values),
            )
            if cursor.rowcount != 1:
                raise ModelEffectStateError(
                    "model effect intent is not pending for this fence"
                )
        return self.get(tenant_id, effect_id)

    def check(self) -> None:
        with self._database.pool.connection() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM public.model_effect_intents"
            ).fetchone()
        if row is None:
            raise RuntimeError("model effect PostgreSQL readiness failed")


def _sha256(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()
