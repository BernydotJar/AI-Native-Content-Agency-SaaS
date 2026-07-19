from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Union

import uvicorn
from fastapi import Depends, FastAPI, Header, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .auth import IdentityContext, development_identity
from .contracts import (
    ApprovalCreate,
    ErrorResponse,
    HealthResponse,
    MissionCreate,
    MissionResponse,
    RunResponse,
    RunStart,
    SCHEMA_VERSION,
)
from .database import build_engine, build_session_factory, create_schema
from .errors import ControlPlaneError
from .observability import configure_logging, request_context_middleware
from .ports import ControlPlaneRepository
from .repository import SqlAlchemyRepository
from .service import ControlPlaneService
from .settings import Settings


_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
MAX_REQUEST_BYTES = 1_048_576
ERROR_DESCRIPTIONS = {
    400: "Bad Request",
    401: "Unauthorized",
    404: "Resource Not Found",
    409: "Conflict",
    413: "Request Body Too Large",
    422: "Request Validation Failed",
    500: "Internal Server Error",
    503: "Database or Dependency Unavailable",
}


def documented_errors(*status_codes: int) -> Dict[Union[int, str], Dict[str, Any]]:
    return {
        status_code: {
            "model": ErrorResponse,
            "description": ERROR_DESCRIPTIONS[status_code],
        }
        for status_code in status_codes
    }


class RequestSizeLimitMiddleware:
    """Enforce the body limit from received ASGI bytes, not a caller-supplied header."""

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_REQUEST_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        content_length = request.headers.get("Content-Length")
        if content_length is not None:
            try:
                declared_bytes = int(content_length)
            except ValueError:
                await self._reject(
                    request,
                    send,
                    400,
                    "INVALID_CONTENT_LENGTH",
                    "Content-Length is invalid",
                )
                return
            if declared_bytes < 0 or declared_bytes > self.max_bytes:
                await self._reject(
                    request,
                    send,
                    413,
                    "REQUEST_TOO_LARGE",
                    "Request body exceeds the control-plane limit",
                )
                return

        if scope["method"] not in {"POST", "PUT", "PATCH", "DELETE"}:
            await self.app(scope, receive, send)
            return

        body = bytearray()
        disconnected = False
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                disconnected = True
                break
            if message["type"] != "http.request":
                continue
            body.extend(message.get("body", b""))
            if len(body) > self.max_bytes:
                await self._reject(
                    request,
                    send,
                    413,
                    "REQUEST_TOO_LARGE",
                    "Request body exceeds the control-plane limit",
                )
                return
            if not message.get("more_body", False):
                break

        replayed = False

        async def replay_receive() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                if disconnected:
                    return {"type": "http.disconnect"}
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay_receive, send)

    async def _reject(
        self,
        request: Request,
        send: Send,
        status_code: int,
        code: str,
        message: str,
    ) -> None:
        response = JSONResponse(
            status_code=status_code,
            content=_error_payload(
                request,
                code,
                message,
                {"maximum_bytes": self.max_bytes} if status_code == 413 else {},
            ),
        )
        await response(request.scope, request.receive, send)


def _correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", "correlation-unavailable")


def _error_payload(
    request: Request,
    code: str,
    message: str,
    details: Optional[dict] = None,
) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "error": {
            "code": code,
            "message": message,
            "correlation_id": _correlation_id(request),
            "details": details or {},
        },
    }


def require_idempotency_key(
    value: str = Header(
        alias="Idempotency-Key",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    ),
) -> str:
    if not _IDEMPOTENCY_KEY.fullmatch(value):
        raise ControlPlaneError(
            400,
            "INVALID_IDEMPOTENCY_KEY",
            "Idempotency-Key is required and must match the command-key contract",
        )
    return value


def enforce_request_size(request: Request) -> None:
    value = request.headers.get("Content-Length")
    if value is None:
        return
    try:
        content_length = int(value)
    except ValueError as error:
        raise ControlPlaneError(400, "INVALID_CONTENT_LENGTH", "Content-Length is invalid") from error
    if content_length < 0 or content_length > MAX_REQUEST_BYTES:
        raise ControlPlaneError(
            413,
            "REQUEST_TOO_LARGE",
            "Request body exceeds the control-plane limit",
            {"maximum_bytes": MAX_REQUEST_BYTES},
        )


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    resolved_settings = settings or Settings()
    configure_logging(resolved_settings.log_level)
    engine = build_engine(resolved_settings.database_url)
    if resolved_settings.auto_create_schema:
        create_schema(engine)
    session_factory = build_session_factory(engine)

    app = FastAPI(
        title="AI-Native Content Agency Control Plane",
        version="1.0.0",
        description=(
            "Versioned, tenant-scoped control plane. External providers remain sandbox-only "
            "and approvals never imply publication or ad spend."
        ),
    )
    app.state.settings = resolved_settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.add_middleware(RequestSizeLimitMiddleware, max_bytes=MAX_REQUEST_BYTES)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=[
            "Content-Type",
            "Idempotency-Key",
            "X-Correlation-ID",
            "X-Tenant-ID",
            "X-Principal-ID",
        ],
    )
    app.middleware("http")(request_context_middleware)

    def repository_dependency() -> Iterator[ControlPlaneRepository]:
        session: Session = session_factory()
        try:
            yield SqlAlchemyRepository(session)
        finally:
            session.close()

    def service_dependency(
        repository: ControlPlaneRepository = Depends(repository_dependency),
    ) -> ControlPlaneService:
        return ControlPlaneService(repository)

    @app.exception_handler(ControlPlaneError)
    async def handle_control_plane_error(
        request: Request, error: ControlPlaneError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content=_error_payload(
                request,
                error.code,
                error.message,
                dict(error.details),
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        invalid_headers = {
            str(issue["loc"][1]).lower()
            for issue in error.errors()
            if len(issue["loc"]) >= 2 and issue["loc"][0] == "header"
        }
        identity_headers = {"x-tenant-id", "x-principal-id"}
        if invalid_headers & identity_headers:
            field = (
                "X-Tenant-ID"
                if "x-tenant-id" in invalid_headers
                else "X-Principal-ID"
            )
            return JSONResponse(
                status_code=401,
                content=_error_payload(
                    request,
                    "INVALID_DEVELOPMENT_IDENTITY",
                    "{} must match the development identity contract".format(field),
                    {"field": field},
                ),
            )
        if "idempotency-key" in invalid_headers:
            return JSONResponse(
                status_code=400,
                content=_error_payload(
                    request,
                    "INVALID_IDEMPOTENCY_KEY",
                    "Idempotency-Key is required and must match the command-key contract",
                ),
            )
        issues = [
            {"location": [str(item) for item in issue["loc"]], "type": issue["type"]}
            for issue in error.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=_error_payload(
                request,
                "REQUEST_VALIDATION_FAILED",
                "Request did not match the versioned API contract",
                {"issues": issues},
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        request: Request, error: StarletteHTTPException
    ) -> JSONResponse:
        code, message = {
            404: ("RESOURCE_NOT_FOUND", "API route was not found"),
            405: ("METHOD_NOT_ALLOWED", "HTTP method is not allowed for this route"),
        }.get(
            error.status_code,
            ("HTTP_ERROR", "HTTP request failed"),
        )
        return JSONResponse(
            status_code=error.status_code,
            content=_error_payload(request, code, message),
            headers=error.headers,
        )

    @app.exception_handler(SQLAlchemyError)
    async def handle_database_error(request: Request, _: SQLAlchemyError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content=_error_payload(
                request,
                "DATABASE_UNAVAILABLE",
                "The control-plane database is unavailable",
            ),
        )

    @app.get(
        "/healthz",
        response_model=HealthResponse,
        responses=documented_errors(500),
        tags=["operations"],
    )
    def health() -> HealthResponse:
        return HealthResponse(schema_version=SCHEMA_VERSION, status="ok")

    @app.get(
        "/readyz",
        response_model=HealthResponse,
        responses=documented_errors(500, 503),
        tags=["operations"],
    )
    def readiness(
        repository: ControlPlaneRepository = Depends(repository_dependency),
    ) -> HealthResponse:
        repository.ping()
        return HealthResponse(schema_version=SCHEMA_VERSION, status="ready")

    @app.post(
        "/api/v1/missions",
        response_model=MissionResponse,
        status_code=status.HTTP_201_CREATED,
        responses=documented_errors(400, 401, 409, 413, 422, 500, 503),
        tags=["missions"],
    )
    def create_mission_endpoint(
        request: Request,
        payload: MissionCreate,
        _: None = Depends(enforce_request_size),
        identity: IdentityContext = Depends(development_identity),
        idempotency_key: str = Depends(require_idempotency_key),
        service: ControlPlaneService = Depends(service_dependency),
    ) -> MissionResponse:
        return service.create_mission(
            identity,
            payload,
            idempotency_key,
            _correlation_id(request),
        )

    @app.post(
        "/api/v1/missions/{mission_id}/runs",
        response_model=RunResponse,
        status_code=status.HTTP_201_CREATED,
        responses=documented_errors(400, 401, 404, 409, 413, 422, 500, 503),
        tags=["runs"],
    )
    def start_run_endpoint(
        request: Request,
        mission_id: str,
        payload: RunStart,
        _: None = Depends(enforce_request_size),
        identity: IdentityContext = Depends(development_identity),
        idempotency_key: str = Depends(require_idempotency_key),
        service: ControlPlaneService = Depends(service_dependency),
    ) -> RunResponse:
        return service.start_run(
            identity,
            mission_id,
            payload,
            idempotency_key,
            _correlation_id(request),
        )

    @app.get(
        "/api/v1/runs/{run_id}",
        response_model=RunResponse,
        responses=documented_errors(401, 404, 422, 500, 503),
        tags=["runs"],
    )
    def get_run_endpoint(
        run_id: str,
        identity: IdentityContext = Depends(development_identity),
        service: ControlPlaneService = Depends(service_dependency),
    ) -> RunResponse:
        return service.get_run(identity, run_id)

    @app.post(
        "/api/v1/runs/{run_id}/approvals",
        response_model=RunResponse,
        responses=documented_errors(400, 401, 404, 409, 413, 422, 500, 503),
        tags=["approvals"],
    )
    def decide_run_endpoint(
        request: Request,
        run_id: str,
        payload: ApprovalCreate,
        _: None = Depends(enforce_request_size),
        identity: IdentityContext = Depends(development_identity),
        idempotency_key: str = Depends(require_idempotency_key),
        service: ControlPlaneService = Depends(service_dependency),
    ) -> RunResponse:
        return service.decide_run(
            identity,
            run_id,
            payload,
            idempotency_key,
            _correlation_id(request),
        )

    _mount_optional_spa(app, resolved_settings.web_dist)

    return app


def _mount_optional_spa(app: FastAPI, web_dist: Optional[Path]) -> None:
    if web_dist is None:
        return
    root = web_dist.expanduser().resolve()
    index = root / "index.html"
    if not root.is_dir() or not index.is_file():
        return

    @app.get("/{asset_path:path}", include_in_schema=False)
    def serve_spa(asset_path: str) -> FileResponse:
        if asset_path == "api" or asset_path.startswith("api/"):
            raise ControlPlaneError(404, "RESOURCE_NOT_FOUND", "API route was not found")
        candidate = (root / asset_path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as error:
            raise ControlPlaneError(
                404, "RESOURCE_NOT_FOUND", "Static asset was not found"
            ) from error
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)


def entrypoint() -> None:
    uvicorn.run(
        "control_plane.api:create_app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        factory=True,
    )


if __name__ == "__main__":
    entrypoint()
