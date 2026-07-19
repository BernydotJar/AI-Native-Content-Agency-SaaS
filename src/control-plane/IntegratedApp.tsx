import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Cpu,
  Database,
  FileText,
  Fingerprint,
  Layers,
  Lock,
  PackageOpen,
  Play,
  RefreshCw,
  Send,
  Server,
  ShieldCheck,
  Sparkles,
  Terminal,
  Wifi,
  XCircle,
} from "lucide-react";
import type {
  ApprovalDecision,
  MissionResponse,
  Platform,
  RunResponse,
} from "../api/contracts";
import { GREENLIGHT_POLICY_VERSION } from "../api/contracts";
import {
  ControlPlaneClient,
  createDefaultControlPlaneClient,
  safeControlPlaneError,
  type ControlPlaneApiError,
} from "../api/client";
import { CanvasBackground } from "../components/CanvasBackground";
import { PipelineGraph } from "../components/PipelineGraph";
import {
  activeRoleFromRun,
  AGENT_ROLES,
  isTerminalRun,
  nodeStatesFromRun,
  selectedStep,
} from "./runView";

interface RunStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export interface IntegratedAppProps {
  client?: ControlPlaneClient;
  storage?: RunStorage | null;
  pollIntervalMs?: number;
}

interface MissionDraft {
  title: string;
  objective: string;
  audience: string;
  platforms: Platform[];
  budgetDollars: number;
  campaignGoal: string;
}

type Operation = "idle" | "launching" | "starting" | "refreshing" | "approving" | "rejecting";
type ConnectionState = "idle" | "connecting" | "connected" | "disconnected";

interface PendingDecisionCommand {
  runId: string;
  decision: ApprovalDecision;
  reviewer: string;
  note: string;
  artifactManifestHash: string;
  policyVersion: typeof GREENLIGHT_POLICY_VERSION;
  idempotencyKey: string;
}

const PLATFORM_OPTIONS: ReadonlyArray<{ value: Platform; label: string }> = [
  { value: "x", label: "X" },
  { value: "facebook", label: "Facebook" },
  { value: "tiktok", label: "TikTok" },
  { value: "instagram", label: "Instagram" },
];

const DEFAULT_MISSION: MissionDraft = {
  title: "Evidence-led operating model launch",
  objective: "Explain why reversible AI experiments beat irreversible platform bets.",
  audience: "Engineering leaders and technical founders",
  platforms: ["x", "facebook", "tiktok", "instagram"],
  budgetDollars: 3500,
  campaignGoal: "qualified_demand",
};

function browserStorage(): RunStorage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

function runStorageKey(tenantId: string): string {
  return `native-agency:control-plane:${tenantId}:last-run`;
}

function displayTime(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function prettyPayload(payload: Record<string, unknown>): string {
  const serialized = JSON.stringify(payload, null, 2);
  return serialized.length > 2400 ? `${serialized.slice(0, 2400)}\n…` : serialized;
}

function formatStatus(value: string): string {
  return value.replaceAll("_", " ");
}

function isAmbiguousCommandFailure(error: ControlPlaneApiError): boolean {
  return error.status === 0 || error.status === 429 || error.status >= 500;
}

export function IntegratedApp({
  client,
  storage,
  pollIntervalMs = 2500,
}: IntegratedAppProps) {
  const api = useMemo(() => client ?? createDefaultControlPlaneClient(), [client]);
  const persistedStorage = useMemo(
    () => storage === undefined ? browserStorage() : storage,
    [storage],
  );
  const storageKey = runStorageKey(api.identity.tenantId);

  const [draft, setDraft] = useState<MissionDraft>(DEFAULT_MISSION);
  const [mission, setMission] = useState<MissionResponse | null>(null);
  const [run, setRun] = useState<RunResponse | null>(null);
  const [selectedRole, setSelectedRole] = useState<string>("ceo");
  const [operation, setOperation] = useState<Operation>("idle");
  const [connection, setConnection] = useState<ConnectionState>("idle");
  const [error, setError] = useState<ControlPlaneApiError | null>(null);
  const [reviewer, setReviewer] = useState(api.identity.principalId);
  const [reviewNote, setReviewNote] = useState("");
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const missionCommandKey = useRef<string | null>(null);
  const startCommand = useRef<{ missionId: string; idempotencyKey: string } | null>(null);
  const decisionCommand = useRef<PendingDecisionCommand | null>(null);
  const activeRunId = useRef<string | null>(null);

  const acceptRun = useCallback((incoming: RunResponse) => {
    if (decisionCommand.current?.runId !== incoming.run_id) {
      decisionCommand.current = null;
    }
    activeRunId.current = incoming.run_id;
    setRun((current) => {
      if (
        current
        && current.run_id === incoming.run_id
        && current.version > incoming.version
      ) {
        return current;
      }
      return incoming;
    });
    persistedStorage?.setItem(storageKey, incoming.run_id);
    setConnection("connected");
    setLastUpdated(new Date().toISOString());
  }, [persistedStorage, storageKey]);

  const captureError = useCallback((caught: unknown) => {
    const normalized = safeControlPlaneError(caught);
    setError(normalized);
    setConnection("disconnected");
    return normalized;
  }, []);

  const refreshRun = useCallback(async (
    runId: string,
    showBusyState = true,
  ) => {
    if (showBusyState) setOperation("refreshing");
    setConnection("connecting");
    try {
      const refreshed = await api.getRun(runId);
      if (activeRunId.current !== runId) return null;
      acceptRun(refreshed);
      setError(null);
      return refreshed;
    } catch (caught) {
      if (activeRunId.current !== runId) return null;
      captureError(caught);
      return null;
    } finally {
      if (showBusyState && activeRunId.current === runId) setOperation("idle");
    }
  }, [acceptRun, api, captureError]);

  useEffect(() => {
    const savedRunId = persistedStorage?.getItem(storageKey);
    if (!savedRunId) return;
    let active = true;
    activeRunId.current = savedRunId;
    setConnection("connecting");
    api.getRun(savedRunId).then((restored) => {
      if (!active || activeRunId.current !== savedRunId) return;
      acceptRun(restored);
      setError(null);
    }).catch((caught) => {
      if (!active || activeRunId.current !== savedRunId) return;
      captureError(caught);
    });
    return () => {
      active = false;
    };
  }, [acceptRun, api, captureError, persistedStorage, storageKey]);

  useEffect(() => {
    if (!run || isTerminalRun(run.status) || pollIntervalMs <= 0) return;
    const timer = window.setInterval(() => {
      void refreshRun(run.run_id, false);
    }, pollIntervalMs);
    return () => window.clearInterval(timer);
  }, [pollIntervalMs, refreshRun, run]);

  const launchMission = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (operation !== "idle") return;
    setOperation("launching");
    setConnection("connecting");
    setError(null);
    let commandStage: "mission" | "run" = "mission";
    try {
      const createKey = missionCommandKey.current ?? api.createIdempotencyKey();
      missionCommandKey.current = createKey;
      const createdMission = await api.createMission({
        title: draft.title.trim(),
        objective: draft.objective.trim(),
        audience: draft.audience.trim(),
        platforms: draft.platforms,
        budget_cents: Math.round(draft.budgetDollars * 100),
        source_asset: "sandbox://web/mission-brief",
        campaign_goal: draft.campaignGoal.trim(),
      }, { idempotencyKey: createKey });
      missionCommandKey.current = null;
      setMission(createdMission);
      setOperation("starting");
      commandStage = "run";
      const pendingStart = startCommand.current?.missionId === createdMission.mission_id
        ? startCommand.current
        : {
            missionId: createdMission.mission_id,
            idempotencyKey: api.createIdempotencyKey(),
          };
      startCommand.current = pendingStart;
      const startedRun = await api.startRun(createdMission.mission_id, {
        idempotencyKey: pendingStart.idempotencyKey,
      });
      startCommand.current = null;
      acceptRun(startedRun);
      setSelectedRole(startedRun.status === "awaiting_greenlight" ? "risk" : "ceo");
    } catch (caught) {
      const normalized = captureError(caught);
      if (!isAmbiguousCommandFailure(normalized)) {
        if (commandStage === "mission") missionCommandKey.current = null;
        else startCommand.current = null;
      }
    } finally {
      setOperation("idle");
    }
  };

  const startPersistedMission = async () => {
    if (!mission || operation !== "idle") return;
    setOperation("starting");
    setConnection("connecting");
    setError(null);
    const pendingStart = startCommand.current?.missionId === mission.mission_id
      ? startCommand.current
      : {
          missionId: mission.mission_id,
          idempotencyKey: api.createIdempotencyKey(),
        };
    startCommand.current = pendingStart;
    try {
      acceptRun(await api.startRun(mission.mission_id, {
        idempotencyKey: pendingStart.idempotencyKey,
      }));
      startCommand.current = null;
    } catch (caught) {
      const normalized = captureError(caught);
      if (!isAmbiguousCommandFailure(normalized)) startCommand.current = null;
    } finally {
      setOperation("idle");
    }
  };

  const decide = async (decision: ApprovalDecision) => {
    if (!run || operation !== "idle") return;
    const policyVersion = run.policy_version;
    if (policyVersion !== GREENLIGHT_POLICY_VERSION) return;
    const pendingDecision = decisionCommand.current?.runId === run.run_id
      ? decisionCommand.current
      : {
          runId: run.run_id,
          decision,
          reviewer: reviewer.trim(),
          note: reviewNote.trim(),
          artifactManifestHash: run.artifact_manifest_hash,
          policyVersion,
          idempotencyKey: api.createIdempotencyKey(),
        };
    if (pendingDecision.decision !== decision) return;
    decisionCommand.current = pendingDecision;
    setOperation(pendingDecision.decision === "approved" ? "approving" : "rejecting");
    setConnection("connecting");
    setError(null);
    try {
      const decided = await api.decideRun(run.run_id, {
        decision: pendingDecision.decision,
        reviewer: pendingDecision.reviewer,
        note: pendingDecision.note,
        artifactManifestHash: pendingDecision.artifactManifestHash,
        policyVersion: pendingDecision.policyVersion,
      }, {
        idempotencyKey: pendingDecision.idempotencyKey,
      });
      decisionCommand.current = null;
      acceptRun(decided);
      setReviewNote("");
    } catch (caught) {
      const normalized = captureError(caught);
      if (!isAmbiguousCommandFailure(normalized)) decisionCommand.current = null;
    } finally {
      setOperation("idle");
    }
  };

  const clearLocalSelection = () => {
    persistedStorage?.removeItem(storageKey);
    activeRunId.current = null;
    missionCommandKey.current = null;
    startCommand.current = null;
    decisionCommand.current = null;
    setRun(null);
    setMission(null);
    setError(null);
    setConnection("idle");
    setSelectedRole("ceo");
  };

  const togglePlatform = (platform: Platform) => {
    setDraft((current) => ({
      ...current,
      platforms: current.platforms.includes(platform)
        ? current.platforms.filter((candidate) => candidate !== platform)
        : [...current.platforms, platform],
    }));
  };

  const nodeStates = useMemo(() => nodeStatesFromRun(run), [run]);
  const activeRole = useMemo(() => activeRoleFromRun(run), [run]);
  const step = selectedStep(run, selectedRole);
  const roleArtifacts = run?.artifacts.filter((artifact) => artifact.created_by === selectedRole) ?? [];
  const evidenceIds = new Set(roleArtifacts.flatMap((artifact) => artifact.evidence_ids));
  const roleEvidence = run?.evidence.filter((item) => evidenceIds.has(item.evidence_id)) ?? [];
  const roleEvents = run?.events.filter((event) => event.role === selectedRole) ?? [];
  const completedSteps = run?.steps.filter((item) => item.status === "ready").length ?? 0;
  const overallProgress = run?.steps.length
    ? Math.round(run.steps.reduce((total, item) => total + item.progress, 0) / run.steps.length)
    : 0;
  const awaitingDecision = run?.status === "awaiting_greenlight" && !run.approval;
  const busy = operation !== "idle";
  const missionInvalid = !draft.title.trim()
    || !draft.objective.trim()
    || !draft.audience.trim()
    || !draft.campaignGoal.trim()
    || draft.platforms.length === 0
    || !Number.isFinite(draft.budgetDollars)
    || draft.budgetDollars < 0;
  const policyMatches = run?.policy_version === GREENLIGHT_POLICY_VERSION;

  return (
    <div className="relative min-h-screen w-full overflow-x-clip bg-[#070708] font-sans text-[#f4f4f5]">
      <a href="#main-content" className="skip-link">Saltar al contenido principal</a>
      <CanvasBackground />
      <div className="scene-vignette" aria-hidden="true" />
      <div className="scene-noise" aria-hidden="true" />

      <header className="relative z-40 border-b border-white/[0.06] bg-[#070708]/75 backdrop-blur-xl">
        <div className="mx-auto flex w-full max-w-[1840px] flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <div className="brand-glyph" aria-hidden="true"><span /><span /><Cpu size={17} /></div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-extrabold tracking-[-0.02em] text-white">NATIVE / CONTROL ROOM</p>
                <span className="rounded-full border border-emerald-300/20 bg-emerald-300/[0.08] px-2 py-0.5 font-mono text-[9px] text-emerald-200">INTEGRATED API MODE</span>
              </div>
              <p className="mt-0.5 truncate text-[11px] text-zinc-500">Persisted FastAPI authority · polling transport · sandbox providers</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-[11px]">
            <span className="status-pill"><Layers size={12} aria-hidden="true" /> Backend-owned run</span>
            <span className={`status-pill ${run?.external_side_effects ? "text-rose-200" : "status-pill--amber"}`}><ShieldCheck size={12} aria-hidden="true" /> {run?.external_side_effects ? "External effects reported" : "No publication or spend"}</span>
            <span className={`status-pill ${connection === "connected" ? "status-pill--live" : ""}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${connection === "connected" ? "bg-emerald-300" : connection === "connecting" ? "animate-pulse bg-sky-300" : "bg-zinc-500"}`} />
              {connection === "connected" ? "API connected" : connection === "connecting" ? "API syncing" : connection === "disconnected" ? "Reconnect required" : "No run selected"}
            </span>
          </div>
        </div>
      </header>

      <main id="main-content" className="relative z-10 mx-auto w-full max-w-[1840px] px-4 pb-12 pt-5 sm:px-6 lg:px-8 lg:pb-16">
        {error && (
          <section role="alert" className="mb-5 rounded-2xl border border-rose-300/20 bg-rose-400/[0.07] p-4 text-sm text-rose-100">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="flex gap-3">
                <AlertTriangle className="mt-0.5 shrink-0 text-rose-300" size={18} aria-hidden="true" />
                <div>
                  <p className="font-bold">{error.code}</p>
                  <p className="mt-1 text-rose-100/80">{error.message}</p>
                  <p className="mt-2 font-mono text-[10px] uppercase tracking-wider text-rose-200/60">Correlation {error.correlationId}</p>
                </div>
              </div>
              {run && (
                <button type="button" className="cyber-btn min-h-11 px-4" onClick={() => void refreshRun(run.run_id)} disabled={busy}>
                  <RefreshCw size={13} aria-hidden="true" /> Reconnect
                </button>
              )}
            </div>
          </section>
        )}

        <section aria-labelledby="hero-title" className="hero-stage">
          <div className="hero-copy">
            <div className="coordinate-tag"><span>API / V1</span><i /><span>TENANT {api.identity.tenantId}</span></div>
            <p className="mt-8 flex items-center gap-2 font-mono text-[10px] font-semibold uppercase tracking-[0.22em] text-[var(--primary-color)]">
              <Sparkles size={13} aria-hidden="true" /> One persisted source of truth
            </p>
            <h1 id="hero-title" className="hero-title">Convierte una misión en un <span>run verificable.</span></h1>
            <p className="mt-5 max-w-2xl text-sm leading-7 text-zinc-400 sm:text-base sm:leading-8">
              La interfaz crea la misión en FastAPI, consulta el estado persistido y envía decisiones humanas ligadas al hash exacto de artefactos. Ningún timer del navegador fabrica progreso.
            </p>
            <div className="mt-7 grid max-w-2xl grid-cols-2 gap-px overflow-hidden rounded-xl border border-white/[0.07] bg-white/[0.07] sm:grid-cols-4">
              <div className="hero-stat"><strong>08</strong><span>steps</span></div>
              <div className="hero-stat"><strong>{String(completedSteps).padStart(2, "0")}</strong><span>ready</span></div>
              <div className="hero-stat"><strong>{String(run?.artifacts.length ?? 0).padStart(2, "0")}</strong><span>artifacts</span></div>
              <div className="hero-stat"><strong>{String(overallProgress).padStart(2, "0")}%</strong><span>persisted</span></div>
            </div>
          </div>
          <div className="orchestration-visual" aria-hidden="true">
            <div className="orchestration-halo" />
            <div className="orbit-ring orbit-ring--outer"><span /><span /><span /></div>
            <div className="orbit-ring orbit-ring--inner"><span /><span /></div>
            <div className="orchestration-core"><Server size={24} /><strong>V1</strong><small>FASTAPI / SQL</small></div>
            <span className="orbit-tag orbit-tag--one">POLL / 2.5S</span>
            <span className="orbit-tag orbit-tag--two">AUDIT / SQL</span>
            <span className="orbit-tag orbit-tag--three">GATE / HASH</span>
          </div>
        </section>

        <section aria-labelledby="mission-control-title" className="mt-10 lg:mt-14">
          <div className="section-heading">
            <div><p className="section-kicker">01 / COMMAND</p><h2 id="mission-control-title">Create a persisted mission.</h2></div>
            <p>Every logical command carries tenant, principal and a retry-stable idempotency key. Provider effects remain disabled.</p>
          </div>
          <div className="mt-5 grid items-start gap-5 xl:grid-cols-[minmax(330px,0.72fr)_minmax(0,1.65fr)] 2xl:gap-6">
            <form onSubmit={launchMission} className="surface-panel space-y-4 p-4 sm:p-5">
              <div className="flex items-center justify-between border-b border-white/[0.07] pb-4">
                <div className="flex items-center gap-3">
                  <span className="grid h-10 w-10 place-items-center rounded-xl border border-white/[0.08] bg-white/[0.035] text-[var(--primary-color)]"><Send size={16} aria-hidden="true" /></span>
                  <div><p className="text-sm font-bold text-zinc-100">Mission command</p><p className="mt-0.5 font-mono text-[9px] uppercase tracking-[0.12em] text-zinc-500">POST /api/v1/missions</p></div>
                </div>
                <span className="font-mono text-[9px] text-zinc-600">SCHEMA V1</span>
              </div>
              <label className="block text-xs font-semibold text-zinc-300">Mission title
                <input className="mt-2 w-full rounded-xl border border-white/10 bg-black/25 px-3 py-3 text-sm text-white" maxLength={160} value={draft.title} onChange={(event) => setDraft((current) => ({ ...current, title: event.target.value }))} />
              </label>
              <label className="block text-xs font-semibold text-zinc-300">Objective
                <textarea className="mt-2 min-h-28 w-full resize-y rounded-xl border border-white/10 bg-black/25 px-3 py-3 text-sm leading-6 text-white" maxLength={4000} value={draft.objective} onChange={(event) => setDraft((current) => ({ ...current, objective: event.target.value }))} />
              </label>
              <label className="block text-xs font-semibold text-zinc-300">Audience
                <input className="mt-2 w-full rounded-xl border border-white/10 bg-black/25 px-3 py-3 text-sm text-white" maxLength={500} value={draft.audience} onChange={(event) => setDraft((current) => ({ ...current, audience: event.target.value }))} />
              </label>
              <fieldset>
                <legend className="text-xs font-semibold text-zinc-300">Platforms</legend>
                <div className="mt-2 grid grid-cols-2 gap-2">
                  {PLATFORM_OPTIONS.map((option) => (
                    <label key={option.value} className="flex min-h-11 items-center gap-2 rounded-xl border border-white/[0.08] bg-black/20 px-3 text-xs text-zinc-300">
                      <input type="checkbox" checked={draft.platforms.includes(option.value)} onChange={() => togglePlatform(option.value)} /> {option.label}
                    </label>
                  ))}
                </div>
              </fieldset>
              <div className="grid grid-cols-2 gap-3">
                <label className="block text-xs font-semibold text-zinc-300">Budget USD
                  <input type="number" min={0} max={1000000} step={1} className="mt-2 w-full rounded-xl border border-white/10 bg-black/25 px-3 py-3 text-sm text-white" value={draft.budgetDollars} onChange={(event) => setDraft((current) => ({ ...current, budgetDollars: Number(event.target.value) }))} />
                </label>
                <label className="block text-xs font-semibold text-zinc-300">Campaign goal
                  <input className="mt-2 w-full rounded-xl border border-white/10 bg-black/25 px-3 py-3 text-sm text-white" maxLength={120} value={draft.campaignGoal} onChange={(event) => setDraft((current) => ({ ...current, campaignGoal: event.target.value }))} />
                </label>
              </div>
              <button type="submit" className="cyber-btn flex min-h-12 w-full items-center justify-center gap-2 px-4" disabled={busy || missionInvalid}>
                <Play size={14} aria-hidden="true" /> {operation === "launching" ? "Creating mission…" : operation === "starting" ? "Starting persisted run…" : "Create mission & start run"}
              </button>
              {mission && !run && (
                <button type="button" className="cyber-btn flex min-h-11 w-full items-center justify-center gap-2 px-4" disabled={busy} onClick={() => void startPersistedMission()}>
                  <RefreshCw size={13} aria-hidden="true" /> Retry start for {mission.mission_id}
                </button>
              )}
              <div className="rounded-xl border border-white/[0.07] bg-black/20 p-3 font-mono text-[9px] leading-5 text-zinc-500">
                <p>X-Tenant-ID: {api.identity.tenantId}</p><p>X-Principal-ID: {api.identity.principalId}</p><p>Idempotency-Key: stable across ambiguous retries</p>
              </div>
            </form>

            <div className="min-w-0">
              <div className="mb-3 flex flex-wrap items-end justify-between gap-3 px-1">
                <div><p className="section-kicker">PERSISTED TOPOLOGY / POLLING</p><h3 className="mt-1 text-base font-bold text-zinc-100">Backend-owned eight-station run</h3></div>
                <div className="flex flex-wrap items-center gap-2">
                  {run && <span className="status-pill font-mono text-[9px]">{run.run_id}</span>}
                  <button type="button" className="cyber-btn min-h-11 px-3" disabled={!run || busy} onClick={() => run && void refreshRun(run.run_id)} aria-label="Refresh persisted run">
                    <RefreshCw size={13} className={operation === "refreshing" ? "animate-spin" : ""} aria-hidden="true" /> Refresh
                  </button>
                </div>
              </div>
              <PipelineGraph activeStep={activeRole} nodeStates={nodeStates} selectedNodeId={selectedRole} onNodeSelect={setSelectedRole} />
              <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/[0.07] bg-black/20 px-3 py-2 font-mono text-[9px] uppercase tracking-wider text-zinc-500">
                <span>Status {run ? formatStatus(run.status) : "no run"}</span>
                <span>Version {run?.version ?? "—"}</span>
                <span>{lastUpdated ? `Synced ${displayTime(lastUpdated)}` : "Awaiting first API response"}</span>
              </div>
            </div>
          </div>
        </section>

        <section aria-labelledby="operations-title" className="mt-10 lg:mt-14">
          <div className="section-heading">
            <div><p className="section-kicker">02 / OBSERVE & DECIDE</p><h2 id="operations-title">Persisted steps, evidence and Greenlight.</h2></div>
            <p>Everything shown below comes from the current RunResponse. Refresh never synthesizes a transition.</p>
          </div>
          <div className="mt-5 grid items-start gap-5 2xl:grid-cols-[minmax(330px,0.85fr)_minmax(380px,1fr)_minmax(390px,0.92fr)] 2xl:gap-6">
            <aside id="agent-detail" className="inspector-panel min-h-[540px] overflow-hidden">
              <header className="border-b border-white/[0.07] px-4 py-4">
                <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--primary-color)]">STEP / {selectedRole.toUpperCase()}</p>
                <h3 className="mt-1 text-lg font-bold text-white">{step ? formatStatus(step.status) : "No persisted step"}</h3>
                <p className="mt-2 text-xs leading-5 text-zinc-500">{step?.detail ?? "Create or restore a run to inspect backend state."}</p>
                {step && <div className="mt-3 h-1 overflow-hidden rounded-full bg-white/[0.06]"><div className="h-full bg-[var(--primary-color)]" style={{ width: `${step.progress}%` }} /></div>}
              </header>
              <div className="max-h-[470px] space-y-5 overflow-y-auto p-4">
                <section aria-labelledby="step-events-title"><h4 id="step-events-title" className="inspector-eyebrow"><Activity size={12} aria-hidden="true" /> Persisted events</h4>
                  <div className="mt-2 space-y-2">{roleEvents.length ? roleEvents.map((event) => <article key={event.event_id} className="rounded-xl border border-white/[0.07] bg-black/20 p-3"><p className="text-xs font-semibold text-zinc-200">{event.action}</p><p className="mt-1 text-[11px] leading-5 text-zinc-500">{event.detail}</p><p className="mt-2 font-mono text-[9px] text-zinc-600">#{event.sequence} · {displayTime(event.timestamp)}</p></article>) : <p className="text-xs text-zinc-600">No events for this step.</p>}</div>
                </section>
                <section aria-labelledby="step-evidence-title"><h4 id="step-evidence-title" className="inspector-eyebrow"><Database size={12} aria-hidden="true" /> Tool evidence</h4>
                  <div className="mt-2 space-y-2">{roleEvidence.length ? roleEvidence.map((item) => <article key={item.evidence_id} className="rounded-xl border border-white/[0.07] bg-black/20 p-3"><div className="flex items-center justify-between gap-2"><p className="text-xs font-semibold text-zinc-200">{item.tool} / {item.operation}</p><span className="rounded-full border border-amber-300/20 px-2 py-0.5 font-mono text-[8px] text-amber-200">{item.sandbox ? "SANDBOX" : "LIVE"}</span></div><p className="mt-1 text-[11px] leading-5 text-zinc-500">{item.summary}</p></article>) : <p className="text-xs text-zinc-600">No linked evidence for this step.</p>}</div>
                </section>
              </div>
            </aside>

            <section className="surface-panel min-h-[540px] overflow-hidden" aria-labelledby="artifacts-title">
              <header className="flex items-center justify-between border-b border-white/[0.07] px-4 py-4 sm:px-5"><div><h3 id="artifacts-title" className="text-sm font-bold text-zinc-100">Artifacts / {selectedRole}</h3><p className="mt-0.5 text-[10px] text-zinc-500">Versioned API payloads · tenant scoped</p></div><PackageOpen size={17} className="text-[var(--primary-color)]" aria-hidden="true" /></header>
              <div className="max-h-[540px] space-y-3 overflow-y-auto p-4 sm:p-5">
                {roleArtifacts.length ? roleArtifacts.map((artifact) => <article key={artifact.artifact_id} className="overflow-hidden rounded-xl border border-white/[0.08] bg-black/25"><header className="flex items-start justify-between gap-3 border-b border-white/[0.06] p-3"><div><p className="text-xs font-bold text-zinc-200">{artifact.title}</p><p className="mt-1 font-mono text-[9px] text-zinc-600">{artifact.kind} · #{artifact.ordinal}</p></div><FileText size={14} className="text-zinc-500" aria-hidden="true" /></header><pre className="max-h-72 overflow-auto p-3 text-[10px] leading-5 text-zinc-400">{prettyPayload(artifact.payload)}</pre><footer className="border-t border-white/[0.06] px-3 py-2 font-mono text-[8px] text-zinc-600">{artifact.artifact_id}</footer></article>) : <div className="grid min-h-72 place-items-center text-center"><div><PackageOpen className="mx-auto text-zinc-700" size={24} aria-hidden="true" /><p className="mt-3 text-xs font-semibold text-zinc-500">No persisted artifacts for this step</p></div></div>}
              </div>
            </section>

            <section className="surface-panel min-h-[540px] overflow-hidden" aria-labelledby="greenlight-title">
              <header className="border-b border-white/[0.07] px-4 py-4 sm:px-5"><div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-amber-300/10 text-amber-200"><Lock size={16} aria-hidden="true" /></span><div><h3 id="greenlight-title" className="text-sm font-bold text-zinc-100">Backend Greenlight</h3><p className="mt-0.5 text-[10px] text-zinc-500">Exact manifest · policy-bound · audited</p></div></div></header>
              <div className="space-y-4 p-4 sm:p-5">
                <div className="rounded-xl border border-white/[0.07] bg-black/20 p-3">
                  <p className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wider text-zinc-500"><Fingerprint size={12} aria-hidden="true" /> Artifact manifest hash</p>
                  <p className="mt-2 break-all font-mono text-[10px] leading-5 text-zinc-300">{run?.artifact_manifest_hash || "Unavailable until run creation"}</p>
                  <p className={`mt-2 text-[10px] ${policyMatches ? "text-emerald-300" : "text-amber-200"}`}>Policy {run?.policy_version ?? "—"}</p>
                </div>
                {run?.approval ? (
                  <div className={`rounded-xl border p-4 ${run.approval.decision === "approved" ? "border-emerald-300/20 bg-emerald-400/[0.07]" : "border-rose-300/20 bg-rose-400/[0.07]"}`}>
                    <div className="flex items-center gap-2 font-bold text-zinc-100">{run.approval.decision === "approved" ? <CheckCircle2 size={16} className="text-emerald-300" aria-hidden="true" /> : <XCircle size={16} className="text-rose-300" aria-hidden="true" />} {formatStatus(run.approval.decision)}</div>
                    <p className="mt-2 text-xs text-zinc-400">Reviewer {run.approval.reviewer}</p><p className="mt-1 text-xs text-zinc-500">{run.approval.note || "No note supplied."}</p><p className="mt-2 font-mono text-[9px] text-zinc-600">{displayTime(run.approval.decided_at)}</p>
                  </div>
                ) : (
                  <>
                    <label className="block text-xs font-semibold text-zinc-300">Reviewer
                      <input className="mt-2 w-full rounded-xl border border-white/10 bg-black/25 px-3 py-3 text-sm text-white" maxLength={160} value={reviewer} onChange={(event) => setReviewer(event.target.value)} />
                    </label>
                    <label className="block text-xs font-semibold text-zinc-300">Decision note
                      <textarea className="mt-2 min-h-24 w-full resize-y rounded-xl border border-white/10 bg-black/25 px-3 py-3 text-sm leading-6 text-white" maxLength={2000} value={reviewNote} onChange={(event) => setReviewNote(event.target.value)} />
                    </label>
                    <div className="grid grid-cols-2 gap-2">
                      <button type="button" className="flex min-h-12 items-center justify-center gap-2 rounded-xl border border-rose-300/20 bg-rose-400/[0.07] px-3 text-xs font-bold text-rose-100 disabled:opacity-40" disabled={!awaitingDecision || !reviewer.trim() || busy || !policyMatches || decisionCommand.current?.decision === "approved"} onClick={() => void decide("rejected")}><XCircle size={14} aria-hidden="true" /> {operation === "rejecting" ? "Rejecting…" : decisionCommand.current?.decision === "rejected" ? "Retry rejection" : "Reject"}</button>
                      <button type="button" className="flex min-h-12 items-center justify-center gap-2 rounded-xl border border-emerald-300/20 bg-emerald-400/[0.08] px-3 text-xs font-bold text-emerald-100 disabled:opacity-40" disabled={!awaitingDecision || !reviewer.trim() || busy || !policyMatches || decisionCommand.current?.decision === "rejected"} onClick={() => void decide("approved")}><CheckCircle2 size={14} aria-hidden="true" /> {operation === "approving" ? "Approving…" : decisionCommand.current?.decision === "approved" ? "Retry exact approval" : "Approve exact manifest"}</button>
                    </div>
                    <p className="text-[10px] leading-5 text-zinc-600">Approval only releases sandbox packaging. It never authorizes publication, media spend or a provider API.</p>
                  </>
                )}
              </div>
            </section>
          </div>
        </section>

        <section aria-labelledby="run-audit-title" className="mt-10 surface-panel overflow-hidden lg:mt-14">
          <header className="flex flex-col gap-3 border-b border-white/[0.07] px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5"><div><p className="section-kicker">03 / AUDIT</p><h2 id="run-audit-title" className="mt-1 text-lg font-bold text-white">Persisted event and command ledger</h2></div><div className="flex flex-wrap gap-2"><span className="status-pill"><Terminal size={12} aria-hidden="true" /> {run?.events.length ?? 0} progress events</span><span className="status-pill"><Fingerprint size={12} aria-hidden="true" /> {run?.audit_events.length ?? 0} audit events</span><span className="status-pill"><Database size={12} aria-hidden="true" /> SQL-backed</span></div></header>
          <ol className="grid gap-2 p-4 sm:grid-cols-2 sm:p-5 xl:grid-cols-3">
            {run?.events.length ? run.events.map((event) => <li key={event.event_id} className="rounded-xl border border-white/[0.07] bg-black/20 p-3"><div className="flex items-center justify-between gap-2"><p className="text-xs font-bold text-zinc-200">{event.role} / {event.action}</p><span className="font-mono text-[9px] text-zinc-600">#{event.sequence}</span></div><p className="mt-1 text-[11px] leading-5 text-zinc-500">{event.detail}</p><p className="mt-2 font-mono text-[9px] text-zinc-600">{displayTime(event.timestamp)}</p></li>) : <li className="col-span-full py-10 text-center text-sm text-zinc-600">Create or restore a run to load its persisted event ledger.</li>}
          </ol>
          <div className="border-t border-white/[0.07] p-4 sm:p-5">
            <h3 className="inspector-eyebrow">Tenant-scoped command audit</h3>
            <ol className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {run?.audit_events.length ? run.audit_events.map((event) => <li key={event.audit_id} className="rounded-xl border border-white/[0.07] bg-black/20 p-3"><div className="flex items-center justify-between gap-2"><p className="text-xs font-bold text-zinc-200">{event.action}</p><span className="font-mono text-[8px] text-zinc-600">{event.principal_id}</span></div><p className="mt-2 font-mono text-[9px] text-zinc-500">{event.correlation_id}</p><p className="mt-1 text-[10px] text-zinc-600">{displayTime(event.occurred_at)}</p></li>) : <li className="col-span-full py-6 text-center text-xs text-zinc-600">No persisted command audit events.</li>}
            </ol>
          </div>
        </section>

        {run && (
          <div className="mt-6 flex flex-col gap-3 rounded-2xl border border-white/[0.07] bg-black/20 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3"><Wifi size={16} className="text-emerald-300" aria-hidden="true" /><div><p className="text-xs font-bold text-zinc-200">Run ID persisted locally for reconnect only</p><p className="mt-1 text-[10px] text-zinc-500">All run content is reloaded from FastAPI; browser storage contains only the opaque ID.</p></div></div>
            <button type="button" onClick={clearLocalSelection} className="cyber-btn min-h-11 px-4">Forget local run selection</button>
          </div>
        )}
      </main>

      <footer className="relative z-10 border-t border-white/[0.06] bg-black/20">
        <div className="mx-auto flex w-full max-w-[1840px] flex-col gap-3 px-4 py-4 text-[11px] text-zinc-500 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <div className="flex items-center gap-2"><ShieldCheck size={13} className="text-[var(--primary-color)]" aria-hidden="true" /><span>Tenant-scoped control plane · exact-manifest Greenlight · sandbox effects disabled.</span></div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-[9px] uppercase tracking-[0.1em] text-zinc-600"><span>Integrated API mode</span><span>No fabricated progress</span><span>© 2026 Native Agency OS</span></div>
        </div>
      </footer>
    </div>
  );
}

export { AGENT_ROLES };
