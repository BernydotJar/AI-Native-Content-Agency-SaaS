from __future__ import annotations

import hashlib
from dataclasses import replace
from typing import Callable, Dict, Mapping, Optional, Sequence, Tuple

from .campaign_intelligence import (
    claim_ledger,
    copy_payload,
    critique_payload,
    growth_payload,
    media_payload,
    strategy_payload,
)
from .memory import MemoryStore, utc_now
from .models import (
    AGENT_SEQUENCE,
    AgentRole,
    AgentState,
    AgentStatus,
    Artifact,
    ExecutionRun,
    Greenlight,
    GreenlightDecision,
    MissionBrief,
    Provenance,
    RunExecution,
    RunStatus,
    ToolEvidence,
    TraceEvent,
)
from .tools import (
    BrowserRequest,
    CampaignPackageRequest,
    Context7Request,
    GitHubRequest,
    ImageToVideoRequest,
    MetaAdsRequest,
    SandboxToolset,
    TrendsRequest,
    VideoOptimizationRequest,
)
from .utils import canonical_json, stable_id, to_primitive


Clock = Callable[[], str]


class GreenlightError(RuntimeError):
    pass


class PoliticalReviewerSeparationError(GreenlightError):
    pass


class AgencyOrchestrator:
    """Sequential eight-agent runtime with a hard Publisher approval boundary."""

    def __init__(
        self,
        tools: SandboxToolset,
        memory: MemoryStore,
        clock: Clock = utc_now,
    ) -> None:
        self.tools = tools
        self.memory = memory
        self._clock = clock
        self._runs: Dict[str, ExecutionRun] = {}

    def create(self, brief: MissionBrief, *, asynchronous: bool = False) -> ExecutionRun:
        run_id = stable_id("run", brief)
        if run_id in self._runs:
            raise ValueError("run already exists in this orchestrator: {}".format(run_id))
        now = self._clock()
        run = ExecutionRun(
            run_id=run_id,
            brief=brief,
            status=RunStatus.QUEUED if asynchronous else RunStatus.RUNNING,
            started_at=now,
            agent_states={role: AgentState(role=role) for role in AGENT_SEQUENCE},
            execution=RunExecution(
                state="queued" if asynchronous else "inline",
                next_station=AgentRole.CEO.value,
                checkpointed_at=now,
            ),
        )
        self._runs[run_id] = run
        return run

    def start(self, brief: MissionBrief) -> ExecutionRun:
        run = self.create(brief)
        while run.status in {RunStatus.QUEUED, RunStatus.RUNNING}:
            self.advance(run.run_id)
        return run

    def advance(self, run_id: str) -> ExecutionRun:
        run = self.get_run(run_id)
        if run.status is RunStatus.QUEUED:
            run.status = RunStatus.RUNNING
            run.execution.state = "running"

        if run.status is not RunStatus.RUNNING:
            return run

        executable = AGENT_SEQUENCE[:-1]
        for index, role in enumerate(executable):
            state = run.state_for(role)
            if state.status is AgentStatus.READY:
                continue
            run.execution.next_station = role.value
            if state.status is AgentStatus.STANDBY:
                self._begin(run, role, self._start_detail(role))
                return run
            if state.status is AgentStatus.PROCESSING:
                self._execute_role(run, role)
                next_index = index + 1
                run.execution.next_station = (
                    executable[next_index].value
                    if next_index < len(executable)
                    else AgentRole.PUBLISHER.value
                )
                if role is AgentRole.RISK:
                    self._await_greenlight(run)
                return run
            raise RuntimeError("run contains an invalid station state")
        self._await_greenlight(run)
        return run

    @staticmethod
    def _start_detail(role: AgentRole) -> str:
        return {
            AgentRole.CEO: "Interpreting mission constraints",
            AgentRole.RESEARCH: "Collecting synthetic market evidence",
            AgentRole.STRATEGIST: "Designing channel strategy",
            AgentRole.GROWTH: "Forecasting sandbox acquisition envelope",
            AgentRole.WRITER: "Writing platform variants",
            AgentRole.MEDIA: "Planning video and motion assets",
            AgentRole.RISK: "Auditing release constraints",
        }[role]

    def _execute_role(self, run: ExecutionRun, role: AgentRole) -> None:
        handlers = {
            AgentRole.CEO: self._run_ceo,
            AgentRole.RESEARCH: self._run_research,
            AgentRole.STRATEGIST: self._run_strategist,
            AgentRole.GROWTH: self._run_growth,
            AgentRole.WRITER: self._run_writer,
            AgentRole.MEDIA: self._run_media,
            AgentRole.RISK: self._run_risk,
        }
        handlers[role](run)

    def _await_greenlight(self, run: ExecutionRun) -> None:
        if run.status is RunStatus.AWAITING_GREENLIGHT:
            return
        publisher = run.state_for(AgentRole.PUBLISHER)
        risk_report = run.artifact("risk_report")
        critique_passed = risk_report.payload.get("passed") is True
        publication_eligible = risk_report.payload.get("publication_eligible") is True
        if not critique_passed or (
            run.brief.campaign_type == "political" and not publication_eligible
        ):
            publisher.update(
                AgentStatus.ATTENTION,
                0,
                "Critique requires revision; Greenlight and publication are blocked.",
            )
            event_action = "critique_revision_required"
            event_status = AgentStatus.ATTENTION.value
            event_detail = "The run is reviewable, but it cannot receive Greenlight."
        else:
            publisher.update(
                AgentStatus.WAITING_GREENLIGHT,
                0,
                "Risk passed; manual Greenlight is required before packaging.",
            )
            event_action = "approval_gate"
            event_status = AgentStatus.WAITING_GREENLIGHT.value
            event_detail = "No packaging or publication has occurred."
        run.status = RunStatus.AWAITING_GREENLIGHT
        run.execution.state = "awaiting_greenlight"
        run.execution.next_station = AgentRole.PUBLISHER.value
        self._event(
            run,
            AgentRole.PUBLISHER,
            event_action,
            event_status,
            event_detail,
        )

    def approve(self, run_id: str, reviewer: str, note: str = "") -> ExecutionRun:
        return self._decide(
            run_id=run_id,
            reviewer=reviewer,
            decision=GreenlightDecision.APPROVED,
            note=note,
        )

    def reject(self, run_id: str, reviewer: str, note: str = "") -> ExecutionRun:
        return self._decide(
            run_id=run_id,
            reviewer=reviewer,
            decision=GreenlightDecision.REJECTED,
            note=note,
        )

    def revoke(self, run_id: str, reviewer: str, reason: str) -> ExecutionRun:
        run = self.get_run(run_id)
        greenlight = run.greenlight
        if (
            run.status is not RunStatus.COMPLETED
            or greenlight is None
            or not greenlight.active
        ):
            raise GreenlightError("Greenlight is not active")
        normalized_reviewer = reviewer.strip()
        normalized_reason = reason.strip()
        if not normalized_reviewer:
            raise GreenlightError("reviewer must not be empty")
        if not normalized_reason:
            raise GreenlightError("revocation reason must not be empty")
        revoked_at = self._clock()
        run.greenlight = replace(
            greenlight,
            fencing_token=greenlight.fencing_token + 1,
            revoked_at=revoked_at,
            revoked_by=normalized_reviewer,
            revocation_reason=normalized_reason,
        )
        run.status = RunStatus.REVOKED
        run.execution.state = "completed"
        run.state_for(AgentRole.PUBLISHER).update(
            AgentStatus.BLOCKED,
            100,
            "Greenlight revoked; all prior effect tokens are fenced.",
        )
        self._event(
            run,
            AgentRole.PUBLISHER,
            "greenlight_revoked",
            AgentStatus.BLOCKED.value,
            "Approval revoked locally; publication remains disabled.",
        )
        return run

    def get_run(self, run_id: str) -> ExecutionRun:
        try:
            return self._runs[run_id]
        except KeyError as error:
            raise KeyError("run not found: {}".format(run_id)) from error

    def restore_run(self, run: ExecutionRun) -> ExecutionRun:
        """Hydrate a durable run before applying a state transition."""
        self._runs[run.run_id] = run
        return run

    def _decide(
        self,
        run_id: str,
        reviewer: str,
        decision: GreenlightDecision,
        note: str,
    ) -> ExecutionRun:
        run = self.get_run(run_id)
        if run.status is not RunStatus.AWAITING_GREENLIGHT:
            raise GreenlightError(
                "run {} is not awaiting Greenlight (status={})".format(
                    run_id, run.status.value
                )
            )
        risk_report = run.artifact("risk_report")
        if risk_report.payload.get("passed") is not True:
            raise GreenlightError("Risk must pass before a Greenlight decision")
        if (
            run.brief.campaign_type == "political"
            and risk_report.payload.get("publication_eligible") is not True
        ):
            raise GreenlightError("Political critique must pass before Greenlight")
        if not reviewer or not reviewer.strip():
            raise GreenlightError("reviewer must not be empty")
        normalized_reviewer = reviewer.strip()
        if (
            decision is GreenlightDecision.APPROVED
            and run.brief.campaign_type == "political"
            and run.brief.legal_reviewed_by.strip() == normalized_reviewer
        ):
            raise PoliticalReviewerSeparationError(
                "political legal reviewer and Greenlight approver must be distinct"
            )

        decided_at = self._clock()
        if decision is GreenlightDecision.APPROVED and run.brief.campaign_type == "political":
            claim_hashes = []
            for claim in run.brief.evidence_claims:
                contract = {
                    "statement": str(claim.get("statement", "")).strip(),
                    "source": str(claim.get("source", "")).strip(),
                    "locator": str(claim.get("locator", "")).strip(),
                    "verification_status": str(claim.get("verification_status", "unverified")),
                    "reviewed_by": str(claim.get("reviewed_by", "")).strip(),
                }
                claim_hashes.append(
                    {
                        "claim_sha256": hashlib.sha256(
                            canonical_json(contract).encode("utf-8")
                        ).hexdigest(),
                        "source_sha256": hashlib.sha256(
                            contract["source"].encode("utf-8")
                        ).hexdigest(),
                        "locator_sha256": hashlib.sha256(
                            contract["locator"].encode("utf-8")
                        ).hexdigest(),
                    }
                )
            payload = {
                "jurisdiction": run.brief.jurisdiction.strip(),
                "publication_mode": run.brief.publication_mode,
                "disclosure_sha256": hashlib.sha256(
                    run.brief.disclosure.strip().encode("utf-8")
                ).hexdigest(),
                "legal_reviewer": run.brief.legal_reviewed_by.strip(),
                "greenlight_approver": normalized_reviewer,
                "claim_source_hashes": claim_hashes,
                "retention_state": "durable_until_governed_deletion",
            }
            run.add_artifact(
                Artifact(
                    artifact_id=stable_id(
                        "political-compliance-record", run.run_id, payload, length=48
                    ),
                    kind="political_compliance_record",
                    title="Political compliance approval record",
                    created_by=AgentRole.RISK,
                    payload=payload,
                )
            )

        approved_artifacts = tuple(run.artifacts)
        approved_ids = tuple(item.artifact_id for item in approved_artifacts)
        approved_hashes = tuple(
            stable_id("sha256", canonical_json(item), length=64)
            for item in approved_artifacts
        )
        greenlight = Greenlight(
            greenlight_id=stable_id(
                "greenlight", run_id, decision, reviewer.strip(), note.strip(),
                decided_at, approved_ids, approved_hashes
            ),
            run_id=run_id,
            decision=decision,
            reviewer=normalized_reviewer,
            note=note.strip(),
            decided_at=decided_at,
            approved_artifact_ids=approved_ids,
            approved_artifact_hashes=approved_hashes,
            authorized_channels=run.brief.platforms,
            authorized_budget_cents=run.brief.budget_cents,
        )
        run.greenlight = greenlight

        if decision is GreenlightDecision.REJECTED:
            run.status = RunStatus.REJECTED
            run.execution.state = "completed"
            run.completed_at = decided_at
            run.state_for(AgentRole.PUBLISHER).update(
                AgentStatus.BLOCKED,
                0,
                "Greenlight rejected; sandbox package was not created.",
            )
            self._event(
                run,
                AgentRole.PUBLISHER,
                "greenlight_rejected",
                AgentStatus.BLOCKED.value,
                "Reviewer rejected release. No packaging or publication occurred.",
            )
            return run

        publisher = run.state_for(AgentRole.PUBLISHER)
        publisher.update(
            AgentStatus.PROCESSING,
            50,
            "Greenlight recorded; creating local sandbox manifest.",
        )
        self._event(
            run,
            AgentRole.PUBLISHER,
            "greenlight_approved",
            AgentStatus.PROCESSING.value,
            "Approval recorded locally; publication remains disabled.",
        )
        response = self.tools.campaign_packager.package(
            CampaignPackageRequest(
                run_id=run.run_id,
                platforms=run.brief.platforms,
                artifacts=tuple(run.artifacts),
            )
        )
        package = response.result
        artifact = self._complete_agent(
            run=run,
            role=AgentRole.PUBLISHER,
            kind="campaign_package",
            title="Sandbox campaign manifest",
            payload=to_primitive(package),
            evidence=(response.evidence,),
            detail="Manifest packaged locally; external publication was not performed.",
        )
        run.status = RunStatus.COMPLETED
        run.execution.state = "completed"
        run.execution.next_station = AgentRole.PUBLISHER.value
        run.completed_at = self._clock()
        self._remember(
            run,
            AgentRole.PUBLISHER,
            "Greenlight {} produced sandbox manifest {} with publication_performed=false.".format(
                greenlight.greenlight_id, package.manifest_uri
            ),
            confidence=1.0,
            tags=("greenlight", "publisher", "sandbox"),
            artifact=artifact,
            evidence=response.evidence,
        )
        return run

    def _run_ceo(self, run: ExecutionRun) -> None:
        brief = run.brief
        self._complete_agent(
            run,
            AgentRole.CEO,
            "mission_charter",
            "Mission charter",
            {
                "title": brief.title,
                "objective": brief.objective,
                "audience": brief.audience,
                "platforms": [platform.value for platform in brief.platforms],
                "budget_cents": brief.budget_cents,
                "campaign_type": brief.campaign_type,
                "locale": brief.locale,
                "jurisdiction": brief.jurisdiction,
                "office": brief.office,
                "candidate_name": brief.candidate_name,
                "locality": brief.locality,
                "legal_review_status": brief.legal_review_status,
                "legal_reviewed_by": brief.legal_reviewed_by,
                "constraints": [
                    "sandbox adapters only",
                    "manual Greenlight before Publisher",
                    "no external side effects",
                ],
            },
            detail="Mission chartered with sandbox and approval constraints.",
        )

    def _run_research(self, run: ExecutionRun) -> None:
        trends = self.tools.trends.collect(
            TrendsRequest(
                query=run.brief.objective,
                audience=run.brief.audience,
                platforms=run.brief.platforms,
            )
        )
        browser = self.tools.browser.observe(
            BrowserRequest(
                url="sandbox://market-pulse/fixture",
                purpose="audience language and category framing",
            )
        )
        claims = claim_ledger(run.brief, run.run_id)
        artifact = self._complete_agent(
            run,
            AgentRole.RESEARCH,
            "research_dossier",
            "Dossier de investigación y afirmaciones",
            {
                "trends": to_primitive(trends.result),
                "browser_observation": to_primitive(browser.result),
                "claim_ledger": claims,
                "scholar": {
                    "reencuadre_cognitivo": "Convertir una propuesta verificable en una decisión comprensible.",
                    "tension_del_trade_off": "La claridad no puede simplificar una afirmación más allá de su fuente.",
                    "resolucion_operativa": "Mapear claims, adaptar el canal y mantener Critique y Greenlight.",
                },
                "live_sources_contacted": False,
            },
            evidence=(trends.evidence, browser.evidence),
            detail="Afirmaciones y fuentes consolidadas sin navegación externa.",
        )
        self._remember(
            run,
            AgentRole.RESEARCH,
            "Research mapped {} claims for {}.".format(len(claims), run.brief.audience),
            confidence=0.84 if claims else 0.72,
            tags=("research", "claims", run.brief.campaign_goal),
            artifact=artifact,
            evidence=trends.evidence,
        )

    def _run_strategist(self, run: ExecutionRun) -> None:
        docs = self.tools.context7.lookup(
            Context7Request(
                library="sandbox-adapter-contracts",
                topic="idempotent approval-gated orchestration",
            )
        )
        payload = strategy_payload(run.brief)
        payload["platforms"] = [platform.value for platform in run.brief.platforms]
        payload["documentation_guardrails"] = list(docs.result.recommendations)
        artifact = self._complete_agent(
            run,
            AgentRole.STRATEGIST,
            "channel_strategy",
            "Arquitectura de mensaje por canal",
            payload,
            evidence=(docs.evidence,),
            detail="Estrategia basada en problema, propuesta, prueba y acción.",
        )
        self._remember(
            run,
            AgentRole.STRATEGIST,
            "Strategy prepared {} governed message pillars.".format(len(payload["pillars"])),
            confidence=0.9 if run.brief.campaign_type == "political" else 0.83,
            tags=("strategy", "pillars"),
            artifact=artifact,
            evidence=docs.evidence,
        )

    def _run_growth(self, run: ExecutionRun) -> None:
        forecast = self.tools.meta_ads.forecast(
            MetaAdsRequest(
                objective=run.brief.campaign_goal,
                audience=run.brief.audience,
                budget_cents=run.brief.budget_cents,
                platforms=run.brief.platforms,
            )
        )
        payload = growth_payload(run.brief, to_primitive(forecast.result))
        artifact = self._complete_agent(
            run,
            AgentRole.GROWTH,
            "growth_forecast",
            "Plan de distribución orgánica" if run.brief.campaign_type == "political" else "Synthetic growth forecast",
            payload,
            evidence=(forecast.evidence,),
            detail="Métricas y guardrails definidos sin afirmar alcance electoral."
            if run.brief.campaign_type == "political"
            else "Forecast calculated without ad-account access or spend.",
        )
        self._remember(
            run,
            AgentRole.GROWTH,
            "Growth plan remains synthetic and external spend is disabled.",
            confidence=0.82 if run.brief.campaign_type == "political" else 0.58,
            tags=("growth", "organic", "synthetic"),
            artifact=artifact,
            evidence=forecast.evidence,
        )

    def _run_writer(self, run: ExecutionRun) -> None:
        research = run.artifact("research_dossier")
        payload = copy_payload(run.brief, research.payload.get("claim_ledger", []))
        artifact = self._complete_agent(
            run,
            AgentRole.WRITER,
            "copy_deck",
            "Copy gobernado por plataforma",
            payload,
            detail="Variantes listas para crítica factual y revisión humana.",
        )
        self._remember(
            run,
            AgentRole.WRITER,
            "Drafted {} platform variants with explicit claim mapping.".format(
                len(payload["variants"])
            ),
            confidence=0.93,
            tags=("copy", "draft", run.brief.locale),
            artifact=artifact,
        )

    def _run_media(self, run: ExecutionRun) -> None:
        primary_platform = run.brief.platforms[0]
        video = self.tools.video_optimizer.plan(
            VideoOptimizationRequest(
                source_asset=run.brief.source_asset,
                platform=primary_platform,
                target_duration_seconds=15,
            )
        )
        motion = self.tools.image_to_video.plan(
            ImageToVideoRequest(
                source_asset=run.brief.source_asset,
                prompt="Motion study for {}".format(run.brief.title),
                target_duration_seconds=8,
            )
        )
        payload = media_payload(
            run.brief,
            video=to_primitive(video.result),
            image_to_video=to_primitive(motion.result),
        )
        artifact = self._complete_agent(
            run,
            AgentRole.MEDIA,
            "media_plan",
            "Plan de medios accesible",
            payload,
            evidence=(video.evidence, motion.evidence),
            detail="Plan editorial creado; no se renderizó ni publicó media.",
        )
        self._remember(
            run,
            AgentRole.MEDIA,
            "Media plan is accessible, non-rendered and publication-blocking.",
            confidence=0.96,
            tags=("media", "plan", "sandbox"),
            artifact=artifact,
            evidence=video.evidence,
        )

    def _run_risk(self, run: ExecutionRun) -> None:
        inspection = self.tools.github.inspect(
            GitHubRequest(
                repository="sandbox://local/agency-runtime",
                paths=("policy/claims", "policy/platforms"),
                question="Does the sandbox package preserve the Greenlight boundary?",
            )
        )
        research = run.artifact("research_dossier")
        writer = run.artifact("copy_deck")
        payload = critique_payload(
            run.brief,
            claims=research.payload.get("claim_ledger", []),
            variants=writer.payload.get("variants", {}),
        )
        payload["codebase_inspection"] = to_primitive(inspection.result)
        artifact = self._complete_agent(
            run,
            AgentRole.RISK,
            "risk_report",
            "Crítica pre-Greenlight",
            payload,
            evidence=(inspection.evidence,),
            detail="Crítica factual y de canal completada; Greenlight humano sigue siendo obligatorio.",
        )
        self._remember(
            run,
            AgentRole.RISK,
            "Critique evaluated {} checks; publication_eligible={}.".format(
                len(payload["checks"]), payload["publication_eligible"]
            ),
            confidence=1.0,
            tags=("risk", "critique", "greenlight"),
            artifact=artifact,
            evidence=inspection.evidence,
        )

    def _begin(self, run: ExecutionRun, role: AgentRole, detail: str) -> None:
        run.state_for(role).update(AgentStatus.PROCESSING, 10, detail)
        self._event(
            run,
            role,
            "agent_started",
            AgentStatus.PROCESSING.value,
            detail,
        )

    def _complete_agent(
        self,
        run: ExecutionRun,
        role: AgentRole,
        kind: str,
        title: str,
        payload: Mapping[str, object],
        evidence: Sequence[ToolEvidence] = (),
        detail: str = "Artifact ready",
    ) -> Artifact:
        artifact = Artifact(
            artifact_id=stable_id("art", run.run_id, role, kind, payload),
            kind=kind,
            title=title,
            created_by=role,
            payload=payload,
            evidence_ids=tuple(item.evidence_id for item in evidence),
        )
        for item in evidence:
            if all(existing.evidence_id != item.evidence_id for existing in run.evidence):
                run.evidence.append(item)
        run.add_artifact(artifact)
        run.state_for(role).update(AgentStatus.READY, 100, detail)
        self._event(
            run,
            role,
            "artifact_ready",
            AgentStatus.READY.value,
            detail,
            artifact_ids=(artifact.artifact_id,),
            evidence_ids=artifact.evidence_ids,
        )
        return artifact

    def _event(
        self,
        run: ExecutionRun,
        role: AgentRole,
        action: str,
        status: str,
        detail: str,
        artifact_ids: Tuple[str, ...] = (),
        evidence_ids: Tuple[str, ...] = (),
    ) -> None:
        run.trace.append(
            TraceEvent(
                sequence=len(run.trace) + 1,
                timestamp=self._clock(),
                role=role,
                action=action,
                status=status,
                detail=detail,
                artifact_ids=artifact_ids,
                evidence_ids=evidence_ids,
            )
        )

    def _remember(
        self,
        run: ExecutionRun,
        role: AgentRole,
        content: str,
        confidence: float,
        tags: Sequence[str],
        artifact: Artifact,
        evidence: Optional[ToolEvidence] = None,
    ) -> None:
        trace_id = run.trace[-1].sequence if run.trace else 0
        provenance = Provenance(
            source="agency_run",
            locator="sandbox://runs/{}/artifacts/{}".format(
                run.run_id, artifact.artifact_id
            ),
            observed_at=self._clock(),
            tool=evidence.tool if evidence is not None else "agency_runtime",
            trace_id="{}:{}".format(run.run_id, trace_id),
        )
        observation = self.memory.observe(
            content=content,
            provenance=provenance,
            confidence=confidence,
            tags=tuple(tags) + (role.value,),
        )
        self.memory.store(observation)
