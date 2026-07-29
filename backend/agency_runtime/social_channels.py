from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional, Tuple
from urllib.parse import urlsplit


class SocialChannelConfigurationError(ValueError):
    """Raised when social-channel configuration is unsafe or ambiguous."""


@dataclass(frozen=True)
class _SocialChannelDefinition:
    channel_id: str
    display_name: str
    oauth_flow: str
    credential_groups: Tuple[Tuple[str, ...], ...]
    public_credential_environments: Tuple[str, ...]
    redirect_environment: str
    scopes: Tuple[str, ...]
    account_requirement: str
    publish_protocol: str
    supported_content: Tuple[str, ...]
    requires_media: bool


@dataclass(frozen=True)
class SocialChannelContract:
    channel_id: str
    display_name: str
    oauth_flow: str
    configured: bool
    configuration_state: str
    credentials_configured: bool
    callback_configured: bool
    connection_state: str
    oauth_start_available: bool
    publishing_available: bool
    external_effects_enabled: bool
    credential_environments: Tuple[str, ...]
    redirect_environment: str
    scopes: Tuple[str, ...]
    account_requirement: str
    publish_protocol: str
    supported_content: Tuple[str, ...]
    requires_media: bool

    def public_dict(self) -> dict[str, object]:
        return {
            "channel_id": self.channel_id,
            "display_name": self.display_name,
            "oauth_flow": self.oauth_flow,
            "configured": self.configured,
            "configuration_state": self.configuration_state,
            "credentials_configured": self.credentials_configured,
            "callback_configured": self.callback_configured,
            "connection_state": self.connection_state,
            "oauth_start_available": self.oauth_start_available,
            "publishing_available": self.publishing_available,
            "external_effects_enabled": self.external_effects_enabled,
            "credential_location": "server_environment",
            "credential_environments": list(self.credential_environments),
            "redirect_environment": self.redirect_environment,
            "scopes": list(self.scopes),
            "account_requirement": self.account_requirement,
            "publish_protocol": self.publish_protocol,
            "supported_content": list(self.supported_content),
            "requires_media": self.requires_media,
        }


@dataclass(frozen=True)
class SocialChannelPrivateConfig:
    channel_id: str
    redirect_uri: str
    credentials: Tuple[str, ...] = field(repr=False)


_DEFINITIONS: Tuple[_SocialChannelDefinition, ...] = (
    _SocialChannelDefinition(
        channel_id="x",
        display_name="X",
        oauth_flow="oauth_1_0a_user_context",
        credential_groups=(
            ("AGENCY_X_CONSUMER_KEY", "AGENCY_X_CLIENT_ID"),
            ("AGENCY_X_CONSUMER_SECRET", "AGENCY_X_CLIENT_SECRET"),
        ),
        public_credential_environments=(
            "AGENCY_X_CONSUMER_KEY",
            "AGENCY_X_CONSUMER_SECRET",
        ),
        redirect_environment="AGENCY_X_REDIRECT_URI",
        scopes=("tweet.read", "tweet.write", "users.read"),
        account_requirement="X account authorized by the tenant",
        publish_protocol="POST /2/tweets",
        supported_content=("text", "image", "video"),
        requires_media=False,
    ),
    _SocialChannelDefinition(
        channel_id="instagram",
        display_name="Instagram",
        oauth_flow="instagram_business_login",
        credential_groups=(
            ("AGENCY_INSTAGRAM_APP_ID",),
            ("AGENCY_INSTAGRAM_APP_SECRET",),
        ),
        public_credential_environments=(
            "AGENCY_INSTAGRAM_APP_ID",
            "AGENCY_INSTAGRAM_APP_SECRET",
        ),
        redirect_environment="AGENCY_INSTAGRAM_REDIRECT_URI",
        scopes=(
            "instagram_business_basic",
            "instagram_business_content_publish",
        ),
        account_requirement="Instagram Professional account (Business or Creator)",
        publish_protocol="POST /media then POST /media_publish",
        supported_content=("image", "reel", "carousel"),
        requires_media=True,
    ),
)


class SocialChannelRegistry:
    """Secret-free readiness catalog for tenant social publishing channels.

    This registry validates server configuration only. It deliberately does not issue
    OAuth requests, persist access tokens, or publish content. Those effects require a
    durable encrypted credential store and publication intent/receipt boundary.
    """

    def __init__(
        self,
        channels: Tuple[SocialChannelContract, ...],
        private_configs: Tuple[SocialChannelPrivateConfig, ...],
    ) -> None:
        expected = tuple(item.channel_id for item in _DEFINITIONS)
        if tuple(item.channel_id for item in channels) != expected:
            raise SocialChannelConfigurationError(
                "social channel registry must use the exact allowlist"
            )
        if tuple(item.channel_id for item in private_configs) != expected:
            raise SocialChannelConfigurationError(
                "social channel private configuration must use the exact allowlist"
            )
        self._channels = channels
        self._by_id = {item.channel_id: item for item in channels}
        self._private_by_id = {item.channel_id: item for item in private_configs}

    @classmethod
    def from_environment(
        cls, environment: Optional[Mapping[str, str]] = None
    ) -> "SocialChannelRegistry":
        source = environment if environment is not None else {}
        pairs = tuple(cls._configured(definition, source) for definition in _DEFINITIONS)
        return cls(
            tuple(pair[0] for pair in pairs),
            tuple(pair[1] for pair in pairs),
        )

    @staticmethod
    def _configured(
        definition: _SocialChannelDefinition,
        environment: Mapping[str, str],
    ) -> Tuple[SocialChannelContract, SocialChannelPrivateConfig]:
        credentials = tuple(
            SocialChannelRegistry._alias_value(
                environment,
                aliases,
                "{} credential".format(definition.channel_id),
            )
            for aliases in definition.credential_groups
        )
        credentials_configured = all(credentials)
        redirect_uri = str(environment.get(definition.redirect_environment, "")).strip()
        callback_configured = bool(redirect_uri)
        if redirect_uri:
            SocialChannelRegistry._validate_redirect_uri(
                definition.redirect_environment, redirect_uri
            )

        if not credentials_configured:
            state = "missing_credentials"
        elif not callback_configured:
            state = "missing_redirect_uri"
        else:
            state = "ready_for_authentication"

        contract = SocialChannelContract(
            channel_id=definition.channel_id,
            display_name=definition.display_name,
            oauth_flow=definition.oauth_flow,
            configured=state == "ready_for_authentication",
            configuration_state=state,
            credentials_configured=credentials_configured,
            callback_configured=callback_configured,
            connection_state="not_connected",
            oauth_start_available=False,
            publishing_available=False,
            external_effects_enabled=False,
            credential_environments=definition.public_credential_environments,
            redirect_environment=definition.redirect_environment,
            scopes=definition.scopes,
            account_requirement=definition.account_requirement,
            publish_protocol=definition.publish_protocol,
            supported_content=definition.supported_content,
            requires_media=definition.requires_media,
        )
        private = SocialChannelPrivateConfig(
            channel_id=definition.channel_id,
            redirect_uri=redirect_uri,
            credentials=credentials,
        )
        return contract, private

    @staticmethod
    def _alias_value(
        environment: Mapping[str, str], aliases: Tuple[str, ...], field: str
    ) -> str:
        values = tuple(
            str(environment.get(name, "")).strip()
            for name in aliases
            if str(environment.get(name, "")).strip()
        )
        distinct = tuple(dict.fromkeys(values))
        if len(distinct) > 1:
            raise SocialChannelConfigurationError(
                "{} aliases disagree".format(field)
            )
        value = distinct[0] if distinct else ""
        if any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise SocialChannelConfigurationError("{} contains control characters".format(field))
        if len(value) > 4096:
            raise SocialChannelConfigurationError("{} is too long".format(field))
        return value

    @staticmethod
    def _validate_redirect_uri(name: str, value: str) -> None:
        parsed = urlsplit(value)
        hostname = (parsed.hostname or "").lower()
        local_http = parsed.scheme == "http" and hostname in {
            "127.0.0.1",
            "localhost",
            "::1",
        }
        if not ((parsed.scheme == "https" and hostname) or local_http):
            raise SocialChannelConfigurationError(
                "{} must be HTTPS or a loopback HTTP URL".format(name)
            )
        if parsed.username is not None or parsed.password is not None:
            raise SocialChannelConfigurationError(
                "{} must not contain credentials".format(name)
            )
        if parsed.query or parsed.fragment:
            raise SocialChannelConfigurationError(
                "{} must not contain query or fragment data".format(name)
            )
        if not parsed.path.startswith("/"):
            raise SocialChannelConfigurationError(
                "{} must contain an absolute callback path".format(name)
            )

    def list(self) -> Tuple[SocialChannelContract, ...]:
        return self._channels

    def public_list(self) -> list[dict[str, object]]:
        return [item.public_dict() for item in self._channels]

    def get(self, channel_id: str) -> SocialChannelContract:
        normalized = channel_id.strip().lower()
        try:
            return self._by_id[normalized]
        except KeyError as error:
            raise KeyError("social channel not found") from error

    def private_config(self, channel_id: str) -> SocialChannelPrivateConfig:
        normalized = channel_id.strip().lower()
        try:
            return self._private_by_id[normalized]
        except KeyError as error:
            raise KeyError("social channel not found") from error
