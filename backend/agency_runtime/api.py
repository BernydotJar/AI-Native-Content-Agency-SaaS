from __future__ import annotations

import os
from pathlib import Path
from threading import RLock
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .memory import SQLiteMemory
from .models import ExecutionRun, MissionBrief, Platform
from .orchestrator import AgencyOrchestrator, GreenlightError
from .tools import build_sandbox_toolset
from .utils import to_primitive


class BriefRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=4000)
    audience: str = Field(min_length=1, max_length=1000)
    platforms: List[Platform] = Field(min_length=1)
    budget_cents: int = Field(default=0, ge=0)
    source_asset: str = Field(default="sandbox://brief/no-external-asset", max_length=2000)
    campaign_goal: str = Field(default="awareness", min_length=1, max_length=200)


class GreenlightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reviewer: str = Field(min_length=1, max_length=200)
    note: str = Field(default="", max_length=2000)


class RuntimeService:
    """Process-local service boundary for the deterministic sandbox runtime."""

    def __init__(self, database_path: str) -> None:
        self.memory = SQLiteMemory(database_path)
        self.orchestrator = AgencyOrchestrator(build_sandbox_toolset(), self.memory)
        self._lock = RLock()

    def start(self, request: BriefRequest) -> ExecutionRun:
        brief = MissionBrief(
            title=request.title,
            objective=request.objective,
            audience=request.audience,
            platforms=tuple(request.platforms),
            budget_cents=request.budget_cents,
            source_asset=request.source_asset,
            campaign_goal=request.campaign_goal,
        )
        with self._lock:
            return self.orchestrator.start(brief)

    def get(self, run_id: str) -> ExecutionRun:
        with self._lock:
            return self.orchestrator.get_run(run_id)

    def approve(self, run_id: str, request: GreenlightRequest) -> ExecutionRun:
        with self._lock:
            return self.orchestrator.approve(run_id, request.reviewer, request.note)

    def reject(self, run_id: str, request: GreenlightRequest) -> ExecutionRun:
        with self._lock:
            return self.orchestrator.reject(run_id, request.reviewer, request.note)


def _run_document(run: ExecutionRun) -> Dict[str, object]:
    document = to_primitive(run)
    document["sandbox"] = True
    document["external_side_effects_enabled"] = False
    return document


def create_app(database_path: Optional[str] = None, static_dir: Optional[Path] = None) -> FastAPI:
    db_path = database_path or os.environ.get("AGENCY_MEMORY_DB", ":memory:")
    service = RuntimeService(db_path)
    app = FastAPI(
        title="AI Native Content Agency API",
        version="0.2.0",
        description=(
            "Network-addressable deterministic sandbox. No endpoint publishes content, "
            "spends budget, renders media, or contacts external services."
        ),
    )
    app.state.runtime_service = service

    @app.get("/healthz", tags=["operations"])
    def healthz() -> Dict[str, object]:
        return {
            "status": "ok",
            "runtime_mode": "deterministic_sandbox",
            "external_side_effects_enabled": False,
        }

    @app.post("/api/v1/runs", status_code=status.HTTP_201_CREATED, tags=["runs"])
    def create_run(request: BriefRequest) -> Dict[str, object]:
        try:
            return _run_document(service.start(request))
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/api/v1/runs/{run_id}", tags=["runs"])
    def get_run(run_id: str) -> Dict[str, object]:
        try:
            return _run_document(service.get(run_id))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post("/api/v1/runs/{run_id}/greenlight/approve", tags=["greenlight"])
    def approve_run(run_id: str, request: GreenlightRequest) -> Dict[str, object]:
        try:
            return _run_document(service.approve(run_id, request))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except GreenlightError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/api/v1/runs/{run_id}/greenlight/reject", tags=["greenlight"])
    def reject_run(run_id: str, request: GreenlightRequest) -> Dict[str, object]:
        try:
            return _run_document(service.reject(run_id, request))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except GreenlightError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    resolved_static = static_dir or Path(os.environ.get("AGENCY_STATIC_DIR", "/app/dist"))
    if resolved_static.is_dir():
        assets = resolved_static / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            candidate = (resolved_static / path).resolve()
            if path and candidate.is_file() and resolved_static.resolve() in candidate.parents:
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
