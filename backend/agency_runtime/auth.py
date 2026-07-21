from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from typing import Mapping, Optional, Tuple


_TENANT_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")


class AuthConfigurationError(ValueError):
    pass


class AuthenticationError(PermissionError):
    pass


@dataclass(frozen=True)
class TenantPrincipal:
    tenant_id: str
    credential_fingerprint: str
    auth_method: str = "bearer"
    session_id: str = ""


class TenantAuthenticator:
    """Resolve tenant identity from bearer credentials without storing raw keys."""

    def __init__(self, tenant_api_keys: Optional[Mapping[str, str]] = None) -> None:
        entries = []
        for tenant_id, api_key in sorted((tenant_api_keys or {}).items()):
            normalized_tenant = tenant_id.strip().lower()
            if not _TENANT_PATTERN.fullmatch(normalized_tenant):
                raise AuthConfigurationError(
                    "tenant ids must match [a-z0-9][a-z0-9_-]{0,62}"
                )
            if not api_key or len(api_key) < 24:
                raise AuthConfigurationError(
                    "API keys must contain at least 24 characters"
                )
            digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
            entries.append((digest, normalized_tenant))
        self._entries: Tuple[Tuple[str, str], ...] = tuple(entries)

    @property
    def configured(self) -> bool:
        return bool(self._entries)

    def authenticate(self, api_key: str) -> TenantPrincipal:
        candidate = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
        matched_tenant = ""
        for digest, tenant_id in self._entries:
            if hmac.compare_digest(candidate, digest):
                matched_tenant = tenant_id
        if not matched_tenant:
            raise AuthenticationError("invalid bearer credential")
        return TenantPrincipal(
            tenant_id=matched_tenant,
            credential_fingerprint=candidate[:16],
        )

    @classmethod
    def from_json(cls, raw_value: Optional[str]) -> "TenantAuthenticator":
        if raw_value is None or not raw_value.strip():
            return cls()
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError as error:
            raise AuthConfigurationError(
                "AGENCY_TENANT_API_KEYS_JSON must be valid JSON"
            ) from error
        if not isinstance(parsed, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in parsed.items()
        ):
            raise AuthConfigurationError(
                "AGENCY_TENANT_API_KEYS_JSON must be an object of tenant to API key"
            )
        return cls(parsed)
