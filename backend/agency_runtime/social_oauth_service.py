from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Mapping, Optional, Tuple
from urllib.parse import parse_qs, quote, urlencode, urlsplit, urlunsplit

import httpx

from .memory import utc_now
from .social_channels import SocialChannelRegistry
from .social_oauth import SocialTokenCipher
from .social_oauth_store import (
    SocialConnectionRecord,
    SocialOAuthStateRecord,
    SocialOAuthStateUnavailableError,
)
from .utils import stable_id


Clock = Callable[[], str]
TokenFactory = Callable[[], str]
TimestampFactory = Callable[[], int]
_MAX_RESPONSE_BYTES = 1024 * 1024
_STATE_TTL_SECONDS = 600
_X_REQUEST_TOKEN_URL = "https://api.x.com/oauth/request_token"
_X_AUTHORIZE_URL = "https://api.x.com/oauth/authorize"
_X_ACCESS_TOKEN_URL = "https://api.x.com/oauth/access_token"
_INSTAGRAM_AUTHORIZE_URL = "https://www.instagram.com/oauth/authorize"
_INSTAGRAM_ACCESS_TOKEN_URL = "https://api.instagram.com/oauth/access_token"
_INSTAGRAM_PROFILE_URL = "https://graph.instagram.com/me"
_PROFESSIONAL_ACCOUNT_TYPES = frozenset({"BUSINESS", "CREATOR", "MEDIA_CREATOR"})


class SocialOAuthError(RuntimeError):
    pass


class SocialOAuthUnavailableError(SocialOAuthError):
    pass


class SocialOAuthProviderError(SocialOAuthError):
    def __init__(
        self,
        message: str,
        *,
        phase: str = "provider",
        reason: str = "invalid_response",
        exception_type: str = "",
    ) -> None:
        super().__init__(message)
        self.phase = phase
        self.reason = reason
        self.exception_type = exception_type


class SocialOAuthCallbackError(SocialOAuthError):
    pass


@dataclass(frozen=True)
class SocialOAuthStartResult:
    channel_id: str
    authorization_url: str
    expires_at: str


@dataclass(frozen=True)
class SocialConnectionResult:
    channel_id: str
    account_id: str
    account_username: str
    scopes: Tuple[str, ...]
    token_expires_at: Optional[str]
    connected_at: str

    @classmethod
    def from_record(cls, record: SocialConnectionRecord) -> "SocialConnectionResult":
        return cls(
            channel_id=record.channel_id,
            account_id=record.account_id,
            account_username=record.account_username,
            scopes=record.scopes,
            token_expires_at=record.token_expires_at,
            connected_at=record.connected_at,
        )

    def public_dict(self) -> dict[str, object]:
        return {
            "channel_id": self.channel_id,
            "account_id": self.account_id,
            "account_username": self.account_username,
            "scopes": list(self.scopes),
            "token_expires_at": self.token_expires_at,
            "connected_at": self.connected_at,
        }


class SocialOAuthService:
    def __init__(
        self,
        *,
        registry: SocialChannelRegistry,
        store: object,
        cipher: SocialTokenCipher,
        transport: Optional[httpx.BaseTransport] = None,
        clock: Clock = utc_now,
        token_factory: TokenFactory = lambda: secrets.token_urlsafe(32),
        oauth_nonce_factory: TokenFactory = lambda: secrets.token_urlsafe(18),
        timestamp_factory: TimestampFactory = lambda: int(time.time()),
        timeout_seconds: float = 20.0,
    ) -> None:
        if timeout_seconds < 1 or timeout_seconds > 120:
            raise ValueError("social OAuth timeout must be between 1 and 120 seconds")
        self._registry = registry
        self._store = store
        self._cipher = cipher
        self._clock = clock
        self._token_factory = token_factory
        self._oauth_nonce_factory = oauth_nonce_factory
        self._timestamp_factory = timestamp_factory
        self._client = httpx.Client(
            transport=transport,
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=False,
            trust_env=False,
            headers={
                "User-Agent": "ai-native-content-agency/0.7",
                "Accept-Encoding": "identity",
            },
        )

    def close(self) -> None:
        self._client.close()

    def start(
        self, *, tenant_id: str, session_id: str, channel_id: str
    ) -> SocialOAuthStartResult:
        contract = self._registry.get(channel_id)
        if not contract.configured:
            raise SocialOAuthUnavailableError(
                "social channel is not configured for authentication"
            )
        if not session_id:
            raise SocialOAuthUnavailableError("browser session is required")
        if channel_id == "x":
            return self._start_x(tenant_id=tenant_id, session_id=session_id)
        if channel_id == "instagram":
            return self._start_instagram(tenant_id=tenant_id, session_id=session_id)
        raise SocialOAuthUnavailableError("social channel is not supported")

    def complete_x(
        self,
        *,
        tenant_id: str,
        session_id: str,
        oauth_token: str,
        oauth_verifier: str,
    ) -> SocialConnectionResult:
        if not oauth_token or not oauth_verifier:
            raise SocialOAuthCallbackError("X OAuth callback is incomplete")
        token_digest = _sha256(oauth_token)
        try:
            state = self._store.consume_state(
                tenant_id=tenant_id,
                session_id=session_id,
                channel_id="x",
                state_digest=token_digest,
                provider_token_digest=token_digest,
            )
        except SocialOAuthStateUnavailableError as error:
            raise SocialOAuthCallbackError("X OAuth callback is invalid or expired") from error
        payload = self._cipher.decrypt(
            state.encrypted_payload,
            associated_data=_state_aad(state.tenant_id, state.channel_id, state.state_id),
        )
        request_secret = str(payload.get("request_token_secret", ""))
        if not request_secret:
            raise SocialOAuthCallbackError("X OAuth state is incomplete")
        config = self._registry.private_config("x")
        consumer_key, consumer_secret = config.credentials
        response = self._oauth1_post(
            _X_ACCESS_TOKEN_URL,
            phase="x_access_token",
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            token=oauth_token,
            token_secret=request_secret,
            extra_oauth={"oauth_verifier": oauth_verifier},
        )
        values = _form_response(response)
        access_token = _one(values, "oauth_token")
        access_secret = _one(values, "oauth_token_secret")
        account_id = _one(values, "user_id")
        username = _one(values, "screen_name")
        now = self._clock()
        encrypted = self._cipher.encrypt(
            {
                "access_token": access_token,
                "access_token_secret": access_secret,
            },
            associated_data=_connection_aad(tenant_id, "x"),
        )
        record = SocialConnectionRecord(
            tenant_id=tenant_id,
            channel_id="x",
            account_id=account_id,
            account_username=username,
            encrypted_tokens=encrypted,
            scopes=self._registry.get("x").scopes,
            token_expires_at=None,
            connected_at=now,
            updated_at=now,
        )
        self._store.upsert_connection(record)
        return SocialConnectionResult.from_record(record)

    def complete_instagram(
        self,
        *,
        tenant_id: str,
        session_id: str,
        state_value: str,
        code: str,
    ) -> SocialConnectionResult:
        if not state_value or not code:
            raise SocialOAuthCallbackError("Instagram OAuth callback is incomplete")
        try:
            state = self._store.consume_state(
                tenant_id=tenant_id,
                session_id=session_id,
                channel_id="instagram",
                state_digest=_sha256(state_value),
                provider_token_digest=None,
            )
        except SocialOAuthStateUnavailableError as error:
            raise SocialOAuthCallbackError(
                "Instagram OAuth callback is invalid or expired"
            ) from error
        payload = self._cipher.decrypt(
            state.encrypted_payload,
            associated_data=_state_aad(state.tenant_id, state.channel_id, state.state_id),
        )
        if not hmac.compare_digest(
            str(payload.get("state_value", "")), state_value
        ):
            raise SocialOAuthCallbackError("Instagram OAuth state is invalid")
        config = self._registry.private_config("instagram")
        app_id, app_secret = config.credentials
        response = self._bounded_request(
            "POST",
            _INSTAGRAM_ACCESS_TOKEN_URL,
            phase="instagram_token_exchange",
            data={
                "client_id": app_id,
                "client_secret": app_secret,
                "grant_type": "authorization_code",
                "redirect_uri": config.redirect_uri,
                "code": code,
            },
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "identity",
                "Connection": "close",
            },
            timeout=httpx.Timeout(60.0, connect=10.0),
        )
        token_payload = _json_object(response)
        access_token = _required_text(token_payload, "access_token")
        token_user_id = _optional_text(token_payload, "user_id")
        profile_response = self._bounded_request(
            "GET",
            _INSTAGRAM_PROFILE_URL,
            phase="instagram_profile",
            params={"fields": "id,username,account_type,user_id"},
            headers={"Authorization": "Bearer {}".format(access_token)},
        )
        profile = _json_object(profile_response)
        account_id = _required_text(profile, "id") or token_user_id
        username = _required_text(profile, "username")
        account_type = _required_text(profile, "account_type").upper()
        if account_type not in _PROFESSIONAL_ACCOUNT_TYPES:
            raise SocialOAuthCallbackError(
                "Instagram account must be Professional (Business or Creator)"
            )
        expires_in = token_payload.get("expires_in")
        expires_at = None
        if expires_in is not None:
            if not isinstance(expires_in, int) or expires_in < 60 or expires_in > 10_000_000:
                raise SocialOAuthProviderError("Instagram token response is invalid")
            expires_at = (
                _as_datetime(self._clock()) + timedelta(seconds=expires_in)
            ).isoformat()
        now = self._clock()
        encrypted = self._cipher.encrypt(
            {"access_token": access_token},
            associated_data=_connection_aad(tenant_id, "instagram"),
        )
        record = SocialConnectionRecord(
            tenant_id=tenant_id,
            channel_id="instagram",
            account_id=account_id,
            account_username=username,
            encrypted_tokens=encrypted,
            scopes=self._registry.get("instagram").scopes,
            token_expires_at=expires_at,
            connected_at=now,
            updated_at=now,
        )
        self._store.upsert_connection(record)
        return SocialConnectionResult.from_record(record)

    def connection(
        self, tenant_id: str, channel_id: str
    ) -> Optional[SocialConnectionResult]:
        record = self._store.get_connection(tenant_id, channel_id)
        return None if record is None else SocialConnectionResult.from_record(record)

    def list_connections(self, tenant_id: str) -> Tuple[SocialConnectionResult, ...]:
        return tuple(
            SocialConnectionResult.from_record(record)
            for record in self._store.list_connections(tenant_id)
        )

    def disconnect(self, tenant_id: str, channel_id: str) -> bool:
        self._registry.get(channel_id)
        return self._store.delete_connection(tenant_id, channel_id)

    def _start_x(self, *, tenant_id: str, session_id: str) -> SocialOAuthStartResult:
        config = self._registry.private_config("x")
        consumer_key, consumer_secret = config.credentials
        response = self._oauth1_post(
            _X_REQUEST_TOKEN_URL,
            phase="x_request_token",
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            token=None,
            token_secret="",
            extra_oauth={"oauth_callback": config.redirect_uri},
        )
        values = _form_response(response)
        if _one(values, "oauth_callback_confirmed") != "true":
            raise SocialOAuthProviderError("X OAuth callback was not confirmed")
        request_token = _one(values, "oauth_token")
        request_secret = _one(values, "oauth_token_secret")
        now = _as_datetime(self._clock())
        expires_at = (now + timedelta(seconds=_STATE_TTL_SECONDS)).isoformat()
        state_id = stable_id("social-oauth-state", tenant_id, "x", request_token, length=48)
        encrypted = self._cipher.encrypt(
            {"request_token_secret": request_secret},
            associated_data=_state_aad(tenant_id, "x", state_id),
        )
        digest = _sha256(request_token)
        self._store.create_state(
            SocialOAuthStateRecord(
                state_id=state_id,
                tenant_id=tenant_id,
                session_id=session_id,
                channel_id="x",
                state_digest=digest,
                provider_token_digest=digest,
                encrypted_payload=encrypted,
                created_at=now.isoformat(),
                expires_at=expires_at,
                consumed_at=None,
            )
        )
        return SocialOAuthStartResult(
            channel_id="x",
            authorization_url="{}?{}".format(
                _X_AUTHORIZE_URL, urlencode({"oauth_token": request_token})
            ),
            expires_at=expires_at,
        )

    def _start_instagram(
        self, *, tenant_id: str, session_id: str
    ) -> SocialOAuthStartResult:
        config = self._registry.private_config("instagram")
        app_id, _ = config.credentials
        state_value = self._token_factory()
        if len(state_value) < 32 or len(state_value) > 256:
            raise SocialOAuthUnavailableError("OAuth state generator returned an invalid value")
        now = _as_datetime(self._clock())
        expires_at = (now + timedelta(seconds=_STATE_TTL_SECONDS)).isoformat()
        state_id = stable_id(
            "social-oauth-state", tenant_id, "instagram", state_value, length=48
        )
        encrypted = self._cipher.encrypt(
            {"state_value": state_value},
            associated_data=_state_aad(tenant_id, "instagram", state_id),
        )
        self._store.create_state(
            SocialOAuthStateRecord(
                state_id=state_id,
                tenant_id=tenant_id,
                session_id=session_id,
                channel_id="instagram",
                state_digest=_sha256(state_value),
                provider_token_digest=None,
                encrypted_payload=encrypted,
                created_at=now.isoformat(),
                expires_at=expires_at,
                consumed_at=None,
            )
        )
        query = urlencode(
            {
                "force_reauth": "true",
                "client_id": app_id,
                "redirect_uri": config.redirect_uri,
                "scope": ",".join(self._registry.get("instagram").scopes),
                "response_type": "code",
                "state": state_value,
            }
        )
        return SocialOAuthStartResult(
            channel_id="instagram",
            authorization_url="{}?{}".format(_INSTAGRAM_AUTHORIZE_URL, query),
            expires_at=expires_at,
        )

    def _oauth1_post(
        self,
        url: str,
        *,
        phase: str,
        consumer_key: str,
        consumer_secret: str,
        token: Optional[str],
        token_secret: str,
        extra_oauth: Mapping[str, str],
    ) -> httpx.Response:
        oauth = {
            "oauth_consumer_key": consumer_key,
            "oauth_nonce": self._oauth_nonce_factory(),
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": str(self._timestamp_factory()),
            "oauth_version": "1.0",
            **extra_oauth,
        }
        if token:
            oauth["oauth_token"] = token
        oauth["oauth_signature"] = _oauth1_signature(
            "POST",
            url,
            oauth,
            consumer_secret=consumer_secret,
            token_secret=token_secret,
        )
        authorization = "OAuth " + ", ".join(
            '{}="{}"'.format(_percent(name), _percent(value))
            for name, value in sorted(oauth.items())
        )
        return self._bounded_request(
            "POST", url, phase=phase, headers={"Authorization": authorization}
        )

    def _bounded_request(
        self, method: str, url: str, *, phase: str, **kwargs: object
    ) -> httpx.Response:
        try:
            with self._client.stream(method, url, **kwargs) as upstream:
                chunks = []
                total = 0
                if upstream.is_stream_consumed:
                    materialized = upstream.content
                    total = len(materialized)
                    chunks.append(materialized)
                else:
                    for chunk in upstream.iter_raw():
                        total += len(chunk)
                        if total > _MAX_RESPONSE_BYTES:
                            raise SocialOAuthProviderError(
                                "social provider response is too large",
                                phase=phase,
                                reason="invalid_response",
                            )
                        chunks.append(chunk)
                if total > _MAX_RESPONSE_BYTES:
                    raise SocialOAuthProviderError(
                        "social provider response is too large",
                        phase=phase,
                        reason="invalid_response",
                    )
                safe_headers = {
                    name: value
                    for name, value in upstream.headers.items()
                    if name.lower()
                    not in {"content-encoding", "content-length", "transfer-encoding"}
                }
                response = httpx.Response(
                    status_code=upstream.status_code,
                    headers=safe_headers,
                    content=b"".join(chunks),
                    request=upstream.request,
                )
        except SocialOAuthProviderError:
            raise
        except httpx.DecodingError as error:
            raise SocialOAuthProviderError(
                "social provider response decoding failed",
                phase=phase,
                reason="invalid_response",
                exception_type=type(error).__name__,
            ) from error
        except httpx.HTTPError as error:
            raise SocialOAuthProviderError(
                "social provider request failed",
                phase=phase,
                reason="unreachable",
                exception_type=type(error).__name__,
            ) from error
        if response.status_code < 200 or response.status_code >= 300:
            raise SocialOAuthProviderError(
                "social provider rejected the request",
                phase=phase,
                reason="rejected",
            )
        return response


def _oauth1_signature(
    method: str,
    url: str,
    parameters: Mapping[str, str],
    *,
    consumer_secret: str,
    token_secret: str,
) -> str:
    parsed = urlsplit(url)
    base_url = urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, "", ""))
    query = parse_qs(parsed.query, keep_blank_values=True)
    pairs = [(str(name), str(value)) for name, value in parameters.items()]
    pairs.extend((name, value) for name, values in query.items() for value in values)
    normalized = "&".join(
        "{}={}".format(_percent(name), _percent(value))
        for name, value in sorted(pairs, key=lambda item: (_percent(item[0]), _percent(item[1])))
    )
    base = "&".join((_percent(method.upper()), _percent(base_url), _percent(normalized)))
    signing_key = "{}&{}".format(_percent(consumer_secret), _percent(token_secret))
    digest = hmac.new(signing_key.encode(), base.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("ascii")


def _percent(value: object) -> str:
    return quote(str(value), safe="~-._")


def _form_response(response: httpx.Response) -> Mapping[str, list[str]]:
    try:
        parsed = parse_qs(response.text, keep_blank_values=True, strict_parsing=True)
    except ValueError as error:
        raise SocialOAuthProviderError("social provider response is invalid") from error
    if not parsed:
        raise SocialOAuthProviderError("social provider response is invalid")
    return parsed


def _one(values: Mapping[str, list[str]], name: str) -> str:
    items = values.get(name, [])
    if len(items) != 1 or not items[0] or len(items[0]) > 8192:
        raise SocialOAuthProviderError("social provider response is invalid")
    return items[0]


def _json_object(response: httpx.Response) -> Mapping[str, object]:
    try:
        parsed = response.json()
    except (json.JSONDecodeError, ValueError) as error:
        raise SocialOAuthProviderError("social provider response is invalid") from error
    if not isinstance(parsed, Mapping):
        raise SocialOAuthProviderError("social provider response is invalid")
    return parsed


def _required_text(payload: Mapping[str, object], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip() or len(value) > 8192:
        raise SocialOAuthProviderError("social provider response is invalid")
    return value.strip()


def _optional_text(payload: Mapping[str, object], name: str) -> str:
    value = payload.get(name)
    if value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    if not isinstance(value, str) or len(value) > 8192:
        raise SocialOAuthProviderError("social provider response is invalid")
    return value.strip()


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _state_aad(tenant_id: str, channel_id: str, state_id: str) -> str:
    return "{}:{}:state:{}".format(tenant_id, channel_id, state_id)


def _connection_aad(tenant_id: str, channel_id: str) -> str:
    return "{}:{}:connection".format(tenant_id, channel_id)


def _as_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


_BOOTSTRAP_FIELDS = {
    "x": (
        "AGENCY_X_USER_ACCESS_TOKEN",
        "AGENCY_X_USER_ACCESS_TOKEN_SECRET",
        "AGENCY_X_ACCOUNT_ID",
        "AGENCY_X_ACCOUNT_USERNAME",
    ),
    "instagram": (
        "AGENCY_INSTAGRAM_ACCESS_TOKEN",
        "AGENCY_INSTAGRAM_ACCOUNT_ID",
        "AGENCY_INSTAGRAM_ACCOUNT_USERNAME",
    ),
}


def social_bootstrap_requested(environment: Mapping[str, str]) -> bool:
    names = {"AGENCY_SOCIAL_BOOTSTRAP_TENANT_ID"}
    for fields in _BOOTSTRAP_FIELDS.values():
        names.update(fields)
    names.add("AGENCY_INSTAGRAM_TOKEN_EXPIRES_AT")
    return any(str(environment.get(name, "")).strip() for name in names)


def bootstrap_social_connections(
    *,
    environment: Mapping[str, str],
    registry: SocialChannelRegistry,
    store: object,
    cipher: SocialTokenCipher,
    clock: Clock = utc_now,
) -> Tuple[SocialConnectionRecord, ...]:
    tenant_id = str(environment.get("AGENCY_SOCIAL_BOOTSTRAP_TENANT_ID", "")).strip()
    requested_channels = []
    for channel_id, fields in _BOOTSTRAP_FIELDS.items():
        values = tuple(str(environment.get(name, "")).strip() for name in fields)
        if any(values):
            requested_channels.append((channel_id, fields, values))
    if not requested_channels:
        if tenant_id:
            raise SocialOAuthUnavailableError(
                "social bootstrap tenant is configured without channel tokens"
            )
        return ()
    if not tenant_id:
        raise SocialOAuthUnavailableError(
            "social bootstrap tenant is required when tokens are configured"
        )

    records = []
    now = clock()
    _as_datetime(now)
    for channel_id, fields, values in requested_channels:
        missing = [name for name, value in zip(fields, values) if not value]
        if missing:
            raise SocialOAuthUnavailableError(
                "{} social bootstrap configuration is incomplete".format(channel_id)
            )
        contract = registry.get(channel_id)
        if not contract.configured:
            raise SocialOAuthUnavailableError(
                "{} application credentials and callback must be configured before bootstrap".format(
                    channel_id
                )
            )
        if channel_id == "x":
            access_token, access_secret, account_id, username = values
            token_payload = {
                "access_token": access_token,
                "access_token_secret": access_secret,
            }
            expires_at = None
        else:
            access_token, account_id, username = values
            token_payload = {"access_token": access_token}
            raw_expiry = str(
                environment.get("AGENCY_INSTAGRAM_TOKEN_EXPIRES_AT", "")
            ).strip()
            expires_at = raw_expiry or None
            if expires_at is not None:
                _as_datetime(expires_at)
        encrypted = cipher.encrypt(
            token_payload,
            associated_data=_connection_aad(tenant_id, channel_id),
        )
        record = SocialConnectionRecord(
            tenant_id=tenant_id,
            channel_id=channel_id,
            account_id=account_id,
            account_username=username,
            encrypted_tokens=encrypted,
            scopes=contract.scopes,
            token_expires_at=expires_at,
            connected_at=now,
            updated_at=now,
        )
        store.upsert_connection(record)
        records.append(record)
    return tuple(records)
