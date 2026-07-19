from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, cast

from sqlalchemy import Select, func, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agency_runtime.models import Artifact, ExecutionRun
from agency_runtime.utils import stable_id, to_primitive

from .auth import IdentityContext
from .contracts import (
    ApprovalDecision,
    ApprovalResponse,
    ArtifactResponse,
    AuditEventResponse,
    MissionCreate,
    MissionResponse,
    POLICY_VERSION,
    RunEventResponse,
    RunResponse,
    RunStepResponse,
    SCHEMA_VERSION,
    ToolEvidenceResponse,
)
from .errors import conflict, not_found
from .manifest import artifact_manifest_hash
from .ports import ApprovalRecord, MissionRecord, RunRecord
from .storage import (
    ApprovalRow,
    ArtifactRow,
    AuditEventRow,
    IdempotencyRow,
    MissionRow,
    PrincipalRow,
    RunEventRow,
    RunRow,
    RunStepRow,
    TenantRow,
    ToolEvidenceRow,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def parse_runtime_timestamp(value: str) -> datetime:
    return as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


class SqlAlchemyRepository:
    """Transactional repository used by every control-plane request."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()

    def flush(self) -> None:
        self.session.flush()

    def ping(self) -> None:
        self.session.execute(select(1)).scalar_one()

    def ensure_identity(self, identity: IdentityContext, now: datetime) -> None:
        values = {
            "tenant_id": identity.tenant_id,
            "created_at": now,
        }
        principal_values = {
            "tenant_id": identity.tenant_id,
            "principal_id": identity.principal_id,
            "auth_mode": identity.auth_mode,
            "created_at": now,
        }
        dialect = self.session.get_bind().dialect.name
        tenant_insert: Any
        principal_insert: Any
        if dialect == "sqlite":
            tenant_insert = sqlite_insert(TenantRow).values(**values).on_conflict_do_nothing(
                index_elements=[TenantRow.tenant_id]
            )
            principal_insert = (
                sqlite_insert(PrincipalRow)
                .values(**principal_values)
                .on_conflict_do_nothing(
                    index_elements=[PrincipalRow.tenant_id, PrincipalRow.principal_id]
                )
            )
        elif dialect == "postgresql":
            tenant_insert = postgresql_insert(TenantRow).values(
                **values
            ).on_conflict_do_nothing(index_elements=[TenantRow.tenant_id])
            principal_insert = (
                postgresql_insert(PrincipalRow)
                .values(**principal_values)
                .on_conflict_do_nothing(
                    index_elements=[PrincipalRow.tenant_id, PrincipalRow.principal_id]
                )
            )
        else:
            raise RuntimeError("unsupported control-plane database dialect: {}".format(dialect))
        self.session.execute(tenant_insert)
        self.session.execute(principal_insert)

    def idempotent_response(
        self,
        tenant_id: str,
        key: str,
        operation: str,
        request_hash: str,
    ) -> Optional[Tuple[int, Dict[str, object]]]:
        row = self.session.scalar(
            select(IdempotencyRow).where(
                IdempotencyRow.tenant_id == tenant_id,
                IdempotencyRow.idempotency_key == key,
            )
        )
        if row is None:
            return None
        if row.operation != operation or row.request_hash != request_hash:
            raise conflict(
                "IDEMPOTENCY_KEY_REUSED",
                "The Idempotency-Key was already used with a different command",
                idempotency_key=key,
            )
        return row.status_code, dict(row.response_payload)

    def record_idempotency(
        self,
        identity: IdentityContext,
        key: str,
        operation: str,
        request_hash: str,
        status_code: int,
        response_payload: Mapping[str, object],
        now: datetime,
    ) -> None:
        self.session.add(
            IdempotencyRow(
                record_id="idem-{}".format(uuid.uuid4().hex),
                tenant_id=identity.tenant_id,
                idempotency_key=key,
                operation=operation,
                request_hash=request_hash,
                status_code=status_code,
                response_payload=dict(response_payload),
                created_at=now,
            )
        )

    def create_mission(
        self,
        identity: IdentityContext,
        request: MissionCreate,
        now: datetime,
    ) -> MissionResponse:
        row = MissionRow(
            mission_id="mission-{}".format(uuid.uuid4().hex),
            tenant_id=identity.tenant_id,
            created_by=identity.principal_id,
            schema_version=SCHEMA_VERSION,
            title=request.title,
            objective=request.objective,
            audience=request.audience,
            platforms=[item.value for item in request.platforms],
            budget_cents=request.budget_cents,
            source_asset=request.source_asset,
            campaign_goal=request.campaign_goal,
            created_at=now,
            version=1,
        )
        self.session.add(row)
        self.session.flush()
        return self._mission_response(row)

    def get_mission(self, tenant_id: str, mission_id: str) -> MissionRecord:
        row = self.session.scalar(
            select(MissionRow).where(
                MissionRow.mission_id == mission_id,
                MissionRow.tenant_id == tenant_id,
            )
        )
        if row is None:
            raise not_found("mission", mission_id)
        return self._mission_record(row)

    def persist_workflow_run(
        self,
        identity: IdentityContext,
        mission_id: str,
        execution: ExecutionRun,
        correlation_id: str,
        now: datetime,
    ) -> RunResponse:
        artifact_items = [
            {
                "artifact_id": item.artifact_id,
                "kind": item.kind,
                "title": item.title,
                "created_by": item.created_by.value,
                "payload": to_primitive(item.payload),
                "evidence_ids": list(item.evidence_ids),
                "ordinal": ordinal,
            }
            for ordinal, item in enumerate(execution.artifacts, start=1)
        ]
        manifest_hash = artifact_manifest_hash(execution.run_id, artifact_items)
        run = RunRow(
            run_id=execution.run_id,
            mission_id=mission_id,
            tenant_id=identity.tenant_id,
            schema_version=SCHEMA_VERSION,
            status=execution.status.value,
            artifact_manifest_hash=manifest_hash,
            policy_version=POLICY_VERSION,
            external_side_effects=False,
            started_at=parse_runtime_timestamp(execution.started_at),
            completed_at=None,
            version=1,
        )
        self.session.add(run)
        self.session.flush()

        for sequence, role in enumerate(execution.agent_states, start=1):
            state = execution.state_for(role)
            self.session.add(
                RunStepRow(
                    step_id=stable_id("step", execution.run_id, role.value),
                    run_id=execution.run_id,
                    tenant_id=identity.tenant_id,
                    role=role.value,
                    sequence=sequence,
                    status=state.status.value,
                    progress=state.progress,
                    detail=state.detail,
                    updated_at=now,
                )
            )
        for item in artifact_items:
            self.session.add(
                ArtifactRow(
                    artifact_id=str(item["artifact_id"]),
                    run_id=execution.run_id,
                    tenant_id=identity.tenant_id,
                    kind=str(item["kind"]),
                    title=str(item["title"]),
                    created_by=str(item["created_by"]),
                    payload=dict(item["payload"]),
                    evidence_ids=list(item["evidence_ids"]),
                    ordinal=int(item["ordinal"]),
                    created_at=now,
                )
            )
        for evidence in execution.evidence:
            self.session.add(
                ToolEvidenceRow(
                    evidence_id=evidence.evidence_id,
                    run_id=execution.run_id,
                    tenant_id=identity.tenant_id,
                    tool=evidence.tool,
                    operation=evidence.operation,
                    sandbox=evidence.sandbox,
                    summary=evidence.summary,
                    payload=dict(to_primitive(evidence.payload)),
                    references=list(evidence.references),
                    created_at=now,
                )
            )
        for event in execution.trace:
            self.session.add(
                RunEventRow(
                    event_id=stable_id("evt", execution.run_id, event.sequence, event.action),
                    run_id=execution.run_id,
                    tenant_id=identity.tenant_id,
                    sequence=event.sequence,
                    timestamp=parse_runtime_timestamp(event.timestamp),
                    role=event.role.value,
                    action=event.action,
                    status=event.status,
                    detail=event.detail,
                    artifact_ids=list(event.artifact_ids),
                    evidence_ids=list(event.evidence_ids),
                )
            )
        self.add_audit(
            identity,
            "run.started",
            {"mission_id": mission_id, "manifest_hash": manifest_hash},
            correlation_id=correlation_id,
            now=now,
            run_id=execution.run_id,
        )
        self.session.flush()
        return self.get_run(identity.tenant_id, execution.run_id)

    def get_run(self, tenant_id: str, run_id: str) -> RunResponse:
        run = self.session.scalar(self._run_query(tenant_id, run_id))
        if run is None:
            raise not_found("run", run_id)
        steps = list(
            self.session.scalars(
                select(RunStepRow)
                .where(RunStepRow.run_id == run_id, RunStepRow.tenant_id == tenant_id)
                .order_by(RunStepRow.sequence)
            )
        )
        artifacts = list(
            self.session.scalars(
                select(ArtifactRow)
                .where(ArtifactRow.run_id == run_id, ArtifactRow.tenant_id == tenant_id)
                .order_by(ArtifactRow.ordinal)
            )
        )
        evidence = list(
            self.session.scalars(
                select(ToolEvidenceRow)
                .where(ToolEvidenceRow.run_id == run_id, ToolEvidenceRow.tenant_id == tenant_id)
                .order_by(ToolEvidenceRow.evidence_id)
            )
        )
        events = list(
            self.session.scalars(
                select(RunEventRow)
                .where(RunEventRow.run_id == run_id, RunEventRow.tenant_id == tenant_id)
                .order_by(RunEventRow.sequence)
            )
        )
        approval = self.session.scalar(
            select(ApprovalRow).where(
                ApprovalRow.run_id == run_id,
                ApprovalRow.tenant_id == tenant_id,
            )
        )
        audit_events = list(
            self.session.scalars(
                select(AuditEventRow)
                .where(AuditEventRow.run_id == run_id, AuditEventRow.tenant_id == tenant_id)
                .order_by(AuditEventRow.occurred_at, AuditEventRow.action.desc())
            )
        )
        return RunResponse(
            schema_version=SCHEMA_VERSION,
            run_id=run.run_id,
            mission_id=run.mission_id,
            tenant_id=run.tenant_id,
            status=run.status,
            artifact_manifest_hash=run.artifact_manifest_hash,
            policy_version=run.policy_version,
            external_side_effects=run.external_side_effects,
            started_at=as_utc(run.started_at),
            completed_at=as_utc(run.completed_at) if run.completed_at else None,
            version=run.version,
            steps=[
                RunStepResponse(
                    schema_version=SCHEMA_VERSION,
                    step_id=item.step_id,
                    role=item.role,
                    sequence=item.sequence,
                    status=item.status,
                    progress=item.progress,
                    detail=item.detail,
                    updated_at=as_utc(item.updated_at),
                )
                for item in steps
            ],
            artifacts=[self._artifact_response(item) for item in artifacts],
            evidence=[self._evidence_response(item) for item in evidence],
            events=[self._event_response(item) for item in events],
            audit_events=[self._audit_response(item) for item in audit_events],
            approval=self._approval_response(approval) if approval else None,
        )

    def run_for_update(self, tenant_id: str, run_id: str) -> RunRecord:
        run = self.session.scalar(self._run_query(tenant_id, run_id).with_for_update())
        if run is None:
            raise not_found("run", run_id)
        return self._run_record(run)

    def mission_for_run(self, tenant_id: str, run_id: str) -> MissionRecord:
        run = self.session.scalar(self._run_query(tenant_id, run_id))
        if run is None:
            raise not_found("run", run_id)
        return self.get_mission(tenant_id, run.mission_id)

    def approval_exists(self, tenant_id: str, run_id: str) -> bool:
        return (
            self.session.scalar(
                select(ApprovalRow.approval_id).where(
                    ApprovalRow.run_id == run_id,
                    ApprovalRow.tenant_id == tenant_id,
                )
            )
            is not None
        )

    def current_manifest_hash(
        self,
        tenant_id: str,
        run_id: str,
        *,
        for_update: bool = False,
    ) -> str:
        return artifact_manifest_hash(
            run_id,
            self.artifact_manifest_items(tenant_id, run_id, for_update=for_update),
        )

    def artifact_manifest_items(
        self,
        tenant_id: str,
        run_id: str,
        *,
        for_update: bool = False,
    ) -> List[Mapping[str, object]]:
        statement = (
            select(ArtifactRow)
            .where(
                ArtifactRow.run_id == run_id,
                ArtifactRow.tenant_id == tenant_id,
                ArtifactRow.created_by != "publisher",
            )
            .order_by(ArtifactRow.ordinal)
        )
        if for_update:
            statement = statement.with_for_update()
        rows = list(
            self.session.scalars(statement)
        )
        return [
            {
                "artifact_id": item.artifact_id,
                "kind": item.kind,
                "title": item.title,
                "created_by": item.created_by,
                "payload": item.payload,
                "evidence_ids": item.evidence_ids,
                "ordinal": item.ordinal,
            }
            for item in rows
        ]

    def risk_passed(self, tenant_id: str, run_id: str) -> bool:
        risk = self.session.scalar(
            select(ArtifactRow).where(
                ArtifactRow.run_id == run_id,
                ArtifactRow.tenant_id == tenant_id,
                ArtifactRow.kind == "risk_report",
            )
        )
        return risk is not None and risk.payload.get("passed") is True

    def runtime_artifacts(self, tenant_id: str, run_id: str) -> Tuple[Artifact, ...]:
        rows = list(
            self.session.scalars(
                select(ArtifactRow)
                .where(ArtifactRow.run_id == run_id, ArtifactRow.tenant_id == tenant_id)
                .order_by(ArtifactRow.ordinal)
            )
        )
        from agency_runtime.models import AgentRole

        return tuple(
            Artifact(
                artifact_id=item.artifact_id,
                kind=item.kind,
                title=item.title,
                created_by=AgentRole(item.created_by),
                payload=item.payload,
                evidence_ids=tuple(item.evidence_ids),
            )
            for item in rows
            if item.created_by != "publisher"
        )

    def claim_approval_transition(
        self,
        tenant_id: str,
        run_id: str,
        current_version: int,
        next_status: str,
        now: datetime,
    ) -> bool:
        completed_at = now if next_status in {"completed", "rejected"} else None
        result = cast(
            CursorResult[Any],
            self.session.execute(
                update(RunRow)
                .where(
                    RunRow.run_id == run_id,
                    RunRow.tenant_id == tenant_id,
                    RunRow.status == "awaiting_greenlight",
                    RunRow.version == current_version,
                )
                .values(
                    status=next_status,
                    completed_at=completed_at,
                    version=current_version + 1,
                )
            ),
        )
        return result.rowcount == 1

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
    ) -> ApprovalRecord:
        row = ApprovalRow(
            approval_id="approval-{}".format(uuid.uuid4().hex),
            run_id=run_id,
            tenant_id=identity.tenant_id,
            principal_id=identity.principal_id,
            decision=decision.value,
            reviewer=reviewer,
            note=note,
            artifact_manifest_hash=manifest_hash,
            policy_version=policy_version,
            decided_at=now,
        )
        self.session.add(row)
        return ApprovalRecord(approval_id=row.approval_id)

    def finalize_publisher_rejection(
        self, tenant_id: str, run_id: str, now: datetime
    ) -> None:
        self.session.execute(
            update(RunStepRow)
            .where(
                RunStepRow.run_id == run_id,
                RunStepRow.tenant_id == tenant_id,
                RunStepRow.role == "publisher",
            )
            .values(
                status="blocked",
                progress=0,
                detail="Greenlight rejected; sandbox package was not created.",
                updated_at=now,
            )
        )
        self.add_run_event(
            tenant_id,
            run_id,
            role="publisher",
            action="greenlight_rejected",
            status="blocked",
            detail="Reviewer rejected release. No packaging or publication occurred.",
            now=now,
        )

    def finalize_publisher_approval(
        self,
        tenant_id: str,
        run_id: str,
        artifact: Artifact,
        evidence: Mapping[str, object],
        now: datetime,
    ) -> None:
        next_ordinal = int(
            self.session.scalar(
                select(func.coalesce(func.max(ArtifactRow.ordinal), 0)).where(
                    ArtifactRow.run_id == run_id
                )
            )
            or 0
        ) + 1
        self.session.add(
            ArtifactRow(
                artifact_id=artifact.artifact_id,
                run_id=run_id,
                tenant_id=tenant_id,
                kind=artifact.kind,
                title=artifact.title,
                created_by=artifact.created_by.value,
                payload=dict(to_primitive(artifact.payload)),
                evidence_ids=list(artifact.evidence_ids),
                ordinal=next_ordinal,
                created_at=now,
            )
        )
        self.session.add(
            ToolEvidenceRow(
                evidence_id=str(evidence["evidence_id"]),
                run_id=run_id,
                tenant_id=tenant_id,
                tool=str(evidence["tool"]),
                operation=str(evidence["operation"]),
                sandbox=bool(evidence["sandbox"]),
                summary=str(evidence["summary"]),
                payload=dict(cast(Mapping[str, object], evidence["payload"])),
                references=list(cast(Iterable[str], evidence["references"])),
                created_at=now,
            )
        )
        self.session.execute(
            update(RunStepRow)
            .where(
                RunStepRow.run_id == run_id,
                RunStepRow.tenant_id == tenant_id,
                RunStepRow.role == "publisher",
            )
            .values(
                status="ready",
                progress=100,
                detail="Manifest packaged locally; external publication was not performed.",
                updated_at=now,
            )
        )
        self.add_run_event(
            tenant_id,
            run_id,
            role="publisher",
            action="artifact_ready",
            status="ready",
            detail="Sandbox campaign manifest created; publication_performed=false.",
            now=now,
            artifact_ids=(artifact.artifact_id,),
            evidence_ids=artifact.evidence_ids,
        )

    def add_run_event(
        self,
        tenant_id: str,
        run_id: str,
        role: str,
        action: str,
        status: str,
        detail: str,
        now: datetime,
        artifact_ids: Sequence[str] = (),
        evidence_ids: Sequence[str] = (),
    ) -> None:
        sequence = int(
            self.session.scalar(
                select(func.coalesce(func.max(RunEventRow.sequence), 0)).where(
                    RunEventRow.run_id == run_id
                )
            )
            or 0
        ) + 1
        self.session.add(
            RunEventRow(
                event_id=stable_id("evt", run_id, sequence, action),
                run_id=run_id,
                tenant_id=tenant_id,
                sequence=sequence,
                timestamp=now,
                role=role,
                action=action,
                status=status,
                detail=detail,
                artifact_ids=list(artifact_ids),
                evidence_ids=list(evidence_ids),
            )
        )

    def add_audit(
        self,
        identity: IdentityContext,
        action: str,
        payload: Mapping[str, object],
        correlation_id: str,
        now: datetime,
        run_id: Optional[str] = None,
    ) -> None:
        self.session.add(
            AuditEventRow(
                audit_id="audit-{}".format(uuid.uuid4().hex),
                tenant_id=identity.tenant_id,
                principal_id=identity.principal_id,
                run_id=run_id,
                action=action,
                payload=dict(payload),
                correlation_id=correlation_id,
                occurred_at=now,
            )
        )

    @staticmethod
    def is_integrity_error(error: BaseException) -> bool:
        return isinstance(error, IntegrityError)

    @staticmethod
    def _run_query(tenant_id: str, run_id: str) -> Select[Tuple[RunRow]]:
        return select(RunRow).where(
            RunRow.run_id == run_id,
            RunRow.tenant_id == tenant_id,
        )

    @staticmethod
    def _mission_record(row: MissionRow) -> MissionRecord:
        return MissionRecord(
            mission_id=row.mission_id,
            title=row.title,
            objective=row.objective,
            audience=row.audience,
            platforms=tuple(row.platforms),
            budget_cents=row.budget_cents,
            source_asset=row.source_asset,
            campaign_goal=row.campaign_goal,
        )

    @staticmethod
    def _run_record(row: RunRow) -> RunRecord:
        return RunRecord(
            run_id=row.run_id,
            status=row.status,
            artifact_manifest_hash=row.artifact_manifest_hash,
            policy_version=row.policy_version,
            version=row.version,
        )

    @staticmethod
    def _mission_response(row: MissionRow) -> MissionResponse:
        return MissionResponse(
            schema_version=SCHEMA_VERSION,
            mission_id=row.mission_id,
            tenant_id=row.tenant_id,
            created_by=row.created_by,
            title=row.title,
            objective=row.objective,
            audience=row.audience,
            platforms=row.platforms,
            budget_cents=row.budget_cents,
            source_asset=row.source_asset,
            campaign_goal=row.campaign_goal,
            created_at=as_utc(row.created_at),
            version=row.version,
        )

    @staticmethod
    def _artifact_response(row: ArtifactRow) -> ArtifactResponse:
        return ArtifactResponse(
            schema_version=SCHEMA_VERSION,
            artifact_id=row.artifact_id,
            kind=row.kind,
            title=row.title,
            created_by=row.created_by,
            payload=row.payload,
            evidence_ids=row.evidence_ids,
            ordinal=row.ordinal,
            created_at=as_utc(row.created_at),
        )

    @staticmethod
    def _evidence_response(row: ToolEvidenceRow) -> ToolEvidenceResponse:
        return ToolEvidenceResponse(
            schema_version=SCHEMA_VERSION,
            evidence_id=row.evidence_id,
            tool=row.tool,
            operation=row.operation,
            sandbox=row.sandbox,
            summary=row.summary,
            payload=row.payload,
            references=row.references,
            created_at=as_utc(row.created_at),
        )

    @staticmethod
    def _event_response(row: RunEventRow) -> RunEventResponse:
        return RunEventResponse(
            schema_version=SCHEMA_VERSION,
            event_id=row.event_id,
            sequence=row.sequence,
            timestamp=as_utc(row.timestamp),
            role=row.role,
            action=row.action,
            status=row.status,
            detail=row.detail,
            artifact_ids=row.artifact_ids,
            evidence_ids=row.evidence_ids,
        )

    @staticmethod
    def _approval_response(row: ApprovalRow) -> ApprovalResponse:
        return ApprovalResponse(
            schema_version=SCHEMA_VERSION,
            approval_id=row.approval_id,
            decision=ApprovalDecision(row.decision),
            reviewer=row.reviewer,
            note=row.note,
            artifact_manifest_hash=row.artifact_manifest_hash,
            policy_version=row.policy_version,
            principal_id=row.principal_id,
            decided_at=as_utc(row.decided_at),
        )

    @staticmethod
    def _audit_response(row: AuditEventRow) -> AuditEventResponse:
        return AuditEventResponse(
            schema_version=SCHEMA_VERSION,
            audit_id=row.audit_id,
            principal_id=row.principal_id,
            action=row.action,
            payload=row.payload,
            correlation_id=row.correlation_id,
            occurred_at=as_utc(row.occurred_at),
        )
