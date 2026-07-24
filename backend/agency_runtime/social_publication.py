from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Callable, Mapping, Optional
from urllib.parse import parse_qs, quote, urlencode, urlsplit, urlunsplit

import httpx

from .memory import utc_now
from .social_oauth import SocialTokenCipher
from .social_publication_store import (
    SocialPublicationConflictError,
    SocialPublicationIntent,
    SocialPublicationReservation,
    SocialPublicationStateError,
)
from .utils import canonical_json, stable_id


Clock = Callable[[], str]
TokenFactory = Callable[[], str]
TimestampFactory = Callable[[], int]
_X_CREATE_POST_URL = "https://api.x.com/2/tweets"
_INSTAGRAM_GRAPH_BASE = "https://graph.instagram.com"
_MAX_RESPONSE_BYTES = 1024 * 1024
_MAX_CONTENT_BYTES = 25_000
_MAX_MEDIA_URL_BYTES = 4096


class SocialPublicationError(RuntimeError):
    pass


class SocialPublicationUnavailableError(SocialPublicationError):
    pass


class SocialPublicationBlockedError(SocialPublicationError):
    def __init__(self, status: str) -> None:
        super().__init__("social publication is blocked by durable state")
        self.status = status


class SocialPublicationProviderRejectedError(SocialPublicationError):
    pass


class SocialPublicationUnknownError(SocialPublicationError):
    pass


@dataclass(frozen=True)
class SocialPublicationCommand:
    tenant_id: str
    channel_id: str
    account_id: str
    run_id: str
    artifact_id: str
    artifact_hash: str
    content: str
    media_url: Optional[str]
    media_hash: Optional[str]
    greenlight_id: str
    greenlight_fencing_token: int
    budget_cents: int
    idempotency_key: str


@dataclass(frozen=True)
class SocialPublicationResult:
    intent_id: str
    channel_id: str
    account_id: str
    run_id: str
    artifact_id: str
    artifact_hash: str
    greenlight_id: str
    greenlight_fencing_token: int
    status: str
    execution_fencing_token: int
    provider_container_id: Optional[str]
    provider_post_id: Optional[str]
    receipt: Mapping[str, object]
    replayed: bool

    @classmethod
    def from_intent(
        cls, intent: SocialPublicationIntent, *, replayed: bool
    ) -> "SocialPublicationResult":
        return cls(
            intent_id=intent.intent_id,
            channel_id=intent.channel_id,
            account_id=intent.account_id,
            run_id=intent.run_id,
            artifact_id=intent.artifact_id,
            artifact_hash=intent.artifact_hash,
            greenlight_id=intent.greenlight_id,
            greenlight_fencing_token=intent.greenlight_fencing_token,
            status=intent.status,
            execution_fencing_token=intent.execution_fencing_token,
            provider_container_id=intent.provider_container_id,
            provider_post_id=intent.provider_post_id,
            receipt=dict(intent.receipt),
            replayed=replayed,
        )

    def public_dict(self) -> dict[str, object]:
        return {
            "intent_id": self.intent_id,
            "channel_id": self.channel_id,
            "account_id": self.account_id,
            "run_id": self.run_id,
            "artifact_id": self.artifact_id,
            "artifact_hash": self.artifact_hash,
            "greenlight_id": self.greenlight_id,
            "greenlight_fencing_token": self.greenlight_fencing_token,
            "status": self.status,
            "execution_fencing_token": self.execution_fencing_token,
            "provider_container_id": self.provider_container_id,
            "provider_post_id": self.provider_post_id,
            "receipt": dict(self.receipt),
            "replayed": self.replayed,
        }


class SocialPublicationAuthority:
    def __init__(
        self,
        *,
        store: object,
        connection_store: object,
        cipher: SocialTokenCipher,
        x_consumer_key: str,
        x_consumer_secret: str,
        enabled: bool = False,
        transport: Optional[httpx.BaseTransport] = None,
        clock: Clock = utc_now,
        nonce_factory: TokenFactory = lambda: secrets.token_urlsafe(18),
        timestamp_factory: TimestampFactory = lambda: int(time.time()),
        timeout_seconds: float = 20.0,
    ) -> None:
        if timeout_seconds < 1 or timeout_seconds > 120:
            raise ValueError("publication timeout must be between 1 and 120 seconds")
        self._store = store
        self._connection_store = connection_store
        self._cipher = cipher
        self._x_consumer_key = x_consumer_key.strip()
        self._x_consumer_secret = x_consumer_secret.strip()
        self._enabled = enabled
        self._clock = clock
        self._nonce_factory = nonce_factory
        self._timestamp_factory = timestamp_factory
        self._client = httpx.Client(
            transport=transport,
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=False,
            trust_env=False,
            headers={"User-Agent": "ai-native-content-agency/0.7"},
        )

    @property
    def enabled(self) -> bool:
        return self._enabled

    def close(self) -> None:
        self._client.close()

    def execute(self, command: SocialPublicationCommand) -> SocialPublicationResult:
        if not self._enabled:
            raise SocialPublicationUnavailableError(
                "social publication authority is disabled"
            )
        validated = _validate_command(command)
        connection = self._connection_store.get_connection(
            validated.tenant_id, validated.channel_id
        )
        if connection is None or connection.account_id != validated.account_id:
            raise SocialPublicationUnavailableError(
                "authorized social account is not connected"
            )
        if validated.channel_id == "x" and (
            not self._x_consumer_key or not self._x_consumer_secret
        ):
            raise SocialPublicationUnavailableError(
                "X application credentials are unavailable"
            )
        intent = _build_intent(validated, clock=self._clock)
        try:
            reservation: SocialPublicationReservation = self._store.reserve(intent)
        except SocialPublicationConflictError:
            raise
        if not reservation.executable:
            if reservation.replayed:
                return SocialPublicationResult.from_intent(
                    reservation.intent, replayed=True
                )
            raise SocialPublicationBlockedError(reservation.intent.status)

        try:
            tokens = self._cipher.decrypt(
                connection.encrypted_tokens,
                associated_data=_connection_aad(
                    validated.tenant_id, validated.channel_id
                ),
            )
        except Exception as error:
            self._mark_failed(reservation.intent, "credential_invalid")
            raise SocialPublicationUnavailableError(
                "connected social credential is invalid"
            ) from error
        try:
            if validated.channel_id == "x":
                completed = self._publish_x(validated, reservation.intent, tokens)
            else:
                completed = self._publish_instagram(
                    validated, reservation.intent, tokens
                )
        except SocialPublicationProviderRejectedError:
            self._mark_failed(reservation.intent, "provider_rejected")
            raise
        except SocialPublicationUnknownError:
            self._mark_unknown(reservation.intent, "provider_outcome_unknown")
            raise
        except httpx.HTTPError as error:
            self._mark_unknown(reservation.intent, "provider_outcome_unknown")
            raise SocialPublicationUnknownError(
                "social publication outcome is unknown"
            ) from error
        return SocialPublicationResult.from_intent(completed, replayed=False)

    def _publish_x(
        self,
        command: SocialPublicationCommand,
        intent: SocialPublicationIntent,
        tokens: Mapping[str, object],
    ) -> SocialPublicationIntent:
        access_token = _required_secret(tokens, "access_token")
        access_secret = _required_secret(tokens, "access_token_secret")
        oauth = {
            "oauth_consumer_key": self._x_consumer_key,
            "oauth_nonce": self._nonce_factory(),
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": str(self._timestamp_factory()),
            "oauth_token": access_token,
            "oauth_version": "1.0",
        }
        oauth["oauth_signature"] = _oauth1_signature(
            "POST",
            _X_CREATE_POST_URL,
            oauth,
            consumer_secret=self._x_consumer_secret,
            token_secret=access_secret,
        )
        authorization = "OAuth " + ", ".join(
            '{}="{}"'.format(_percent(name), _percent(value))
            for name, value in sorted(oauth.items())
        )
        response = self._request(
            "POST",
            _X_CREATE_POST_URL,
            headers={"Authorization": authorization},
            json={"text": command.content},
        )
        payload = _json_object(response)
        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise SocialPublicationUnknownError(
                "social publication outcome is unknown"
            )
        provider_post_id = _required_identifier(data, "id")
        receipt = _receipt(
            provider="x",
            provider_post_id=provider_post_id,
            response=response,
            intent=intent,
        )
        try:
            return self._store.complete(
                intent.tenant_id,
                intent.intent_id,
                intent.execution_fencing_token,
                provider_post_id,
                receipt,
            )
        except Exception as error:
            raise SocialPublicationUnknownError(
                "social publication outcome is unknown"
            ) from error

    def _publish_instagram(
        self,
        command: SocialPublicationCommand,
        intent: SocialPublicationIntent,
        tokens: Mapping[str, object],
    ) -> SocialPublicationIntent:
        access_token = _required_secret(tokens, "access_token")
        if command.media_url is None or command.media_hash is None:
            raise SocialPublicationUnavailableError(
                "Instagram publication requires governed media"
            )
        base = "{}/{}".format(_INSTAGRAM_GRAPH_BASE, quote(command.account_id, safe=""))
        container_response = self._request(
            "POST",
            base + "/media",
            headers={"Authorization": "Bearer {}".format(access_token)},
            data={"image_url": command.media_url, "caption": command.content},
        )
        container_payload = _json_object(container_response)
        container_id = _required_identifier(container_payload, "id")
        try:
            pending = self._store.record_container(
                intent.tenant_id,
                intent.intent_id,
                intent.execution_fencing_token,
                container_id,
            )
        except Exception as error:
            raise SocialPublicationUnknownError(
                "social publication outcome is unknown"
            ) from error
        publish_response = self._request(
            "POST",
            base + "/media_publish",
            headers={"Authorization": "Bearer {}".format(access_token)},
            data={"creation_id": container_id},
        )
        publish_payload = _json_object(publish_response)
        provider_post_id = _required_identifier(publish_payload, "id")
        receipt = _receipt(
            provider="instagram",
            provider_post_id=provider_post_id,
            provider_container_id=container_id,
            response=publish_response,
            intent=pending,
        )
        try:
            return self._store.complete(
                pending.tenant_id,
                pending.intent_id,
                pending.execution_fencing_token,
                provider_post_id,
                receipt,
            )
        except Exception as error:
            raise SocialPublicationUnknownError(
                "social publication outcome is unknown"
            ) from error

    def _request(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        try:
            with self._client.stream(method, url, **kwargs) as upstream:
                chunks: list[bytes] = []
                total = 0
                for chunk in upstream.iter_bytes():
                    total += len(chunk)
                    if total > _MAX_RESPONSE_BYTES:
                        raise SocialPublicationUnknownError(
                            "social publication outcome is unknown"
                        )
                    chunks.append(chunk)
                response = httpx.Response(
                    status_code=upstream.status_code,
                    headers=upstream.headers,
                    content=b"".join(chunks),
                    request=upstream.request,
                )
        except SocialPublicationUnknownError:
            raise
        except httpx.HTTPError as error:
            raise SocialPublicationUnknownError(
                "social publication outcome is unknown"
            ) from error
        if 400 <= response.status_code < 500:
            raise SocialPublicationProviderRejectedError(
                "social provider rejected publication"
            )
        if response.status_code < 200 or response.status_code >= 300:
            raise SocialPublicationUnknownError(
                "social publication outcome is unknown"
            )
        return response

    def _mark_unknown(
        self, intent: SocialPublicationIntent, reason: str
    ) -> None:
        try:
            self._store.mark_unknown(
                intent.tenant_id,
                intent.intent_id,
                intent.execution_fencing_token,
                reason,
            )
        except SocialPublicationStateError:
            pass

    def _mark_failed(self, intent: SocialPublicationIntent, reason: str) -> None:
        try:
            self._store.mark_failed(
                intent.tenant_id,
                intent.intent_id,
                intent.execution_fencing_token,
                reason,
            )
        except SocialPublicationStateError:
            pass


def _validate_command(command: SocialPublicationCommand) -> SocialPublicationCommand:
    content = command.content.strip()
    encoded = content.encode("utf-8")
    if not content or len(encoded) > _MAX_CONTENT_BYTES:
        raise ValueError("publication content is invalid")
    if command.channel_id not in {"x", "instagram"}:
        raise ValueError("publication channel is invalid")
    for value in (
        command.tenant_id,
        command.account_id,
        command.run_id,
        command.artifact_id,
        command.greenlight_id,
    ):
        if not value or len(value) > 256:
            raise ValueError("publication identity is invalid")
    if not _is_sha256(command.artifact_hash):
        raise ValueError("artifact hash is invalid")
    if command.greenlight_fencing_token < 0 or command.budget_cents < 0:
        raise ValueError("publication authority is invalid")
    if len(command.idempotency_key) < 8 or len(command.idempotency_key) > 200:
        raise ValueError("publication idempotency key is invalid")
    media_url = command.media_url
    if media_url is not None:
        if len(media_url.encode("utf-8")) > _MAX_MEDIA_URL_BYTES:
            raise ValueError("publication media URL is invalid")
        parsed = urlsplit(media_url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            raise ValueError("publication media URL is invalid")
    if command.media_hash is not None and not _is_sha256(command.media_hash):
        raise ValueError("publication media hash is invalid")
    if command.channel_id == "instagram" and (
        media_url is None or command.media_hash is None
    ):
        raise ValueError("Instagram publication requires media URL and hash")
    return SocialPublicationCommand(
        tenant_id=command.tenant_id,
        channel_id=command.channel_id,
        account_id=command.account_id,
        run_id=command.run_id,
        artifact_id=command.artifact_id,
        artifact_hash=command.artifact_hash,
        content=content,
        media_url=media_url,
        media_hash=command.media_hash,
        greenlight_id=command.greenlight_id,
        greenlight_fencing_token=command.greenlight_fencing_token,
        budget_cents=command.budget_cents,
        idempotency_key=command.idempotency_key,
    )


def _build_intent(
    command: SocialPublicationCommand, *, clock: Clock
) -> SocialPublicationIntent:
    content_hash = hashlib.sha256(command.content.encode("utf-8")).hexdigest()
    media_url_hash = (
        None
        if command.media_url is None
        else hashlib.sha256(command.media_url.encode("utf-8")).hexdigest()
    )
    binding = {
        "tenant_id": command.tenant_id,
        "channel_id": command.channel_id,
        "account_id": command.account_id,
        "run_id": command.run_id,
        "artifact_id": command.artifact_id,
        "artifact_hash": command.artifact_hash,
        "content_hash": content_hash,
        "media_url_hash": media_url_hash,
        "media_hash": command.media_hash,
        "greenlight_id": command.greenlight_id,
        "greenlight_fencing_token": command.greenlight_fencing_token,
        "budget_cents": command.budget_cents,
    }
    binding_digest = hashlib.sha256(
        canonical_json(binding).encode("utf-8")
    ).hexdigest()
    idempotency_digest = hashlib.sha256(
        command.idempotency_key.encode("utf-8")
    ).hexdigest()
    now = clock()
    return SocialPublicationIntent(
        intent_id=stable_id(
            "social-publication-intent",
            command.tenant_id,
            idempotency_digest,
            length=48,
        ),
        tenant_id=command.tenant_id,
        channel_id=command.channel_id,
        account_id=command.account_id,
        run_id=command.run_id,
        artifact_id=command.artifact_id,
        artifact_hash=command.artifact_hash,
        content_hash=content_hash,
        media_url_hash=media_url_hash,
        media_hash=command.media_hash,
        greenlight_id=command.greenlight_id,
        greenlight_fencing_token=command.greenlight_fencing_token,
        budget_cents=command.budget_cents,
        idempotency_digest=idempotency_digest,
        binding_digest=binding_digest,
        status="pending",
        execution_fencing_token=1,
        provider_container_id=None,
        provider_post_id=None,
        receipt={},
        failure_reason="",
        created_at=now,
        updated_at=now,
        completed_at=None,
        revoked_at=None,
    )


def _receipt(
    *,
    provider: str,
    provider_post_id: str,
    response: httpx.Response,
    intent: SocialPublicationIntent,
    provider_container_id: Optional[str] = None,
) -> dict[str, object]:
    request_id = (
        response.headers.get("x-request-id")
        or response.headers.get("x-fb-trace-id")
        or ""
    )
    return {
        "provider": provider,
        "provider_post_id": provider_post_id,
        "provider_container_id": provider_container_id,
        "provider_request_id": request_id[:256],
        "artifact_hash": intent.artifact_hash,
        "binding_digest": intent.binding_digest,
        "response_status": response.status_code,
    }


def _required_secret(payload: Mapping[str, object], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value or len(value) > 8192:
        raise SocialPublicationUnavailableError(
            "connected social credential is invalid"
        )
    return value


def _json_object(response: httpx.Response) -> Mapping[str, object]:
    try:
        payload = response.json()
    except (json.JSONDecodeError, ValueError) as error:
        raise SocialPublicationUnknownError(
            "social publication outcome is unknown"
        ) from error
    if not isinstance(payload, Mapping):
        raise SocialPublicationUnknownError(
            "social publication outcome is unknown"
        )
    return payload


def _required_identifier(payload: Mapping[str, object], name: str) -> str:
    value = payload.get(name)
    if isinstance(value, int):
        value = str(value)
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 256
        or any(ord(character) < 32 for character in value)
    ):
        raise SocialPublicationUnknownError(
            "social publication outcome is unknown"
        )
    return value


def _oauth1_signature(
    method: str,
    url: str,
    parameters: Mapping[str, str],
    *,
    consumer_secret: str,
    token_secret: str,
) -> str:
    parsed = urlsplit(url)
    base_url = urlunsplit(
        (parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, "", "")
    )
    query = parse_qs(parsed.query, keep_blank_values=True)
    pairs = [(str(name), str(value)) for name, value in parameters.items()]
    pairs.extend((name, value) for name, values in query.items() for value in values)
    normalized = "&".join(
        "{}={}".format(_percent(name), _percent(value))
        for name, value in sorted(
            pairs, key=lambda item: (_percent(item[0]), _percent(item[1]))
        )
    )
    base = "&".join(
        (_percent(method.upper()), _percent(base_url), _percent(normalized))
    )
    key = "{}&{}".format(_percent(consumer_secret), _percent(token_secret))
    digest = hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("ascii")


def _percent(value: object) -> str:
    return quote(str(value), safe="~-._")


def _connection_aad(tenant_id: str, channel_id: str) -> str:
    return "{}:{}:connection".format(tenant_id, channel_id)


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)
