from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from typing import Mapping, Optional, Sequence, Tuple


_TENANT_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")
_SUBJECT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$")
_KEY_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_VALID_ROLES = frozenset({"viewer", "operator", "approver", "admin"})
_VALID_ENTITLEMENTS = frozenset({"theme:premium"})
_ROLE_PERMISSIONS = {
    "viewer": frozenset({"identity:read", "runs:read", "audit:read"}),
    "operator": frozenset(
        {"identity:read", "runs:read", "runs:create", "audit:read"}
    ),
    "approver": frozenset(
        {
            "identity:read",
            "runs:read",
            "greenlight:decide",
            "greenlight:revoke",
            "audit:read",
        }
    ),
    "admin": frozenset(
        {
            "identity:read",
            "runs:read",
            "runs:create",
            "greenlight:decide",
            "greenlight:revoke",
            "audit:read",
            "social:manage",
        }
    ),
}


class AuthConfigurationError(ValueError):
    pass


class AuthenticationError(PermissionError):
    pass


class AuthorizationError(PermissionError):
    pass


@dataclass(frozen=True)
class TenantPrincipal:
    tenant_id: str
    subject_id: str
    role: str
    key_id: str
    credential_fingerprint: str
    entitlements: Tuple[str, ...] = ()
    auth_method: str = "bearer"
    session_id: str = ""

    @property
    def permissions(self) -> Tuple[str, ...]:
        return tuple(sorted(_ROLE_PERMISSIONS[self.role]))

    def permits(self, permission: str) -> bool:
        return permission in _ROLE_PERMISSIONS[self.role]

    def require(self, permission: str) -> None:
        if not self.permits(permission):
            raise AuthorizationError(
                "role '{}' does not grant '{}'".format(self.role, permission)
            )


@dataclass(frozen=True)
class _CredentialEntry:
    digest: str
    tenant_id: str
    subject_id: str
    role: str
    key_id: str
    entitlements: Tuple[str, ...] = ()
    legacy: bool = False

    def principal(self, auth_method: str = "bearer", session_id: str = "") -> TenantPrincipal:
        return TenantPrincipal(
            tenant_id=self.tenant_id,
            subject_id=self.subject_id,
            role=self.role,
            key_id=self.key_id,
            credential_fingerprint=self.digest,
            entitlements=self.entitlements,
            auth_method=auth_method,
            session_id=session_id,
        )


class TenantAuthenticator:
    """Resolve individual tenant identity without retaining raw credentials.

    The legacy tenant-to-key mapping remains supported and is translated into an
    administrator identity. The preferred identity configuration is an array of
    records with tenant_id, subject_id, role, key_id, api_key, optional active and exact allowlisted entitlements.
    Multiple active key IDs for the same subject enable overlap during rotation.
    """

    def __init__(
        self,
        tenant_api_keys: Optional[Mapping[str, str]] = None,
        identity_credentials: Optional[Sequence[Mapping[str, object]]] = None,
    ) -> None:
        entries = []
        seen_digests = set()
        seen_key_ids = set()
        subject_authority = {}

        def add_entry(
            *,
            tenant_id: str,
            subject_id: str,
            role: str,
            key_id: str,
            api_key: str,
            entitlements: Sequence[str],
            legacy: bool,
        ) -> None:
            normalized_tenant = self._tenant_id(tenant_id)
            normalized_subject = self._subject_id(subject_id)
            normalized_role = self._role(role)
            normalized_key_id = self._key_id(key_id)
            normalized_entitlements = self._entitlements(entitlements)
            self._validate_api_key(api_key)
            digest = self.fingerprint(api_key)
            if digest in seen_digests:
                raise AuthConfigurationError(
                    "the same API key cannot be assigned to multiple identities"
                )
            key_identity = (normalized_tenant, normalized_key_id)
            if key_identity in seen_key_ids:
                raise AuthConfigurationError(
                    "key_id must be unique within a tenant: {}".format(
                        normalized_key_id
                    )
                )
            authority_identity = (normalized_tenant, normalized_subject)
            authority = (normalized_role, normalized_entitlements)
            existing_authority = subject_authority.get(authority_identity)
            if existing_authority is not None and existing_authority != authority:
                raise AuthConfigurationError(
                    "active keys for one subject must share role and entitlements"
                )
            subject_authority[authority_identity] = authority
            seen_digests.add(digest)
            seen_key_ids.add(key_identity)
            entries.append(
                _CredentialEntry(
                    digest=digest,
                    tenant_id=normalized_tenant,
                    subject_id=normalized_subject,
                    role=normalized_role,
                    key_id=normalized_key_id,
                    entitlements=normalized_entitlements,
                    legacy=legacy,
                )
            )

        for tenant_id, api_key in sorted((tenant_api_keys or {}).items()):
            normalized_tenant = self._tenant_id(tenant_id)
            add_entry(
                tenant_id=normalized_tenant,
                subject_id="tenant:{}".format(normalized_tenant),
                role="admin",
                key_id="legacy:{}".format(normalized_tenant),
                api_key=api_key,
                entitlements=(),
                legacy=True,
            )

        for index, raw in enumerate(identity_credentials or ()):
            if not isinstance(raw, Mapping):
                raise AuthConfigurationError(
                    "identity credential at index {} must be an object".format(index)
                )
            active = raw.get("active", True)
            if not isinstance(active, bool):
                raise AuthConfigurationError(
                    "identity credential active must be boolean at index {}".format(index)
                )
            if not active:
                continue
            required = ("tenant_id", "subject_id", "role", "key_id", "api_key")
            if any(not isinstance(raw.get(field), str) for field in required):
                raise AuthConfigurationError(
                    "identity credential at index {} must contain string tenant_id, "
                    "subject_id, role, key_id and api_key".format(index)
                )
            entitlements = self._entitlements(raw.get("entitlements", ()))
            add_entry(
                tenant_id=str(raw["tenant_id"]),
                subject_id=str(raw["subject_id"]),
                role=str(raw["role"]),
                key_id=str(raw["key_id"]),
                api_key=str(raw["api_key"]),
                entitlements=entitlements,
                legacy=False,
            )

        self._entries: Tuple[_CredentialEntry, ...] = tuple(
            sorted(entries, key=lambda item: (item.tenant_id, item.subject_id, item.key_id))
        )
        self._individual_identity_configured = any(not item.legacy for item in entries)

    @property
    def configured(self) -> bool:
        return bool(self._entries)

    @property
    def credential_count(self) -> int:
        return len(self._entries)

    @property
    def individual_identity_configured(self) -> bool:
        return self._individual_identity_configured

    def authenticate(self, api_key: str) -> TenantPrincipal:
        candidate = self.fingerprint(api_key)
        matched: Optional[_CredentialEntry] = None
        for entry in self._entries:
            if hmac.compare_digest(candidate, entry.digest):
                matched = entry
        if matched is None:
            raise AuthenticationError("invalid bearer credential")
        return matched.principal()

    def resolve_active_session(
        self,
        *,
        tenant_id: str,
        subject_id: str,
        key_id: str,
        credential_fingerprint: str,
        session_id: str,
    ) -> TenantPrincipal:
        matched: Optional[_CredentialEntry] = None
        for entry in self._entries:
            identity_match = (
                entry.tenant_id == tenant_id
                and entry.subject_id == subject_id
                and entry.key_id == key_id
            )
            full_fingerprint_match = hmac.compare_digest(
                entry.digest, credential_fingerprint
            )
            legacy_fingerprint_match = (
                len(credential_fingerprint) == 16
                and hmac.compare_digest(entry.digest[:16], credential_fingerprint)
            )
            fingerprint_match = full_fingerprint_match or legacy_fingerprint_match
            if identity_match and fingerprint_match:
                matched = entry
        if matched is None:
            raise AuthenticationError("session credential is no longer active")
        return matched.principal(auth_method="session", session_id=session_id)

    @classmethod
    def from_json(cls, raw_value: Optional[str]) -> "TenantAuthenticator":
        return cls(tenant_api_keys=cls._legacy_json(raw_value))

    @classmethod
    def from_environment(
        cls,
        tenant_api_keys_json: Optional[str],
        identity_credentials_json: Optional[str],
    ) -> "TenantAuthenticator":
        legacy = cls._legacy_json(tenant_api_keys_json)
        identities = cls._identity_json(identity_credentials_json)
        return cls(tenant_api_keys=legacy, identity_credentials=identities)

    @staticmethod
    def fingerprint(api_key: str) -> str:
        return hashlib.sha256(api_key.encode("utf-8")).hexdigest()

    @staticmethod
    def _legacy_json(raw_value: Optional[str]) -> Mapping[str, str]:
        if raw_value is None or not raw_value.strip():
            return {}
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
        return parsed

    @staticmethod
    def _identity_json(raw_value: Optional[str]) -> Sequence[Mapping[str, object]]:
        if raw_value is None or not raw_value.strip():
            return ()
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError as error:
            raise AuthConfigurationError(
                "AGENCY_IDENTITY_CREDENTIALS_JSON must be valid JSON"
            ) from error
        if not isinstance(parsed, list) or not all(
            isinstance(item, dict) for item in parsed
        ):
            raise AuthConfigurationError(
                "AGENCY_IDENTITY_CREDENTIALS_JSON must be an array of objects"
            )
        return parsed

    @staticmethod
    def _tenant_id(value: str) -> str:
        normalized = value.strip().lower()
        if not _TENANT_PATTERN.fullmatch(normalized):
            raise AuthConfigurationError(
                "tenant ids must match [a-z0-9][a-z0-9_-]{0,62}"
            )
        return normalized

    @staticmethod
    def _subject_id(value: str) -> str:
        normalized = value.strip()
        if not _SUBJECT_PATTERN.fullmatch(normalized):
            raise AuthConfigurationError(
                "subject ids must contain 1-128 safe identity characters"
            )
        return normalized

    @staticmethod
    def _key_id(value: str) -> str:
        normalized = value.strip()
        if not _KEY_ID_PATTERN.fullmatch(normalized):
            raise AuthConfigurationError(
                "key ids must contain 1-128 safe identifier characters"
            )
        return normalized

    @staticmethod
    def _role(value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in _VALID_ROLES:
            raise AuthConfigurationError(
                "role must be one of: {}".format(", ".join(sorted(_VALID_ROLES)))
            )
        return normalized

    @staticmethod
    def _entitlements(value: object) -> Tuple[str, ...]:
        if value is None:
            return ()
        if not isinstance(value, (list, tuple)) or isinstance(value, (str, bytes)):
            raise AuthConfigurationError("identity entitlements must be an array")
        if not all(isinstance(item, str) for item in value):
            raise AuthConfigurationError("identity entitlements must contain strings")
        normalized = tuple(item.strip().lower() for item in value)
        if any(not item for item in normalized):
            raise AuthConfigurationError("identity entitlements must not be empty")
        if len(set(normalized)) != len(normalized):
            raise AuthConfigurationError("identity entitlements must not contain duplicates")
        unknown = sorted(set(normalized) - _VALID_ENTITLEMENTS)
        if unknown:
            raise AuthConfigurationError(
                "unsupported identity entitlement: {}".format(", ".join(unknown))
            )
        return tuple(sorted(normalized))

    @staticmethod
    def _validate_api_key(api_key: str) -> None:
        if not api_key or len(api_key) < 24:
            raise AuthConfigurationError("API keys must contain at least 24 characters")
