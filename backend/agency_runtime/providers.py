from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Mapping, Optional, Tuple
from urllib.parse import urlsplit


_PROVIDER_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")
_MODEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")


class ProviderConfigurationError(ValueError):
    """Raised when provider metadata is unsafe or ambiguous."""


@dataclass(frozen=True)
class _ProviderDefinition:
    provider_id: str
    display_name: str
    protocol: str
    credential_envs: Tuple[str, ...]
    model_env: str
    base_url_env: str
    default_base_url: str
    recommended_models: Tuple[str, ...]


@dataclass(frozen=True)
class ProviderContract:
    provider_id: str
    display_name: str
    protocol: str
    configured: bool
    configuration_state: str
    model: str
    endpoint_host: str
    model_environment: str
    base_url_environment: str
    recommended_models: Tuple[str, ...]

    def public_dict(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "display_name": self.display_name,
            "protocol": self.protocol,
            "configured": self.configured,
            "configuration_state": self.configuration_state,
            "model": self.model,
            "endpoint_host": self.endpoint_host,
            "model_environment": self.model_environment,
            "base_url_environment": self.base_url_environment,
            "credential_location": "server_environment",
            "recommended_models": list(self.recommended_models),
        }


@dataclass(frozen=True)
class ProviderExecutionConfig:
    """Private provider material used only by the server-side gateway."""

    provider_id: str
    protocol: str
    model: str
    base_url: str
    endpoint_host: str
    credential: str = field(repr=False)


_DEFINITIONS: Tuple[_ProviderDefinition, ...] = (
    _ProviderDefinition(
        provider_id="openai",
        display_name="OpenAI",
        protocol="openai_responses",
        credential_envs=("OPENAI_API_KEY",),
        model_env="AGENCY_OPENAI_MODEL",
        base_url_env="AGENCY_OPENAI_BASE_URL",
        default_base_url="https://api.openai.com/v1",
        recommended_models=("gpt-5.2", "gpt-5-mini"),
    ),
    _ProviderDefinition(
        provider_id="anthropic",
        display_name="Anthropic",
        protocol="anthropic_messages",
        credential_envs=("ANTHROPIC_API_KEY",),
        model_env="AGENCY_ANTHROPIC_MODEL",
        base_url_env="AGENCY_ANTHROPIC_BASE_URL",
        default_base_url="https://api.anthropic.com",
        recommended_models=("claude-opus-4-1", "claude-sonnet-4"),
    ),
    _ProviderDefinition(
        provider_id="deepseek",
        display_name="DeepSeek",
        protocol="openai_compatible",
        credential_envs=("DEEPSEEK_API_KEY",),
        model_env="AGENCY_DEEPSEEK_MODEL",
        base_url_env="AGENCY_DEEPSEEK_BASE_URL",
        default_base_url="https://api.deepseek.com",
        recommended_models=("deepseek-v4-flash", "deepseek-v4-pro"),
    ),
    _ProviderDefinition(
        provider_id="moonshot",
        display_name="Moonshot / Kimi",
        protocol="openai_compatible",
        credential_envs=("MOONSHOT_API_KEY", "KIMI_API_KEY"),
        model_env="AGENCY_MOONSHOT_MODEL",
        base_url_env="AGENCY_MOONSHOT_BASE_URL",
        default_base_url="https://api.moonshot.ai/v1",
        recommended_models=("kimi-k3",),
    ),
    _ProviderDefinition(
        provider_id="llama",
        display_name="Llama",
        protocol="openai_compatible",
        credential_envs=("LLAMA_API_KEY",),
        model_env="AGENCY_LLAMA_MODEL",
        base_url_env="AGENCY_LLAMA_BASE_URL",
        default_base_url="",
        recommended_models=("llama-4-maverick", "llama-4-scout"),
    ),
)


class ProviderRegistry:
    """Read-only public registry plus private server execution configuration.

    Raw credentials never enter public contracts. The registry itself performs no
    network requests and creates no provider clients.
    """

    def __init__(
        self,
        providers: Tuple[ProviderContract, ...],
        execution_configs: Tuple[ProviderExecutionConfig, ...],
    ) -> None:
        expected_ids = tuple(item.provider_id for item in _DEFINITIONS)
        ids = tuple(item.provider_id for item in providers)
        config_ids = tuple(item.provider_id for item in execution_configs)
        if ids != expected_ids or config_ids != expected_ids:
            raise ProviderConfigurationError("provider registry must use the exact allowlist")
        self._providers = providers
        self._by_id = {item.provider_id: item for item in providers}
        self._execution_by_id = {
            item.provider_id: item for item in execution_configs
        }

    @classmethod
    def from_environment(
        cls, environment: Optional[Mapping[str, str]] = None
    ) -> "ProviderRegistry":
        source = environment if environment is not None else {}
        pairs = tuple(cls._configured(definition, source) for definition in _DEFINITIONS)
        return cls(
            tuple(pair[0] for pair in pairs),
            tuple(pair[1] for pair in pairs),
        )

    @staticmethod
    def _configured(
        definition: _ProviderDefinition,
        environment: Mapping[str, str],
    ) -> Tuple[ProviderContract, ProviderExecutionConfig]:
        if not _PROVIDER_ID_PATTERN.fullmatch(definition.provider_id):
            raise ProviderConfigurationError("invalid provider id")

        credential_values = tuple(
            str(environment.get(name, "")).strip()
            for name in definition.credential_envs
            if str(environment.get(name, "")).strip()
        )
        distinct_credentials = tuple(dict.fromkeys(credential_values))
        if len(distinct_credentials) > 1:
            raise ProviderConfigurationError(
                "{} credential aliases disagree".format(definition.provider_id)
            )
        credential = distinct_credentials[0] if distinct_credentials else ""

        model = str(environment.get(definition.model_env, "")).strip()
        if model and not _MODEL_PATTERN.fullmatch(model):
            raise ProviderConfigurationError(
                "{} must contain a safe model identifier".format(definition.model_env)
            )

        raw_base_url = str(
            environment.get(definition.base_url_env, definition.default_base_url)
        ).strip()
        endpoint_host = ""
        if raw_base_url:
            endpoint_host = ProviderRegistry._endpoint_host(
                definition.base_url_env, raw_base_url
            )

        if not credential:
            state = "missing_credential"
        elif not model:
            state = "missing_model"
        elif not endpoint_host:
            state = "missing_endpoint"
        else:
            state = "ready"

        contract = ProviderContract(
            provider_id=definition.provider_id,
            display_name=definition.display_name,
            protocol=definition.protocol,
            configured=state == "ready",
            configuration_state=state,
            model=model,
            endpoint_host=endpoint_host,
            model_environment=definition.model_env,
            base_url_environment=definition.base_url_env,
            recommended_models=definition.recommended_models,
        )
        execution = ProviderExecutionConfig(
            provider_id=definition.provider_id,
            protocol=definition.protocol,
            model=model,
            base_url=raw_base_url,
            endpoint_host=endpoint_host,
            credential=credential,
        )
        return contract, execution

    @staticmethod
    def _endpoint_host(name: str, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ProviderConfigurationError(
                "{} must be an absolute HTTPS URL".format(name)
            )
        if parsed.username is not None or parsed.password is not None:
            raise ProviderConfigurationError(
                "{} must not contain credentials".format(name)
            )
        if parsed.query or parsed.fragment:
            raise ProviderConfigurationError(
                "{} must not contain query or fragment data".format(name)
            )
        return parsed.hostname.lower()

    def list(self) -> Tuple[ProviderContract, ...]:
        return self._providers

    def public_list(self) -> list[dict[str, object]]:
        return [item.public_dict() for item in self._providers]

    def get(self, provider_id: str) -> ProviderContract:
        normalized = provider_id.strip().lower()
        if normalized not in self._by_id:
            raise KeyError("provider not found")
        return self._by_id[normalized]

    def execution_config(self, provider_id: str) -> ProviderExecutionConfig:
        normalized = provider_id.strip().lower()
        if normalized not in self._execution_by_id:
            raise KeyError("provider not found")
        return self._execution_by_id[normalized]
