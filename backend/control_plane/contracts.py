from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


SCHEMA_VERSION: Literal["v1"] = "v1"
POLICY_VERSION: Literal["greenlight.v1"] = "greenlight.v1"


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Platform(str, Enum):
    X = "x"
    FACEBOOK = "facebook"
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"


class ApprovalDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class AgentRole(str, Enum):
    CEO = "ceo"
    RESEARCH = "research"
    STRATEGIST = "strategist"
    GROWTH = "growth"
    WRITER = "writer"
    MEDIA = "media"
    RISK = "risk"
    PUBLISHER = "publisher"


class AgentStatus(str, Enum):
    STANDBY = "standby"
    PROCESSING = "processing"
    READY = "ready"
    WAITING_GREENLIGHT = "waiting_greenlight"
    BLOCKED = "blocked"
    ATTENTION = "attention"


class RunStatus(str, Enum):
    RUNNING = "running"
    AWAITING_GREENLIGHT = "awaiting_greenlight"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"


class MissionCreate(StrictContract):
    schema_version: Literal["v1"]
    title: str = Field(min_length=1, max_length=160)
    objective: str = Field(min_length=1, max_length=4000)
    audience: str = Field(min_length=1, max_length=500)
    platforms: List[Platform] = Field(min_length=1, max_length=4)
    budget_cents: int = Field(default=0, ge=0, le=100_000_000)
    source_asset: str = Field(
        default="sandbox://brief/no-external-asset",
        min_length=1,
        max_length=1000,
    )
    campaign_goal: str = Field(default="awareness", min_length=1, max_length=120)

    @field_validator("title", "objective", "audience", "campaign_goal")
    @classmethod
    def reject_blank_values(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("platforms")
    @classmethod
    def require_distinct_platforms(cls, value: List[Platform]) -> List[Platform]:
        if len(set(value)) != len(value):
            raise ValueError("platforms must not contain duplicates")
        return value

    @field_validator("source_asset")
    @classmethod
    def sandbox_assets_only(cls, value: str) -> str:
        if not value.startswith("sandbox://"):
            raise ValueError("only sandbox:// source assets are accepted in V1")
        return value


class RunStart(StrictContract):
    schema_version: Literal["v1"]


class ApprovalCreate(StrictContract):
    schema_version: Literal["v1"]
    decision: ApprovalDecision
    reviewer: str = Field(min_length=1, max_length=160)
    note: str = Field(default="", max_length=2000)
    artifact_manifest_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    policy_version: Literal["greenlight.v1"]

    @field_validator("reviewer")
    @classmethod
    def reviewer_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("reviewer must not be blank")
        return normalized


class MissionResponse(StrictContract):
    schema_version: Literal["v1"]
    mission_id: str
    tenant_id: str
    created_by: str
    title: str
    objective: str
    audience: str
    platforms: List[Platform]
    budget_cents: int
    source_asset: str
    campaign_goal: str
    created_at: datetime
    version: int


class RunStepResponse(StrictContract):
    schema_version: Literal["v1"]
    step_id: str
    role: AgentRole
    sequence: int
    status: AgentStatus
    progress: int
    detail: str
    updated_at: datetime


class ArtifactResponse(StrictContract):
    schema_version: Literal["v1"]
    artifact_id: str
    kind: str
    title: str
    created_by: AgentRole
    payload: Dict[str, Any]
    evidence_ids: List[str]
    ordinal: int
    created_at: datetime


class ToolEvidenceResponse(StrictContract):
    schema_version: Literal["v1"]
    evidence_id: str
    tool: str
    operation: str
    sandbox: bool
    summary: str
    payload: Dict[str, Any]
    references: List[str]
    created_at: datetime


class RunEventResponse(StrictContract):
    schema_version: Literal["v1"]
    event_id: str
    sequence: int
    timestamp: datetime
    role: AgentRole
    action: str
    status: AgentStatus
    detail: str
    artifact_ids: List[str]
    evidence_ids: List[str]


class AuditEventResponse(StrictContract):
    schema_version: Literal["v1"]
    audit_id: str
    principal_id: str
    action: str
    payload: Dict[str, Any]
    correlation_id: str
    occurred_at: datetime


class ApprovalResponse(StrictContract):
    schema_version: Literal["v1"]
    approval_id: str
    idempotency_key: str
    decision: ApprovalDecision
    reviewer: str
    note: str
    artifact_manifest_hash: str
    policy_version: Literal["greenlight.v1"]
    principal_id: str
    decided_at: datetime


class TenantIdentityResponse(StrictContract):
    schema_version: Literal["v1"]
    tenant_id: str


class PrincipalIdentityResponse(StrictContract):
    schema_version: Literal["v1"]
    tenant_id: str
    principal_id: str
    auth_mode: str


class IdentityResponse(StrictContract):
    schema_version: Literal["v1"]
    tenant: TenantIdentityResponse
    principal: PrincipalIdentityResponse


class RunResponse(StrictContract):
    schema_version: Literal["v1"]
    run_id: str
    mission_id: str
    tenant_id: str
    status: RunStatus
    artifact_manifest_hash: str
    policy_version: Literal["greenlight.v1"]
    external_side_effects: bool
    started_at: datetime
    completed_at: Optional[datetime]
    version: int
    steps: List[RunStepResponse]
    artifacts: List[ArtifactResponse]
    evidence: List[ToolEvidenceResponse]
    events: List[RunEventResponse]
    audit_events: List[AuditEventResponse]
    approval: Optional[ApprovalResponse]


class HealthResponse(StrictContract):
    schema_version: Literal["v1"]
    status: Literal["ok", "ready"]


class ErrorBody(StrictContract):
    code: str
    message: str
    correlation_id: str
    details: Dict[str, Any]


class ErrorResponse(StrictContract):
    schema_version: Literal["v1"]
    error: ErrorBody
