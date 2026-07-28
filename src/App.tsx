import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Activity, ChevronLeft, ChevronRight, Cpu, LogIn, Network, Settings, ShieldCheck } from "lucide-react";
import { CanvasBackground } from "./components/CanvasBackground";
import { CampaignOutputPanel } from "./components/CampaignOutputPanel";
import { CinematicHero } from "./components/CinematicHero";
import { PipelineGraph } from "./components/PipelineGraph";
import type { NodeState } from "./components/PipelineGraph";
import { StationInspector } from "./components/StationInspector";
import { TrendRadar } from "./components/TrendRadar";
import { WorkspaceRuntime } from "./components/WorkspaceRuntime";
import { WorkspaceSettingsDialog } from "./components/WorkspaceSettingsDialog";
import { runtimeApi } from "./lib/runtimeApi";
import {
  requiresSocialReconnect,
  socialPublicationErrorMessage,
} from "./lib/socialPublicationError";
import type {
  BrowserRuntimeSession,
  RuntimeIntegrationSummary,
  RuntimeProvider,
  RuntimeProviderGatewayStatus,
  RuntimeRun,
  RuntimeSocialChannel,
  RuntimeSocialPublication,
  RuntimeTrendPilotSeed,
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

const STATION_NODE_IDS = [
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
  const [socialChannels, setSocialChannels] = useState<RuntimeSocialChannel[]>([]);
  const [socialActionChannel, setSocialActionChannel] = useState<RuntimeSocialChannel["channel_id"] | null>(null);
  const [socialActionError, setSocialActionError] = useState("");
  const [socialNotice, setSocialNotice] = useState("");
  const [publicationBusy, setPublicationBusy] = useState<RuntimeSocialChannel["channel_id"] | null>(null);
  const [publicationError, setPublicationError] = useState("");
  const [publicationNotice, setPublicationNotice] = useState("");
  const [publicationHistory, setPublicationHistory] = useState<RuntimeSocialPublication[]>([]);
  const [mediaAttachmentBusy, setMediaAttachmentBusy] = useState(false);
  const [mediaAttachmentError, setMediaAttachmentError] = useState("");
  const [mediaAttachmentNotice, setMediaAttachmentNotice] = useState("");
  const [fabricLoading, setFabricLoading] = useState(false);
  const [fabricError, setFabricError] = useState("");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>("ceo");
  const [connectionRequest, setConnectionRequest] = useState(0);
  const [trendPilotSeed, setTrendPilotSeed] = useState<RuntimeTrendPilotSeed | null>(null);
  const sessionButtonRef = useRef<HTMLButtonElement>(null);

  const premiumThemeEntitled = runtimeEntitlements.includes("theme:premium");
  const nodeStates = useMemo(() => pipelineState(run), [run]);
  const completedStations = Object.values(run?.agent_states ?? {}).filter((state) => state.progress === 100).length;
  const readyProviders = providers.filter((provider) => provider.configured).length;
  const selectedState = selectedNodeId ? nodeStates[selectedNodeId] : null;
  const activeStep = Object.entries(nodeStates).find(([, state]) => state.status === "running")?.[0] ?? "";
  const selectedProvider = providerGateway.selected_provider || providers.find((provider) => provider.configured)?.provider_id || "";
  const activeRunId = run?.run_id ?? "";
  const selectedStationIndex = Math.max(0, STATION_NODE_IDS.indexOf(selectedNodeId as typeof STATION_NODE_IDS[number]));
  const selectPreviousStation = () => setSelectedNodeId(STATION_NODE_IDS[Math.max(0, selectedStationIndex - 1)]);
  const selectNextStation = () => setSelectedNodeId(STATION_NODE_IDS[Math.min(STATION_NODE_IDS.length - 1, selectedStationIndex + 1)]);
  const openSessionOrCommand = () => {
    if (session) {
      document.getElementById("command")?.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    setConnectionRequest((value) => value + 1);
  };

  const prepareTrendPilot = useCallback((seed: RuntimeTrendPilotSeed) => {
    setTrendPilotSeed(seed);
    window.requestAnimationFrame(() => {
      document.getElementById("command")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }, []);

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
      setSocialChannels([]);
      setFabricError("");
      return;
    }
    setFabricLoading(true);
    setFabricError("");
    try {
      const [providerCatalog, nextIntegrations, nextSocialChannels] = await Promise.all([
        runtimeApi.providerCatalog(),
        runtimeApi.integrations(),
        runtimeApi.socialChannels(),
      ]);
      setProviders(providerCatalog.providers);
      setProviderGateway(providerCatalog.gateway);
      setIntegrations(nextIntegrations);
      setSocialChannels(nextSocialChannels);
    } catch {
      setFabricError("Provider and integration status is temporarily unavailable.");
    } finally {
      setFabricLoading(false);
    }
  }, [session]);

  useEffect(() => {
    void refreshFabric();
  }, [refreshFabric]);

  useEffect(() => {
    if (!session || !activeRunId) {
      setPublicationHistory([]);
      return;
    }
    let cancelled = false;
    void runtimeApi.socialPublications(activeRunId)
      .then((items) => {
        if (!cancelled) setPublicationHistory(items);
      })
      .catch(() => {
        if (!cancelled) setPublicationHistory([]);
      });
    return () => {
      cancelled = true;
    };
  }, [activeRunId, session]);

  useEffect(() => {
    if (!session) return;
    const query = new URLSearchParams(window.location.search);
    const channel = query.get("social_channel");
    const status = query.get("status");
    if (channel === "x" || channel === "instagram") {
      if (status === "connected") {
        setSettingsOpen(true);
        setSocialNotice(`${channel === "x" ? "X" : "Instagram"} quedó conectado correctamente.`);
        void refreshFabric();
        window.history.replaceState({}, "", `${window.location.pathname}${window.location.hash}`);
        return;
      }
      if (status === "error") {
        const errorCode = query.get("error");
        const messages: Record<string, string> = {
          social_oauth_callback_invalid: "La autorización expiró o ya fue utilizada. Inicia una conexión nueva.",
          instagram_code_exchange_rejected: "Instagram rechazó el código de autorización. Inicia una conexión nueva y confirma que la callback coincida exactamente.",
          instagram_long_lived_exchange_rejected: "Instagram rechazó la extensión de la autorización. Inicia una conexión nueva; CampaignOS no guardó la credencial corta.",
          instagram_profile_validation_rejected: "Instagram rechazó la validación del perfil profesional. Confirma que la cuenta sea Business o Creator y vuelve a conectar.",
          social_provider_rejected: "Instagram rechazó el flujo OAuth. Revisa credenciales, callback y permisos de la app.",
          social_provider_unreachable: "No se pudo completar la comunicación con Instagram. Intenta nuevamente.",
          social_provider_response_invalid: "Instagram devolvió una respuesta OAuth que no pudo procesarse.",
        };
        setSettingsOpen(true);
        setSocialActionError(messages[errorCode ?? ""] ?? "No se pudo completar la conexión social.");
        window.history.replaceState({}, "", `${window.location.pathname}${window.location.hash}`);
      }
    }
  }, [refreshFabric, session]);

  const connectSocialChannel = async (channelId: RuntimeSocialChannel["channel_id"]) => {
    if (!session || session.role !== "admin") return;
    setSocialActionChannel(channelId);
    setSocialActionError("");
    setSocialNotice("");
    try {
      const started = await runtimeApi.startSocialOAuth(channelId, session.csrf_token);
      window.location.assign(started.authorization_url);
    } catch (error) {
      setSocialActionError(error instanceof Error ? error.message : "No se pudo iniciar la autorización social.");
      setSocialActionChannel(null);
    }
  };

  const attachPublicationMedia = async (
    channelId: RuntimeSocialChannel["channel_id"],
    file: File,
    altText: string,
    rightsConfirmed: boolean,
    idempotencyKey: string,
  ) => {
    if (!session || session.role !== "admin" || !run) {
      throw new Error("Se requiere una sesión admin y un run activo.");
    }
    setMediaAttachmentBusy(true);
    setMediaAttachmentError("");
    setMediaAttachmentNotice("");
    try {
      const updated = await runtimeApi.attachPublicationMedia(
        run.run_id,
        channelId,
        file,
        altText,
        rightsConfirmed,
        session.csrf_token,
        idempotencyKey,
      );
      setRun(updated);
      const media = updated.artifacts.find((artifact) =>
        artifact.kind === "publication_media" && artifact.payload.channel === channelId
      );
      const digest = typeof media?.payload.sha256 === "string"
        ? media.payload.sha256.slice(0, 12)
        : "registrado";
      setMediaAttachmentNotice(
        `Media gobernada adjunta · SHA-256 ${digest}… · quedará incluida en Greenlight.`,
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : "No se pudo adjuntar la media gobernada.";
      setMediaAttachmentError(message);
      throw error;
    } finally {
      setMediaAttachmentBusy(false);
    }
  };

  const revokePublicationMedia = async (
    channelId: RuntimeSocialChannel["channel_id"],
    mediaId: string,
    reason: string,
    idempotencyKey: string,
  ) => {
    if (!session || session.role !== "admin" || !run || channelId !== "instagram") {
      throw new Error("Se requiere una sesión admin y media de Instagram activa.");
    }
    setMediaAttachmentBusy(true);
    setMediaAttachmentError("");
    setMediaAttachmentNotice("");
    try {
      const updated = await runtimeApi.revokePublicationMedia(
        run.run_id,
        mediaId,
        reason,
        session.csrf_token,
        idempotencyKey,
      );
      setRun(updated);
      setMediaAttachmentNotice("La media fue retirada y su capability pública quedó revocada.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "No se pudo retirar la media.";
      setMediaAttachmentError(message);
      throw error;
    } finally {
      setMediaAttachmentBusy(false);
    }
  };

  const publishSocialArtifact = async (
    channelId: RuntimeSocialChannel["channel_id"],
    artifactId: string,
    mediaArtifactId: string | null,
    politicalConfirmation: string,
    idempotencyKey: string,
  ) => {
    if (!session || session.role !== "admin" || !run?.greenlight) {
      throw new Error("Se requiere una sesión admin y Greenlight activo.");
    }
    setPublicationBusy(channelId);
    setPublicationError("");
    setPublicationNotice("");
    try {
      const result = await runtimeApi.publishSocial(
        run.run_id,
        channelId,
        artifactId,
        mediaArtifactId,
        run.greenlight.greenlight_id,
        run.greenlight.fencing_token,
        politicalConfirmation,
        session.csrf_token,
        idempotencyKey,
      );
      const label = channelId === "x" ? "X" : "Instagram";
      setPublicationNotice(
        `${label} confirmó la publicación ${result.provider_post_id ?? result.intent_id}. Receipt durable registrado.`,
      );
      setPublicationHistory((current) => [
        ...current.filter((item) => item.intent_id !== result.intent_id),
        result,
      ]);
    } catch (error) {
      const message = socialPublicationErrorMessage(error);
      setPublicationError(message);
      if (requiresSocialReconnect(error)) {
        await refreshFabric();
        setSettingsOpen(true);
        setSocialActionError(message);
      }
      throw error;
    } finally {
      setPublicationBusy(null);
    }
  };

  const disconnectSocialChannel = async (channelId: RuntimeSocialChannel["channel_id"]) => {
    if (!session || session.role !== "admin") return;
    setSocialActionChannel(channelId);
    setSocialActionError("");
    setSocialNotice("");
    try {
      await runtimeApi.disconnectSocialChannel(channelId, session.csrf_token);
      await refreshFabric();
      setSocialNotice(`${channelId === "x" ? "X" : "Instagram"} quedó desconectado y sus tokens fueron eliminados.`);
    } catch (error) {
      setSocialActionError(error instanceof Error ? error.message : "No se pudo desconectar la cuenta social.");
    } finally {
      setSocialActionChannel(null);
    }
  };

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
            <button
              ref={sessionButtonRef}
              type="button"
              onClick={openSessionOrCommand}
              className={`status-pill ${session ? "status-pill--live" : ""}`}
            >
              {session ? (
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-300" />
              ) : (
                <LogIn size={12} aria-hidden="true" />
              )}
              {session ? `${session.subject_id} · conectado` : "Iniciar sesión"}
            </button>
            <span className="status-pill status-pill--amber">
              <ShieldCheck size={12} aria-hidden="true" /> Aprobación manual
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

        <div className="mt-8 lg:mt-10">
          <TrendRadar
            sessionActive={Boolean(session)}
            onPreparePilot={prepareTrendPilot}
          />
        </div>

        <section id="command" aria-labelledby="command-title" className="scroll-mt-24 mt-10 lg:mt-14">
          <div className="section-heading">
            <div>
              <p className="section-kicker">01 / COMMAND</p>
              <h2 id="command-title">Define la misión. Ejecuta el sistema.</h2>
            </div>
            <p>Una misión produce entregables versionados y una decisión de aprobación humana verificable.</p>
          </div>
          <div className="mt-5">
            <WorkspaceRuntime
              onSessionChange={setSession}
              onRunChange={setRun}
              onEntitlementsChange={setRuntimeEntitlements}
              connectionRequest={connectionRequest}
              connectionReturnFocusRef={sessionButtonRef}
              briefSeed={trendPilotSeed}
            />
          </div>
        </section>

        <section id="execution-map" aria-labelledby="execution-map-title" className="scroll-mt-24 mt-10 lg:mt-14">
          <div className="section-heading">
            <div>
              <p className="section-kicker">02 / LIVE TOPOLOGY / FABRIC FLOW</p>
              <h2 id="execution-map-title">Mapa de orquestación de ocho estaciones</h2>
            </div>
            <div className="flex flex-wrap items-center justify-end gap-2">
              <div className="flex items-center gap-2 rounded-full border border-white/[0.07] bg-black/20 px-3 py-2 font-mono text-[10px] text-zinc-400" aria-live="polite">
                <Activity size={12} className="text-[var(--primary-color)]" aria-hidden="true" />
                Estación {selectedStationIndex + 1} de {STATION_NODE_IDS.length} · {selectedState?.status ?? "idle"} · {selectedState?.progress ?? 0}%
              </div>
              <button
                type="button"
                onClick={selectPreviousStation}
                disabled={selectedStationIndex === 0}
                className="station-nav-button"
                aria-label="Estación anterior"
              >
                <ChevronLeft size={14} aria-hidden="true" />
              </button>
              <button
                type="button"
                onClick={selectNextStation}
                disabled={selectedStationIndex === STATION_NODE_IDS.length - 1}
                className="station-nav-button"
                aria-label="Siguiente estación"
              >
                <ChevronRight size={14} aria-hidden="true" />
              </button>
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
            <CampaignOutputPanel
              run={run}
              socialChannels={socialChannels}
              publicationAllowed={session?.role === "admin"}
              publicationBusy={publicationBusy}
              publicationError={publicationError}
              publicationNotice={publicationNotice}
              publications={publicationHistory}
              mediaAttachmentBusy={mediaAttachmentBusy}
              mediaAttachmentError={mediaAttachmentError}
              mediaAttachmentNotice={mediaAttachmentNotice}
              onOpenSettings={() => setSettingsOpen(true)}
              onAttachMedia={attachPublicationMedia}
              onRevokeMedia={revokePublicationMedia}
              onPublish={publishSocialArtifact}
            />
          </div>
        </section>
      </main>

      <footer className="relative z-10 border-t border-white/[0.06] bg-black/20">
        <div className="mx-auto flex w-full max-w-[1840px] flex-col gap-3 px-4 py-4 text-[11px] text-zinc-500 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <div className="flex items-center gap-2">
            <Network size={13} className="text-[var(--primary-color)]" aria-hidden="true" />
            <span>Sesión, estados, entregables y aprobaciones provienen del backend gobernado.</span>
          </div>
          <div className="text-right font-mono text-[9px] uppercase tracking-[0.1em] text-zinc-600">
            <span className="block">Los efectos externos requieren autoridad durable y Greenlight exacto. Greenlight significa una aprobación humana ligada a esa versión.</span>
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
        socialChannels={socialChannels}
        providerLoading={fabricLoading}
        providerError={fabricError}
        sessionActive={Boolean(session)}
        sessionRole={session?.role ?? null}
        socialActionChannel={socialActionChannel}
        socialActionError={socialActionError}
        socialNotice={socialNotice}
        onConnectSocial={(channelId) => void connectSocialChannel(channelId)}
        onDisconnectSocial={(channelId) => void disconnectSocialChannel(channelId)}
        onRefreshProviders={() => void refreshFabric()}
      />
    </div>
  );

}
