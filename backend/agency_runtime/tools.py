from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Generic, Protocol, Tuple, TypeVar

from .models import Artifact, Platform, ToolEvidence
from .utils import stable_id, to_primitive


ResultT = TypeVar("ResultT")


@dataclass(frozen=True)
class ToolResponse(Generic[ResultT]):
    result: ResultT
    evidence: ToolEvidence


@dataclass(frozen=True)
class TrendsRequest:
    query: str
    audience: str
    platforms: Tuple[Platform, ...]


@dataclass(frozen=True)
class TrendSignal:
    platform: Platform
    topic: str
    relevance: float
    rationale: str


@dataclass(frozen=True)
class TrendsReport:
    query: str
    signals: Tuple[TrendSignal, ...]
    collection_mode: str = "deterministic_fixture"


@dataclass(frozen=True)
class MetaAdsRequest:
    objective: str
    audience: str
    budget_cents: int
    platforms: Tuple[Platform, ...]


@dataclass(frozen=True)
class MetaAdsForecast:
    budget_cents: int
    estimated_reach_low: int
    estimated_reach_high: int
    estimated_cac_cents: int
    execution_mode: str = "forecast_only"


@dataclass(frozen=True)
class BrowserRequest:
    url: str
    purpose: str


@dataclass(frozen=True)
class BrowserObservation:
    requested_url: str
    headings: Tuple[str, ...]
    notes: Tuple[str, ...]
    navigation_performed: bool = False


@dataclass(frozen=True)
class GitHubRequest:
    repository: str
    paths: Tuple[str, ...]
    question: str


@dataclass(frozen=True)
class CodebaseInspection:
    repository: str
    findings: Tuple[str, ...]
    inspection_mode: str = "deterministic_fixture"
    changes_performed: bool = False


@dataclass(frozen=True)
class Context7Request:
    library: str
    topic: str


@dataclass(frozen=True)
class DocsFinding:
    library: str
    topic: str
    recommendations: Tuple[str, ...]
    lookup_mode: str = "deterministic_fixture"


@dataclass(frozen=True)
class VideoOptimizationRequest:
    source_asset: str
    platform: Platform
    target_duration_seconds: int


@dataclass(frozen=True)
class VideoOptimizationPlan:
    source_asset: str
    platform: Platform
    target_duration_seconds: int
    operations: Tuple[str, ...]
    output_uri: str
    rendered: bool = False


@dataclass(frozen=True)
class ImageToVideoRequest:
    source_asset: str
    prompt: str
    target_duration_seconds: int


@dataclass(frozen=True)
class ImageToVideoPlan:
    source_asset: str
    storyboard: Tuple[str, ...]
    output_uri: str
    rendered: bool = False


@dataclass(frozen=True)
class CampaignPackageRequest:
    run_id: str
    platforms: Tuple[Platform, ...]
    artifacts: Tuple[Artifact, ...]


@dataclass(frozen=True)
class CampaignPackage:
    manifest_uri: str
    artifact_ids: Tuple[str, ...]
    platform_targets: Tuple[Platform, ...]
    checksums: Tuple[str, ...]
    publication_performed: bool = False


class MultiPlatformTrendsTool(Protocol):
    sandbox: bool

    def collect(self, request: TrendsRequest) -> ToolResponse[TrendsReport]: ...


class MetaAdsMcpTool(Protocol):
    sandbox: bool

    def forecast(self, request: MetaAdsRequest) -> ToolResponse[MetaAdsForecast]: ...


class PuppeteerBrowserTool(Protocol):
    sandbox: bool

    def observe(self, request: BrowserRequest) -> ToolResponse[BrowserObservation]: ...


class GitHubCodebaseTool(Protocol):
    sandbox: bool

    def inspect(self, request: GitHubRequest) -> ToolResponse[CodebaseInspection]: ...


class Context7DocsTool(Protocol):
    sandbox: bool

    def lookup(self, request: Context7Request) -> ToolResponse[DocsFinding]: ...


class VideoOptimizerTool(Protocol):
    sandbox: bool

    def plan(self, request: VideoOptimizationRequest) -> ToolResponse[VideoOptimizationPlan]: ...


class ImageToVideoTool(Protocol):
    sandbox: bool

    def plan(self, request: ImageToVideoRequest) -> ToolResponse[ImageToVideoPlan]: ...


class CampaignPackagerTool(Protocol):
    sandbox: bool

    def package(self, request: CampaignPackageRequest) -> ToolResponse[CampaignPackage]: ...


def _evidence(tool: str, operation: str, summary: str, result: object) -> ToolEvidence:
    payload = to_primitive(result)
    return ToolEvidence(
        evidence_id=stable_id("ev", tool, operation, payload),
        tool=tool,
        operation=operation,
        sandbox=True,
        summary=summary,
        payload=payload,
        references=("sandbox://{}/{}".format(tool, operation),),
    )


def _score(seed: str, minimum: int, maximum: int) -> int:
    value = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16)
    return minimum + value % (maximum - minimum + 1)


class MockMultiPlatformTrendsTool:
    sandbox = True

    def collect(self, request: TrendsRequest) -> ToolResponse[TrendsReport]:
        topic_map = {
            Platform.X: "expert conversation",
            Platform.FACEBOOK: "community proof",
            Platform.TIKTOK: "fast transformation",
            Platform.INSTAGRAM: "visual ritual",
        }
        signals = tuple(
            TrendSignal(
                platform=platform,
                topic="{} · {}".format(request.query, topic_map[platform]),
                relevance=_score(request.query + platform.value, 72, 94) / 100.0,
                rationale="Synthetic platform prior for {} in the requested audience.".format(
                    request.audience
                ),
            )
            for platform in request.platforms
        )
        result = TrendsReport(query=request.query, signals=signals)
        return ToolResponse(
            result=result,
            evidence=_evidence(
                "multi_platform_trends",
                "collect_fixture",
                "Generated synthetic X/Facebook/TikTok/Instagram trend signals; no network query.",
                result,
            ),
        )


class MockMetaAdsMcpTool:
    sandbox = True

    def forecast(self, request: MetaAdsRequest) -> ToolResponse[MetaAdsForecast]:
        budget = request.budget_cents
        reach_low = max(0, budget // 18)
        reach_high = max(reach_low, budget // 9)
        estimated_cac = _score(request.audience + request.objective, 850, 2400)
        result = MetaAdsForecast(
            budget_cents=budget,
            estimated_reach_low=reach_low,
            estimated_reach_high=reach_high,
            estimated_cac_cents=estimated_cac,
        )
        return ToolResponse(
            result=result,
            evidence=_evidence(
                "meta_ads_mcp",
                "forecast_fixture",
                "Calculated a synthetic forecast; no Meta API call, campaign mutation, or spend.",
                result,
            ),
        )


class MockPuppeteerBrowserTool:
    sandbox = True

    def observe(self, request: BrowserRequest) -> ToolResponse[BrowserObservation]:
        result = BrowserObservation(
            requested_url=request.url,
            headings=("Fixture market pulse", "Fixture audience language"),
            notes=(
                "No page was opened.",
                "The observation is a deterministic stand-in for: {}.".format(request.purpose),
            ),
        )
        return ToolResponse(
            result=result,
            evidence=_evidence(
                "puppeteer_browser",
                "observe_fixture",
                "Returned local browser-observation fixtures; navigation was not performed.",
                result,
            ),
        )


class MockGitHubCodebaseTool:
    sandbox = True

    def inspect(self, request: GitHubRequest) -> ToolResponse[CodebaseInspection]:
        paths = ", ".join(request.paths) if request.paths else "no paths supplied"
        result = CodebaseInspection(
            repository=request.repository,
            findings=(
                "Fixture policy scan for {}.".format(paths),
                "No secrets, remote branches, issues, or pull requests were accessed.",
                "Question recorded: {}".format(request.question),
            ),
        )
        return ToolResponse(
            result=result,
            evidence=_evidence(
                "github_codebase",
                "inspect_fixture",
                "Returned a synthetic codebase-policy inspection; GitHub was not contacted.",
                result,
            ),
        )


class MockContext7DocsTool:
    sandbox = True

    def lookup(self, request: Context7Request) -> ToolResponse[DocsFinding]:
        result = DocsFinding(
            library=request.library,
            topic=request.topic,
            recommendations=(
                "Treat adapter outputs as untrusted input.",
                "Keep idempotency keys and approval records in the execution trace.",
                "Use official documentation before replacing this fixture with a live adapter.",
            ),
        )
        return ToolResponse(
            result=result,
            evidence=_evidence(
                "context7_docs",
                "lookup_fixture",
                "Returned bundled documentation guidance; Context7 was not contacted.",
                result,
            ),
        )


class MockVideoOptimizerTool:
    sandbox = True

    def plan(self, request: VideoOptimizationRequest) -> ToolResponse[VideoOptimizationPlan]:
        result = VideoOptimizationPlan(
            source_asset=request.source_asset,
            platform=request.platform,
            target_duration_seconds=request.target_duration_seconds,
            operations=(
                "derive {}s edit decision list".format(request.target_duration_seconds),
                "reserve safe-title and caption regions",
                "normalize loudness in a future renderer",
            ),
            output_uri="sandbox://media/{}/video-plan.json".format(request.platform.value),
        )
        return ToolResponse(
            result=result,
            evidence=_evidence(
                "video_optimizer",
                "plan_only",
                "Created an edit plan; no source file was read and no video was rendered.",
                result,
            ),
        )


class MockImageToVideoTool:
    sandbox = True

    def plan(self, request: ImageToVideoRequest) -> ToolResponse[ImageToVideoPlan]:
        result = ImageToVideoPlan(
            source_asset=request.source_asset,
            storyboard=(
                "0-2s: slow reveal",
                "2-5s: product or idea focus",
                "5-{}s: clear call to action".format(request.target_duration_seconds),
            ),
            output_uri="sandbox://media/image-to-video/storyboard.json",
        )
        return ToolResponse(
            result=result,
            evidence=_evidence(
                "image_to_video",
                "plan_only",
                "Created a storyboard fixture; no image was read and no media was generated.",
                result,
            ),
        )


class MockCampaignPackagerTool:
    sandbox = True

    def __init__(self) -> None:
        self.call_count = 0

    def package(self, request: CampaignPackageRequest) -> ToolResponse[CampaignPackage]:
        self.call_count += 1
        artifact_ids = tuple(item.artifact_id for item in request.artifacts)
        checksums = tuple(
            hashlib.sha256(item.artifact_id.encode("utf-8")).hexdigest()[:16]
            for item in request.artifacts
        )
        result = CampaignPackage(
            manifest_uri="sandbox://campaigns/{}/manifest.json".format(request.run_id),
            artifact_ids=artifact_ids,
            platform_targets=request.platforms,
            checksums=checksums,
        )
        return ToolResponse(
            result=result,
            evidence=_evidence(
                "campaign_packager",
                "package_manifest",
                "Created an in-memory sandbox manifest; no content was published.",
                result,
            ),
        )


@dataclass(frozen=True)
class SandboxToolset:
    trends: MultiPlatformTrendsTool
    meta_ads: MetaAdsMcpTool
    browser: PuppeteerBrowserTool
    github: GitHubCodebaseTool
    context7: Context7DocsTool
    video_optimizer: VideoOptimizerTool
    image_to_video: ImageToVideoTool
    campaign_packager: CampaignPackagerTool

    def __post_init__(self) -> None:
        tools = (
            self.trends,
            self.meta_ads,
            self.browser,
            self.github,
            self.context7,
            self.video_optimizer,
            self.image_to_video,
            self.campaign_packager,
        )
        if not all(tool.sandbox for tool in tools):
            raise ValueError("SandboxToolset refuses non-sandbox tool implementations")


def build_sandbox_toolset() -> SandboxToolset:
    return SandboxToolset(
        trends=MockMultiPlatformTrendsTool(),
        meta_ads=MockMetaAdsMcpTool(),
        browser=MockPuppeteerBrowserTool(),
        github=MockGitHubCodebaseTool(),
        context7=MockContext7DocsTool(),
        video_optimizer=MockVideoOptimizerTool(),
        image_to_video=MockImageToVideoTool(),
        campaign_packager=MockCampaignPackagerTool(),
    )
