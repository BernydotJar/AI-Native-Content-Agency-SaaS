from __future__ import annotations

import base64
import binascii
import json
import os
import re
from dataclasses import dataclass
from typing import Mapping, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .utils import canonical_json


_KEY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
_MAX_PLAINTEXT_BYTES = 16 * 1024
_MAX_FIELDS = 16
_MAX_FIELD_NAME = 64
_MAX_FIELD_VALUE = 8192
_NONCE_BYTES = 12


class SocialTokenCipherConfigurationError(ValueError):
    pass


class SocialTokenDecryptionError(ValueError):
    pass


@dataclass(frozen=True)
class EncryptedSocialValue:
    key_id: str
    ciphertext: str


class SocialTokenCipher:
    """Versioned authenticated encryption for tenant-bound social credentials."""

    def __init__(self, keys: Mapping[str, bytes], active_key_id: str) -> None:
        normalized = dict(keys)
        if not normalized or active_key_id not in normalized:
            raise SocialTokenCipherConfigurationError(
                "social token encryption active key is unavailable"
            )
        for key_id, raw_key in normalized.items():
            if not _KEY_ID.fullmatch(key_id) or len(raw_key) != 32:
                raise SocialTokenCipherConfigurationError(
                    "social token encryption key configuration is invalid"
                )
        self._keys = normalized
        self.active_key_id = active_key_id

    @classmethod
    def from_environment(
        cls, raw_keys: Optional[str], active_key_id: Optional[str]
    ) -> "SocialTokenCipher":
        if not raw_keys or not raw_keys.strip() or not active_key_id:
            raise SocialTokenCipherConfigurationError(
                "social token encryption keys are not configured"
            )
        try:
            parsed = json.loads(raw_keys)
        except json.JSONDecodeError as error:
            raise SocialTokenCipherConfigurationError(
                "social token encryption keys must be valid JSON"
            ) from error
        if not isinstance(parsed, dict) or not parsed:
            raise SocialTokenCipherConfigurationError(
                "social token encryption keys must be a non-empty object"
            )
        keys: dict[str, bytes] = {}
        for key_id, encoded in parsed.items():
            if not isinstance(key_id, str) or not isinstance(encoded, str):
                raise SocialTokenCipherConfigurationError(
                    "social token encryption key entries must be strings"
                )
            if not _KEY_ID.fullmatch(key_id):
                raise SocialTokenCipherConfigurationError(
                    "social token encryption key id is invalid"
                )
            try:
                raw = _decode_base64url(encoded)
            except (ValueError, binascii.Error) as error:
                raise SocialTokenCipherConfigurationError(
                    "social token encryption key is invalid"
                ) from error
            if len(raw) != 32:
                raise SocialTokenCipherConfigurationError(
                    "social token encryption keys must contain 32 bytes"
                )
            keys[key_id] = raw
        return cls(keys, active_key_id.strip())

    @classmethod
    def from_process_environment(cls) -> "SocialTokenCipher":
        return cls.from_environment(
            os.environ.get("AGENCY_SOCIAL_TOKEN_ENCRYPTION_KEYS_JSON"),
            os.environ.get("AGENCY_SOCIAL_TOKEN_ACTIVE_KEY_ID"),
        )

    def encrypt(
        self, payload: Mapping[str, object], *, associated_data: str
    ) -> EncryptedSocialValue:
        normalized = _validated_payload(payload)
        aad = _associated_data(associated_data)
        plaintext = canonical_json(normalized).encode("utf-8")
        if len(plaintext) > _MAX_PLAINTEXT_BYTES:
            raise ValueError("social token payload is too large")
        nonce = os.urandom(_NONCE_BYTES)
        encrypted = AESGCM(self._keys[self.active_key_id]).encrypt(
            nonce, plaintext, aad
        )
        return EncryptedSocialValue(
            key_id=self.active_key_id,
            ciphertext=_encode_base64url(nonce + encrypted),
        )

    def decrypt(
        self, value: EncryptedSocialValue, *, associated_data: str
    ) -> dict[str, object]:
        key = self._keys.get(value.key_id)
        if key is None:
            raise SocialTokenDecryptionError(
                "social token encryption key is unavailable"
            )
        try:
            raw = _decode_base64url(value.ciphertext)
            if len(raw) <= _NONCE_BYTES + 16:
                raise ValueError("ciphertext is too short")
            plaintext = AESGCM(key).decrypt(
                raw[:_NONCE_BYTES], raw[_NONCE_BYTES:], _associated_data(associated_data)
            )
            parsed = json.loads(plaintext.decode("utf-8"))
            if not isinstance(parsed, dict):
                raise ValueError("payload is not an object")
            return _validated_payload(parsed)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError, binascii.Error) as error:
            raise SocialTokenDecryptionError(
                "social token could not be decrypted"
            ) from error
        except Exception as error:
            raise SocialTokenDecryptionError(
                "social token could not be decrypted"
            ) from error

    def __repr__(self) -> str:
        return "SocialTokenCipher(active_key_id={!r}, key_count={})".format(
            self.active_key_id, len(self._keys)
        )


def _validated_payload(payload: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(payload, Mapping) or not payload or len(payload) > _MAX_FIELDS:
        raise ValueError("social token payload must be a bounded non-empty object")
    result: dict[str, object] = {}
    for raw_name, raw_value in payload.items():
        if (
            not isinstance(raw_name, str)
            or not raw_name
            or len(raw_name) > _MAX_FIELD_NAME
            or not re.fullmatch(r"[a-z][a-z0-9_]*", raw_name)
        ):
            raise ValueError("social token payload field is invalid")
        if raw_value is None:
            result[raw_name] = None
        elif isinstance(raw_value, bool):
            result[raw_name] = raw_value
        elif isinstance(raw_value, int):
            result[raw_name] = raw_value
        elif isinstance(raw_value, str) and len(raw_value) <= _MAX_FIELD_VALUE:
            result[raw_name] = raw_value
        elif isinstance(raw_value, list) and len(raw_value) <= 32 and all(
            isinstance(item, str) and len(item) <= 256 for item in raw_value
        ):
            result[raw_name] = list(raw_value)
        else:
            raise ValueError("social token payload value is invalid")
    return result


def _associated_data(value: str) -> bytes:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise ValueError("social token associated data is invalid")
    return value.encode("utf-8")


def _encode_base64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_base64url(value: str) -> bytes:
    if not isinstance(value, str) or not value or len(value) > 65536:
        raise ValueError("base64url value is invalid")
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
