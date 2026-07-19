from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Mapping, Optional, Protocol, Tuple, runtime_checkable

from agency_runtime.models import Artifact, ExecutionRun

from .auth import IdentityContext
from .contracts import ApprovalDecision, MissionCreate, MissionResponse, RunResponse


@dataclass(frozen=True)
class MissionRecord:
    mission_id: str
    title: str
    objective: str
    audience: str
    platforms: Tuple[str, ...]
    budget_cents: int
    source_asset: str
    campaign_goal: str


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    status: str
    artifact_manifest_hash: str
    policy_version: str
    version: int


@dataclass(frozen=True)
class ApprovalRecord:
    approval_id: str


@runtime_checkable
class ControlPlaneRepository(Protocol):
    """Provider-neutral transactional port consumed by the application service."""

    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def flush(self) -> None: ...
    def ping(self) -> None: ...

    def ensure_identity(self, identity: IdentityContext, now: datetime) -> None: ...

    def idempotent_response(
        self,
        tenant_id: str,
        key: str,
        operation: str,
        request_hash: str,
    ) -> Optional[Tuple[int, Dict[str, object]]]: ...

    def record_idempotency(
        self,
        identity: IdentityContext,
        key: str,
        operation: str,
        request_hash: str,
        status_code: int,
        response_payload: Mapping[str, object],
        now: datetime,
    ) -> None: ...

    def create_mission(
        self,
        identity: IdentityContext,
        request: MissionCreate,
        now: datetime,
    ) -> MissionResponse: ...

    def get_mission(self, tenant_id: str, mission_id: str) -> MissionRecord: ...

    def persist_workflow_run(
        self,
        identity: IdentityContext,
        mission_id: str,
        execution: ExecutionRun,
        correlation_id: str,
        now: datetime,
    ) -> RunResponse: ...

    def get_run(self, tenant_id: str, run_id: str) -> RunResponse: ...
    def run_for_update(self, tenant_id: str, run_id: str) -> RunRecord: ...
    def mission_for_run(self, tenant_id: str, run_id: str) -> MissionRecord: ...
    def approval_exists(self, tenant_id: str, run_id: str) -> bool: ...

    def current_manifest_hash(
        self,
        tenant_id: str,
        run_id: str,
        *,
        for_update: bool = False,
    ) -> str: ...

    def risk_passed(self, tenant_id: str, run_id: str) -> bool: ...
    def runtime_artifacts(self, tenant_id: str, run_id: str) -> Tuple[Artifact, ...]: ...

    def claim_approval_transition(
        self,
        tenant_id: str,
        run_id: str,
        current_version: int,
        next_status: str,
        now: datetime,
    ) -> bool: ...

    def add_approval(
        self,
        identity: IdentityContext,
        run_id: str,
        decision: ApprovalDecision,
        reviewer: str,
        note: str,
        manifest_hash: str,
        policy_version: str,
        now: datetime,
    ) -> ApprovalRecord: ...

    def finalize_publisher_rejection(
        self,
        tenant_id: str,
        run_id: str,
        now: datetime,
    ) -> None: ...

    def finalize_publisher_approval(
        self,
        tenant_id: str,
        run_id: str,
        artifact: Artifact,
        evidence: Mapping[str, object],
        now: datetime,
    ) -> None: ...

    def add_audit(
        self,
        identity: IdentityContext,
        action: str,
        payload: Mapping[str, object],
        correlation_id: str,
        now: datetime,
        run_id: Optional[str] = None,
    ) -> None: ...
