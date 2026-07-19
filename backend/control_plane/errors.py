from __future__ import annotations

from typing import Any, Mapping, Optional


class ControlPlaneError(RuntimeError):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Optional[Mapping[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = dict(details or {})


def not_found(resource: str, resource_id: str) -> ControlPlaneError:
    return ControlPlaneError(
        404,
        "RESOURCE_NOT_FOUND",
        "{} was not found".format(resource),
        {"resource": resource, "resource_id": resource_id},
    )


def conflict(code: str, message: str, **details: Any) -> ControlPlaneError:
    return ControlPlaneError(409, code, message, details)
