from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from time import perf_counter
from typing import Callable, Mapping, Optional, Type, TypeVar

from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from agency_runtime import AgencyOrchestrator, MissionBrief, Platform, SQLiteMemory
from agency_runtime.models import AgentRole, Artifact
from agency_runtime.tools import CampaignPackageRequest, build_sandbox_toolset
from agency_runtime.utils import stable_id, to_primitive

from .auth import IdentityContext
from .contracts import (
    ApprovalCreate,
    ApprovalDecision,
    MissionCreate,
    MissionResponse,
    RunResponse,
    RunStart,
)
from .errors import ControlPlaneError, conflict
from .manifest import request_payload_hash
from .ports import ControlPlaneRepository
from .repository import utc_now


ResponseModel = TypeVar("ResponseModel", bound=BaseModel)
LOGGER = logging.getLogger("agency.control_plane")


class ControlPlaneService:
    def __init__(self, repository: ControlPlaneRepository) -> None:
        self.repository = repository

    def create_mission(
        self,
        identity: IdentityContext,
        request: MissionCreate,
        idempotency_key: str,
        correlation_id: str,
    ) -> MissionResponse:
        operation = "mission.create"
        request_hash = self._request_hash(operation, request)
        replay = self._replay(
            identity, idempotency_key, operation, request_hash, MissionResponse
        )
        if replay is not None:
            return replay
        now = utc_now()
        try:
            self.repository.ensure_identity(identity, now)
            response = self.repository.create_mission(identity, request, now)
            self.repository.add_audit(
                identity,
                operation,
                {"mission_id": response.mission_id},
                correlation_id,
                now,
            )
            self._record(
                identity,
                idempotency_key,
                operation,
                request_hash,
                201,
                response,
                now,
            )
            self.repository.commit()
            return response
        except IntegrityError as error:
            return self._recover_concurrent_replay(
                identity,
                idempotency_key,
                operation,
                request_hash,
                MissionResponse,
                error,
            )

    def start_run(
        self,
        identity: IdentityContext,
        mission_id: str,
        request: RunStart,
        idempotency_key: str,
        correlation_id: str,
    ) -> RunResponse:
        operation = "run.start"
        payload = request.model_dump(mode="json")
        payload["mission_id"] = mission_id
        request_hash = request_payload_hash(operation, payload)
        replay = self._replay(identity, idempotency_key, operation, request_hash, RunResponse)
        if replay is not None:
            return replay
        now = utc_now()
        memory = SQLiteMemory(":memory:")
        try:
            self.repository.ensure_identity(identity, now)
            mission = self.repository.get_mission(identity.tenant_id, mission_id)
            brief = MissionBrief(
                title=mission.title,
                objective=mission.objective,
                audience=mission.audience,
                platforms=tuple(Platform(item) for item in mission.platforms),
                budget_cents=mission.budget_cents,
                source_asset=mission.source_asset,
                campaign_goal=mission.campaign_goal,
            )
            run_id = "run-{}".format(uuid.uuid4().hex)
            execution = AgencyOrchestrator(
                tools=build_sandbox_toolset(),
                memory=memory,
                tool_call_observer=self._tool_observer(
                    identity,
                    correlation_id,
                    run_id,
                ),
            ).start(brief, run_id=run_id)
            response = self.repository.persist_workflow_run(
                identity,
                mission.mission_id,
                execution,
                correlation_id,
                now,
            )
            self._record(
                identity,
                idempotency_key,
                operation,
                request_hash,
                201,
                response,
                now,
            )
            self.repository.commit()
            return response
        except IntegrityError as error:
            return self._recover_concurrent_replay(
                identity,
                idempotency_key,
                operation,
                request_hash,
                RunResponse,
                error,
            )
        finally:
            memory.close()

    def get_run(self, identity: IdentityContext, run_id: str) -> RunResponse:
        return self.repository.get_run(identity.tenant_id, run_id)

    def decide_run(
        self,
        identity: IdentityContext,
        run_id: str,
        request: ApprovalCreate,
        idempotency_key: str,
        correlation_id: str,
    ) -> RunResponse:
        operation = "run.approval"
        payload = request.model_dump(mode="json")
        payload["run_id"] = run_id
        request_hash = request_payload_hash(operation, payload)
        replay = self._replay(identity, idempotency_key, operation, request_hash, RunResponse)
        if replay is not None:
            return replay
        now = utc_now()
        try:
            self.repository.ensure_identity(identity, now)
            run = self.repository.run_for_update(identity.tenant_id, run_id)
            if run.status != "awaiting_greenlight" or self.repository.approval_exists(
                identity.tenant_id, run_id
            ):
                raise conflict(
                    "APPROVAL_ALREADY_DECIDED",
                    "A Greenlight decision already exists for this run",
                    run_id=run_id,
                    status=run.status,
                )
            if not self.repository.risk_passed(identity.tenant_id, run_id):
                raise conflict(
                    "RISK_NOT_PASSED",
                    "Risk must pass before a Greenlight decision",
                    run_id=run_id,
                )
            current_hash = self.repository.current_manifest_hash(
                identity.tenant_id,
                run_id,
                for_update=True,
            )
            if (
                request.policy_version != run.policy_version
                or request.artifact_manifest_hash != run.artifact_manifest_hash
                or current_hash != run.artifact_manifest_hash
            ):
                raise conflict(
                    "STALE_ARTIFACT_MANIFEST",
                    "Approval does not match the current artifact manifest and policy",
                    run_id=run_id,
                    expected_manifest_hash=run.artifact_manifest_hash,
                    current_manifest_hash=current_hash,
                    policy_version=run.policy_version,
                )
            next_status = (
                "completed"
                if request.decision is ApprovalDecision.APPROVED
                else "rejected"
            )
            claimed = self.repository.claim_approval_transition(
                identity.tenant_id,
                run_id,
                run.version,
                next_status,
                now,
            )
            if not claimed:
                raise conflict(
                    "APPROVAL_ALREADY_DECIDED",
                    "Another Greenlight decision already claimed this run",
                    run_id=run_id,
                )
            approval = self.repository.add_approval(
                identity,
                run_id,
                request.decision,
                request.reviewer,
                request.note,
                current_hash,
                request.policy_version,
                now,
            )
            if request.decision is ApprovalDecision.APPROVED:
                self._package_sandbox_campaign(identity, run_id, correlation_id, now)
            else:
                self.repository.finalize_publisher_rejection(identity.tenant_id, run_id, now)
            final_manifest_hash = self.repository.current_manifest_hash(
                identity.tenant_id,
                run_id,
                for_update=True,
            )
            if final_manifest_hash != current_hash:
                raise conflict(
                    "STALE_ARTIFACT_MANIFEST",
                    "Artifacts changed while the Greenlight decision was being committed",
                    run_id=run_id,
                    expected_manifest_hash=current_hash,
                    current_manifest_hash=final_manifest_hash,
                    policy_version=run.policy_version,
                )
            self.repository.add_audit(
                identity,
                operation,
                {
                    "approval_id": approval.approval_id,
                    "decision": request.decision.value,
                    "manifest_hash": current_hash,
                    "policy_version": request.policy_version,
                    "external_side_effects": False,
                },
                correlation_id,
                now,
                run_id=run_id,
            )
            self.repository.flush()
            response = self.repository.get_run(identity.tenant_id, run_id)
            self._record(
                identity,
                idempotency_key,
                operation,
                request_hash,
                200,
                response,
                now,
            )
            self.repository.commit()
            self._log(
                {
                    "event": "approval_decision",
                    "correlation_id": correlation_id,
                    "tenant_id": identity.tenant_id,
                    "principal_id": identity.principal_id,
                    "run_id": run_id,
                    "decision": request.decision.value,
                    "artifact_manifest_hash": current_hash,
                    "policy_version": request.policy_version,
                    "external_side_effects": False,
                    "success": True,
                }
            )
            return response
        except IntegrityError as error:
            replay_after_conflict = self._recover_optional_replay(
                identity, idempotency_key, operation, request_hash, RunResponse
            )
            if replay_after_conflict is not None:
                return replay_after_conflict
            raise conflict(
                "APPROVAL_ALREADY_DECIDED",
                "Another Greenlight decision already completed for this run",
                run_id=run_id,
            ) from error
        except ControlPlaneError:
            self.repository.rollback()
            raise

    def _package_sandbox_campaign(
        self,
        identity: IdentityContext,
        run_id: str,
        correlation_id: str,
        now: datetime,
    ) -> None:
        artifacts = self.repository.runtime_artifacts(identity.tenant_id, run_id)
        mission_row = self.repository.mission_for_run(identity.tenant_id, run_id)
        platforms = tuple(Platform(item) for item in mission_row.platforms)
        started = perf_counter()
        try:
            response = build_sandbox_toolset().campaign_packager.package(
                CampaignPackageRequest(run_id=run_id, platforms=platforms, artifacts=artifacts)
            )
        except Exception as error:
            self._tool_observer(identity, correlation_id, run_id)(
                {
                    "step": AgentRole.PUBLISHER.value,
                    "tool": "campaign_packager",
                    "operation": "package_manifest",
                    "sandbox": True,
                    "success": False,
                    "retry_count": 0,
                    "latency_ms": round((perf_counter() - started) * 1000, 3),
                    "error_type": type(error).__name__,
                }
            )
            raise
        self._tool_observer(identity, correlation_id, run_id)(
            {
                "step": AgentRole.PUBLISHER.value,
                "tool": response.evidence.tool,
                "operation": response.evidence.operation,
                "sandbox": response.evidence.sandbox,
                "success": True,
                "retry_count": 0,
                "latency_ms": round((perf_counter() - started) * 1000, 3),
                "evidence_id": response.evidence.evidence_id,
            }
        )
        payload = to_primitive(response.result)
        artifact = Artifact(
            artifact_id=stable_id("art", run_id, AgentRole.PUBLISHER, "campaign_package", payload),
            kind="campaign_package",
            title="Sandbox campaign manifest",
            created_by=AgentRole.PUBLISHER,
            payload=payload,
            evidence_ids=(response.evidence.evidence_id,),
        )
        evidence = to_primitive(response.evidence)
        self.repository.finalize_publisher_approval(
            identity.tenant_id,
            run_id,
            artifact,
            evidence,
            now,
        )

    def _replay(
        self,
        identity: IdentityContext,
        key: str,
        operation: str,
        request_hash: str,
        model: Type[ResponseModel],
    ) -> Optional[ResponseModel]:
        replay = self.repository.idempotent_response(
            identity.tenant_id, key, operation, request_hash
        )
        if replay is None:
            return None
        _, payload = replay
        return model.model_validate(payload)

    def _record(
        self,
        identity: IdentityContext,
        key: str,
        operation: str,
        request_hash: str,
        status_code: int,
        response: BaseModel,
        now: datetime,
    ) -> None:
        self.repository.record_idempotency(
            identity,
            key,
            operation,
            request_hash,
            status_code,
            response.model_dump(mode="json"),
            now,
        )

    def _recover_concurrent_replay(
        self,
        identity: IdentityContext,
        key: str,
        operation: str,
        request_hash: str,
        model: Type[ResponseModel],
        original_error: IntegrityError,
    ) -> ResponseModel:
        replay = self._recover_optional_replay(identity, key, operation, request_hash, model)
        if replay is None:
            raise original_error
        return replay

    def _recover_optional_replay(
        self,
        identity: IdentityContext,
        key: str,
        operation: str,
        request_hash: str,
        model: Type[ResponseModel],
    ) -> Optional[ResponseModel]:
        self.repository.rollback()
        return self._replay(identity, key, operation, request_hash, model)

    @staticmethod
    def _request_hash(operation: str, request: BaseModel) -> str:
        payload: Mapping[str, object] = request.model_dump(mode="json")
        return request_payload_hash(operation, payload)

    def _tool_observer(
        self,
        identity: IdentityContext,
        correlation_id: str,
        run_id: str,
    ) -> Callable[[Mapping[str, object]], None]:
        def observe(payload: Mapping[str, object]) -> None:
            step_role = str(payload.get("step", "unknown"))
            self._log(
                {
                    **payload,
                    "event": "sandbox_tool_call",
                    "correlation_id": correlation_id,
                    "tenant_id": identity.tenant_id,
                    "principal_id": identity.principal_id,
                    "run_id": run_id,
                    "role": step_role,
                    "step_id": stable_id("step", run_id, step_role),
                    "external_side_effects": False,
                }
            )

        return observe

    @staticmethod
    def _log(payload: Mapping[str, object]) -> None:
        LOGGER.info(json.dumps(payload, sort_keys=True, separators=(",", ":")))
