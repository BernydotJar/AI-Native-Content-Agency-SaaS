import { useCallback, useEffect, useLayoutEffect, useMemo, useState } from "react";
import { Activity, Cpu, Network, Settings, ShieldCheck } from "lucide-react";
import { CanvasBackground } from "./components/CanvasBackground";
import { CampaignOutputPanel } from "./components/CampaignOutputPanel";
import { CinematicHero } from "./components/CinematicHero";
import { PipelineGraph } from "./components/PipelineGraph";
import type { NodeState } from "./components/PipelineGraph";
import { StationInspector } from "./components/StationInspector";
import { WorkspaceRuntime } from "./components/WorkspaceRuntime";
import { WorkspaceSettingsDialog } from "./components/WorkspaceSettingsDialog";
import { runtimeApi } from "./lib/runtimeApi";
import type {
  BrowserRuntimeSession,
  RuntimeIntegrationSummary,
  RuntimeProvider,
  RuntimeProviderGatewayStatus,
  RuntimeRun,
} from "./lib/runtimeApi";
import {
  DEFAULT_THEME_ID,
  THEME_CATALOG,
  applyTheme,
  isThemeAvailable,
} from "./lib/themeCatalog";
import type { ThemeId } from "./lib/themeCatalog";

const DEFAULT_GATEWAY_STATUS: RuntimeProviderGatewayStatus = {
  execution_enabled: false,
  selected_provider: "",
  execution_available: false,
  durable_outbound_receipt: false,
  automatic_run_integration: false,
};

const EMPTY_NODE_STATE: NodeState = {
  status: "idle",
  progress: 0,
  itemsCount: 0,
  itemsLabel: "outputs",
};

const PIPELINE_NODE_IDS = [
  "ingestion",
  "ceo",
  "research",
  "strategist",
  "growth",
  "writer",
  "media",
  "risk",
  "publisher",
] as const;

function nodeStatus(status: string, progress: number): NodeState["status"] {
  const normalized = status.toLowerCase();
  if (normalized.includes("fail") || normalized.includes("error")) return "error";
  if (progress >= 100 || normalized === "ready" || normalized === "completed") return "success";
  if (progress > 0 || normalized.includes("process") || normalized.includes("running")) return "running";
  return "idle";
}

function pipelineState(run: RuntimeRun | null): Record<string, NodeState> {
  const result = Object.fromEntries(
    PIPELINE_NODE_IDS.map((nodeId) => [nodeId, { ...EMPTY_NODE_STATE }]),
  ) as Record<string, NodeState>;
  if (!run) return result;

  result.ingestion = {
    status: "success",
    progress: 100,
    itemsCount: 1,
    itemsLabel: "brief",
  };
  for (const [nodeId, state] of Object.entries(run.agent_states)) {
    result[nodeId] = {
      status: nodeStatus(state.status, state.progress),
      progress: state.progress,
      itemsCount: state.artifact_ids.length,
      itemsLabel: state.artifact_ids.length === 1 ? "output" : "outputs",
    };
  }
  return result;
}

export default function App() {
  const [themeId, setThemeId] = useState<ThemeId>(DEFAULT_THEME_ID);
  const [runtimeEntitlements, setRuntimeEntitlements] = useState<readonly string[]>([]);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [session, setSession] = useState<BrowserRuntimeSession | null>(null);
  const [run, setRun] = useState<RuntimeRun | null>(null);
  const [providers, setProviders] = useState<RuntimeProvider[]>([]);
  const [providerGateway, setProviderGateway] = useState<RuntimeProviderGatewayStatus>(DEFAULT_GATEWAY_STATUS);
  const [integrations, setIntegrations] = useState<RuntimeIntegrationSummary[]>([]);
  const [fabricLoading, setFabricLoading] = useState(false);
  const [fabricError, setFabricError] = useState("");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>("ceo");

  const premiumThemeEntitled = runtimeEntitlements.includes("theme:premium");
  const nodeStates = useMemo(() => pipelineState(run), [run]);
  const completedStations = Object.values(run?.agent_states ?? {}).filter((state) => state.progress === 100).length;
  const readyProviders = providers.filter((provider) => provider.configured).length;
  const selectedState = selectedNodeId ? nodeStates[selectedNodeId] : null;
  const activeStep = Object.entries(nodeStates).find(([, state]) => state.status === "running")?.[0] ?? "";
  const selectedProvider = providerGateway.selected_provider || providers.find((provider) => provider.configured)?.provider_id || "";

  useEffect(() => {
    applyTheme(themeId);
  }, [themeId]);

  useLayoutEffect(() => {
    if (themeId === "premium" && !premiumThemeEntitled) {
      setThemeId(DEFAULT_THEME_ID);
    }
  }, [premiumThemeEntitled, themeId]);

  const changeTheme = (nextThemeId: ThemeId) => {
    const theme = THEME_CATALOG.find((candidate) => candidate.id === nextThemeId);
    if (!theme || !isThemeAvailable(theme, premiumThemeEntitled)) return;
    setThemeId(nextThemeId);
  };

  const refreshFabric = useCallback(async () => {
    if (!session) {
      setProviders([]);
      setProviderGateway(DEFAULT_GATEWAY_STATUS);
      setIntegrations([]);
      setFabricError("");
      return;
    }
    setFabricLoading(true);
    setFabricError("");
    try {
      const [providerCatalog, nextIntegrations] = await Promise.all([
        runtimeApi.providerCatalog(),
        runtimeApi.integrations(),
      ]);
      setProviders(providerCatalog.providers);
      setProviderGateway(providerCatalog.gateway);
      setIntegrations(nextIntegrations);
    } catch {
      setFabricError("Provider and integration status is temporarily unavailable.");
    } finally {
      setFabricLoading(false);
    }
  }, [session]);

  useEffect(() => {
    void refreshFabric();
  }, [refreshFabric]);

  return (
    <div className="relative min-h-screen w-full overflow-x-clip bg-[var(--bg-obsidian)] font-sans text-[var(--text-light)]">
      <a href="#main-content" className="skip-link">Saltar al espacio de trabajo</a>
      <CanvasBackground />
      <div className="scene-vignette" aria-hidden="true" />
      <div className="scene-noise" aria-hidden="true" />

      <header className="app-header relative z-40 border-b border-white/[0.06] backdrop-blur-xl">
        <div className="mx-auto flex w-full max-w-[1840px] flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <div className="brand-glyph" aria-hidden="true"><span /><span /><Cpu size={17} /></div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-extrabold tracking-[-0.02em] text-white">NATIVE / CAMPAIGN OPS</p>
                <span className="rounded-full border border-white/[0.08] bg-white/[0.035] px-2 py-0.5 font-mono text-[9px] text-zinc-400">0.7.0</span>
              </div>
              <p className="mt-0.5 truncate text-[11px] text-zinc-500">Cinematic interface · governed runtime</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className={`status-pill ${session ? "status-pill--live" : ""}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${session ? "bg-emerald-300" : "bg-zinc-500"}`} />
              {session ? `${session.tenant_id} conectado` : "Espacio desconectado"}
            </span>
            <span className="status-pill status-pill--amber">
              <ShieldCheck size={12} aria-hidden="true" /> Greenlight visible
            </span>
            <button
              type="button"
              onClick={() => setSettingsOpen(true)}
              className="inline-flex min-h-10 items-center gap-2 rounded-full border border-white/[0.09] bg-white/[0.025] px-3 text-xs font-semibold text-zinc-300 hover:border-white/[0.18] hover:text-white"
            >
              <Settings size={13} aria-hidden="true" /> Configuración
            </button>
          </div>
        </div>
      </header>

      <main id="main-content" tabIndex={-1} className="relative z-10 mx-auto w-full max-w-[1840px] px-4 pb-12 pt-5 sm:px-6 lg:px-8 lg:pb-16">
        <CinematicHero
          sessionActive={Boolean(session)}
          tenantId={session?.tenant_id}
          completedStations={completedStations}
          totalStations={8}
          readyProviders={readyProviders}
          totalProviders={providers.length || 5}
          deliverables={run?.artifacts.length ?? 0}
          runStatus={run?.status}
          selectedProvider={selectedProvider}
        />

        <section aria-labelledby="command-title" className="mt-10 lg:mt-14">
          <div className="section-heading">
            <div>
              <p className="section-kicker">01 / COMMAND</p>
              <h2 id="command-title">Define la misión. Ejecuta el sistema.</h2>
            </div>
            <p>El comando produce un run durable, artefactos versionados y una decisión Greenlight verificable.</p>
          </div>
          <div className="mt-5">
            <WorkspaceRuntime
              onSessionChange={setSession}
              onRunChange={setRun}
              onEntitlementsChange={setRuntimeEntitlements}
            />
          </div>
        </section>

        <section aria-labelledby="execution-map-title" className="mt-10 lg:mt-14">
          <div className="section-heading">
            <div>
              <p className="section-kicker">02 / LIVE TOPOLOGY / FABRIC FLOW</p>
              <h2 id="execution-map-title">Mapa de orquestación de ocho estaciones</h2>
            </div>
            <div className="flex items-center gap-2 rounded-full border border-white/[0.07] bg-black/20 px-3 py-2 font-mono text-[10px] text-zinc-400" aria-live="polite">
              <Activity size={12} className="text-[var(--primary-color)]" aria-hidden="true" />
              {selectedNodeId ? `${selectedNodeId} · ${selectedState?.status ?? "idle"} · ${selectedState?.progress ?? 0}%` : "Selecciona una estación"}
            </div>
          </div>
          <div className="mt-5 grid items-start gap-5 xl:grid-cols-[minmax(0,1.55fr)_minmax(320px,0.72fr)]">
            <PipelineGraph
              activeStep={activeStep}
              nodeStates={nodeStates}
              selectedNodeId={selectedNodeId}
              onNodeSelect={setSelectedNodeId}
            />
            <StationInspector run={run} stationId={selectedNodeId} />
          </div>
        </section>

        <section aria-labelledby="campaign-output-heading" className="mt-10 lg:mt-14">
          <div className="section-heading">
            <div>
              <p className="section-kicker">03 / REVIEW & PUBLISH</p>
              <h2 id="campaign-output-heading">Revisa el post. Aprueba. Publica.</h2>
            </div>
            <p>El output editorial ocupa el centro; evidencia y configuración permanecen disponibles sin competir con el trabajo.</p>
          </div>
          <div className="mt-5">
            <CampaignOutputPanel run={run} />
          </div>
        </section>
      </main>

      <footer className="relative z-10 border-t border-white/[0.06] bg-black/20">
        <div className="mx-auto flex w-full max-w-[1840px] flex-col gap-3 px-4 py-4 text-[11px] text-zinc-500 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <div className="flex items-center gap-2">
            <Network size={13} className="text-[var(--primary-color)]" aria-hidden="true" />
            <span>Sesión, estados, artefactos y Greenlight provienen del backend gobernado.</span>
          </div>
          <div className="text-right font-mono text-[9px] uppercase tracking-[0.1em] text-zinc-600">
            <span className="block">Runtime determinista local; no publica contenido ni ejecuta gasto externo.</span>
            <span className="mt-1 block">Las credenciales de proveedores permanecen server-side.</span>
          </div>
        </div>
      </footer>

      <WorkspaceSettingsDialog
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        activeTheme={themeId}
        premiumThemeEntitled={premiumThemeEntitled}
        onThemeChange={changeTheme}
        providers={providers}
        gateway={providerGateway}
        integrations={integrations}
        providerLoading={fabricLoading}
        providerError={fabricError}
        sessionActive={Boolean(session)}
        onRefreshProviders={() => void refreshFabric()}
      />
    </div>
  );

}
