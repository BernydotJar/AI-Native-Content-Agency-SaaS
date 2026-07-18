import { describe, expect, it } from "vitest";
import {
  CAMPAIGN_CHANNELS,
  SIMULATION_TOOL_CATALOG,
  SOCIAL_PLATFORMS,
  TOOL_CONNECTION_STATES,
  TREND_SIGNALS,
  createScholarExplanation,
  mixTrendSignals,
  packageCampaign,
  type SocialPlatform,
} from "./simulationRuntime";

const THESIS = "Build an AI-native operating system";
const AUDIENCE = "engineering founders";

describe("simulation tool contracts", () => {
  it("publishes exactly the eight required tools as side-effect-free mocks", () => {
    expect(SIMULATION_TOOL_CATALOG).toHaveLength(8);
    expect(SIMULATION_TOOL_CATALOG.map((tool) => tool.id)).toEqual([
      "MultiPlatformTrendsTool",
      "MetaAdsMcpTool",
      "PuppeteerBrowserTool",
      "GitHubCodebaseTool",
      "Context7DocsTool",
      "VideoOptimizerTool",
      "ImageToVideoTool",
      "CampaignPackagerTool",
    ]);
    expect(SIMULATION_TOOL_CATALOG.every((tool) => (
      tool.state === "mock" && tool.sandbox && !tool.externalSideEffects
    ))).toBe(true);
    expect(TOOL_CONNECTION_STATES).toEqual(["disconnected", "mock", "connected", "error"]);
  });
});

describe("trend mixing", () => {
  it("contains deterministic signals for all four required sources", () => {
    const platforms: readonly SocialPlatform[] = TREND_SIGNALS.map((signal) => signal.platform);

    expect(TREND_SIGNALS).toHaveLength(4);
    expect(platforms).toEqual(SOCIAL_PLATFORMS);
    expect(new Set(platforms).size).toBe(4);
    expect(TREND_SIGNALS.every((signal) => signal.sourceState === "mock" && signal.sandbox)).toBe(true);
  });

  it("adapts every insight to the supplied thesis and audience", () => {
    const result = mixTrendSignals(THESIS, AUDIENCE, ["scholar-nlp"]);
    const serialized = JSON.stringify(result.insights);

    expect(result).toMatchObject({
      thesis: THESIS,
      audience: AUDIENCE,
      mode: "sandbox",
      sandbox: true,
    });
    expect(result.insights).toHaveLength(4);
    expect(serialized).toContain(THESIS);
    expect(serialized).toContain(AUDIENCE);
    expect(mixTrendSignals(THESIS, AUDIENCE, ["scholar-nlp"])).toEqual(result);
  });

  it("changes its strategic overlays when enabled skills change", () => {
    const discovery = mixTrendSignals(THESIS, AUDIENCE, ["ai-seo"]);
    const retention = mixTrendSignals(THESIS, AUDIENCE, ["churn-prevention", "brand-guard"]);

    expect(discovery.enabledSkills).toEqual(["ai-seo"]);
    expect(retention.enabledSkills).toEqual(["churn-prevention", "brand-guard"]);
    expect(discovery.insights[0].skillEffects).not.toEqual(retention.insights[0].skillEffects);
    expect(JSON.stringify(discovery.insights)).toContain("AI-SEO");
    expect(JSON.stringify(retention.insights)).toContain("Retention cue");
  });

  it("always returns the three Scholar points in the required order", () => {
    const scholar = createScholarExplanation(THESIS, AUDIENCE);

    expect(scholar).toHaveLength(3);
    expect(scholar.map((point) => point.id)).toEqual([
      "cognitive-reframe",
      "tradeoff-tension",
      "operational-resolution",
    ]);
  });
});

describe("campaign packaging", () => {
  it("packages exactly three thread parts plus every required campaign asset", () => {
    const campaign = packageCampaign({
      thesis: THESIS,
      audience: AUDIENCE,
      enabledSkills: ["scholar-nlp", "brand-guard"],
      channels: CAMPAIGN_CHANNELS,
      durationDays: 12,
      budget: 3_500,
    });

    expect(campaign.thread).toHaveLength(3);
    expect(campaign.thread.map((part) => part.part)).toEqual([1, 2, 3]);
    expect(campaign.videoHook).toBeDefined();
    expect(campaign.paidConcept).toMatchObject({ sandbox: true, audience: AUDIENCE });
    expect(campaign.newsletter.sections).toHaveLength(3);
    expect(campaign.schedule).toHaveLength(5);
    expect(campaign.channels).toEqual(CAMPAIGN_CHANNELS);
    expect(campaign.durationDays).toBe(12);
    expect(campaign.schedule.at(-1)?.offsetHours).toBe(11 * 24);
    expect(campaign.paidConcept.dailyBudget).toBe(210);
    expect(campaign.budget).toBe(3_500);
    expect(Object.values(campaign.budgetAllocation).reduce((sum, value) => sum + value, 0)).toBe(3_500);
    expect(campaign.mode).toBe("sandbox");
  });

  it("uses thesis, audience and skills in a stable package identity and content", () => {
    const first = packageCampaign({
      thesis: THESIS,
      audience: AUDIENCE,
      enabledSkills: { "scholar-nlp": true, "ai-seo": true },
      channels: ["X", "Instagram"],
      budget: 1_250,
    });
    const repeated = packageCampaign({
      thesis: THESIS,
      audience: AUDIENCE,
      enabledSkills: { "scholar-nlp": true, "ai-seo": true },
      channels: ["X", "Instagram"],
      budget: 1_250,
    });
    const differentSkill = packageCampaign({
      thesis: THESIS,
      audience: AUDIENCE,
      enabledSkills: ["churn-prevention"],
      channels: ["X", "Instagram"],
      budget: 1_250,
    });

    expect(repeated).toEqual(first);
    expect(first.campaignId).not.toBe(differentSkill.campaignId);
    expect(JSON.stringify(first)).toContain(THESIS);
    expect(JSON.stringify(first)).toContain(AUDIENCE);
    expect(first.trendMix.enabledSkills).toEqual(["scholar-nlp", "ai-seo"]);
  });

  it("requires a Meta surface before creating a paid campaign concept", () => {
    expect(() => packageCampaign({
      thesis: THESIS,
      audience: AUDIENCE,
      channels: ["X", "LinkedIn"],
      budget: 1_000,
    })).toThrow(/Facebook or Instagram/);
  });

  it("requires X before creating the three-part thread", () => {
    expect(() => packageCampaign({
      thesis: THESIS,
      audience: AUDIENCE,
      channels: ["LinkedIn", "Facebook"],
      budget: 1_000,
    })).toThrow(/include X/);
  });
});
