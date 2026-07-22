import { useCallback, useEffect, useLayoutEffect, useMemo, useState } from "react";
import { Activity, Cpu, Network, Settings, ShieldCheck } from "lucide-react";
import { CanvasBackground } from "./components/CanvasBackground";
import { OperationalFabricPanel } from "./components/OperationalFabricPanel";
import { PipelineGraph } from "./components/PipelineGraph";
import type { NodeState } from "./components/PipelineGraph";
import { RunContextPanel } from "./components/RunContextPanel";
import { WorkspaceRuntime } from "./components/WorkspaceRuntime";
import { WorkspaceSettingsDialog } from "./components/WorkspaceSettingsDialog";
import { runtimeApi } from "./lib/runtimeApi";
import type {
  BrowserRuntimeSession,
  RuntimeIntegrationSummary,
  RuntimeProvider,
  RuntimeRun,
} from "./lib/runtimeApi";
import {
  DEFAULT_THEME_ID,
  THEME_CATALOG,
  applyTheme,
  isThemeAvailable,
} from "./lib/themeCatalog";
import type { ThemeId } from "./lib/themeCatalog";

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
  const [integrations, setIntegrations] = useState<RuntimeIntegrationSummary[]>([]);
  const [fabricLoading, setFabricLoading] = useState(false);
  const [fabricError, setFabricError] = useState("");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>("ceo");

  const premiumThemeEntitled = runtimeEntitlements.includes("theme:premium");
  const nodeStates = useMemo(() => pipelineState(run), [run]);
  const completedStations = Object.values(nodeStates).filter((state) => state.status === "success").length;
  const readyProviders = providers.filter((provider) => provider.configured).length;
  const selectedState = selectedNodeId ? nodeStates[selectedNodeId] : null;

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
      setIntegrations([]);
      setFabricError("");
      return;
    }
    setFabricLoading(true);
    setFabricError("");
    try {
      const [nextProviders, nextIntegrations] = await Promise.all([
        runtimeApi.providers(),
        runtimeApi.integrations(),
      ]);
      setProviders(nextProviders);
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
              <p className="mt-0.5 truncate text-[11px] text-zinc-500">Ejecución gobernada de campañas y evidencia</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className={`status-pill ${session ? "status-pill--live" : ""}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${session ? "bg-emerald-300" : "bg-zinc-500"}`} />
              {session ? `${session.tenant_id} conectado` : "Espacio desconectado"}
            </span>
            <span className="status-pill status-pill--amber">
              <ShieldCheck size={12} aria-hidden="true" /> Entrega gobernada
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

      <main id="main-content" tabIndex={-1} className="relative z-10 mx-auto w-full max-w-[1840px] px-4 pb-12 pt-6 sm:px-6 lg:px-8 lg:pb-16">
        <section aria-labelledby="workspace-title" className="grid gap-5 border-b border-white/[0.06] pb-7 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
          <div>
            <p className="section-kicker">Centro de control de campañas</p>
            <h1 id="workspace-title" className="mt-2 max-w-4xl text-3xl font-black tracking-[-0.04em] text-white sm:text-4xl lg:text-5xl">
              Crea, inspecciona y aprueba una campaña gobernada.
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-zinc-400">
              El brief, el estado de las estaciones, la evidencia y Greenlight comparten un único registro de ejecución por tenant.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-white/[0.07] bg-white/[0.07] sm:grid-cols-4 lg:min-w-[560px]">
            <div className="hero-stat"><strong>{session ? "ON" : "OFF"}</strong><span>sesión</span></div>
            <div className="hero-stat"><strong>{String(completedStations).padStart(2, "0")}</strong><span>estaciones</span></div>
            <div className="hero-stat"><strong>{readyProviders}/{providers.length || 5}</strong><span>proveedores</span></div>
            <div className="hero-stat"><strong>{run ? run.artifacts.length : 0}</strong><span>entregables</span></div>
          </div>
        </section>

        <div className="mt-7">
          <WorkspaceRuntime
            onSessionChange={setSession}
            onRunChange={setRun}
            onEntitlementsChange={setRuntimeEntitlements}
          />
        </div>

        <section aria-labelledby="execution-map-title" className="mt-7">
          <div className="mb-4 flex flex-col gap-3 px-1 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="section-kicker">LIVE TOPOLOGY / FABRIC FLOW</p>
              <h2 id="execution-map-title" className="mt-1 text-lg font-bold text-zinc-100">Mapa de orquestación de ocho estaciones</h2>
              <p className="mt-1 text-xs text-zinc-500">Selecciona una estación para inspeccionar su estado actual.</p>
            </div>
            <div className="flex items-center gap-2 rounded-full border border-white/[0.07] bg-black/20 px-3 py-2 font-mono text-[10px] text-zinc-400" aria-live="polite">
              <Activity size={12} className="text-[var(--primary-color)]" aria-hidden="true" />
              {selectedNodeId ? `${selectedNodeId} · ${selectedState?.status ?? "idle"} · ${selectedState?.progress ?? 0}%` : "Ninguna estación seleccionada"}
            </div>
          </div>
          <PipelineGraph
            activeStep={Object.entries(nodeStates).find(([, state]) => state.status === "running")?.[0] ?? ""}
            nodeStates={nodeStates}
            selectedNodeId={selectedNodeId}
            onNodeSelect={setSelectedNodeId}
          />
        </section>

        <div className="mt-7 grid items-start gap-5 xl:grid-cols-[minmax(340px,0.72fr)_minmax(0,1.28fr)]">
          <RunContextPanel run={run} />
          <OperationalFabricPanel
            providers={providers}
            integrations={integrations}
            sessionActive={Boolean(session)}
            loading={fabricLoading}
            run={run}
          />
        </div>
      </main>

      <footer className="relative z-10 border-t border-white/[0.06] bg-black/20">
        <div className="mx-auto flex w-full max-w-[1840px] flex-col gap-3 px-4 py-4 text-[11px] text-zinc-500 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <div className="flex items-center gap-2">
            <Network size={13} className="text-[var(--primary-color)]" aria-hidden="true" />
            <span>Las credenciales de proveedores permanecen en el servidor; el navegador sólo conserva la cookie de sesión del tenant.</span>
          </div>
          <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-zinc-600">Runtime determinista local; no publica contenido ni ejecuta gasto externo.</span>
        </div>
      </footer>

      <WorkspaceSettingsDialog
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        activeTheme={themeId}
        premiumThemeEntitled={premiumThemeEntitled}
        onThemeChange={changeTheme}
        providers={providers}
        providerLoading={fabricLoading}
        providerError={fabricError}
        sessionActive={Boolean(session)}
        onRefreshProviders={() => void refreshFabric()}
      />
    </div>
  );
}
