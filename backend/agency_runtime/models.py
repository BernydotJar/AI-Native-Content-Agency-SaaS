from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Mapping, Optional, Tuple

from .utils import require_confidence, require_non_empty


class Platform(str, Enum):
    X = "x"
    FACEBOOK = "facebook"
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"


class AgentRole(str, Enum):
    CEO = "ceo"
    RESEARCH = "research"
    STRATEGIST = "strategist"
    GROWTH = "growth"
    WRITER = "writer"
    MEDIA = "media"
    RISK = "risk"
    PUBLISHER = "publisher"


AGENT_SEQUENCE: Tuple[AgentRole, ...] = (
    AgentRole.CEO,
    AgentRole.RESEARCH,
    AgentRole.STRATEGIST,
    AgentRole.GROWTH,
    AgentRole.WRITER,
    AgentRole.MEDIA,
    AgentRole.RISK,
    AgentRole.PUBLISHER,
)


class AgentStatus(str, Enum):
    STANDBY = "standby"
    PROCESSING = "processing"
    READY = "ready"
    WAITING_GREENLIGHT = "waiting_greenlight"
    BLOCKED = "blocked"
    ATTENTION = "attention"


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_GREENLIGHT = "awaiting_greenlight"
    COMPLETED = "completed"
    REJECTED = "rejected"
    REVOKED = "revoked"
    FAILED = "failed"


class GreenlightDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class Provenance:
    source: str
    locator: str
    observed_at: str
    tool: str = "human"
    trace_id: str = ""

    def __post_init__(self) -> None:
        require_non_empty(self.source, "source")
        require_non_empty(self.locator, "locator")
        require_non_empty(self.observed_at, "observed_at")
        require_non_empty(self.tool, "tool")


@dataclass(frozen=True)
class MissionBrief:
    title: str
    objective: str
    audience: str
    platforms: Tuple[Platform, ...]
    budget_cents: int = 0
    source_asset: str = "sandbox://brief/no-external-asset"
    campaign_goal: str = "awareness"

    def __post_init__(self) -> None:
        require_non_empty(self.title, "title")
        require_non_empty(self.objective, "objective")
        require_non_empty(self.audience, "audience")
        if not self.platforms:
            raise ValueError("platforms must contain at least one platform")
        if self.budget_cents < 0:
            raise ValueError("budget_cents must not be negative")


@dataclass(frozen=True)
class ToolEvidence:
    evidence_id: str
    tool: str
    operation: str
    sandbox: bool
    summary: str
    payload: Mapping[str, object]
    references: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Artifact:
    artifact_id: str
    kind: str
    title: str
    created_by: AgentRole
    payload: Mapping[str, object]
    evidence_ids: Tuple[str, ...] = ()


@dataclass
class AgentState:
    role: AgentRole
    status: AgentStatus = AgentStatus.STANDBY
    progress: int = 0
    detail: str = "Awaiting mission"
    artifact_ids: List[str] = field(default_factory=list)

    def update(self, status: AgentStatus, progress: int, detail: str) -> None:
        if progress < 0 or progress > 100:
            raise ValueError("progress must be between 0 and 100")
        self.status = status
        self.progress = progress
        self.detail = detail


@dataclass(frozen=True)
class TraceEvent:
    sequence: int
    timestamp: str
    role: AgentRole
    action: str
    status: str
    detail: str
    artifact_ids: Tuple[str, ...] = ()
    evidence_ids: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Greenlight:
    greenlight_id: str
    run_id: str
    decision: GreenlightDecision
    reviewer: str
    note: str
    decided_at: str
    approved_artifact_ids: Tuple[str, ...] = ()
    approved_artifact_hashes: Tuple[str, ...] = ()
    authorized_channels: Tuple[Platform, ...] = ()
    authorized_budget_cents: int = 0
    fencing_token: int = 1
    revoked_at: Optional[str] = None
    revoked_by: str = ""
    revocation_reason: str = ""

    def __post_init__(self) -> None:
        require_non_empty(self.reviewer, "reviewer")
        require_non_empty(self.decided_at, "decided_at")
        if len(self.approved_artifact_ids) != len(self.approved_artifact_hashes):
            raise ValueError("approved artifact ids and hashes must have equal length")
        if self.authorized_budget_cents < 0:
            raise ValueError("authorized_budget_cents must not be negative")
        if self.fencing_token < 1:
            raise ValueError("fencing_token must be positive")
        if self.revoked_at is None:
            if self.revoked_by or self.revocation_reason:
                raise ValueError("active Greenlight cannot contain revocation metadata")
        else:
            require_non_empty(self.revoked_by, "revoked_by")
            require_non_empty(self.revocation_reason, "revocation_reason")

    @property
    def active(self) -> bool:
        return (
            self.decision is GreenlightDecision.APPROVED
            and self.revoked_at is None
        )


@dataclass
class RunExecution:
    state: str = "inline"
    next_station: str = "ceo"
    lease_owner: str = ""
    lease_expires_at: Optional[str] = None
    fencing_token: int = 0
    attempts: int = 0
    checkpointed_at: Optional[str] = None
    failure_detail: str = ""

    def __post_init__(self) -> None:
        if self.state not in {
            "inline", "queued", "leased", "running",
            "awaiting_greenlight", "completed", "failed"
        }:
            raise ValueError("run execution state is invalid")
        if self.fencing_token < 0 or self.attempts < 0:
            raise ValueError("run execution counters must not be negative")
        if self.lease_owner and self.lease_expires_at is None:
            raise ValueError("run execution lease requires an expiry")

@dataclass
class ExecutionRun:
    run_id: str
    brief: MissionBrief
    status: RunStatus
    started_at: str
    agent_states: Dict[AgentRole, AgentState]
    artifacts: List[Artifact] = field(default_factory=list)
    evidence: List[ToolEvidence] = field(default_factory=list)
    trace: List[TraceEvent] = field(default_factory=list)
    greenlight: Optional[Greenlight] = None
    completed_at: Optional[str] = None
    execution: RunExecution = field(default_factory=RunExecution)

    def state_for(self, role: AgentRole) -> AgentState:
        return self.agent_states[role]

    def add_artifact(self, artifact: Artifact) -> None:
        self.artifacts.append(artifact)
        self.state_for(artifact.created_by).artifact_ids.append(artifact.artifact_id)

    def artifact(self, kind: str) -> Artifact:
        for item in reversed(self.artifacts):
            if item.kind == kind:
                return item
        raise KeyError("artifact kind not found: {}".format(kind))


@dataclass(frozen=True)
class MemoryObservation:
    observation_id: str
    content: str
    provenance: Provenance
    confidence: float
    tags: Tuple[str, ...]
    observed_at: str

    def __post_init__(self) -> None:
        require_non_empty(self.content, "content")
        require_confidence(self.confidence)


@dataclass(frozen=True)
class MemoryRecord:
    memory_id: str
    content: str
    provenance: Provenance
    confidence: float
    tags: Tuple[str, ...]
    observed_at: str
    stored_at: str


@dataclass(frozen=True)
class MemorySearchResult:
    record: MemoryRecord
    score: float
