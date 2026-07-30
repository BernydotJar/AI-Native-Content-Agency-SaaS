from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from types import MappingProxyType
from typing import Mapping, Optional

from .utils import canonical_json

_KEY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_BASE64URL = re.compile(r"^[A-Za-z0-9_-]+={0,2}$")
_MAX_KEYS = 16
_LEGACY_KEY_ID = "legacy"


class PublicMediaSigningConfigurationError(ValueError):
    """Raised when the public-media signing keyring is unsafe or ambiguous."""


class PublicMediaSigningKeyUnavailableError(RuntimeError):
    """Raised when durable media references a signing key no longer configured."""


class PublicMediaSigningKeyring:
    """Immutable HMAC keyring for durable public publication-media capabilities."""

    def __init__(self, keys: Mapping[str, bytes], active_key_id: str) -> None:
        normalized: dict[str, bytes] = {}
        if not keys or len(keys) > _MAX_KEYS:
            raise PublicMediaSigningConfigurationError(
                "public media signing keyring must contain 1..16 keys"
            )
        for key_id, raw_key in keys.items():
            if not isinstance(key_id, str) or not _KEY_ID.fullmatch(key_id):
                raise PublicMediaSigningConfigurationError(
                    "public media signing key identifier is invalid"
                )
            valid_length = (
                isinstance(raw_key, bytes)
                and (
                    len(raw_key) == 32
                    or (key_id == _LEGACY_KEY_ID and 32 <= len(raw_key) <= 4096)
                )
            )
            if not valid_length:
                raise PublicMediaSigningConfigurationError(
                    "public media signing keys must contain exactly 32 bytes"
                )
            normalized[key_id] = bytes(raw_key)
        if active_key_id not in normalized:
            raise PublicMediaSigningConfigurationError(
                "active public media signing key is absent from the keyring"
            )
        self._keys = MappingProxyType(normalized)
        self.active_key_id = active_key_id

    @classmethod
    def from_environment(
        cls,
        raw_keys_json: Optional[str],
        active_key_id: Optional[str],
        legacy_key: Optional[str],
    ) -> Optional["PublicMediaSigningKeyring"]:
        raw_keys = (raw_keys_json or "").strip()
        active = (active_key_id or "").strip()
        legacy = legacy_key or ""
        if legacy and (raw_keys or active):
            raise PublicMediaSigningConfigurationError(
                "legacy and keyring public media signing configuration are mutually exclusive"
            )
        if legacy:
            encoded = legacy.encode("utf-8")
            if len(encoded) < 32 or len(encoded) > 4096:
                raise PublicMediaSigningConfigurationError(
                    "legacy public media signing key must contain 32..4096 bytes"
                )
            # Preserve the exact historical HMAC input so existing capability URLs and
            # durable token digests remain valid during migration.
            return cls({_LEGACY_KEY_ID: encoded}, _LEGACY_KEY_ID)
        if not raw_keys and not active:
            return None
        if not raw_keys or not active:
            raise PublicMediaSigningConfigurationError(
                "public media signing keyring and active key ID must be configured together"
            )

        def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
            result: dict[str, object] = {}
            for key, value in pairs:
                if key in result:
                    raise PublicMediaSigningConfigurationError(
                        "public media signing keyring contains a duplicate key ID"
                    )
                result[key] = value
            return result

        try:
            parsed = json.loads(raw_keys, object_pairs_hook=unique_object)
        except PublicMediaSigningConfigurationError:
            raise
        except json.JSONDecodeError as error:
            raise PublicMediaSigningConfigurationError(
                "public media signing keyring JSON is invalid"
            ) from error
        if not isinstance(parsed, dict):
            raise PublicMediaSigningConfigurationError(
                "public media signing keyring must be a JSON object"
            )
        decoded: dict[str, bytes] = {}
        for key_id, value in parsed.items():
            if not isinstance(value, str) or not _BASE64URL.fullmatch(value):
                raise PublicMediaSigningConfigurationError(
                    "public media signing key material is not canonical base64url"
                )
            try:
                padded = value + "=" * (-len(value) % 4)
                raw = base64.b64decode(
                    padded.encode("ascii"), altchars=b"-_", validate=True
                )
            except (UnicodeEncodeError, ValueError) as error:
                raise PublicMediaSigningConfigurationError(
                    "public media signing key material is invalid"
                ) from error
            canonical = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
            if value.rstrip("=") != canonical:
                raise PublicMediaSigningConfigurationError(
                    "public media signing key material is not canonical base64url"
                )
            decoded[key_id] = raw
        return cls(decoded, active)

    @property
    def key_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._keys))

    def sign(self, key_id: str, media_id: str, expires_at: str) -> str:
        key = self._keys.get(key_id)
        if key is None:
            raise PublicMediaSigningKeyUnavailableError(
                "required public media signing key is unavailable"
            )
        digest = hmac.new(
            key,
            canonical_json(("publication-media", media_id, expires_at)).encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    def sign_active(self, media_id: str, expires_at: str) -> tuple[str, str]:
        return self.active_key_id, self.sign(self.active_key_id, media_id, expires_at)

    def __repr__(self) -> str:
        return "PublicMediaSigningKeyring(active_key_id={!r}, key_count={})".format(
            self.active_key_id, len(self._keys)
        )
