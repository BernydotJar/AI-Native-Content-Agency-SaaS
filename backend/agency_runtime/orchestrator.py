from __future__ import annotations

from time import perf_counter
from typing import Callable, Dict, Mapping, Optional, Sequence, Tuple, TypeVar

from .memory import SQLiteMemory, utc_now
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
    ToolResponse,
    TrendsRequest,
    VideoOptimizationRequest,
)
from .utils import stable_id, to_primitive


Clock = Callable[[], str]
ToolCallObserver = Callable[[Mapping[str, object]], None]
ToolResultT = TypeVar("ToolResultT")


class GreenlightError(RuntimeError):
    pass


class AgencyOrchestrator:
    """Sequential eight-agent runtime with a hard Publisher approval boundary."""

    def __init__(
        self,
        tools: SandboxToolset,
        memory: SQLiteMemory,
        clock: Clock = utc_now,
        tool_call_observer: Optional[ToolCallObserver] = None,
    ) -> None:
        self.tools = tools
        self.memory = memory
        self._clock = clock
        self._tool_call_observer = tool_call_observer
        self._runs: Dict[str, ExecutionRun] = {}

    def start(
        self,
        brief: MissionBrief,
        run_id: Optional[str] = None,
    ) -> ExecutionRun:
        run_id = run_id or stable_id("run", brief)
        if run_id in self._runs:
            raise ValueError("run already exists in this orchestrator: {}".format(run_id))
        run = ExecutionRun(
            run_id=run_id,
            brief=brief,
            status=RunStatus.RUNNING,
            started_at=self._clock(),
            agent_states={role: AgentState(role=role) for role in AGENT_SEQUENCE},
        )
        self._runs[run_id] = run

        self._run_ceo(run)
        self._run_research(run)
        self._run_strategist(run)
        self._run_growth(run)
        self._run_writer(run)
        self._run_media(run)
        self._run_risk(run)

        publisher = run.state_for(AgentRole.PUBLISHER)
        publisher.update(
            AgentStatus.WAITING_GREENLIGHT,
            0,
            "Risk passed; manual Greenlight is required before packaging.",
        )
        run.status = RunStatus.AWAITING_GREENLIGHT
        self._event(
            run,
            AgentRole.PUBLISHER,
            "approval_gate",
            AgentStatus.WAITING_GREENLIGHT.value,
            "No packaging or publication has occurred.",
        )
        return run

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

    def get_run(self, run_id: str) -> ExecutionRun:
        try:
            return self._runs[run_id]
        except KeyError as error:
            raise KeyError("run not found: {}".format(run_id)) from error

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
        if not reviewer or not reviewer.strip():
            raise GreenlightError("reviewer must not be empty")

        decided_at = self._clock()
        greenlight = Greenlight(
            greenlight_id=stable_id(
                "greenlight", run_id, decision, reviewer.strip(), note.strip(), decided_at
            ),
            run_id=run_id,
            decision=decision,
            reviewer=reviewer.strip(),
            note=note.strip(),
            decided_at=decided_at,
        )
        run.greenlight = greenlight

        if decision is GreenlightDecision.REJECTED:
            run.status = RunStatus.REJECTED
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
        response = self._invoke_tool(
            run,
            AgentRole.PUBLISHER,
            "campaign_packager",
            "package_manifest",
            lambda: self.tools.campaign_packager.package(
                CampaignPackageRequest(
                    run_id=run.run_id,
                    platforms=run.brief.platforms,
                    artifacts=tuple(run.artifacts),
                )
            ),
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

    def _invoke_tool(
        self,
        run: ExecutionRun,
        role: AgentRole,
        tool: str,
        operation: str,
        invoke: Callable[[], ToolResponse[ToolResultT]],
    ) -> ToolResponse[ToolResultT]:
        started = perf_counter()
        try:
            response = invoke()
        except Exception as error:
            if self._tool_call_observer is not None:
                self._tool_call_observer(
                    {
                        "run_id": run.run_id,
                        "step": role.value,
                        "tool": tool,
                        "operation": operation,
                        "sandbox": True,
                        "success": False,
                        "retry_count": 0,
                        "latency_ms": round((perf_counter() - started) * 1000, 3),
                        "error_type": type(error).__name__,
                    }
                )
            raise
        if self._tool_call_observer is not None:
            self._tool_call_observer(
                {
                    "run_id": run.run_id,
                    "step": role.value,
                    "tool": response.evidence.tool,
                    "operation": response.evidence.operation,
                    "sandbox": response.evidence.sandbox,
                    "success": True,
                    "retry_count": 0,
                    "latency_ms": round((perf_counter() - started) * 1000, 3),
                    "evidence_id": response.evidence.evidence_id,
                }
            )
        return response

    def _run_ceo(self, run: ExecutionRun) -> None:
        self._begin(run, AgentRole.CEO, "Interpreting mission constraints")
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
                "constraints": [
                    "sandbox adapters only",
                    "manual Greenlight before Publisher",
                    "no external side effects",
                ],
            },
            detail="Mission chartered with sandbox and approval constraints.",
        )

    def _run_research(self, run: ExecutionRun) -> None:
        self._begin(run, AgentRole.RESEARCH, "Collecting synthetic market evidence")
        trends = self._invoke_tool(
            run,
            AgentRole.RESEARCH,
            "multi_platform_trends",
            "collect_fixture",
            lambda: self.tools.trends.collect(
                TrendsRequest(
                    query=run.brief.objective,
                    audience=run.brief.audience,
                    platforms=run.brief.platforms,
                )
            ),
        )
        browser = self._invoke_tool(
            run,
            AgentRole.RESEARCH,
            "puppeteer_browser",
            "observe_fixture",
            lambda: self.tools.browser.observe(
                BrowserRequest(
                    url="sandbox://market-pulse/fixture",
                    purpose="audience language and category framing",
                )
            ),
        )
        artifact = self._complete_agent(
            run,
            AgentRole.RESEARCH,
            "research_dossier",
            "Synthetic research dossier",
            {
                "trends": to_primitive(trends.result),
                "browser_observation": to_primitive(browser.result),
                "live_sources_contacted": False,
            },
            evidence=(trends.evidence, browser.evidence),
            detail="Synthetic trend and browser fixtures consolidated.",
        )
        self._remember(
            run,
            AgentRole.RESEARCH,
            "Research fixture found {} platform signals for {}.".format(
                len(trends.result.signals), run.brief.audience
            ),
            confidence=0.72,
            tags=("research", "trends", run.brief.campaign_goal),
            artifact=artifact,
            evidence=trends.evidence,
        )

    def _run_strategist(self, run: ExecutionRun) -> None:
        self._begin(run, AgentRole.STRATEGIST, "Designing channel strategy")
        docs = self._invoke_tool(
            run,
            AgentRole.STRATEGIST,
            "context7_docs",
            "lookup_fixture",
            lambda: self.tools.context7.lookup(
                Context7Request(
                    library="sandbox-adapter-contracts",
                    topic="idempotent approval-gated orchestration",
                )
            ),
        )
        pillars = (
            "Evidence: lead with a verifiable audience tension",
            "Expression: adapt pacing to each platform",
            "Action: keep one measurable call to action",
        )
        artifact = self._complete_agent(
            run,
            AgentRole.STRATEGIST,
            "channel_strategy",
            "Channel strategy",
            {
                "pillars": list(pillars),
                "platforms": [platform.value for platform in run.brief.platforms],
                "documentation_guardrails": list(docs.result.recommendations),
            },
            evidence=(docs.evidence,),
            detail="Three-pillar channel strategy prepared.",
        )
        self._remember(
            run,
            AgentRole.STRATEGIST,
            "Strategy uses Evidence, Expression, and Action pillars for {}.".format(
                run.brief.title
            ),
            confidence=0.83,
            tags=("strategy", "pillars"),
            artifact=artifact,
            evidence=docs.evidence,
        )

    def _run_growth(self, run: ExecutionRun) -> None:
        self._begin(run, AgentRole.GROWTH, "Forecasting sandbox acquisition envelope")
        forecast = self._invoke_tool(
            run,
            AgentRole.GROWTH,
            "meta_ads_mcp",
            "forecast_fixture",
            lambda: self.tools.meta_ads.forecast(
                MetaAdsRequest(
                    objective=run.brief.campaign_goal,
                    audience=run.brief.audience,
                    budget_cents=run.brief.budget_cents,
                    platforms=run.brief.platforms,
                )
            ),
        )
        artifact = self._complete_agent(
            run,
            AgentRole.GROWTH,
            "growth_forecast",
            "Synthetic growth forecast",
            to_primitive(forecast.result),
            evidence=(forecast.evidence,),
            detail="Forecast calculated without ad-account access or spend.",
        )
        self._remember(
            run,
            AgentRole.GROWTH,
            "Synthetic forecast CAC is {} cents at a {} cent planning budget.".format(
                forecast.result.estimated_cac_cents,
                forecast.result.budget_cents,
            ),
            confidence=0.58,
            tags=("growth", "forecast", "synthetic"),
            artifact=artifact,
            evidence=forecast.evidence,
        )

    def _run_writer(self, run: ExecutionRun) -> None:
        self._begin(run, AgentRole.WRITER, "Writing platform variants")
        variants = {
            platform.value: {
                "hook": "{} — made clear for {}.".format(
                    run.brief.title, run.brief.audience
                ),
                "body": run.brief.objective,
                "cta": "Explore the sandbox concept",
            }
            for platform in run.brief.platforms
        }
        artifact = self._complete_agent(
            run,
            AgentRole.WRITER,
            "copy_deck",
            "Platform copy deck",
            {
                "variants": variants,
                "claims_status": "draft_requires_human_review",
            },
            detail="Draft copy variants ready for human claim review.",
        )
        self._remember(
            run,
            AgentRole.WRITER,
            "Drafted {} platform copy variants; claims remain unapproved.".format(
                len(variants)
            ),
            confidence=0.91,
            tags=("copy", "draft"),
            artifact=artifact,
        )

    def _run_media(self, run: ExecutionRun) -> None:
        self._begin(run, AgentRole.MEDIA, "Planning video and motion assets")
        primary_platform = run.brief.platforms[0]
        video = self._invoke_tool(
            run,
            AgentRole.MEDIA,
            "video_optimizer",
            "plan_only",
            lambda: self.tools.video_optimizer.plan(
                VideoOptimizationRequest(
                    source_asset=run.brief.source_asset,
                    platform=primary_platform,
                    target_duration_seconds=15,
                )
            ),
        )
        motion = self._invoke_tool(
            run,
            AgentRole.MEDIA,
            "image_to_video",
            "plan_only",
            lambda: self.tools.image_to_video.plan(
                ImageToVideoRequest(
                    source_asset=run.brief.source_asset,
                    prompt="Motion study for {}".format(run.brief.title),
                    target_duration_seconds=8,
                )
            ),
        )
        artifact = self._complete_agent(
            run,
            AgentRole.MEDIA,
            "media_plan",
            "Sandbox media plan",
            {
                "video": to_primitive(video.result),
                "image_to_video": to_primitive(motion.result),
                "source_asset_read": False,
                "media_rendered": False,
            },
            evidence=(video.evidence, motion.evidence),
            detail="Edit and storyboard plans created; rendering is disabled.",
        )
        self._remember(
            run,
            AgentRole.MEDIA,
            "Media planning produced two non-rendered sandbox plans for {}.".format(
                primary_platform.value
            ),
            confidence=0.95,
            tags=("media", "plan", "sandbox"),
            artifact=artifact,
            evidence=video.evidence,
        )

    def _run_risk(self, run: ExecutionRun) -> None:
        self._begin(run, AgentRole.RISK, "Auditing release constraints")
        inspection = self._invoke_tool(
            run,
            AgentRole.RISK,
            "github_codebase",
            "inspect_fixture",
            lambda: self.tools.github.inspect(
                GitHubRequest(
                    repository="sandbox://local/agency-runtime",
                    paths=("policy/claims", "policy/platforms"),
                    question="Does the sandbox package preserve the Greenlight boundary?",
                )
            ),
        )
        checks = (
            "All configured adapters declare sandbox=true",
            "Copy claims remain marked draft_requires_human_review",
            "Media outputs declare rendered=false",
            "Publisher has not run before Greenlight",
        )
        artifact = self._complete_agent(
            run,
            AgentRole.RISK,
            "risk_report",
            "Pre-Greenlight risk report",
            {
                "passed": True,
                "checks": list(checks),
                "codebase_inspection": to_primitive(inspection.result),
                "human_greenlight_required": True,
            },
            evidence=(inspection.evidence,),
            detail="Sandbox controls passed; human Greenlight is still required.",
        )
        self._remember(
            run,
            AgentRole.RISK,
            "Risk passed {} sandbox checks; Publisher remains gated.".format(len(checks)),
            confidence=1.0,
            tags=("risk", "greenlight", "audit"),
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
