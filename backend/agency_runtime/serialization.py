from __future__ import annotations

from typing import Dict, Mapping, Optional

from .models import (
    AgentRole,
    AgentState,
    AgentStatus,
    Artifact,
    ExecutionRun,
    Greenlight,
    GreenlightDecision,
    MissionBrief,
    Platform,
    RunExecution,
    RunStatus,
    ToolEvidence,
    TraceEvent,
)
from .utils import to_primitive


def execution_run_to_document(run: ExecutionRun) -> Dict[str, object]:
    return to_primitive(run)


def execution_run_from_document(document: Mapping[str, object]) -> ExecutionRun:
    brief_data = _mapping(document["brief"])
    brief = MissionBrief(
        title=str(brief_data["title"]),
        objective=str(brief_data["objective"]),
        audience=str(brief_data["audience"]),
        platforms=tuple(Platform(value) for value in brief_data["platforms"]),
        budget_cents=int(brief_data.get("budget_cents", 0)),
        source_asset=str(
            brief_data.get("source_asset", "sandbox://brief/no-external-asset")
        ),
        campaign_goal=str(brief_data.get("campaign_goal", "awareness")),
        campaign_type=str(brief_data.get("campaign_type", "commercial")),
        publication_mode=str(brief_data.get("publication_mode", "organic")),
        locale=str(brief_data.get("locale", "es-GT")),
        jurisdiction=str(brief_data.get("jurisdiction", "")),
        office=str(brief_data.get("office", "")),
        candidate_name=str(brief_data.get("candidate_name", "")),
        locality=str(brief_data.get("locality", "")),
        problem=str(brief_data.get("problem", "")),
        proposal=str(brief_data.get("proposal", "")),
        desired_action=str(brief_data.get("desired_action", "")),
        disclosure=str(brief_data.get("disclosure", "")),
        legal_review_status=str(brief_data.get("legal_review_status", "pending")),
        legal_reviewed_by=str(brief_data.get("legal_reviewed_by", "")),
        evidence_claims=tuple(
            {
                "statement": str(_mapping(item).get("statement", "")),
                "source": str(_mapping(item).get("source", "")),
                "locator": str(_mapping(item).get("locator", "")),
                "verification_status": str(
                    _mapping(item).get("verification_status", "unverified")
                ),
                "reviewed_by": str(_mapping(item).get("reviewed_by", "")),
            }
            for item in brief_data.get("evidence_claims", [])
        ),
    )

    states_data = _mapping(document["agent_states"])
    states = {}
    for role_value, raw_state in states_data.items():
        state_data = _mapping(raw_state)
        role = AgentRole(role_value)
        states[role] = AgentState(
            role=role,
            status=AgentStatus(str(state_data["status"])),
            progress=int(state_data["progress"]),
            detail=str(state_data["detail"]),
            artifact_ids=list(state_data.get("artifact_ids", [])),
        )

    artifacts = [
        Artifact(
            artifact_id=str(item["artifact_id"]),
            kind=str(item["kind"]),
            title=str(item["title"]),
            created_by=AgentRole(str(item["created_by"])),
            payload=_mapping(item["payload"]),
            evidence_ids=tuple(item.get("evidence_ids", [])),
        )
        for item in (_mapping(value) for value in document.get("artifacts", []))
    ]
    evidence = [
        ToolEvidence(
            evidence_id=str(item["evidence_id"]),
            tool=str(item["tool"]),
            operation=str(item["operation"]),
            sandbox=bool(item["sandbox"]),
            summary=str(item["summary"]),
            payload=_mapping(item["payload"]),
            references=tuple(item.get("references", [])),
        )
        for item in (_mapping(value) for value in document.get("evidence", []))
    ]
    trace = [
        TraceEvent(
            sequence=int(item["sequence"]),
            timestamp=str(item["timestamp"]),
            role=AgentRole(str(item["role"])),
            action=str(item["action"]),
            status=str(item["status"]),
            detail=str(item["detail"]),
            artifact_ids=tuple(item.get("artifact_ids", [])),
            evidence_ids=tuple(item.get("evidence_ids", [])),
        )
        for item in (_mapping(value) for value in document.get("trace", []))
    ]

    raw_greenlight = document.get("greenlight")
    greenlight: Optional[Greenlight] = None
    if raw_greenlight is not None:
        item = _mapping(raw_greenlight)
        greenlight = Greenlight(
            greenlight_id=str(item["greenlight_id"]),
            run_id=str(item["run_id"]),
            decision=GreenlightDecision(str(item["decision"])),
            reviewer=str(item["reviewer"]),
            note=str(item.get("note", "")),
            decided_at=str(item["decided_at"]),
            approved_artifact_ids=tuple(item.get("approved_artifact_ids", [])),
            approved_artifact_hashes=tuple(item.get("approved_artifact_hashes", [])),
            authorized_channels=tuple(
                Platform(value) for value in item.get("authorized_channels", [])
            ),
            authorized_budget_cents=int(item.get("authorized_budget_cents", 0)),
            fencing_token=int(item.get("fencing_token", 1)),
            revoked_at=(
                str(item["revoked_at"])
                if item.get("revoked_at") is not None
                else None
            ),
            revoked_by=str(item.get("revoked_by", "")),
            revocation_reason=str(item.get("revocation_reason", "")),
        )

    raw_execution = document.get("execution")
    if raw_execution is None:
        execution = RunExecution()
    else:
        execution_data = _mapping(raw_execution)
        execution = RunExecution(
            state=str(execution_data.get("state", "inline")),
            next_station=str(execution_data.get("next_station", "ceo")),
            lease_owner=str(execution_data.get("lease_owner", "")),
            lease_expires_at=(
                str(execution_data["lease_expires_at"])
                if execution_data.get("lease_expires_at") is not None
                else None
            ),
            fencing_token=int(execution_data.get("fencing_token", 0)),
            attempts=int(execution_data.get("attempts", 0)),
            checkpointed_at=(
                str(execution_data["checkpointed_at"])
                if execution_data.get("checkpointed_at") is not None
                else None
            ),
            failure_detail=str(execution_data.get("failure_detail", "")),
        )

    return ExecutionRun(
        run_id=str(document["run_id"]),
        brief=brief,
        status=RunStatus(str(document["status"])),
        started_at=str(document["started_at"]),
        agent_states=states,
        artifacts=artifacts,
        evidence=evidence,
        trace=trace,
        greenlight=greenlight,
        execution=execution,
        completed_at=(
            str(document["completed_at"])
            if document.get("completed_at") is not None
            else None
        ),
    )


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("persisted runtime document contains a non-object value")
    return value
