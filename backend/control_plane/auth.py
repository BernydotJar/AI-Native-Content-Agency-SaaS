from __future__ import annotations

import re
from dataclasses import dataclass
from fastapi import Header, Request

from .errors import ControlPlaneError
from .settings import Settings


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


@dataclass(frozen=True)
class IdentityContext:
    tenant_id: str
    principal_id: str
    auth_mode: str


def _validated_identifier(value: str, field: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ControlPlaneError(
            401,
            "INVALID_DEVELOPMENT_IDENTITY",
            "{} must match the development identity contract".format(field),
            {"field": field},
        )
    return value


def development_identity(
    request: Request,
    x_tenant_id: str = Header(
        alias="X-Tenant-ID",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$",
    ),
    x_principal_id: str = Header(
        alias="X-Principal-ID",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$",
    ),
) -> IdentityContext:
    settings: Settings = request.app.state.settings
    if settings.auth_mode != "development_headers":
        raise ControlPlaneError(
            503,
            "AUTHENTICATION_NOT_CONFIGURED",
            "Protected routes are unavailable until an authentication adapter is configured",
        )
    identity = IdentityContext(
        tenant_id=_validated_identifier(x_tenant_id, "X-Tenant-ID"),
        principal_id=_validated_identifier(x_principal_id, "X-Principal-ID"),
        auth_mode=settings.auth_mode,
    )
    request.state.tenant_id = identity.tenant_id
    request.state.principal_id = identity.principal_id
    return identity
