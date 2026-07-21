from __future__ import annotations

import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Dict, List, Mapping, Optional, Tuple

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .auth import AuthenticationError, TenantAuthenticator, TenantPrincipal
from .memory import SQLiteMemory
from .models import ExecutionRun, MissionBrief, Platform
from .observability import (
    RequestTimer,
    RuntimeMetrics,
    request_id_from_header,
    structured_http_log,
)
from .orchestrator import AgencyOrchestrator, GreenlightError
from .persistence import AuditEvent, AuditWrite, SQLiteRunStore
from .tools import build_sandbox_toolset
from .utils import stable_id, to_primitive


class BriefRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=4000)
    audience: str = Field(min_length=1, max_length=1000)
    platforms: List[Platform] = Field(min_length=1)
    budget_cents: int = Field(default=0, ge=0)
    source_asset: str = Field(
        default="sandbox://brief/no-external-asset", max_length=2000
    )
    campaign_goal: str = Field(default="awareness", min_length=1, max_length=200)


class GreenlightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reviewer: str = Field(min_length=1, max_length=200)
    note: str = Field(default="", max_length=2000)


@dataclass
class TenantRuntime:
    memory: SQLiteMemory
    orchestrator: AgencyOrchestrator


class RuntimeService:
    """Tenant-scoped durable service boundary for the sandbox runtime."""

    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        self.run_store = SQLiteRunStore(database_path)
        self._tenant_runtimes: Dict[str, TenantRuntime] = {}
        self._lock = RLock()

    def _runtime_for(self, tenant_id: str) -> TenantRuntime:
        runtime = self._tenant_runtimes.get(tenant_id)
        if runtime is None:
            memory = SQLiteMemory(self.database_path, namespace=tenant_id)
            runtime = TenantRuntime(
                memory=memory,
                orchestrator=AgencyOrchestrator(build_sandbox_toolset(), memory),
            )
            self._tenant_runtimes[tenant_id] = runtime
        return runtime

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
        return self._decide(
            tenant_id=tenant_id,
            run_id=run_id,
            request=request,
            request_id=request_id,
            actor=actor,
            decision="approved",
        )

    def reject(
        self,
        tenant_id: str,
        run_id: str,
        request: GreenlightRequest,
        request_id: str,
        actor: str,
    ) -> ExecutionRun:
        return self._decide(
            tenant_id=tenant_id,
            run_id=run_id,
            request=request,
            request_id=request_id,
            actor=actor,
            decision="rejected",
        )

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
                run = runtime.orchestrator.approve(
                    run_id, request.reviewer, request.note
                )
            else:
                run = runtime.orchestrator.reject(
                    run_id, request.reviewer, request.note
                )
            greenlight = run.greenlight
            if greenlight is None:
                raise GreenlightError("Greenlight decision was not recorded")
            return self.run_store.save(
                tenant_id,
                run,
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

    def audit_events(
        self,
        tenant_id: str,
        after_sequence: int,
        limit: int,
    ) -> Tuple[AuditEvent, ...]:
        with self._lock:
            return self.run_store.audit_events(
                tenant_id=tenant_id,
                after_sequence=after_sequence,
                limit=limit,
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
    return "tenant-key:{}".format(principal.credential_fingerprint)


def create_app(
    database_path: Optional[str] = None,
    static_dir: Optional[Path] = None,
    tenant_api_keys: Optional[Mapping[str, str]] = None,
) -> FastAPI:
    db_path = database_path or os.environ.get("AGENCY_MEMORY_DB", ":memory:")
    service = RuntimeService(db_path)
    metrics = RuntimeMetrics()
    authenticator = (
        TenantAuthenticator(tenant_api_keys)
        if tenant_api_keys is not None
        else TenantAuthenticator.from_json(
            os.environ.get("AGENCY_TENANT_API_KEYS_JSON")
        )
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            yield
        finally:
            service.close()

    app = FastAPI(
        title="AI Native Content Agency API",
        version="0.4.0",
        description=(
            "Tenant-scoped deterministic sandbox with durable audit evidence. "
            "No endpoint publishes content, spends budget, renders media, or "
            "contacts external services."
        ),
        lifespan=lifespan,
    )
    app.state.runtime_service = service
    app.state.authenticator = authenticator
    app.state.metrics = metrics
    bearer = HTTPBearer(auto_error=False)

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

    def require_principal(
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    ) -> TenantPrincipal:
        if not authenticator.configured:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="tenant authentication is not configured",
            )
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="bearer credential required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            principal = authenticator.authenticate(credentials.credentials)
        except AuthenticationError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(error),
                headers={"WWW-Authenticate": "Bearer"},
            ) from error
        request.state.tenant_id = principal.tenant_id
        return principal

    @app.get("/healthz", tags=["operations"])
    def healthz() -> Dict[str, object]:
        return {
            "status": "ok",
            "runtime_mode": "deterministic_sandbox",
            "external_side_effects_enabled": False,
            "auth_configured": authenticator.configured,
        }

    @app.get("/readyz", tags=["operations"])
    def readyz() -> Dict[str, object]:
        if not authenticator.configured:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="tenant authentication is not configured",
            )
        return {
            "status": "ready",
            "auth_configured": True,
            "durable_run_store": db_path != ":memory:",
        }

    @app.get("/metrics", tags=["operations"], include_in_schema=False)
    def prometheus_metrics() -> Response:
        return Response(
            content=metrics.render(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    @app.get("/api/v1/me", tags=["authentication"])
    def current_tenant(
        principal: TenantPrincipal = Depends(require_principal),
    ) -> Dict[str, object]:
        return {"tenant_id": principal.tenant_id}

    @app.get("/api/v1/audit-events", tags=["audit"])
    def list_audit_events(
        principal: TenantPrincipal = Depends(require_principal),
        after_sequence: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=200),
    ) -> Dict[str, object]:
        events = service.audit_events(
            principal.tenant_id, after_sequence, limit + 1
        )
        page = events[:limit]
        return {
            "events": [to_primitive(item) for item in page],
            "next_after_sequence": (
                page[-1].sequence if page else after_sequence
            ),
            "has_more": len(events) > limit,
        }

    @app.post(
        "/api/v1/runs", status_code=status.HTTP_201_CREATED, tags=["runs"]
    )
    def create_run(
        request: Request,
        brief_request: BriefRequest,
        principal: TenantPrincipal = Depends(require_principal),
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
        principal: TenantPrincipal = Depends(require_principal),
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
        principal: TenantPrincipal = Depends(require_principal),
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
        principal: TenantPrincipal = Depends(require_principal),
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
    )


app = create_app()
