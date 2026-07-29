from __future__ import annotations

from typing import Mapping, Optional, Tuple

from .memory import utc_now
from .social_publication_store import (
    SocialPublicationConflictError,
    SocialPublicationIntent,
    SocialPublicationReservation,
    SocialPublicationStateError,
    intent_from_mapping,
    intent_values,
    reconciliation_matches,
    validate_identity,
    validate_intent,
    validate_provider_id,
    validate_reason,
    validate_receipt,
)
from .utils import canonical_json


class PostgresSocialPublicationStore:
    def __init__(self, database: object, *, clock=utc_now) -> None:
        if not hasattr(database, "pool"):
            raise TypeError("PostgreSQL publication store requires a runtime database")
        self._database = database
        self._clock = clock

    def reserve(self, intent: SocialPublicationIntent) -> SocialPublicationReservation:
        validate_intent(intent, require_pending=True)
        lock_id = "social-publication:{}:{}".format(
            intent.tenant_id, intent.binding_digest
        )
        with self._database.pool.connection() as connection:
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))", (lock_id,)
            )
            existing = connection.execute(
                """
                SELECT * FROM public.social_publication_intents
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
                    raise SocialPublicationConflictError(
                        "publication idempotency key conflicts with a prior binding"
                    )
                if record.binding_digest != intent.binding_digest:
                    raise SocialPublicationConflictError(
                        "publication binding conflicts with a prior intent"
                    )
                return SocialPublicationReservation(
                    record,
                    executable=False,
                    replayed=record.status == "succeeded",
                )
            connection.execute(
                """
                INSERT INTO public.social_publication_intents(
                    intent_id, tenant_id, channel_id, account_id, run_id,
                    artifact_id, artifact_hash, content_hash, media_url_hash,
                    media_hash, confirmation_hash, greenlight_id,
                    greenlight_fencing_token, budget_cents, idempotency_digest,
                    binding_digest, status,
                    execution_fencing_token, provider_container_id,
                    provider_post_id, receipt_json, failure_reason, created_at,
                    updated_at, completed_at, revoked_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    CAST(%s AS jsonb), %s, %s, %s, %s, %s
                )
                """,
                intent_values(intent),
            )
        return SocialPublicationReservation(intent, True, False)

    def get(self, tenant_id: str, intent_id: str) -> SocialPublicationIntent:
        validate_identity(tenant_id, intent_id)
        with self._database.pool.connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM public.social_publication_intents
                WHERE tenant_id = %s AND intent_id = %s
                """,
                (tenant_id, intent_id),
            ).fetchone()
        if row is None:
            raise KeyError("social publication intent not found")
        return intent_from_mapping(row)

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
        with self._database.pool.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE public.social_publication_intents
                SET status = 'succeeded', provider_post_id = %s,
                    receipt_json = CAST(%s AS jsonb), failure_reason = '',
                    completed_at = %s, updated_at = %s
                WHERE tenant_id = %s AND intent_id = %s AND status = 'unknown'
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
                row = connection.execute(
                    """
                    SELECT * FROM public.social_publication_intents
                    WHERE tenant_id = %s AND intent_id = %s
                    FOR UPDATE
                    """,
                    (tenant_id, intent_id),
                ).fetchone()
                if row is not None:
                    existing = intent_from_mapping(row)
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
        validate_identity(tenant_id, tenant_id)
        if channel_id is not None and channel_id not in {"x", "instagram"}:
            raise ValueError("channel_id is invalid")
        if account_id is not None:
            validate_identity(tenant_id, account_id)
        if run_id is not None:
            validate_identity(tenant_id, run_id)
        validate_reason(reason)
        clauses = ["tenant_id = %s", "status = 'pending'"]
        where_values: list[object] = [tenant_id]
        for column, value in (
            ("channel_id", channel_id),
            ("account_id", account_id),
            ("run_id", run_id),
        ):
            if value is not None:
                clauses.append("{} = %s".format(column))
                where_values.append(value)
        now = self._clock()
        values = [reason, now, now, *where_values]
        with self._database.pool.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE public.social_publication_intents
                SET status = 'revoked', failure_reason = %s,
                    revoked_at = %s, updated_at = %s
                WHERE {}
                """.format(" AND ".join(clauses)),
                tuple(values),
            )
            return int(cursor.rowcount)

    def list_for_run(
        self, tenant_id: str, run_id: str
    ) -> Tuple[SocialPublicationIntent, ...]:
        validate_identity(tenant_id, run_id)
        with self._database.pool.connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM public.social_publication_intents
                WHERE tenant_id = %s AND run_id = %s
                ORDER BY created_at ASC, intent_id ASC
                """,
                (tenant_id, run_id),
            ).fetchall()
        return tuple(intent_from_mapping(row) for row in rows)

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
        if status not in {"pending", "succeeded", "unknown", "failed", "revoked"}:
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
        assignments = ["status = %s", "updated_at = %s"]
        values: list[object] = [status, now]
        if provider_container_id is not None:
            assignments.append("provider_container_id = %s")
            values.append(provider_container_id)
        if provider_post_id is not None:
            assignments.append("provider_post_id = %s")
            values.append(provider_post_id)
        if receipt is not None:
            assignments.append("receipt_json = CAST(%s AS jsonb)")
            values.append(canonical_json(receipt))
        if failure_reason or status in {"succeeded", "pending"}:
            assignments.append("failure_reason = %s")
            values.append(failure_reason)
        if completed:
            assignments.append("completed_at = %s")
            values.append(now)
        values.extend((tenant_id, intent_id, fence))
        with self._database.pool.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE public.social_publication_intents SET {}
                WHERE tenant_id = %s AND intent_id = %s
                  AND status = 'pending' AND execution_fencing_token = %s
                """.format(", ".join(assignments)),
                tuple(values),
            )
            if cursor.rowcount != 1:
                raise SocialPublicationStateError(
                    "publication intent is not pending for this fence"
                )
        return self.get(tenant_id, intent_id)

    def check(self) -> None:
        with self._database.pool.connection() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM public.social_publication_intents"
            ).fetchone()
        if row is None:
            raise RuntimeError("social publication PostgreSQL readiness failed")
