from __future__ import annotations

import hashlib
import logging
import os
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from .auth import (
    AuthenticationError,
    AuthorizationError,
    TenantAuthenticator,
    TenantPrincipal,
)
from .memory import MemoryStore, SQLiteMemory
from .models import ExecutionRun, MissionBrief, Platform, RunStatus
from .observability import RequestTimer, RuntimeMetrics, request_id_from_header, structured_http_log
from .orchestrator import AgencyOrchestrator, GreenlightError
from .postgres import PostgresMemory, PostgresRunStore, PostgresRuntimeDatabase
from .persistence import (
    AuditEvent,
    AuditWrite,
    AuthenticationRateLimitError,
    RunStateConflictError,
    SQLiteRunStore,
    SessionAuthenticationError,
    SessionCsrfError,
    SessionIssue,
    SessionRecord,
)
from .tools import build_sandbox_toolset
from .utils import stable_id, to_primitive
from .version import VERSION


API_LOGGER = logging.getLogger("agency_runtime.api")
_PUBLIC_ERROR_CODE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
_MAX_PUBLIC_ERROR_DETAIL = 200
_DEFAULT_MAX_REQUEST_BODY_BYTES = 1024 * 1024
_MAX_CONFIGURED_REQUEST_BODY_BYTES = 10 * 1024 * 1024
_SAFE_HTTP_ERRORS = {
    status.HTTP_400_BAD_REQUEST: ("invalid_request", "invalid request"),
    status.HTTP_401_UNAUTHORIZED: ("authentication_failed", "authentication failed"),
    status.HTTP_403_FORBIDDEN: ("authorization_denied", "request not permitted"),
    status.HTTP_404_NOT_FOUND: ("resource_not_found", "resource not found"),
    status.HTTP_405_METHOD_NOT_ALLOWED: ("method_not_allowed", "method not allowed"),
    status.HTTP_409_CONFLICT: ("resource_state_conflict", "resource state conflict"),
    status.HTTP_413_CONTENT_TOO_LARGE: ("request_too_large", "request too large"),
    status.HTTP_422_UNPROCESSABLE_CONTENT: (
        "request_validation_failed",
        "request validation failed",
    ),
    status.HTTP_429_TOO_MANY_REQUESTS: (
        "authentication_rate_limited",
        "authentication temporarily rate limited",
    ),
    status.HTTP_503_SERVICE_UNAVAILABLE: ("service_unavailable", "service unavailable"),
}


class PublicApiError(HTTPException):
    """An HTTP error whose code and detail are safe to serialize publicly."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        detail: str,
        headers: Optional[Mapping[str, str]] = None,
    ) -> None:
        if status_code < 400 or status_code > 599:
            raise ValueError("public API errors require a 4xx or 5xx status")
        if not _PUBLIC_ERROR_CODE.fullmatch(code):
            raise ValueError("public API error code is invalid")
        if (
            not detail
            or len(detail) > _MAX_PUBLIC_ERROR_DETAIL
            or any(ord(character) < 32 or ord(character) == 127 for character in detail)
        ):
            raise ValueError("public API error detail is invalid")
        super().__init__(status_code=status_code, detail=detail, headers=dict(headers or {}))
        self.code = code


def _error_body(code: str, detail: str, request_id: str) -> Dict[str, object]:
    return {"code": code, "detail": detail, "request_id": request_id}


class RequestBodyLimitMiddleware:
    """Bound and replay request-body messages before application dispatch."""

    def __init__(self, app: object, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: object, receive: object, send: object) -> None:
        if not isinstance(scope, dict) or scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        raw_headers = scope.get("headers", ())
        header_pairs = [
            (bytes(name).lower(), bytes(value))
            for name, value in raw_headers
            if isinstance(name, (bytes, bytearray))
            and isinstance(value, (bytes, bytearray))
        ]
        headers = dict(header_pairs)
        request_id = request_id_from_header(
            headers.get(b"x-request-id", b"").decode("latin-1") or None
        )
        content_length_values = [
            value for name, value in header_pairs if name == b"content-length"
        ]
        transfer_encoding_values = [
            value.lower()
            for name, value in header_pairs
            if name == b"transfer-encoding"
        ]
        if len(content_length_values) > 1 or len(transfer_encoding_values) > 1:
            response = JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=_error_body(
                    "invalid_request", "invalid request", request_id
                ),
                headers={"X-Request-ID": request_id},
            )
            await response(scope, receive, send)
            return
        content_length = (
            content_length_values[0] if content_length_values else None
        )
        transfer_encoding = (
            transfer_encoding_values[0] if transfer_encoding_values else b""
        )
        if transfer_encoding and transfer_encoding != b"chunked":
            response = JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=_error_body(
                    "invalid_request", "invalid request", request_id
                ),
                headers={"X-Request-ID": request_id},
            )
            await response(scope, receive, send)
            return
        if content_length is not None:
            try:
                declared_length = int(content_length.decode("ascii"))
            except (UnicodeDecodeError, ValueError):
                declared_length = -1
            if declared_length < 0 or transfer_encoding:
                response = JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content=_error_body(
                        "invalid_request", "invalid request", request_id
                    ),
                    headers={"X-Request-ID": request_id},
                )
                await response(scope, receive, send)
                return
            if declared_length > self.max_bytes:
                response = JSONResponse(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    content=_error_body(
                        "request_too_large", "request too large", request_id
                    ),
                    headers={"X-Request-ID": request_id},
                )
                await response(scope, receive, send)
                return

        method = str(scope.get("method", "GET")).upper()
        should_buffer = (
            method in {"POST", "PUT", "PATCH", "DELETE"}
            or content_length is not None
            or bool(transfer_encoding)
        )
        if not should_buffer:
            await self.app(scope, receive, send)
            return

        buffered: List[object] = []
        received = 0
        while True:
            message = await receive()
            buffered.append(message)
            if not isinstance(message, dict):
                break
            if message.get("type") == "http.disconnect":
                break
            if message.get("type") != "http.request":
                continue
            body = message.get("body", b"")
            if isinstance(body, (bytes, bytearray)):
                received += len(body)
                if received > self.max_bytes:
                    response = JSONResponse(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        content=_error_body(
                            "request_too_large", "request too large", request_id
                        ),
                        headers={"X-Request-ID": request_id},
                    )
                    await response(scope, receive, send)
                    return
            if not message.get("more_body", False):
                break

        async def replay_receive() -> object:
            if buffered:
                return buffered.pop(0)
            return await receive()

        await self.app(scope, replay_receive, send)


class BriefRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=4000)
    audience: str = Field(min_length=1, max_length=1000)
    platforms: List[Platform] = Field(min_length=1, max_length=4)
    budget_cents: int = Field(default=0, ge=0)
    source_asset: str = Field(default="sandbox://brief/no-external-asset", max_length=2000)
    campaign_goal: str = Field(default="awareness", min_length=1, max_length=200)


class GreenlightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reviewer: str = Field(min_length=1, max_length=200)
    note: str = Field(default="", max_length=2000)


class BrowserSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_key: str = Field(min_length=24, max_length=512)


@dataclass
class TenantRuntime:
    memory: MemoryStore
    orchestrator: AgencyOrchestrator


class RuntimeService:
    """Tenant-scoped durable service boundary for SQLite or shared PostgreSQL."""

    def __init__(
        self,
        database_path: str,
        *,
        database_url: Optional[str] = None,
        postgres_pool_min_size: int = 1,
        postgres_pool_max_size: int = 10,
        postgres_connect_timeout_seconds: float = 15.0,
    ) -> None:
        self.database_path = database_path
        self.database_url = database_url.strip() if database_url else ""
        self._postgres_database: Optional[PostgresRuntimeDatabase] = None
        if self.database_url:
            self._postgres_database = PostgresRuntimeDatabase(
                self.database_url,
                min_size=postgres_pool_min_size,
                max_size=postgres_pool_max_size,
                connect_timeout_seconds=postgres_connect_timeout_seconds,
            )
            self.run_store = PostgresRunStore(self._postgres_database)
            self.storage_backend = "postgresql"
            self.shared_state = True
        else:
            self.run_store = SQLiteRunStore(database_path)
            self.storage_backend = "sqlite"
            self.shared_state = False
        self._tenant_runtimes: Dict[str, TenantRuntime] = {}
        self._lock = RLock()

    def _runtime_for(self, tenant_id: str) -> TenantRuntime:
        runtime = self._tenant_runtimes.get(tenant_id)
        if runtime is None:
            if self._postgres_database is not None:
                memory: MemoryStore = PostgresMemory(
                    self._postgres_database, namespace=tenant_id
                )
            else:
                memory = SQLiteMemory(self.database_path, namespace=tenant_id)
            runtime = TenantRuntime(
                memory=memory,
                orchestrator=AgencyOrchestrator(build_sandbox_toolset(), memory),
            )
            self._tenant_runtimes[tenant_id] = runtime
        return runtime

    def check(self) -> None:
        self.run_store.check()

    @staticmethod
    def _brief(request: BriefRequest) -> MissionBrief:
        return MissionBrief(
            title=request.title,
            objective=request.objective,
            audience=request.audience,
            platforms=tuple(request.platforms),
            budget_cents=request.budget_cents,
            source_asset=request.source_asset,
            campaign_goal=request.campaign_goal,
        )

    def create_browser_session(
        self, principal: TenantPrincipal, ttl_seconds: int, request_id: str
    ) -> SessionIssue:
        with self._lock:
            return self.run_store.create_session(
                tenant_id=principal.tenant_id,
                subject_id=principal.subject_id,
                role=principal.role,
                key_id=principal.key_id,
                credential_fingerprint=principal.credential_fingerprint,
                ttl_seconds=ttl_seconds,
                request_id=request_id,
                actor=_actor(principal),
            )

    def authenticate_browser_session(self, session_token: str) -> SessionRecord:
        with self._lock:
            return self.run_store.authenticate_session(session_token)

    def enforce_authentication_rate_limit(
        self,
        bucket_limits: Tuple[Tuple[str, int], ...],
        window_seconds: int,
    ) -> None:
        with self._lock:
            self.run_store.enforce_authentication_rate_limit(
                bucket_limits, window_seconds
            )

    def record_authentication_failure(
        self,
        bucket_limits: Tuple[Tuple[str, int], ...],
        window_seconds: int,
    ) -> None:
        with self._lock:
            self.run_store.record_authentication_failure(
                bucket_limits, window_seconds=window_seconds
            )

    def record_security_denial(
        self,
        principal: TenantPrincipal,
        request_id: str,
        reason: str,
        permission: str = "",
    ) -> None:
        if reason == "authorization":
            if not permission:
                raise ValueError("authorization denial requires a permission")
            action = "authorization.denied"
            resource_type = "permission"
            resource_id = permission
        elif reason == "csrf":
            action = "request.verification_denied"
            resource_type = "request"
            resource_id = "mutation"
        else:
            raise ValueError("unsupported security denial reason")
        with self._lock:
            self.run_store.append_audit(
                principal.tenant_id,
                AuditWrite(
                    request_id=request_id,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    actor=_actor(principal),
                    payload={
                        "reason": reason,
                        "auth_method": principal.auth_method,
                        "role": principal.role,
                    },
                ),
            )

    def verify_browser_csrf(self, session_id: str, csrf_token: str) -> None:
        with self._lock:
            self.run_store.verify_session_csrf(session_id, csrf_token)

    def resume_browser_session(self, session_id: str) -> SessionIssue:
        with self._lock:
            return self.run_store.rotate_session_csrf(session_id)

    def revoke_browser_session(self, principal: TenantPrincipal, request_id: str) -> None:
        with self._lock:
            self.run_store.revoke_session(
                tenant_id=principal.tenant_id,
                session_id=principal.session_id,
                request_id=request_id,
                actor=_actor(principal),
            )

    def start(
        self,
        tenant_id: str,
        request: BriefRequest,
        request_id: str,
        actor: str,
    ) -> ExecutionRun:
        brief = self._brief(request)
        run_id = stable_id("run", brief)
        with self._lock:
            if self.run_store.exists(tenant_id, run_id):
                raise ValueError("run already exists for tenant: {}".format(run_id))
            run = self._runtime_for(tenant_id).orchestrator.start(brief)
            return self.run_store.create(
                tenant_id,
                run,
                audit=AuditWrite(
                    request_id=request_id,
                    action="run.created",
                    resource_type="execution_run",
                    resource_id=run.run_id,
                    actor=actor,
                    payload={
                        "status": run.status.value,
                        "artifact_ids": [item.artifact_id for item in run.artifacts],
                        "platforms": [item.value for item in run.brief.platforms],
                        "budget_cents": run.brief.budget_cents,
                    },
                ),
            )

    def get(self, tenant_id: str, run_id: str) -> ExecutionRun:
        with self._lock:
            return self.run_store.get(tenant_id, run_id)

    def approve(
        self,
        tenant_id: str,
        run_id: str,
        request: GreenlightRequest,
        request_id: str,
        actor: str,
    ) -> ExecutionRun:
        return self._decide(tenant_id, run_id, request, request_id, actor, "approved")

    def reject(
        self,
        tenant_id: str,
        run_id: str,
        request: GreenlightRequest,
        request_id: str,
        actor: str,
    ) -> ExecutionRun:
        return self._decide(tenant_id, run_id, request, request_id, actor, "rejected")

    def _decide(
        self,
        tenant_id: str,
        run_id: str,
        request: GreenlightRequest,
        request_id: str,
        actor: str,
        decision: str,
    ) -> ExecutionRun:
        with self._lock:
            runtime = self._runtime_for(tenant_id)
            runtime.orchestrator.restore_run(self.run_store.get(tenant_id, run_id))
            if decision == "approved":
                run = runtime.orchestrator.approve(run_id, request.reviewer, request.note)
            else:
                run = runtime.orchestrator.reject(run_id, request.reviewer, request.note)
            greenlight = run.greenlight
            if greenlight is None:
                raise GreenlightError("Greenlight decision was not recorded")
            try:
                return self.run_store.save(
                    tenant_id,
                    run,
                    expected_status=RunStatus.AWAITING_GREENLIGHT.value,
                    audit=AuditWrite(
                        request_id=request_id,
                        action="greenlight.{}".format(decision),
                        resource_type="execution_run",
                        resource_id=run.run_id,
                        actor=actor,
                        payload={
                            "greenlight_id": greenlight.greenlight_id,
                            "decision": greenlight.decision.value,
                            "reviewer": greenlight.reviewer,
                            "note": greenlight.note,
                            "approved_artifact_ids": list(
                                greenlight.approved_artifact_ids
                            ),
                            "approved_artifact_hashes": list(
                                greenlight.approved_artifact_hashes
                            ),
                            "authorized_channels": [
                                item.value for item in greenlight.authorized_channels
                            ],
                            "authorized_budget_cents": (
                                greenlight.authorized_budget_cents
                            ),
                        },
                    ),
                )
            except RunStateConflictError as error:
                raise GreenlightError(
                    "Greenlight was already decided by another request"
                ) from error

    def audit_events(
        self, tenant_id: str, after_sequence: int, limit: int
    ) -> Tuple[AuditEvent, ...]:
        with self._lock:
            return self.run_store.audit_events(
                tenant_id=tenant_id, after_sequence=after_sequence, limit=limit
            )

    def close(self) -> None:
        with self._lock:
            for runtime in self._tenant_runtimes.values():
                runtime.memory.close()
            self._tenant_runtimes.clear()
            self.run_store.close()


def _run_document(run: ExecutionRun, tenant_id: str) -> Dict[str, object]:
    document = to_primitive(run)
    document["tenant_id"] = tenant_id
    document["sandbox"] = True
    document["external_side_effects_enabled"] = False
    return document


def _actor(principal: TenantPrincipal) -> str:
    prefix = "browser-session" if principal.auth_method == "session" else "api-key"
    return "{}:{}".format(prefix, principal.subject_id)


def _environment_bool(name: str, default: bool) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError("{} must be a boolean value".format(name))


def create_app(
    database_path: Optional[str] = None,
    database_url: Optional[str] = None,
    static_dir: Optional[Path] = None,
    tenant_api_keys: Optional[Mapping[str, str]] = None,
    identity_credentials: Optional[Sequence[Mapping[str, object]]] = None,
    session_cookie_secure: Optional[bool] = None,
    session_ttl_seconds: Optional[int] = None,
    login_max_failures: Optional[int] = None,
    login_source_max_failures: Optional[int] = None,
    login_window_seconds: Optional[int] = None,
    postgres_pool_min_size: Optional[int] = None,
    postgres_pool_max_size: Optional[int] = None,
    postgres_connect_timeout_seconds: Optional[float] = None,
    max_request_body_bytes: Optional[int] = None,
) -> FastAPI:
    db_path = database_path or os.environ.get("AGENCY_MEMORY_DB", ":memory:")
    db_url = (
        database_url.strip()
        if database_url is not None
        else os.environ.get("AGENCY_DATABASE_URL", "").strip()
    )
    pool_min_size = (
        int(os.environ.get("AGENCY_DATABASE_POOL_MIN_SIZE", "1"))
        if postgres_pool_min_size is None
        else postgres_pool_min_size
    )
    pool_max_size = (
        int(os.environ.get("AGENCY_DATABASE_POOL_MAX_SIZE", "10"))
        if postgres_pool_max_size is None
        else postgres_pool_max_size
    )
    connect_timeout_seconds = (
        float(os.environ.get("AGENCY_DATABASE_CONNECT_TIMEOUT_SECONDS", "15"))
        if postgres_connect_timeout_seconds is None
        else postgres_connect_timeout_seconds
    )
    cookie_name = os.environ.get("AGENCY_SESSION_COOKIE_NAME", "agency_session")
    cookie_secure = (
        _environment_bool("AGENCY_SESSION_COOKIE_SECURE", True)
        if session_cookie_secure is None
        else session_cookie_secure
    )
    ttl_seconds = (
        int(os.environ.get("AGENCY_SESSION_TTL_SECONDS", "28800"))
        if session_ttl_seconds is None
        else session_ttl_seconds
    )
    if ttl_seconds < 300 or ttl_seconds > 86400:
        raise ValueError("session ttl must be between 300 and 86400 seconds")
    max_failures = (
        int(os.environ.get("AGENCY_LOGIN_MAX_FAILURES", "5"))
        if login_max_failures is None
        else login_max_failures
    )
    source_max_failures = (
        int(os.environ.get("AGENCY_LOGIN_SOURCE_MAX_FAILURES", "50"))
        if login_source_max_failures is None
        else login_source_max_failures
    )
    rate_window_seconds = (
        int(os.environ.get("AGENCY_LOGIN_WINDOW_SECONDS", "300"))
        if login_window_seconds is None
        else login_window_seconds
    )
    if max_failures < 1 or max_failures > 100:
        raise ValueError("login max failures must be between 1 and 100")
    if source_max_failures < max_failures or source_max_failures > 10000:
        raise ValueError(
            "login source max failures must be between login max failures and 10000"
        )
    if rate_window_seconds < 10 or rate_window_seconds > 86400:
        raise ValueError("login window must be between 10 and 86400 seconds")
    body_limit = (
        int(
            os.environ.get(
                "AGENCY_MAX_REQUEST_BODY_BYTES",
                str(_DEFAULT_MAX_REQUEST_BODY_BYTES),
            )
        )
        if max_request_body_bytes is None
        else max_request_body_bytes
    )
    if body_limit < 1024 or body_limit > _MAX_CONFIGURED_REQUEST_BODY_BYTES:
        raise ValueError(
            "request body limit must be between 1024 and {} bytes".format(
                _MAX_CONFIGURED_REQUEST_BODY_BYTES
            )
        )

    if tenant_api_keys is not None or identity_credentials is not None:
        authenticator = TenantAuthenticator(
            tenant_api_keys=tenant_api_keys,
            identity_credentials=identity_credentials,
        )
    else:
        authenticator = TenantAuthenticator.from_environment(
            os.environ.get("AGENCY_TENANT_API_KEYS_JSON"),
            os.environ.get("AGENCY_IDENTITY_CREDENTIALS_JSON"),
        )

    service = RuntimeService(
        db_path,
        database_url=db_url or None,
        postgres_pool_min_size=pool_min_size,
        postgres_pool_max_size=pool_max_size,
        postgres_connect_timeout_seconds=connect_timeout_seconds,
    )
    metrics = RuntimeMetrics()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            yield
        finally:
            service.close()

    app = FastAPI(
        title="AI Native Content Agency API",
        version=VERSION,
        description=(
            "Tenant-scoped deterministic sandbox with individual RBAC, shared PostgreSQL "
            "state, durable rate limiting, HttpOnly browser sessions and audit evidence. No endpoint "
            "publishes content, spends "
            "budget, renders media, or contacts external services."
        ),
        lifespan=lifespan,
    )
    app.state.runtime_service = service
    app.state.authenticator = authenticator
    app.state.metrics = metrics
    app.state.session_cookie_name = cookie_name
    app.state.session_cookie_secure = cookie_secure
    bearer = HTTPBearer(auto_error=False)

    def _request_id(request: Request) -> str:
        return getattr(request.state, "request_id", request_id_from_header(None))

    @app.exception_handler(PublicApiError)
    async def public_api_error_handler(
        request: Request, error: PublicApiError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content=_error_body(error.code, str(error.detail), _request_id(request)),
            headers=error.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        sanitized = []
        for item in error.errors()[:20]:
            location = []
            for component in item.get("loc", ()):
                if isinstance(component, int):
                    location.append(component)
                else:
                    location.append(str(component)[:64])
            sanitized.append(
                {
                    "location": location,
                    "type": str(item.get("type", "validation_error"))[:128],
                }
            )
        content = _error_body(
            "request_validation_failed",
            "request validation failed",
            _request_id(request),
        )
        content["errors"] = sanitized
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=content,
        )

    @app.exception_handler(StarletteHTTPException)
    async def safe_http_error_handler(
        request: Request, error: StarletteHTTPException
    ) -> JSONResponse:
        code, detail = _SAFE_HTTP_ERRORS.get(
            error.status_code, ("request_failed", "request failed")
        )
        return JSONResponse(
            status_code=error.status_code,
            content=_error_body(code, detail, _request_id(request)),
            headers=error.headers,
        )

    @app.exception_handler(Exception)
    async def safe_internal_error_handler(
        request: Request, error: Exception
    ) -> JSONResponse:
        API_LOGGER.error(
            "api_internal_error request_id=%s exception_type=%s",
            _request_id(request),
            type(error).__name__,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body(
                "internal_error", "internal service error", _request_id(request)
            ),
        )

    app.add_middleware(RequestBodyLimitMiddleware, max_bytes=body_limit)
    app.state.max_request_body_bytes = body_limit

    @app.middleware("http")
    async def observe_http(request: Request, call_next):
        request_id = request_id_from_header(request.headers.get("X-Request-ID"))
        request.state.request_id = request_id
        timer = RequestTimer()
        response = None
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            elapsed = timer.elapsed_seconds()
            route_object = request.scope.get("route")
            route = getattr(route_object, "path", "unmatched")
            metrics.record_http(request.method, route, status_code, elapsed)
            structured_http_log(
                request_id=request_id,
                method=request.method,
                route=route,
                status_code=status_code,
                duration_ms=elapsed * 1000.0,
                tenant_id=getattr(request.state, "tenant_id", ""),
            )
            if response is not None:
                response.headers["X-Request-ID"] = request_id
                response.headers["X-Content-Type-Options"] = "nosniff"
                response.headers["X-Frame-Options"] = "DENY"
                response.headers["Referrer-Policy"] = "no-referrer"
                response.headers["Permissions-Policy"] = (
                    "camera=(), microphone=(), geolocation=()"
                )
                response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
                if request.url.path.startswith("/api/") or request.url.path in {
                    "/healthz",
                    "/readyz",
                    "/metrics",
                }:
                    response.headers["Cache-Control"] = "no-store"
                    response.headers["Pragma"] = "no-cache"

    def _authentication_buckets(
        request: Request, api_key: str
    ) -> Tuple[Tuple[str, int], ...]:
        source = request.client.host if request.client is not None else "unknown"
        credential_value = "credential:{}".format(
            TenantAuthenticator.fingerprint(api_key)
        )
        source_value = "source:{}".format(source)
        return (
            (
                hashlib.sha256(credential_value.encode("utf-8")).hexdigest(),
                max_failures,
            ),
            (
                hashlib.sha256(source_value.encode("utf-8")).hexdigest(),
                source_max_failures,
            ),
        )

    def _rate_limited_authenticate(request: Request, api_key: str) -> TenantPrincipal:
        buckets = _authentication_buckets(request, api_key)
        try:
            service.enforce_authentication_rate_limit(
                buckets, rate_window_seconds
            )
        except AuthenticationRateLimitError as error:
            metrics.authentication_attempt("rate_limited")
            raise PublicApiError(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                code="authentication_rate_limited",
                detail="authentication temporarily rate limited",
                headers={"Retry-After": str(error.retry_after_seconds)},
            ) from error
        try:
            principal = authenticator.authenticate(api_key)
        except AuthenticationError:
            try:
                service.record_authentication_failure(
                    buckets,
                    window_seconds=rate_window_seconds,
                )
            except AuthenticationRateLimitError as error:
                metrics.authentication_attempt("rate_limited")
                raise PublicApiError(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    code="authentication_rate_limited",
                    detail="authentication temporarily rate limited",
                    headers={"Retry-After": str(error.retry_after_seconds)},
                ) from error
            metrics.authentication_attempt("failed")
            raise
        metrics.authentication_attempt("succeeded")
        return principal

    def require_principal(
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    ) -> TenantPrincipal:
        if not authenticator.configured:
            raise PublicApiError(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="authentication_unavailable",
                detail="authentication is unavailable",
            )
        if credentials is not None:
            if credentials.scheme.lower() != "bearer":
                raise PublicApiError(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    code="authentication_failed",
                    detail="authentication failed",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            try:
                principal = _rate_limited_authenticate(
                    request, credentials.credentials
                )
            except AuthenticationError as error:
                raise PublicApiError(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    code="authentication_failed",
                    detail="authentication failed",
                    headers={"WWW-Authenticate": "Bearer"},
                ) from error
        else:
            session_token = request.cookies.get(cookie_name, "")
            try:
                session = service.authenticate_browser_session(session_token)
                principal = authenticator.resolve_active_session(
                    tenant_id=session.tenant_id,
                    subject_id=session.subject_id,
                    key_id=session.key_id,
                    credential_fingerprint=session.credential_fingerprint,
                    session_id=session.session_id,
                )
            except (SessionAuthenticationError, AuthenticationError) as error:
                raise PublicApiError(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    code="authentication_failed",
                    detail="authentication failed",
                    headers={"WWW-Authenticate": "Bearer"},
                ) from error
        request.state.tenant_id = principal.tenant_id
        request.state.subject_id = principal.subject_id
        request.state.role = principal.role
        request.state.auth_method = principal.auth_method
        request.state.session_id = principal.session_id
        return principal

    def _record_security_denial(
        request: Request,
        principal: TenantPrincipal,
        reason: str,
        permission: str = "",
    ) -> None:
        service.record_security_denial(
            principal=principal,
            request_id=request.state.request_id,
            reason=reason,
            permission=permission,
        )
        metrics.security_denial(reason)

    def require_mutation_principal(
        request: Request,
        principal: TenantPrincipal = Depends(require_principal),
    ) -> TenantPrincipal:
        if principal.auth_method == "session":
            try:
                service.verify_browser_csrf(
                    principal.session_id, request.headers.get("X-CSRF-Token", "")
                )
            except SessionCsrfError as error:
                _record_security_denial(request, principal, "csrf")
                raise PublicApiError(
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="request_verification_failed",
                    detail="request verification failed",
                ) from error
        return principal

    def _authorize(
        request: Request, principal: TenantPrincipal, permission: str
    ) -> TenantPrincipal:
        try:
            principal.require(permission)
        except AuthorizationError as error:
            _record_security_denial(
                request, principal, "authorization", permission=permission
            )
            raise PublicApiError(
                status_code=status.HTTP_403_FORBIDDEN,
                code="authorization_denied",
                detail="request not permitted",
            ) from error
        return principal

    def require_identity_reader(
        request: Request,
        principal: TenantPrincipal = Depends(require_principal),
    ) -> TenantPrincipal:
        return _authorize(request, principal, "identity:read")

    def require_run_reader(
        request: Request,
        principal: TenantPrincipal = Depends(require_principal),
    ) -> TenantPrincipal:
        return _authorize(request, principal, "runs:read")

    def require_audit_reader(
        request: Request,
        principal: TenantPrincipal = Depends(require_principal),
    ) -> TenantPrincipal:
        return _authorize(request, principal, "audit:read")

    def require_run_creator(
        request: Request,
        principal: TenantPrincipal = Depends(require_mutation_principal),
    ) -> TenantPrincipal:
        return _authorize(request, principal, "runs:create")

    def require_greenlight_approver(
        request: Request,
        principal: TenantPrincipal = Depends(require_mutation_principal),
    ) -> TenantPrincipal:
        return _authorize(request, principal, "greenlight:decide")

    @app.get("/healthz", tags=["operations"])
    def healthz() -> Dict[str, object]:
        return {
            "status": "ok",
            "version": VERSION,
            "runtime_mode": "deterministic_sandbox",
            "external_side_effects_enabled": False,
            "auth_configured": authenticator.configured,
            "individual_identity_configured": authenticator.individual_identity_configured,
        }

    @app.get("/readyz", tags=["operations"])
    def readyz() -> Dict[str, object]:
        if not authenticator.configured:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="tenant authentication is not configured",
            )
        try:
            service.check()
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="runtime storage is unavailable",
            ) from error
        return {
            "status": "ready",
            "version": VERSION,
            "auth_configured": True,
            "storage_backend": service.storage_backend,
            "shared_state": service.shared_state,
            "durable_run_store": service.shared_state or db_path != ":memory:",
            "individual_identity_configured": authenticator.individual_identity_configured,
            "login_rate_limit": {
                "credential_max_failures": max_failures,
                "source_max_failures": source_max_failures,
                "window_seconds": rate_window_seconds,
            },
        }

    @app.get("/metrics", tags=["operations"], include_in_schema=False)
    def prometheus_metrics() -> Response:
        return Response(
            content=metrics.render(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    @app.post(
        "/api/v1/sessions",
        status_code=status.HTTP_201_CREATED,
        tags=["authentication"],
    )
    def create_browser_session(
        request: Request,
        response: Response,
        session_request: BrowserSessionRequest,
    ) -> Dict[str, object]:
        if not authenticator.configured:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="tenant authentication is not configured",
            )
        try:
            principal = _rate_limited_authenticate(request, session_request.api_key)
        except AuthenticationError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid session credential",
            ) from error
        request.state.tenant_id = principal.tenant_id
        request.state.subject_id = principal.subject_id
        request.state.role = principal.role
        issue = service.create_browser_session(
            principal=principal,
            ttl_seconds=ttl_seconds,
            request_id=request.state.request_id,
        )
        response.set_cookie(
            key=cookie_name,
            value=issue.session_token,
            max_age=ttl_seconds,
            path="/",
            secure=cookie_secure,
            httponly=True,
            samesite="strict",
        )
        metrics.session_changed("created")
        return {
            "tenant_id": issue.tenant_id,
            "subject_id": issue.subject_id,
            "role": issue.role,
            "key_id": issue.key_id,
            "csrf_token": issue.csrf_token,
            "expires_at": issue.expires_at,
        }

    @app.get("/api/v1/sessions/current", tags=["authentication"])
    def resume_browser_session(
        principal: TenantPrincipal = Depends(require_principal),
    ) -> Dict[str, object]:
        if principal.auth_method != "session" or not principal.session_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="current browser session required",
            )
        try:
            issue = service.resume_browser_session(principal.session_id)
        except SessionAuthenticationError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)
            ) from error
        return {
            "tenant_id": issue.tenant_id,
            "subject_id": principal.subject_id,
            "role": principal.role,
            "key_id": principal.key_id,
            "csrf_token": issue.csrf_token,
            "expires_at": issue.expires_at,
        }

    @app.delete("/api/v1/sessions/current", tags=["authentication"])
    def revoke_browser_session(
        request: Request,
        response: Response,
        principal: TenantPrincipal = Depends(require_mutation_principal),
    ) -> Dict[str, object]:
        if principal.auth_method != "session" or not principal.session_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="current browser session required",
            )
        try:
            service.revoke_browser_session(principal, request.state.request_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        response.delete_cookie(
            key=cookie_name,
            path="/",
            secure=cookie_secure,
            httponly=True,
            samesite="strict",
        )
        metrics.session_changed("revoked")
        return {"status": "revoked"}

    @app.get("/api/v1/me", tags=["authentication"])
    def current_tenant(
        principal: TenantPrincipal = Depends(require_identity_reader),
    ) -> Dict[str, object]:
        return {
            "tenant_id": principal.tenant_id,
            "subject_id": principal.subject_id,
            "role": principal.role,
            "key_id": principal.key_id,
            "permissions": list(principal.permissions),
            "auth_method": principal.auth_method,
        }

    @app.get("/api/v1/audit-events", tags=["audit"])
    def list_audit_events(
        principal: TenantPrincipal = Depends(require_audit_reader),
        after_sequence: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=200),
    ) -> Dict[str, object]:
        events = service.audit_events(principal.tenant_id, after_sequence, limit + 1)
        page = events[:limit]
        return {
            "events": [to_primitive(item) for item in page],
            "next_after_sequence": page[-1].sequence if page else after_sequence,
            "has_more": len(events) > limit,
        }

    @app.post(
        "/api/v1/runs", status_code=status.HTTP_201_CREATED, tags=["runs"]
    )
    def create_run(
        request: Request,
        brief_request: BriefRequest,
        principal: TenantPrincipal = Depends(require_run_creator),
    ) -> Dict[str, object]:
        try:
            run = service.start(
                principal.tenant_id,
                brief_request,
                request.state.request_id,
                _actor(principal),
            )
            metrics.run_started()
            return _run_document(run, principal.tenant_id)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/api/v1/runs/{run_id}", tags=["runs"])
    def get_run(
        run_id: str,
        principal: TenantPrincipal = Depends(require_run_reader),
    ) -> Dict[str, object]:
        try:
            return _run_document(
                service.get(principal.tenant_id, run_id), principal.tenant_id
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post(
        "/api/v1/runs/{run_id}/greenlight/approve", tags=["greenlight"]
    )
    def approve_run(
        run_id: str,
        request: Request,
        decision_request: GreenlightRequest,
        principal: TenantPrincipal = Depends(require_greenlight_approver),
    ) -> Dict[str, object]:
        try:
            run = service.approve(
                principal.tenant_id,
                run_id,
                decision_request,
                request.state.request_id,
                _actor(principal),
            )
            metrics.greenlight_decided("approved")
            return _run_document(run, principal.tenant_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except GreenlightError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post(
        "/api/v1/runs/{run_id}/greenlight/reject", tags=["greenlight"]
    )
    def reject_run(
        run_id: str,
        request: Request,
        decision_request: GreenlightRequest,
        principal: TenantPrincipal = Depends(require_greenlight_approver),
    ) -> Dict[str, object]:
        try:
            run = service.reject(
                principal.tenant_id,
                run_id,
                decision_request,
                request.state.request_id,
                _actor(principal),
            )
            metrics.greenlight_decided("rejected")
            return _run_document(run, principal.tenant_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except GreenlightError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    resolved_static = static_dir or Path(
        os.environ.get("AGENCY_STATIC_DIR", "/app/dist")
    )
    if resolved_static.is_dir():
        assets = resolved_static / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            candidate = (resolved_static / path).resolve()
            if (
                path
                and candidate.is_file()
                and resolved_static.resolve() in candidate.parents
            ):
                return FileResponse(candidate)
            return FileResponse(resolved_static / "index.html")

    return app


def run() -> None:
    import uvicorn

    uvicorn.run(
        "agency_runtime.api:app",
        host=os.environ.get("AGENCY_HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8080")),
        proxy_headers=True,
        forwarded_allow_ips=os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1"),
    )


app = create_app()
