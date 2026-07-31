from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Optional

from .utils import canonical_json

AUDIT_CHAIN_SCHEMA = "audit-chain.v1"
AUDIT_CHECKPOINT_SCHEMA = "audit-checkpoint.v1"
GENESIS_AUDIT_HASH = "0" * 64
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_KEY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_BASE64URL = re.compile(r"^[A-Za-z0-9_-]+={0,2}$")
_MAX_KEYS = 16


class AuditIntegrityError(RuntimeError):
    """Raised when a stored audit chain cannot be verified."""


class AuditCheckpointSigningConfigurationError(ValueError):
    """Raised when audit checkpoint signing configuration is unsafe."""


class AuditCheckpointSigningKeyUnavailableError(RuntimeError):
    """Raised when a checkpoint references a key that is unavailable."""


@dataclass(frozen=True)
class AuditChainCheckpoint:
    tenant_id: str
    event_count: int
    head_event_id: str
    head_hash: str
    verified_at: str

    def __post_init__(self) -> None:
        if not self.tenant_id:
            raise ValueError("audit checkpoint tenant is required")
        if self.event_count < 0:
            raise ValueError("audit checkpoint event count must not be negative")
        if self.event_count == 0:
            if self.head_event_id:
                raise ValueError("empty audit checkpoint cannot contain a head event")
            if self.head_hash != GENESIS_AUDIT_HASH:
                raise ValueError("empty audit checkpoint must use the genesis hash")
        else:
            if not self.head_event_id:
                raise ValueError("audit checkpoint head event is required")
            if not _HEX64.fullmatch(self.head_hash):
                raise ValueError("audit checkpoint head hash is invalid")
        if not self.verified_at:
            raise ValueError("audit checkpoint verification timestamp is required")

    def document(self) -> Mapping[str, object]:
        return {
            "schema_version": AUDIT_CHECKPOINT_SCHEMA,
            "tenant_id": self.tenant_id,
            "event_count": self.event_count,
            "head_event_id": self.head_event_id,
            "head_hash": self.head_hash,
            "verified_at": self.verified_at,
        }


@dataclass(frozen=True)
class SignedAuditChainCheckpoint:
    checkpoint: AuditChainCheckpoint
    key_id: str
    signature: str

    def document(self) -> Mapping[str, object]:
        return {
            **self.checkpoint.document(),
            "key_id": self.key_id,
            "signature": self.signature,
        }


def audit_event_hash(
    *,
    event_id: str,
    tenant_id: str,
    request_id: str,
    occurred_at: str,
    action: str,
    resource_type: str,
    resource_id: str,
    actor: str,
    payload: Mapping[str, object],
    previous_hash: str,
) -> str:
    if not _HEX64.fullmatch(previous_hash):
        raise ValueError("previous audit hash is invalid")
    document = (
        AUDIT_CHAIN_SCHEMA,
        event_id,
        tenant_id,
        request_id,
        occurred_at,
        action,
        resource_type,
        resource_id,
        actor,
        payload,
        previous_hash,
    )
    return hashlib.sha256(canonical_json(document).encode("utf-8")).hexdigest()


class AuditCheckpointSigningKeyring:
    """Immutable HMAC keyring for exportable audit-chain checkpoints."""

    def __init__(self, keys: Mapping[str, bytes], active_key_id: str) -> None:
        if not keys or len(keys) > _MAX_KEYS:
            raise AuditCheckpointSigningConfigurationError(
                "audit checkpoint keyring must contain 1..16 keys"
            )
        normalized: dict[str, bytes] = {}
        for key_id, raw_key in keys.items():
            if not isinstance(key_id, str) or not _KEY_ID.fullmatch(key_id):
                raise AuditCheckpointSigningConfigurationError(
                    "audit checkpoint key identifier is invalid"
                )
            if not isinstance(raw_key, bytes) or len(raw_key) != 32:
                raise AuditCheckpointSigningConfigurationError(
                    "audit checkpoint signing keys must contain exactly 32 bytes"
                )
            normalized[key_id] = bytes(raw_key)
        if active_key_id not in normalized:
            raise AuditCheckpointSigningConfigurationError(
                "active audit checkpoint key is absent from the keyring"
            )
        self._keys = MappingProxyType(normalized)
        self.active_key_id = active_key_id

    @classmethod
    def from_environment(
        cls, raw_keys_json: Optional[str], active_key_id: Optional[str]
    ) -> Optional["AuditCheckpointSigningKeyring"]:
        raw_keys = (raw_keys_json or "").strip()
        active = (active_key_id or "").strip()
        if not raw_keys and not active:
            return None
        if not raw_keys or not active:
            raise AuditCheckpointSigningConfigurationError(
                "audit checkpoint keyring and active key ID must be configured together"
            )

        def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
            result: dict[str, object] = {}
            for key, value in pairs:
                if key in result:
                    raise AuditCheckpointSigningConfigurationError(
                        "audit checkpoint keyring contains a duplicate key ID"
                    )
                result[key] = value
            return result

        try:
            parsed = json.loads(raw_keys, object_pairs_hook=unique_object)
        except AuditCheckpointSigningConfigurationError:
            raise
        except json.JSONDecodeError as error:
            raise AuditCheckpointSigningConfigurationError(
                "audit checkpoint keyring JSON is invalid"
            ) from error
        if not isinstance(parsed, dict):
            raise AuditCheckpointSigningConfigurationError(
                "audit checkpoint keyring must be a JSON object"
            )
        decoded: dict[str, bytes] = {}
        for key_id, value in parsed.items():
            if not isinstance(value, str) or not _BASE64URL.fullmatch(value):
                raise AuditCheckpointSigningConfigurationError(
                    "audit checkpoint key material is not canonical base64url"
                )
            try:
                padded = value + "=" * (-len(value) % 4)
                raw = base64.b64decode(
                    padded.encode("ascii"), altchars=b"-_", validate=True
                )
            except (UnicodeEncodeError, ValueError) as error:
                raise AuditCheckpointSigningConfigurationError(
                    "audit checkpoint key material is invalid"
                ) from error
            canonical = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
            if value != canonical:
                raise AuditCheckpointSigningConfigurationError(
                    "audit checkpoint key material is not canonical base64url"
                )
            decoded[key_id] = raw
        return cls(decoded, active)

    @property
    def key_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._keys))

    def sign(self, checkpoint: AuditChainCheckpoint) -> SignedAuditChainCheckpoint:
        key = self._keys[self.active_key_id]
        digest = hmac.new(
            key,
            canonical_json(checkpoint.document()).encode("utf-8"),
            hashlib.sha256,
        ).digest()
        signature = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        return SignedAuditChainCheckpoint(
            checkpoint=checkpoint,
            key_id=self.active_key_id,
            signature=signature,
        )

    def verify(self, signed: SignedAuditChainCheckpoint) -> bool:
        key = self._keys.get(signed.key_id)
        if key is None:
            raise AuditCheckpointSigningKeyUnavailableError(
                "required audit checkpoint signing key is unavailable"
            )
        digest = hmac.new(
            key,
            canonical_json(signed.checkpoint.document()).encode("utf-8"),
            hashlib.sha256,
        ).digest()
        expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        return hmac.compare_digest(expected, signed.signature)

    def __repr__(self) -> str:
        return "AuditCheckpointSigningKeyring(active_key_id={!r}, key_count={})".format(
            self.active_key_id, len(self._keys)
        )
