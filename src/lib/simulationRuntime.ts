/**
 * Pure, deterministic contracts for the War Room demo runtime.
 *
 * Nothing in this module performs network requests or mutates an external
 * system. Every fixture and generated artifact is explicitly sandbox-only.
 */

export const TOOL_CONNECTION_STATES = [
  "disconnected",
  "mock",
  "connected",
  "error",
] as const;

export type ToolConnectionState = (typeof TOOL_CONNECTION_STATES)[number];

export type SimulationToolId =
  | "MultiPlatformTrendsTool"
  | "MetaAdsMcpTool"
  | "PuppeteerBrowserTool"
  | "GitHubCodebaseTool"
  | "Context7DocsTool"
  | "VideoOptimizerTool"
  | "ImageToVideoTool"
  | "CampaignPackagerTool";

export interface SandboxToolContract {
  id: SimulationToolId;
  label: string;
  category: "sensor" | "mcp-adapter" | "media" | "packaging";
  description: string;
  capabilities: readonly string[];
  state: ToolConnectionState;
  supportedStates: readonly ToolConnectionState[];
  sandbox: true;
  externalSideEffects: false;
}

const REMOTE_ADAPTER_STATES = TOOL_CONNECTION_STATES;
const LOCAL_SANDBOX_STATES = ["mock", "error"] as const;

export const SIMULATION_TOOL_CATALOG = [
  {
    id: "MultiPlatformTrendsTool",
    label: "Multi-platform trend sensor",
    category: "sensor",
    description: "Returns deterministic trend fixtures for four social platforms.",
    capabilities: ["scan-social-signals", "normalize-trends", "rank-momentum"],
    state: "mock",
    supportedStates: REMOTE_ADAPTER_STATES,
    sandbox: true,
    externalSideEffects: false,
  },
  {
    id: "MetaAdsMcpTool",
    label: "Meta Ads MCP adapter",
    category: "mcp-adapter",
    description: "Drafts paid-media instructions without creating a live campaign.",
    capabilities: ["draft-campaign", "model-targeting", "simulate-bids"],
    state: "mock",
    supportedStates: REMOTE_ADAPTER_STATES,
    sandbox: true,
    externalSideEffects: false,
  },
  {
    id: "PuppeteerBrowserTool",
    label: "Browser QA MCP adapter",
    category: "mcp-adapter",
    description: "Models browser audit requests without opening a remote browser.",
    capabilities: ["describe-viewport-check", "model-layout-audit"],
    state: "mock",
    supportedStates: REMOTE_ADAPTER_STATES,
    sandbox: true,
    externalSideEffects: false,
  },
  {
    id: "GitHubCodebaseTool",
    label: "GitHub codebase MCP adapter",
    category: "mcp-adapter",
    description: "Models repository inspection contracts without contacting GitHub.",
    capabilities: ["describe-code-search", "model-repository-context"],
    state: "mock",
    supportedStates: REMOTE_ADAPTER_STATES,
    sandbox: true,
    externalSideEffects: false,
  },
  {
    id: "Context7DocsTool",
    label: "Context7 documentation MCP adapter",
    category: "mcp-adapter",
    description: "Models documentation queries against a versioned sandbox fixture.",
    capabilities: ["describe-doc-query", "model-versioned-context"],
    state: "mock",
    supportedStates: REMOTE_ADAPTER_STATES,
    sandbox: true,
    externalSideEffects: false,
  },
  {
    id: "VideoOptimizerTool",
    label: "Video optimizer adapter",
    category: "media",
    description: "Builds a mock optimization manifest for captions and reframing.",
    capabilities: ["mock-transcript", "mock-captions", "mock-reframe"],
    state: "mock",
    supportedStates: REMOTE_ADAPTER_STATES,
    sandbox: true,
    externalSideEffects: false,
  },
  {
    id: "ImageToVideoTool",
    label: "Image-to-video adapter",
    category: "media",
    description: "Builds a mock motion manifest without calling a generation provider.",
    capabilities: ["mock-motion-prompt", "mock-video-manifest"],
    state: "mock",
    supportedStates: REMOTE_ADAPTER_STATES,
    sandbox: true,
    externalSideEffects: false,
  },
  {
    id: "CampaignPackagerTool",
    label: "Campaign packager",
    category: "packaging",
    description: "Packages deterministic campaign assets locally in the browser.",
    capabilities: ["package-copy", "build-schedule", "allocate-sandbox-budget"],
    state: "mock",
    supportedStates: LOCAL_SANDBOX_STATES,
    sandbox: true,
    externalSideEffects: false,
  },
] as const satisfies readonly SandboxToolContract[];

export const SOCIAL_PLATFORMS = ["X", "Facebook", "TikTok", "Instagram"] as const;

export type SocialPlatform = "X" | "Facebook" | "TikTok" | "Instagram";

export const CAMPAIGN_CHANNELS = ["X", "LinkedIn", "Facebook", "Instagram", "TikTok"] as const;

export type CampaignChannel = (typeof CAMPAIGN_CHANNELS)[number];

export interface TrendSignal {
  id: string;
  platform: SocialPlatform;
  topic: string;
  nativeFormat: string;
  audienceBehavior: string;
  momentum: number;
  sourceState: "mock";
  sandbox: true;
}

export const TREND_SIGNALS = [
  {
    id: "x-tradeoff-threads",
    platform: "X",
    topic: "Engineering trade-off threads",
    nativeFormat: "Concise contrarian thread",
    audienceBehavior: "Saves decision frameworks and replies with edge cases.",
    momentum: 91,
    sourceState: "mock",
    sandbox: true,
  },
  {
    id: "facebook-builder-stories",
    platform: "Facebook",
    topic: "Founder implementation stories",
    nativeFormat: "Community story with a practical takeaway",
    audienceBehavior: "Shares relatable transformation stories in specialist groups.",
    momentum: 74,
    sourceState: "mock",
    sandbox: true,
  },
  {
    id: "tiktok-myth-busting",
    platform: "TikTok",
    topic: "Fast engineering myth-busting",
    nativeFormat: "15-second hook, reveal and proof",
    audienceBehavior: "Rewatches a visual contradiction before following for the framework.",
    momentum: 96,
    sourceState: "mock",
    sandbox: true,
  },
  {
    id: "instagram-system-carousels",
    platform: "Instagram",
    topic: "Saveable system-design carousels",
    nativeFormat: "Carousel or reel with one decision per frame",
    audienceBehavior: "Saves checklists and sends compact diagrams to peers.",
    momentum: 88,
    sourceState: "mock",
    sandbox: true,
  },
] as const satisfies readonly TrendSignal[];

export const SIMULATION_SKILLS = [
  "scholar-nlp",
  "ai-seo",
  "churn-prevention",
  "brand-guard",
] as const;

export type SimulationSkill = (typeof SIMULATION_SKILLS)[number];

export type EnabledSkillsInput =
  | readonly SimulationSkill[]
  | Readonly<Partial<Record<SimulationSkill, boolean>>>;

export type ScholarPointId = "cognitive-reframe" | "tradeoff-tension" | "operational-resolution";

export interface ScholarPoint {
  id: ScholarPointId;
  label: string;
  explanation: string;
}

export type ScholarExplanation = readonly [ScholarPoint, ScholarPoint, ScholarPoint];

export interface MixedTrendInsight {
  platform: SocialPlatform;
  signalId: string;
  topic: string;
  momentum: number;
  adaptedHook: string;
  nativeExecution: string;
  strategicFit: string;
  skillEffects: readonly string[];
}

export interface TrendMixResult {
  thesis: string;
  audience: string;
  mode: "sandbox";
  sandbox: true;
  sources: readonly TrendSignal[];
  enabledSkills: readonly SimulationSkill[];
  insights: readonly MixedTrendInsight[];
  scholar: ScholarExplanation;
}

export interface PackageCampaignInput {
  thesis: string;
  audience: string;
  enabledSkills?: EnabledSkillsInput;
  channels?: readonly CampaignChannel[];
  durationDays?: number;
  budget: number;
  currency?: "USD";
}

export interface CampaignThreadPart {
  part: 1 | 2 | 3;
  purpose: "pattern-interrupt" | "open-loop" | "operational-close";
  copy: string;
}

export type CampaignThread = readonly [CampaignThreadPart, CampaignThreadPart, CampaignThreadPart];

export interface CampaignVideoHook {
  durationSeconds: 15;
  channels: readonly CampaignChannel[];
  openingLine: string;
  visualDirection: string;
  close: string;
}

export interface PaidCampaignConcept {
  objective: "sandbox-conversion-rehearsal";
  channels: readonly CampaignChannel[];
  audience: string;
  primaryText: string;
  headline: string;
  callToAction: "Learn More";
  dailyBudget: number;
  sandbox: true;
}

export interface CampaignNewsletter {
  subject: string;
  preheader: string;
  introduction: string;
  sections: ScholarExplanation;
  closing: string;
}

export interface CampaignScheduleSlot {
  sequence: number;
  offsetHours: number;
  channel: CampaignChannel;
  asset: "thread" | "community-story" | "video-hook" | "carousel";
  status: "sandbox-queued";
}

export interface CampaignBudgetAllocation {
  paidMedia: number;
  production: number;
  learningReserve: number;
}

export interface CampaignPackage {
  campaignId: string;
  thesis: string;
  audience: string;
  thread: CampaignThread;
  videoHook: CampaignVideoHook;
  paidConcept: PaidCampaignConcept;
  newsletter: CampaignNewsletter;
  schedule: readonly CampaignScheduleSlot[];
  channels: readonly CampaignChannel[];
  durationDays: number;
  budget: number;
  currency: "USD";
  budgetAllocation: CampaignBudgetAllocation;
  trendMix: TrendMixResult;
  mode: "sandbox";
  sandbox: true;
}

const DEFAULT_SKILLS = ["scholar-nlp", "ai-seo", "brand-guard"] as const satisfies readonly SimulationSkill[];

const PLATFORM_HOOK_BUILDERS: Readonly<Record<SocialPlatform, (thesis: string, audience: string) => string>> = {
  X: (thesis, audience) => `A contrarian thread for ${audience}: what if “${thesis}” is a trade-off, not a slogan?`,
  Facebook: (thesis, audience) => `A builder story for ${audience}: the decision that made “${thesis}” operational.`,
  TikTok: (thesis, audience) => `Stop scrolling, ${audience}: the hidden cost inside “${thesis}”.`,
  Instagram: (thesis, audience) => `Save this decision map, ${audience}: turn “${thesis}” into three observable choices.`,
};

const PLATFORM_ASSETS: Readonly<Record<CampaignChannel, CampaignScheduleSlot["asset"]>> = {
  X: "thread",
  LinkedIn: "community-story",
  Facebook: "community-story",
  TikTok: "video-hook",
  Instagram: "carousel",
};

function normalizeRequired(value: string, field: "thesis" | "audience"): string {
  const normalized = value.trim().replace(/\s+/g, " ");
  if (!normalized) {
    throw new TypeError(`${field} must contain at least one non-whitespace character.`);
  }
  return normalized;
}

function normalizeSkills(input: EnabledSkillsInput = DEFAULT_SKILLS): readonly SimulationSkill[] {
  if (Array.isArray(input)) {
    return SIMULATION_SKILLS.filter((skill) => input.includes(skill));
  }

  const state = input as Readonly<Partial<Record<SimulationSkill, boolean>>>;
  return SIMULATION_SKILLS.filter((skill) => state[skill] === true);
}

function skillEffectsFor(
  thesis: string,
  audience: string,
  enabledSkills: readonly SimulationSkill[],
): readonly string[] {
  const effects: string[] = [];

  if (enabledSkills.includes("scholar-nlp")) {
    effects.push(`Scholar cadence: reframe “${thesis}”, expose its trade-off, then close with action.`);
  }
  if (enabledSkills.includes("ai-seo")) {
    effects.push(`AI-SEO cluster: ${thesis}, decision framework, and ${audience} implementation.`);
  }
  if (enabledSkills.includes("churn-prevention")) {
    effects.push(`Retention cue: give ${audience} a next-step checkpoint worth returning to.`);
  }
  if (enabledSkills.includes("brand-guard")) {
    effects.push("Brand Guard: preserve an evidence-led tone and avoid unsupported certainty.");
  }

  return effects;
}

function roundCurrency(value: number): number {
  return Math.round(value * 100) / 100;
}

function stableHash(value: string): string {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
}

export function createScholarExplanation(thesisInput: string, audienceInput: string): ScholarExplanation {
  const thesis = normalizeRequired(thesisInput, "thesis");
  const audience = normalizeRequired(audienceInput, "audience");

  return [
    {
      id: "cognitive-reframe",
      label: "Reencuadre Cognitivo",
      explanation: `For ${audience}, “${thesis}” interrupts tool-first thinking and reframes the decision around outcomes.`,
    },
    {
      id: "tradeoff-tension",
      label: "Tensión del Trade-off",
      explanation: `“${thesis}” has no universal implementation: every gain in speed, scale or autonomy moves cost and risk elsewhere.`,
    },
    {
      id: "operational-resolution",
      label: "Resolución Operativa",
      explanation: `Ask ${audience} to test “${thesis}” with one measurable constraint, one reversible experiment and one review gate.`,
    },
  ];
}

export function mixTrendSignals(
  thesisInput: string,
  audienceInput: string,
  enabledSkillsInput: EnabledSkillsInput = DEFAULT_SKILLS,
): TrendMixResult {
  const thesis = normalizeRequired(thesisInput, "thesis");
  const audience = normalizeRequired(audienceInput, "audience");
  const enabledSkills = normalizeSkills(enabledSkillsInput);
  const skillEffects = skillEffectsFor(thesis, audience, enabledSkills);

  return {
    thesis,
    audience,
    mode: "sandbox",
    sandbox: true,
    sources: TREND_SIGNALS,
    enabledSkills,
    insights: TREND_SIGNALS.map((signal) => ({
      platform: signal.platform,
      signalId: signal.id,
      topic: signal.topic,
      momentum: signal.momentum,
      adaptedHook: PLATFORM_HOOK_BUILDERS[signal.platform](thesis, audience),
      nativeExecution: `${signal.nativeFormat}. Behavior cue: ${signal.audienceBehavior}`,
      strategicFit: `Use ${signal.topic.toLowerCase()} to connect “${thesis}” with a concrete decision for ${audience}.`,
      skillEffects,
    })),
    scholar: createScholarExplanation(thesis, audience),
  };
}

export function packageCampaign(input: PackageCampaignInput): CampaignPackage {
  const thesis = normalizeRequired(input.thesis, "thesis");
  const audience = normalizeRequired(input.audience, "audience");
  if (!Number.isFinite(input.budget) || input.budget <= 0) {
    throw new RangeError("budget must be a finite number greater than zero.");
  }
  const durationDays = input.durationDays ?? 7;
  if (!Number.isInteger(durationDays) || durationDays < 3 || durationDays > 30) {
    throw new RangeError("durationDays must be an integer between 3 and 30.");
  }

  const budget = roundCurrency(input.budget);
  const enabledSkills = normalizeSkills(input.enabledSkills);
  const channels = input.channels?.length
    ? CAMPAIGN_CHANNELS.filter((platform) => input.channels?.includes(platform))
    : [...CAMPAIGN_CHANNELS];
  const trendMix = mixTrendSignals(thesis, audience, enabledSkills);
  const scholar = trendMix.scholar;
  const paidMedia = roundCurrency(budget * 0.72);
  const production = roundCurrency(budget * 0.18);
  const learningReserve = roundCurrency(budget - paidMedia - production);
  const paidChannels = channels.filter((channel) => channel === "Facebook" || channel === "Instagram");
  const videoChannels = channels.filter((channel) => channel === "TikTok" || channel === "Instagram");
  if (!channels.includes("X")) {
    throw new RangeError("channels must include X for the required three-part thread.");
  }
  if (paidChannels.length === 0) {
    throw new RangeError("channels must include Facebook or Instagram for the paid campaign concept.");
  }

  const thread: CampaignThread = [
    {
      part: 1,
      purpose: "pattern-interrupt",
      copy: `1/3 ${audience}: “${thesis}” is not a tool choice. It is a decision about the outcome you refuse to compromise.`,
    },
    {
      part: 2,
      purpose: "open-loop",
      copy: `2/3 The tension: every implementation of “${thesis}” trades speed, reliability, cost and reversibility differently. Which failure can ${audience} tolerate?`,
    },
    {
      part: 3,
      purpose: "operational-close",
      copy: `3/3 Resolve it: define one constraint, run one reversible experiment and review one observable result before scaling “${thesis}”.`,
    },
  ];

  const identitySeed = JSON.stringify({ thesis, audience, enabledSkills, channels, durationDays, budget });

  return {
    campaignId: `sandbox-${stableHash(identitySeed)}`,
    thesis,
    audience,
    thread,
    videoHook: {
      durationSeconds: 15,
      channels: videoChannels.length ? videoChannels : channels.slice(0, 1),
      openingLine: `The expensive myth ${audience} still believes about “${thesis}”.`,
      visualDirection: "Open on the confident claim, cut to a two-column trade-off, then reveal the measurable constraint.",
      close: "Choose the trade-off before the tool chooses it for you.",
    },
    paidConcept: {
      objective: "sandbox-conversion-rehearsal",
      channels: paidChannels,
      audience,
      primaryText: `Turn “${thesis}” into a decision system your team can test, explain and improve.`,
      headline: "Build the decision before buying the stack",
      callToAction: "Learn More",
      dailyBudget: roundCurrency(paidMedia / durationDays),
      sandbox: true,
    },
    newsletter: {
      subject: `${thesis}: the trade-off your roadmap is hiding`,
      preheader: `A three-step decision framework for ${audience}.`,
      introduction: `This sandbox edition translates “${thesis}” into a practical decision loop for ${audience}.`,
      sections: scholar,
      closing: "Document the constraint, make the experiment reversible, and let evidence close the loop.",
    },
    schedule: channels.map((channel, index) => ({
      sequence: index + 1,
      offsetHours: Math.round(
        index * ((durationDays - 1) * 24) / Math.max(1, channels.length - 1),
      ),
      channel,
      asset: PLATFORM_ASSETS[channel],
      status: "sandbox-queued",
    })),
    channels,
    durationDays,
    budget,
    currency: input.currency ?? "USD",
    budgetAllocation: {
      paidMedia,
      production,
      learningReserve,
    },
    trendMix,
    mode: "sandbox",
    sandbox: true,
  };
}
