from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Callable, Mapping

from .memory import utc_now
from .model_effect_store import (
    ModelEffectConflictError,
    ModelEffectIntent,
    ModelEffectReservation,
    ModelEffectStateError,
)
from .model_gateway import (
    ModelGateway,
    ModelGatewayConfigurationError,
    ModelGatewayDisabledError,
    ModelGatewayProviderError,
    ModelRequest,
    ModelRequestDescriptor,
)
from .utils import canonical_json, stable_id


class ModelEffectError(RuntimeError):
    pass


class ModelEffectUnavailableError(ModelEffectError):
    pass


class ModelEffectBlockedError(ModelEffectError):
    def __init__(self, status: str) -> None:
        super().__init__("model effect is blocked by durable state")
        self.status = status


class ModelEffectUnknownError(ModelEffectError):
    pass


@dataclass(frozen=True)
class ModelEffectCommand:
    tenant_id: str
    run_id: str
    station: str
    source_artifact_id: str
    source_artifact_hash: str
    instruction: str
    max_cost_micros: int
    idempotency_key: str
    request: ModelRequest


@dataclass(frozen=True)
class ModelEffectResult:
    effect_id: str
    tenant_id: str
    run_id: str
    station: str
    source_artifact_id: str
    source_artifact_hash: str
    provider_id: str
    model: str
    status: str
    execution_fencing_token: int
    output_text: str
    output_sha256: str
    receipt: Mapping[str, object]
    replayed: bool

    @classmethod
    def from_intent(
        cls, intent: ModelEffectIntent, *, replayed: bool
    ) -> "ModelEffectResult":
        return cls(
            effect_id=intent.effect_id,
            tenant_id=intent.tenant_id,
            run_id=intent.run_id,
            station=intent.station,
            source_artifact_id=intent.source_artifact_id,
            source_artifact_hash=intent.source_artifact_hash,
            provider_id=intent.provider_id,
            model=intent.model,
            status=intent.status,
            execution_fencing_token=intent.execution_fencing_token,
            output_text=intent.output_text,
            output_sha256=intent.output_sha256,
            receipt=dict(intent.receipt),
            replayed=replayed,
        )

    def public_dict(self) -> dict[str, object]:
        return {
            "effect_id": self.effect_id,
            "tenant_id": self.tenant_id,
            "run_id": self.run_id,
            "station": self.station,
            "source_artifact_id": self.source_artifact_id,
            "source_artifact_hash": self.source_artifact_hash,
            "provider_id": self.provider_id,
            "model": self.model,
            "status": self.status,
            "execution_fencing_token": self.execution_fencing_token,
            "output_text": self.output_text,
            "output_sha256": self.output_sha256,
            "receipt": dict(self.receipt),
            "replayed": self.replayed,
        }


class ModelEffectAuthority:
    def __init__(
        self,
        *,
        store: object,
        gateway: ModelGateway,
        enabled: bool = False,
        clock: Callable[[], str] = utc_now,
    ) -> None:
        self._store = store
        self._gateway = gateway
        self._enabled = enabled
        self._clock = clock

    @property
    def enabled(self) -> bool:
        return self._enabled

    def execute(self, command: ModelEffectCommand) -> ModelEffectResult:
        if not self._enabled:
            raise ModelEffectUnavailableError("model effect authority is disabled")
        validated = _validate_command(command)
        try:
            descriptor = self._gateway.describe(validated.request)
        except (ModelGatewayDisabledError, ModelGatewayConfigurationError) as error:
            raise ModelEffectUnavailableError(
                "model provider execution is unavailable"
            ) from error
        intent = _build_intent(validated, descriptor, clock=self._clock)
        reservation: ModelEffectReservation = self._store.reserve(intent)
        if not reservation.executable:
            if reservation.replayed:
                return ModelEffectResult.from_intent(
                    reservation.intent, replayed=True
                )
            raise ModelEffectBlockedError(reservation.intent.status)

        try:
            result = self._gateway.complete(validated.request)
        except ModelGatewayProviderError as error:
            self._mark_unknown(reservation.intent, "provider_outcome_unknown")
            raise ModelEffectUnknownError("model provider outcome is unknown") from error
        if (
            result.receipt.provider_id != descriptor.provider_id
            or result.receipt.model != descriptor.model
            or result.receipt.request_sha256 != descriptor.request_sha256
            or result.receipt.output_sha256
            != hashlib.sha256(result.text.encode("utf-8")).hexdigest()
        ):
            self._mark_unknown(reservation.intent, "provider_receipt_invalid")
            raise ModelEffectUnknownError("model provider receipt is invalid")

        receipt = result.receipt.public_dict()
        receipt.update(
            {
                "effect_binding_digest": intent.binding_digest,
                "execution_fencing_token": intent.execution_fencing_token,
                "max_cost_micros": intent.max_cost_micros,
            }
        )
        try:
            completed = self._store.complete(
                intent.tenant_id,
                intent.effect_id,
                intent.execution_fencing_token,
                result.text,
                receipt,
            )
        except Exception as error:
            self._mark_unknown(intent, "result_persistence_uncertain")
            raise ModelEffectUnknownError(
                "model effect result persistence is uncertain"
            ) from error
        return ModelEffectResult.from_intent(completed, replayed=False)

    def _mark_unknown(self, intent: ModelEffectIntent, reason: str) -> None:
        try:
            self._store.mark_unknown(
                intent.tenant_id,
                intent.effect_id,
                intent.execution_fencing_token,
                reason,
            )
        except ModelEffectStateError:
            pass


def _validate_command(command: ModelEffectCommand) -> ModelEffectCommand:
    for value in (
        command.tenant_id,
        command.run_id,
        command.station,
        command.source_artifact_id,
    ):
        if not value or len(value) > 256:
            raise ValueError("model effect identity is invalid")
    if not _is_sha256(command.source_artifact_hash):
        raise ValueError("source artifact hash is invalid")
    instruction = command.instruction.strip()
    if not instruction or len(instruction.encode("utf-8")) > 4096:
        raise ValueError("model effect instruction is invalid")
    if command.max_cost_micros < 0 or command.max_cost_micros > 10_000_000_000:
        raise ValueError("model effect cost cap is invalid")
    if len(command.idempotency_key) < 8 or len(command.idempotency_key) > 200:
        raise ValueError("model effect idempotency key is invalid")
    return ModelEffectCommand(
        tenant_id=command.tenant_id,
        run_id=command.run_id,
        station=command.station,
        source_artifact_id=command.source_artifact_id,
        source_artifact_hash=command.source_artifact_hash,
        instruction=instruction,
        max_cost_micros=command.max_cost_micros,
        idempotency_key=command.idempotency_key,
        request=command.request,
    )


def _build_intent(
    command: ModelEffectCommand,
    descriptor: ModelRequestDescriptor,
    *,
    clock: Callable[[], str],
) -> ModelEffectIntent:
    instruction_hash = hashlib.sha256(
        command.instruction.encode("utf-8")
    ).hexdigest()
    binding = {
        "tenant_id": command.tenant_id,
        "run_id": command.run_id,
        "station": command.station,
        "source_artifact_id": command.source_artifact_id,
        "source_artifact_hash": command.source_artifact_hash,
        "instruction_hash": instruction_hash,
        "provider_id": descriptor.provider_id,
        "model": descriptor.model,
        "endpoint_host": descriptor.endpoint_host,
        "request_sha256": descriptor.request_sha256,
        "max_output_tokens": descriptor.max_output_tokens,
        "max_cost_micros": command.max_cost_micros,
    }
    binding_digest = hashlib.sha256(
        canonical_json(binding).encode("utf-8")
    ).hexdigest()
    idempotency_digest = hashlib.sha256(
        command.idempotency_key.encode("utf-8")
    ).hexdigest()
    now = clock()
    return ModelEffectIntent(
        effect_id=stable_id(
            "model-effect-intent",
            command.tenant_id,
            idempotency_digest,
            length=48,
        ),
        tenant_id=command.tenant_id,
        run_id=command.run_id,
        station=command.station,
        source_artifact_id=command.source_artifact_id,
        source_artifact_hash=command.source_artifact_hash,
        instruction_hash=instruction_hash,
        provider_id=descriptor.provider_id,
        model=descriptor.model,
        endpoint_host=descriptor.endpoint_host,
        request_sha256=descriptor.request_sha256,
        max_output_tokens=descriptor.max_output_tokens,
        max_cost_micros=command.max_cost_micros,
        idempotency_digest=idempotency_digest,
        binding_digest=binding_digest,
        status="pending",
        execution_fencing_token=1,
        output_text="",
        output_sha256="",
        receipt={},
        failure_reason="",
        created_at=now,
        updated_at=now,
        completed_at=None,
        revoked_at=None,
    )


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)
