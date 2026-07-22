from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from dataclasses import dataclass
from typing import Mapping, Optional, Tuple
from urllib.parse import urlsplit

import httpx

from .providers import ProviderExecutionConfig, ProviderRegistry
from .utils import canonical_json


_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
_HOST_PATTERN = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)


class ModelGatewayError(RuntimeError):
    pass


class ModelGatewayDisabledError(ModelGatewayError):
    pass


class ModelGatewayConfigurationError(ModelGatewayError):
    pass


class ModelGatewayProviderError(ModelGatewayError):
    pass


@dataclass(frozen=True)
class ModelRequest:
    request_id: str
    user: str
    system: str = ""


@dataclass(frozen=True)
class ModelReceipt:
    provider_id: str
    model: str
    provider_request_id: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    request_sha256: str
    output_sha256: str

    def public_dict(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "model": self.model,
            "provider_request_id": self.provider_request_id,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "request_sha256": self.request_sha256,
            "output_sha256": self.output_sha256,
        }


@dataclass(frozen=True)
class ModelResult:
    text: str
    receipt: ModelReceipt


@dataclass(frozen=True)
class _GatewayPolicy:
    enabled: bool
    selected_provider: str
    allowed_hosts: Tuple[str, ...]
    max_input_chars: int
    max_output_tokens: int
    max_response_bytes: int
    timeout_seconds: float


class ModelGateway:
    """Bounded multi-provider HTTP gateway.

    The gateway implements real provider protocols, but no API route or orchestrator
    invokes it automatically. Production activation requires a durable outbound effect
    receipt before the external call can be connected to run execution.
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        policy: _GatewayPolicy,
        *,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self._registry = registry
        self._policy = policy
        self._provider: Optional[ProviderExecutionConfig] = None
        self._client: Optional[httpx.Client] = None

        if not policy.enabled:
            return

        try:
            contract = registry.get(policy.selected_provider)
            provider = registry.execution_config(policy.selected_provider)
        except KeyError as error:
            raise ModelGatewayConfigurationError(
                "selected model provider is not supported"
            ) from error
        if not contract.configured:
            raise ModelGatewayConfigurationError(
                "selected model provider is not fully configured"
            )
        if provider.endpoint_host not in policy.allowed_hosts:
            raise ModelGatewayConfigurationError(
                "selected model provider host is not allowlisted"
            )

        self._provider = provider
        self._client = httpx.Client(
            timeout=httpx.Timeout(policy.timeout_seconds),
            transport=transport,
            trust_env=False,
            follow_redirects=False,
            headers={"Accept": "application/json"},
        )

    @classmethod
    def from_environment(
        cls,
        environment: Optional[Mapping[str, str]] = None,
        *,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> "ModelGateway":
        source = environment if environment is not None else {}
        registry = ProviderRegistry.from_environment(source)
        policy = cls._policy_from_environment(source)
        return cls(registry, policy, transport=transport)

    @staticmethod
    def _policy_from_environment(environment: Mapping[str, str]) -> _GatewayPolicy:
        enabled_raw = str(
            environment.get("AGENCY_MODEL_EXECUTION_ENABLED", "false")
        ).strip().lower()
        if enabled_raw not in {"true", "false"}:
            raise ModelGatewayConfigurationError(
                "AGENCY_MODEL_EXECUTION_ENABLED must be true or false"
            )
        enabled = enabled_raw == "true"

        selected = str(environment.get("AGENCY_MODEL_PROVIDER", "")).strip().lower()
        if selected and not re.fullmatch(r"[a-z][a-z0-9_-]{1,31}", selected):
            raise ModelGatewayConfigurationError(
                "AGENCY_MODEL_PROVIDER contains an invalid provider id"
            )
        if enabled and not selected:
            raise ModelGatewayConfigurationError(
                "AGENCY_MODEL_PROVIDER is required when model execution is enabled"
            )

        allowed_hosts = ModelGateway._allowed_hosts(
            str(environment.get("AGENCY_MODEL_EGRESS_ALLOWED_HOSTS", ""))
        )
        if enabled and not allowed_hosts:
            raise ModelGatewayConfigurationError(
                "AGENCY_MODEL_EGRESS_ALLOWED_HOSTS is required when model execution is enabled"
            )

        return _GatewayPolicy(
            enabled=enabled,
            selected_provider=selected,
            allowed_hosts=allowed_hosts,
            max_input_chars=ModelGateway._bounded_int(
                environment,
                "AGENCY_MODEL_MAX_INPUT_CHARS",
                default=12000,
                minimum=1,
                maximum=200000,
            ),
            max_output_tokens=ModelGateway._bounded_int(
                environment,
                "AGENCY_MODEL_MAX_OUTPUT_TOKENS",
                default=512,
                minimum=1,
                maximum=8192,
            ),
            max_response_bytes=ModelGateway._bounded_int(
                environment,
                "AGENCY_MODEL_MAX_RESPONSE_BYTES",
                default=1048576,
                minimum=64,
                maximum=8388608,
            ),
            timeout_seconds=ModelGateway._bounded_float(
                environment,
                "AGENCY_MODEL_TIMEOUT_SECONDS",
                default=30.0,
                minimum=1.0,
                maximum=120.0,
            ),
        )

    @staticmethod
    def _bounded_int(
        environment: Mapping[str, str],
        name: str,
        *,
        default: int,
        minimum: int,
        maximum: int,
    ) -> int:
        raw = str(environment.get(name, str(default))).strip()
        try:
            value = int(raw)
        except ValueError as error:
            raise ModelGatewayConfigurationError(
                "{} must be an integer".format(name)
            ) from error
        if value < minimum or value > maximum:
            raise ModelGatewayConfigurationError(
                "{} must be between {} and {}".format(name, minimum, maximum)
            )
        return value

    @staticmethod
    def _bounded_float(
        environment: Mapping[str, str],
        name: str,
        *,
        default: float,
        minimum: float,
        maximum: float,
    ) -> float:
        raw = str(environment.get(name, str(default))).strip()
        try:
            value = float(raw)
        except ValueError as error:
            raise ModelGatewayConfigurationError(
                "{} must be numeric".format(name)
            ) from error
        if not minimum <= value <= maximum:
            raise ModelGatewayConfigurationError(
                "{} must be between {} and {}".format(name, minimum, maximum)
            )
        return value

    @staticmethod
    def _allowed_hosts(raw: str) -> Tuple[str, ...]:
        hosts = []
        for item in raw.split(","):
            host = item.strip().lower().rstrip(".")
            if not host:
                continue
            try:
                ipaddress.ip_address(host)
            except ValueError:
                pass
            else:
                raise ModelGatewayConfigurationError(
                    "model egress allowlist rejects IP literals"
                )
            if host == "localhost" or host.endswith(".local"):
                raise ModelGatewayConfigurationError(
                    "model egress allowlist rejects local hosts"
                )
            if not _HOST_PATTERN.fullmatch(host):
                raise ModelGatewayConfigurationError(
                    "model egress allowlist contains an invalid host"
                )
            if host not in hosts:
                hosts.append(host)
        return tuple(hosts)

    def public_status(self) -> dict[str, object]:
        return {
            "execution_enabled": self._policy.enabled,
            "selected_provider": self._policy.selected_provider,
            "execution_available": self._client is not None,
            "durable_outbound_receipt": False,
            "automatic_run_integration": False,
        }

    def close(self) -> None:
        if self._client is not None:
            self._client.close()

    def complete(self, request: ModelRequest) -> ModelResult:
        if not self._policy.enabled or self._provider is None or self._client is None:
            raise ModelGatewayDisabledError("model gateway execution is disabled")
        normalized = self._validated_request(request)
        url, headers, body = self._provider_request(self._provider, normalized)
        payload, response_headers = self._post_json(url, headers, body)
        text, usage = self._parse_response(self._provider.protocol, payload)
        provider_request_id = self._provider_request_id(response_headers, payload)
        request_hash = hashlib.sha256(
            canonical_json(
                {
                    "provider_id": self._provider.provider_id,
                    "model": self._provider.model,
                    "request_id": normalized.request_id,
                    "system": normalized.system,
                    "user": normalized.user,
                    "max_output_tokens": self._policy.max_output_tokens,
                }
            ).encode("utf-8")
        ).hexdigest()
        output_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        receipt = ModelReceipt(
            provider_id=self._provider.provider_id,
            model=self._provider.model,
            provider_request_id=provider_request_id,
            input_tokens=usage[0],
            output_tokens=usage[1],
            total_tokens=usage[2],
            request_sha256=request_hash,
            output_sha256=output_hash,
        )
        return ModelResult(text=text, receipt=receipt)

    def _validated_request(self, request: ModelRequest) -> ModelRequest:
        request_id = request.request_id.strip()
        system = request.system.strip()
        user = request.user.strip()
        if not _REQUEST_ID_PATTERN.fullmatch(request_id):
            raise ModelGatewayConfigurationError("model request id is invalid")
        if not user:
            raise ModelGatewayConfigurationError("model user input must not be empty")
        if len(system) + len(user) > self._policy.max_input_chars:
            raise ModelGatewayConfigurationError(
                "model input exceeded the configured character limit"
            )
        return ModelRequest(request_id=request_id, system=system, user=user)

    def _provider_request(
        self,
        provider: ProviderExecutionConfig,
        request: ModelRequest,
    ) -> Tuple[str, Mapping[str, str], Mapping[str, object]]:
        common_headers = {"Content-Type": "application/json"}
        if provider.protocol == "openai_responses":
            body: dict[str, object] = {
                "model": provider.model,
                "input": request.user,
                "max_output_tokens": self._policy.max_output_tokens,
            }
            if request.system:
                body["instructions"] = request.system
            return (
                self._join_url(provider.base_url, "responses"),
                {**common_headers, "Authorization": "Bearer {}".format(provider.credential)},
                body,
            )
        if provider.protocol == "anthropic_messages":
            body = {
                "model": provider.model,
                "messages": [{"role": "user", "content": request.user}],
                "max_tokens": self._policy.max_output_tokens,
            }
            if request.system:
                body["system"] = request.system
            return (
                self._join_url(provider.base_url, "v1/messages"),
                {
                    **common_headers,
                    "x-api-key": provider.credential,
                    "anthropic-version": "2023-06-01",
                },
                body,
            )
        if provider.protocol == "openai_compatible":
            messages = []
            if request.system:
                messages.append({"role": "system", "content": request.system})
            messages.append({"role": "user", "content": request.user})
            return (
                self._join_url(provider.base_url, "chat/completions"),
                {**common_headers, "Authorization": "Bearer {}".format(provider.credential)},
                {
                    "model": provider.model,
                    "messages": messages,
                    "max_tokens": self._policy.max_output_tokens,
                    "stream": False,
                },
            )
        raise ModelGatewayConfigurationError("unsupported model provider protocol")

    @staticmethod
    def _join_url(base_url: str, suffix: str) -> str:
        parsed = urlsplit(base_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ModelGatewayConfigurationError("model provider base URL is invalid")
        return "{}/{}".format(base_url.rstrip("/"), suffix.lstrip("/"))

    def _post_json(
        self,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object],
    ) -> Tuple[Mapping[str, object], Mapping[str, str]]:
        assert self._client is not None
        try:
            with self._client.stream(
                "POST", url, headers=dict(headers), json=dict(body)
            ) as response:
                if response.status_code < 200 or response.status_code >= 300:
                    raise ModelGatewayProviderError(
                        "model provider request failed (status={})".format(
                            response.status_code
                        )
                    )
                chunks = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > self._policy.max_response_bytes:
                        raise ModelGatewayProviderError(
                            "model provider response exceeded the configured size limit"
                        )
                    chunks.append(chunk)
                raw = b"".join(chunks)
                response_headers = dict(response.headers)
        except ModelGatewayProviderError:
            raise
        except httpx.TimeoutException as error:
            raise ModelGatewayProviderError("model provider request timed out") from error
        except httpx.RequestError as error:
            raise ModelGatewayProviderError("model provider request failed") from error

        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ModelGatewayProviderError(
                "model provider returned an invalid response"
            ) from error
        if not isinstance(payload, Mapping):
            raise ModelGatewayProviderError("model provider returned an invalid response")
        return payload, response_headers

    @staticmethod
    def _parse_response(
        protocol: str, payload: Mapping[str, object]
    ) -> Tuple[str, Tuple[int, int, int]]:
        try:
            if protocol == "openai_responses":
                text = ModelGateway._openai_response_text(payload)
                usage = ModelGateway._usage(
                    payload.get("usage"), "input_tokens", "output_tokens", "total_tokens"
                )
            elif protocol == "anthropic_messages":
                content = payload.get("content")
                if not isinstance(content, list):
                    raise ValueError
                text_parts = [
                    item.get("text")
                    for item in content
                    if isinstance(item, Mapping)
                    and item.get("type") == "text"
                    and isinstance(item.get("text"), str)
                ]
                text = "".join(text_parts).strip()
                usage = ModelGateway._usage(
                    payload.get("usage"), "input_tokens", "output_tokens", None
                )
            elif protocol == "openai_compatible":
                choices = payload.get("choices")
                if not isinstance(choices, list) or not choices:
                    raise ValueError
                first = choices[0]
                if not isinstance(first, Mapping):
                    raise ValueError
                message = first.get("message")
                if not isinstance(message, Mapping) or not isinstance(
                    message.get("content"), str
                ):
                    raise ValueError
                text = str(message["content"]).strip()
                usage = ModelGateway._usage(
                    payload.get("usage"), "prompt_tokens", "completion_tokens", "total_tokens"
                )
            else:
                raise ValueError
            if not text:
                raise ValueError
            return text, usage
        except (KeyError, TypeError, ValueError) as error:
            raise ModelGatewayProviderError(
                "model provider returned an invalid response"
            ) from error

    @staticmethod
    def _openai_response_text(payload: Mapping[str, object]) -> str:
        direct = payload.get("output_text")
        if isinstance(direct, str) and direct.strip():
            return direct.strip()
        output = payload.get("output")
        if not isinstance(output, list):
            raise ValueError
        parts = []
        for item in output:
            if not isinstance(item, Mapping):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for entry in content:
                if (
                    isinstance(entry, Mapping)
                    and entry.get("type") == "output_text"
                    and isinstance(entry.get("text"), str)
                ):
                    parts.append(str(entry["text"]))
        text = "".join(parts).strip()
        if not text:
            raise ValueError
        return text

    @staticmethod
    def _usage(
        raw: object,
        input_name: str,
        output_name: str,
        total_name: Optional[str],
    ) -> Tuple[int, int, int]:
        if not isinstance(raw, Mapping):
            raise ValueError
        input_tokens = ModelGateway._token_count(raw.get(input_name))
        output_tokens = ModelGateway._token_count(raw.get(output_name))
        if total_name is None:
            total_tokens = input_tokens + output_tokens
        else:
            total_tokens = ModelGateway._token_count(raw.get(total_name))
            if total_tokens < input_tokens + output_tokens:
                raise ValueError
        return input_tokens, output_tokens, total_tokens

    @staticmethod
    def _token_count(value: object) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError
        if value < 0 or value > 100000000:
            raise ValueError
        return value

    @staticmethod
    def _provider_request_id(
        headers: Mapping[str, str], payload: Mapping[str, object]
    ) -> str:
        raw = (
            headers.get("x-request-id")
            or headers.get("request-id")
            or payload.get("id")
            or ""
        )
        value = str(raw).strip()
        if _REQUEST_ID_PATTERN.fullmatch(value):
            return value
        return "provider-{}".format(
            hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]
        )
