from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from importlib.resources import files
from pathlib import PurePosixPath
from typing import Dict, Mapping, Sequence, Tuple


_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._:-]{2,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SECRET_REF = re.compile(r"^secret://[a-z0-9][a-z0-9/_-]{2,127}$")
_REVIEWED_AT = re.compile(r"^20[0-9]{2}-[01][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-5][0-9]Z$")
_UPSTREAM_REPOSITORY = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_FINDING_ID = re.compile(r"^[A-Z0-9][A-Z0-9-]{2,63}$")
_FINDING_SEVERITIES = frozenset({"CRITICAL", "HIGH", "MEDIUM", "LOW"})
_ALLOWED_OPERATIONS = frozenset({"render_video", "transcribe_media"})
_REQUIRED_UNTRUSTED_INPUTS = frozenset({"media", "transcript", "prompt"})
_OPERATION_NETWORK = {
    "render_video": frozenset(),
    "transcribe_media": frozenset({"api.elevenlabs.io"}),
}
_OPERATION_SECRETS = {
    "render_video": frozenset(),
    "transcribe_media": frozenset({"secret://elevenlabs/api-key"}),
}


class IntegrationContractError(ValueError):
    """Raised when a future integration plan violates the reviewed contract."""


class IntegrationDisabledError(RuntimeError):
    """Raised when code attempts to execute a review-only integration."""


def _identifier(value: object, field: str) -> str:
    normalized = str(value).strip().lower()
    if not _IDENTIFIER.fullmatch(normalized):
        raise IntegrationContractError(f"{field} is invalid")
    return normalized


def _bounded_integer(value: object, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise IntegrationContractError(f"{field} is invalid")
    try:
        normalized = int(value)
    except (TypeError, ValueError) as error:
        raise IntegrationContractError(f"{field} is invalid") from error
    if normalized < minimum or normalized > maximum:
        raise IntegrationContractError(f"{field} is out of bounds")
    return normalized


def _virtual_paths(values: Sequence[str], root: str, field: str) -> Tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not values:
        raise IntegrationContractError(f"{field} must not be empty")
    normalized = []
    for raw in values:
        value = str(raw).strip().replace("\\", "/")
        path = PurePosixPath(value)
        if (
            not value
            or path.is_absolute()
            or value.startswith("/")
            or any(part in {"", ".", ".."} for part in path.parts)
            or (root in {"inputs", "outputs"} and any("%" in part for part in path.parts))
            or path.parts[0] != root
        ):
            raise IntegrationContractError(f"{field} must stay under {root}/")
        canonical = str(path)
        if canonical != value:
            raise IntegrationContractError(f"{field} must be canonical")
        normalized.append(canonical)
    if len(set(normalized)) != len(normalized):
        raise IntegrationContractError(f"{field} must not contain duplicates")
    return tuple(normalized)


def _exact_tuple(values: Sequence[str], field: str) -> Tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise IntegrationContractError(f"{field} must be a sequence")
    normalized = tuple(str(value).strip().lower() for value in values)
    if any(not value for value in normalized):
        raise IntegrationContractError(f"{field} must not contain empty values")
    if len(set(normalized)) != len(normalized):
        raise IntegrationContractError(f"{field} must not contain duplicates")
    return tuple(sorted(normalized))


@dataclass(frozen=True)
class IntegrationReviewManifest:
    schema: str
    integration_id: str
    display_name: str
    upstream_repository: str
    upstream_commit: str
    reviewed_at: str
    license: str
    review_status: str
    activation_allowed: bool
    execution_available: bool
    external_effects_enabled: bool
    reviewed_files: Mapping[str, str]
    capabilities: Tuple[str, ...]
    required_binaries: Tuple[str, ...]
    optional_binaries: Tuple[str, ...]
    external_services: Tuple[str, ...]
    known_findings: Tuple[Mapping[str, str], ...]
    activation_requirements: Tuple[str, ...]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "IntegrationReviewManifest":
        expected = {
            "schema",
            "integration_id",
            "display_name",
            "upstream_repository",
            "upstream_commit",
            "reviewed_at",
            "license",
            "review_status",
            "activation_allowed",
            "execution_available",
            "external_effects_enabled",
            "reviewed_files",
            "capabilities",
            "required_binaries",
            "optional_binaries",
            "external_services",
            "known_findings",
            "activation_requirements",
        }
        if set(raw) != expected:
            raise IntegrationContractError("integration manifest fields are invalid")
        if raw["schema"] != "agency-integration-review.v1":
            raise IntegrationContractError("integration manifest schema is unsupported")
        display_name = str(raw["display_name"]).strip()
        repository = str(raw["upstream_repository"]).strip()
        reviewed_at = str(raw["reviewed_at"]).strip()
        license_name = str(raw["license"]).strip()
        if not display_name or len(display_name) > 100:
            raise IntegrationContractError("display_name is invalid")
        if not _UPSTREAM_REPOSITORY.fullmatch(repository):
            raise IntegrationContractError("upstream_repository is invalid")
        if not _REVIEWED_AT.fullmatch(reviewed_at):
            raise IntegrationContractError("reviewed_at is invalid")
        if not license_name or len(license_name) > 64:
            raise IntegrationContractError("license is invalid")
        integration_id = _identifier(raw["integration_id"], "integration_id")
        commit = str(raw["upstream_commit"]).strip().lower()
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise IntegrationContractError("upstream_commit is invalid")
        reviewed_files_raw = raw["reviewed_files"]
        if not isinstance(reviewed_files_raw, dict) or not reviewed_files_raw:
            raise IntegrationContractError("reviewed_files is invalid")
        reviewed_files: Dict[str, str] = {}
        for path, digest in reviewed_files_raw.items():
            normalized_path = _virtual_paths((str(path),), str(PurePosixPath(str(path)).parts[0]), "reviewed_files")[0]
            normalized_digest = str(digest).strip().lower()
            if not _SHA256.fullmatch(normalized_digest):
                raise IntegrationContractError("reviewed file digest is invalid")
            if normalized_path in reviewed_files:
                raise IntegrationContractError("reviewed file paths must be unique")
            reviewed_files[normalized_path] = normalized_digest
        findings_raw = raw["known_findings"]
        if not isinstance(findings_raw, list) or not findings_raw:
            raise IntegrationContractError("known_findings is invalid")
        findings = []
        for item in findings_raw:
            if not isinstance(item, dict) or set(item) != {
                "id",
                "severity",
                "code",
                "state",
                "evidence",
            }:
                raise IntegrationContractError("known finding is invalid")
            normalized_finding = {key: str(value).strip() for key, value in item.items()}
            if not _FINDING_ID.fullmatch(normalized_finding["id"]):
                raise IntegrationContractError("known finding id is invalid")
            if normalized_finding["severity"] not in _FINDING_SEVERITIES:
                raise IntegrationContractError("known finding severity is invalid")
            if any(not normalized_finding[key] for key in ("code", "state", "evidence")):
                raise IntegrationContractError("known finding content is invalid")
            findings.append(normalized_finding)
        activation_requirements_raw = raw["activation_requirements"]
        if isinstance(activation_requirements_raw, (str, bytes)):
            raise IntegrationContractError("activation_requirements must be a sequence")
        activation_requirements = tuple(
            str(value).strip() for value in activation_requirements_raw
        )
        if not activation_requirements or any(not value for value in activation_requirements):
            raise IntegrationContractError("activation_requirements is invalid")
        if len(set(activation_requirements)) != len(activation_requirements):
            raise IntegrationContractError("activation_requirements must be unique")
        if raw["review_status"] != "reviewed_disabled":
            raise IntegrationContractError("integration must remain reviewed_disabled")
        if any(
            bool(raw[field])
            for field in (
                "activation_allowed",
                "execution_available",
                "external_effects_enabled",
            )
        ):
            raise IntegrationContractError("integration effects must remain disabled")
        return cls(
            schema=str(raw["schema"]),
            integration_id=integration_id,
            display_name=display_name,
            upstream_repository=repository,
            upstream_commit=commit,
            reviewed_at=reviewed_at,
            license=license_name,
            review_status=str(raw["review_status"]),
            activation_allowed=False,
            execution_available=False,
            external_effects_enabled=False,
            reviewed_files=dict(sorted(reviewed_files.items())),
            capabilities=_exact_tuple(raw["capabilities"], "capabilities"),
            required_binaries=_exact_tuple(raw["required_binaries"], "required_binaries"),
            optional_binaries=_exact_tuple(raw["optional_binaries"], "optional_binaries"),
            external_services=_exact_tuple(raw["external_services"], "external_services"),
            known_findings=tuple(findings),
            activation_requirements=activation_requirements,
        )

    def public_dict(self) -> Dict[str, object]:
        document = asdict(self)
        document["reviewed_files"] = dict(self.reviewed_files)
        document["known_findings"] = [dict(item) for item in self.known_findings]
        return document


@dataclass(frozen=True)
class IntegrationInvocationPlan:
    schema: str
    review_status: str
    execution_permitted: bool
    integration_id: str
    operation: str
    tenant_id: str
    campaign_id: str
    workspace_id: str
    idempotency_key: str
    greenlight_id: str
    fencing_token: int
    input_paths: Tuple[str, ...]
    output_paths: Tuple[str, ...]
    secret_refs: Tuple[str, ...]
    network_hosts: Tuple[str, ...]
    untrusted_inputs: Tuple[str, ...]
    max_input_bytes: int
    max_output_bytes: int
    max_duration_seconds: int
    max_attempts: int
    max_cost_cents: int

    @classmethod
    def review_only(
        cls,
        *,
        integration_id: str,
        operation: str,
        tenant_id: str,
        campaign_id: str,
        workspace_id: str,
        idempotency_key: str,
        greenlight_id: str,
        fencing_token: int,
        input_paths: Sequence[str],
        output_paths: Sequence[str],
        secret_refs: Sequence[str],
        network_hosts: Sequence[str],
        untrusted_inputs: Sequence[str],
        max_input_bytes: int,
        max_output_bytes: int,
        max_duration_seconds: int,
        max_attempts: int,
        max_cost_cents: int,
    ) -> "IntegrationInvocationPlan":
        normalized_integration = _identifier(integration_id, "integration_id")
        normalized_operation = _identifier(operation, "operation")
        if normalized_integration != "video-use":
            raise IntegrationContractError("integration_id is not reviewed")
        if normalized_operation not in _ALLOWED_OPERATIONS:
            raise IntegrationContractError("operation is not reviewed")
        normalized_idempotency = _identifier(idempotency_key, "idempotency_key")
        if len(normalized_idempotency) < 24:
            raise IntegrationContractError("idempotency_key is too short")
        normalized_greenlight = _identifier(greenlight_id, "greenlight_id")
        normalized_secrets = _exact_tuple(secret_refs, "secret_refs")
        if any(not _SECRET_REF.fullmatch(value) for value in normalized_secrets):
            raise IntegrationContractError("secret_refs must contain references only")
        expected_secrets = _OPERATION_SECRETS[normalized_operation]
        if set(normalized_secrets) != expected_secrets:
            raise IntegrationContractError("secret_refs do not match operation")
        normalized_hosts = _exact_tuple(network_hosts, "network_hosts")
        if set(normalized_hosts) != _OPERATION_NETWORK[normalized_operation]:
            raise IntegrationContractError("network_hosts do not match operation")
        normalized_untrusted = _exact_tuple(untrusted_inputs, "untrusted_inputs")
        if set(normalized_untrusted) != _REQUIRED_UNTRUSTED_INPUTS:
            raise IntegrationContractError("untrusted input classes must match the reviewed boundary")
        cost = _bounded_integer(max_cost_cents, "max_cost_cents", 0, 0)
        return cls(
            schema="agency-integration-invocation.v1",
            review_status="review_only",
            execution_permitted=False,
            integration_id=normalized_integration,
            operation=normalized_operation,
            tenant_id=_identifier(tenant_id, "tenant_id"),
            campaign_id=_identifier(campaign_id, "campaign_id"),
            workspace_id=_identifier(workspace_id, "workspace_id"),
            idempotency_key=normalized_idempotency,
            greenlight_id=normalized_greenlight,
            fencing_token=_bounded_integer(
                fencing_token, "fencing_token", 1, 2_147_483_647
            ),
            input_paths=_virtual_paths(input_paths, "inputs", "input_paths"),
            output_paths=_virtual_paths(output_paths, "outputs", "output_paths"),
            secret_refs=normalized_secrets,
            network_hosts=normalized_hosts,
            untrusted_inputs=normalized_untrusted,
            max_input_bytes=_bounded_integer(
                max_input_bytes, "max_input_bytes", 1, 500_000_000
            ),
            max_output_bytes=_bounded_integer(
                max_output_bytes, "max_output_bytes", 1, 100_000_000
            ),
            max_duration_seconds=_bounded_integer(
                max_duration_seconds, "max_duration_seconds", 1, 3600
            ),
            max_attempts=_bounded_integer(max_attempts, "max_attempts", 1, 3),
            max_cost_cents=cost,
        )


@dataclass(frozen=True)
class IntegrationExecutionReceipt:
    schema: str
    integration_id: str
    operation: str
    tenant_id: str
    campaign_id: str
    workspace_id: str
    idempotency_key_digest: str
    greenlight_id: str
    fencing_token: int
    input_sha256: Tuple[str, ...]
    output_sha256: Tuple[str, ...]
    provider_request_id: str
    cost_cents: int
    completed_at: str


class IntegrationRegistry:
    def __init__(self, manifests: Sequence[IntegrationReviewManifest]):
        self._manifests = {manifest.integration_id: manifest for manifest in manifests}
        if len(self._manifests) != len(manifests):
            raise IntegrationContractError("integration ids must be unique")

    @classmethod
    def default(cls) -> "IntegrationRegistry":
        resource = files("agency_runtime").joinpath(
            "integration_reviews/video_use.json"
        )
        raw = json.loads(resource.read_text(encoding="utf-8"))
        return cls((IntegrationReviewManifest.from_mapping(raw),))

    def list(self) -> Tuple[IntegrationReviewManifest, ...]:
        return tuple(self._manifests[key] for key in sorted(self._manifests))

    def get(self, integration_id: str) -> IntegrationReviewManifest:
        normalized = _identifier(integration_id, "integration_id")
        try:
            return self._manifests[normalized]
        except KeyError as error:
            raise KeyError("integration not found") from error

    def execute(self, plan: IntegrationInvocationPlan) -> None:
        del plan
        raise IntegrationDisabledError("integration execution is disabled")

    def receipt_from_plan(
        self,
        plan: IntegrationInvocationPlan,
        *,
        provider_request_id: str,
        output_sha256: Sequence[str],
    ) -> IntegrationExecutionReceipt:
        del plan, provider_request_id, output_sha256
        raise IntegrationDisabledError("integration receipts require enabled execution")
