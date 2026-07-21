import { useEffect, useId, useState } from "react";
import type { ComponentType, MouseEvent } from "react";
import { flushSync } from "react-dom";
import { CAMPAIGN_CHANNELS } from "../lib/simulationRuntime";
import type { CampaignChannel } from "../lib/simulationRuntime";
import { THEME_CATALOG, getTheme, isThemeAvailable } from "../lib/themeCatalog";
import type { ThemeDefinition, ThemeId } from "../lib/themeCatalog";
import {
  Aperture,
  ArrowUpRight,
  FileVideo,
  Megaphone,
  Palette,
  Play,
  Sparkles,
  UploadCloud,
} from "lucide-react";

export interface VideoSimulationParams {
  videoName: string;
  platform: string;
}

export interface ImageSimulationParams {
  imageName: string;
  duration: number;
  style: string;
}

export interface CampaignSimulationParams {
  prompt: string;
  audience: string;
  channels: CampaignChannel[];
  durationDays: number;
  budget: number;
}

export type SimulationParams = VideoSimulationParams | ImageSimulationParams | CampaignSimulationParams;
export type UseCaseId = 1 | 2 | 3;

interface ControlPanelProps {
  onRunSimulation: (useCaseId: UseCaseId, params: SimulationParams) => void;
  isRunning: boolean;
  activeTheme: ThemeId;
  premiumThemeEntitled: boolean;
  onThemeChange: (themeId: ThemeId) => void;
}

const USE_CASES: Array<{
  id: UseCaseId;
  kicker: string;
  name: string;
  output: string;
  icon: ComponentType<{ size?: number }>;
}> = [
  { id: 1, kicker: "01 / OPTIMIZE", name: "Video ready-to-publish", output: "Captions · reframing · copy", icon: FileVideo },
  { id: 2, kicker: "02 / ANIMATE", name: "Still image to motion", output: "4–5s clip · channel pack", icon: Aperture },
  { id: 3, kicker: "03 / ORCHESTRATE", name: "Idea to full campaign", output: "Organic · paid · scholar", icon: Megaphone },
];

export const ControlPanel = ({
  onRunSimulation,
  isRunning,
  activeTheme,
  premiumThemeEntitled,
  onThemeChange,
}: ControlPanelProps) => {
  const uid = useId().replace(/:/g, "");
  const [activeUseCase, setActiveUseCase] = useState<UseCaseId>(3);
  const [themeStatus, setThemeStatus] = useState(`${getTheme(activeTheme).label} activo.`);

  useEffect(() => {
    setThemeStatus(`${getTheme(activeTheme).label} activo.`);
  }, [activeTheme]);
  const [videoParams, setVideoParams] = useState<VideoSimulationParams>({
    videoName: "entrevista_raw_final.mp4",
    platform: "TikTok",
  });
  const [imageParams, setImageParams] = useState<ImageSimulationParams>({
    imageName: "flyer_evento_arquitectura.png",
    duration: 5,
    style: "Cinemático Cyber",
  });
  const [campaignParams, setCampaignParams] = useState<CampaignSimulationParams>({
    prompt: "Quiero una campaña sobre por qué no hay soluciones técnicas universales basándome en Kleppmann.",
    audience: "Desarrolladores Senior y Technical Founders",
    channels: [...CAMPAIGN_CHANNELS],
    durationDays: 7,
    budget: 3500,
  });

  const handleThemeSelect = (event: MouseEvent<HTMLButtonElement>, theme: ThemeDefinition) => {
    if (!isThemeAvailable(theme, premiumThemeEntitled)) {
      setThemeStatus(
        "Tema premium bloqueado: requiere un entitlement de pago emitido por el servidor.",
      );
      return;
    }
    if (theme.id === activeTheme) {
      setThemeStatus(`${theme.label} activo.`);
      return;
    }

    const applySelection = () => {
      onThemeChange(theme.id);
      setThemeStatus(`${theme.label} activo.`);
    };
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const startViewTransition = typeof document.startViewTransition === "function"
      ? document.startViewTransition.bind(document)
      : null;

    if (reduceMotion || !startViewTransition) {
      applySelection();
      return;
    }

    const originX = event.clientX;
    const originY = event.clientY;
    const radius = Math.hypot(
      Math.max(originX, window.innerWidth - originX),
      Math.max(originY, window.innerHeight - originY),
    );
    const transition = startViewTransition(() => flushSync(applySelection));

    transition.ready.then(() => {
      document.documentElement.animate(
        {
          clipPath: [
            `circle(0px at ${originX}px ${originY}px)`,
            `circle(${radius}px at ${originX}px ${originY}px)`,
          ],
        },
        {
          duration: 680,
          easing: "cubic-bezier(0.22, 1, 0.36, 1)",
          pseudoElement: "::view-transition-new(root)",
        },
      );
    }).catch(() => undefined);
  };

  const handleRun = () => {
    if (activeUseCase === 1) onRunSimulation(1, videoParams);
    if (activeUseCase === 2) onRunSimulation(2, imageParams);
    if (activeUseCase === 3) onRunSimulation(3, campaignParams);
  };

  const missionInvalid = activeUseCase === 3
    ? !campaignParams.prompt.trim()
      || !campaignParams.audience.trim()
      || campaignParams.channels.length === 0
      || !campaignParams.channels.includes("X")
      || !campaignParams.channels.some((channel) => channel === "Facebook" || channel === "Instagram")
      || campaignParams.durationDays < 3
      || campaignParams.durationDays > 30
      || campaignParams.budget < 500
    : activeUseCase === 2
      ? imageParams.duration < 4 || imageParams.duration > 5
      : !videoParams.videoName.trim();

  const videoInputId = `${uid}-video`;
  const imageInputId = `${uid}-image`;

  return (
    <div className="flex flex-col gap-5">
      <fieldset className="rounded-xl border border-white/[0.07] bg-black/20 p-3">
        <legend className="sr-only">Tema visual de campaña</legend>
        <div className="flex items-start gap-2.5">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-white/[0.08] bg-white/[0.035] text-[var(--primary-color)]">
            <Palette size={15} aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <p className="text-xs font-semibold text-zinc-200">Tema visual de campaña</p>
            <p className="mt-1 text-[10px] leading-4 text-zinc-500">
              El color no cambia permisos, decisiones ni recomendaciones políticas.
            </p>
          </div>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-2 2xl:grid-cols-3" aria-label="Seleccionar tema visual">
          {THEME_CATALOG.map((theme) => {
            const selected = activeTheme === theme.id;
            const available = isThemeAvailable(theme, premiumThemeEntitled);
            return (
              <button
                key={theme.id}
                type="button"
                onClick={(event) => handleThemeSelect(event, theme)}
                aria-label={theme.label}
                aria-pressed={selected}
                aria-disabled={!available}
                aria-describedby={`${uid}-theme-${theme.id}-description`}
                className={`min-h-16 rounded-xl border px-3 py-2.5 text-left transition-[border-color,background-color,transform] ${selected ? "border-[var(--primary-color)] bg-[var(--primary-color-glow)]" : "border-white/[0.08] bg-white/[0.025] hover:border-white/20"} ${available ? "cursor-pointer" : "cursor-not-allowed opacity-70"}`}
              >
                <span className="flex items-center gap-2">
                  <span
                    className="h-3.5 w-3.5 shrink-0 rounded-full border border-black/40"
                    style={{ backgroundColor: theme.accent }}
                    aria-hidden="true"
                  />
                  <span className="text-[11px] font-bold text-zinc-100">{theme.label}</span>
                </span>
                <span id={`${uid}-theme-${theme.id}-description`} className="mt-1 block text-[9px] leading-4 text-zinc-500">
                  {theme.premium ? (available ? "Premium habilitado" : "Premium · pago requerido") : "Incluido"}
                </span>
              </button>
            );
          })}
        </div>
        <p role="status" aria-live="polite" className="mt-3 min-h-5 text-[10px] leading-5 text-zinc-400">
          {themeStatus}
        </p>
      </fieldset>

      <fieldset disabled={isRunning} className="space-y-2">
        <legend className="mb-2 font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-zinc-500">
          Select mission profile
        </legend>
        <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-1 2xl:grid-cols-3">
          {USE_CASES.map((useCase) => {
            const Icon = useCase.icon;
            const selected = activeUseCase === useCase.id;
            return (
              <button
                key={useCase.id}
                type="button"
                onClick={() => setActiveUseCase(useCase.id)}
                aria-pressed={selected}
                className={`mission-option ${selected ? "is-selected" : ""}`}
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="font-mono text-[9px] font-semibold tracking-[0.12em] text-zinc-500">{useCase.kicker}</span>
                  <Icon size={14} aria-hidden="true" />
                </span>
                <span className="mt-4 block text-left text-xs font-bold leading-snug text-zinc-100">{useCase.name}</span>
                <span className="mt-1 block text-left text-[10px] leading-relaxed text-zinc-500">{useCase.output}</span>
              </button>
            );
          })}
        </div>
      </fieldset>

      <div className="rounded-2xl border border-white/[0.07] bg-zinc-950/55 p-4 shadow-inner shadow-black/20">
        {activeUseCase === 1 && (
          <div className="space-y-4">
            <div>
              <label htmlFor={videoInputId} className="form-label">Source video</label>
              <input
                id={videoInputId}
                name="source-video"
                type="file"
                accept="video/mp4,video/quicktime"
                disabled={isRunning}
                className="sr-only"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) setVideoParams((current) => ({ ...current, videoName: file.name }));
                }}
              />
              <label htmlFor={videoInputId} className="upload-zone">
                <UploadCloud size={20} aria-hidden="true" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold text-zinc-200">{videoParams.videoName}</span>
                  <span className="mt-0.5 block text-[11px] text-zinc-500">MP4 or MOV · demo records filename only</span>
                </span>
                <ArrowUpRight size={15} aria-hidden="true" />
              </label>
            </div>
            <div>
              <label htmlFor={`${uid}-platform`} className="form-label">Target surface</label>
              <select
                id={`${uid}-platform`}
                name="target-platform"
                value={videoParams.platform}
                onChange={(event) => setVideoParams((current) => ({ ...current, platform: event.target.value }))}
                className="form-control"
              >
                <option value="TikTok">TikTok · vertical 9:16</option>
                <option value="Instagram">Instagram Reels · vertical 9:16</option>
                <option value="YouTube">YouTube Shorts · vertical 9:16</option>
                <option value="X">X · square 1:1</option>
              </select>
            </div>
          </div>
        )}

        {activeUseCase === 2 && (
          <div className="space-y-4">
            <div>
              <label htmlFor={imageInputId} className="form-label">Source still</label>
              <input
                id={imageInputId}
                name="source-image"
                type="file"
                accept="image/png,image/jpeg,image/webp"
                disabled={isRunning}
                className="sr-only"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) setImageParams((current) => ({ ...current, imageName: file.name }));
                }}
              />
              <label htmlFor={imageInputId} className="upload-zone">
                <UploadCloud size={20} aria-hidden="true" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold text-zinc-200">{imageParams.imageName}</span>
                  <span className="mt-0.5 block text-[11px] text-zinc-500">PNG, JPG or WebP · demo reads filename only</span>
                </span>
                <ArrowUpRight size={15} aria-hidden="true" />
              </label>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label htmlFor={`${uid}-duration`} className="form-label">Duration / seconds</label>
                <input
                  id={`${uid}-duration`}
                  name="clip-duration"
                  type="number"
                  min={4}
                  max={5}
                  value={imageParams.duration}
                  onChange={(event) => setImageParams((current) => ({
                    ...current,
                    duration: Math.min(5, Math.max(4, Number(event.target.value) || 4)),
                  }))}
                  className="form-control"
                />
              </div>
              <div>
                <label htmlFor={`${uid}-style`} className="form-label">Motion treatment</label>
                <select
                  id={`${uid}-style`}
                  name="motion-treatment"
                  value={imageParams.style}
                  onChange={(event) => setImageParams((current) => ({ ...current, style: event.target.value }))}
                  className="form-control"
                >
                  <option value="Cinemático Cyber">Cinematic cyber</option>
                  <option value="Anime Hyper-detail">Anime hyper-detail</option>
                  <option value="Sleek Obsidian 3D">Obsidian 3D</option>
                  <option value="Realista Documental">Documentary</option>
                </select>
              </div>
            </div>
          </div>
        )}

        {activeUseCase === 3 && (
          <div className="space-y-4">
            <div>
              <label htmlFor={`${uid}-prompt`} className="form-label">Campaign thesis</label>
              <textarea
                id={`${uid}-prompt`}
                name="campaign-thesis"
                value={campaignParams.prompt}
                onChange={(event) => setCampaignParams((current) => ({ ...current, prompt: event.target.value }))}
                rows={4}
                placeholder="Describe the idea, tension or point of view..."
                className="form-control min-h-28 resize-y leading-relaxed"
              />
            </div>
            <div>
              <label htmlFor={`${uid}-audience`} className="form-label">Audience / NLP target</label>
              <input
                id={`${uid}-audience`}
                name="campaign-audience"
                type="text"
                value={campaignParams.audience}
                onChange={(event) => setCampaignParams((current) => ({ ...current, audience: event.target.value }))}
                className="form-control"
              />
            </div>
            <fieldset>
              <legend className="form-label">Target channels</legend>
              <div className="grid grid-cols-2 gap-2">
                {CAMPAIGN_CHANNELS.map((platform) => {
                  const selected = campaignParams.channels.includes(platform);
                  return (
                    <button
                      key={platform}
                      type="button"
                      aria-pressed={selected}
                      onClick={() => setCampaignParams((current) => ({
                        ...current,
                        channels: selected
                          ? current.channels.filter((channel) => channel !== platform)
                          : [...current.channels, platform],
                      }))}
                      className={`min-h-11 rounded-xl border px-3 text-left text-xs font-semibold transition-colors ${selected ? "border-sky-300/25 bg-sky-400/10 text-sky-200" : "border-white/[0.07] bg-black/20 text-zinc-500 hover:text-zinc-300"}`}
                    >
                      {platform}
                    </button>
                  );
                })}
              </div>
              <p className="mt-2 text-[11px] leading-5 text-zinc-500">
                X is required for the 3-part thread; Facebook or Instagram is required for paid media.
              </p>
            </fieldset>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label htmlFor={`${uid}-campaign-duration`} className="form-label">Flight / days</label>
                <input
                  id={`${uid}-campaign-duration`}
                  name="campaign-duration"
                  type="number"
                  min={3}
                  max={30}
                  value={campaignParams.durationDays}
                  onChange={(event) => setCampaignParams((current) => ({
                    ...current,
                    durationDays: Math.min(30, Math.max(3, Number(event.target.value) || 3)),
                  }))}
                  className="form-control font-mono"
                />
              </div>
              <div>
                <label htmlFor={`${uid}-budget`} className="form-label">Media budget / USD</label>
                <input
                  id={`${uid}-budget`}
                  name="campaign-budget"
                  type="number"
                  min={500}
                  step={500}
                  value={campaignParams.budget}
                  onChange={(event) => setCampaignParams((current) => ({
                    ...current,
                    budget: Math.max(500, Number(event.target.value) || 500),
                  }))}
                  className="form-control font-mono"
                />
              </div>
            </div>
          </div>
        )}
      </div>

      <button
        type="button"
        onClick={handleRun}
        disabled={isRunning || missionInvalid}
        className="launch-button"
      >
        <span className="grid h-9 w-9 place-items-center rounded-full bg-black/15">
          {isRunning ? <Sparkles size={15} className="animate-pulse" aria-hidden="true" /> : <Play size={14} fill="currentColor" aria-hidden="true" />}
        </span>
        <span className="flex-1 text-left">
          <span className="block text-sm font-bold">{isRunning ? "War Room is orchestrating" : "Launch autonomous cycle"}</span>
          <span className="mt-0.5 block text-[10px] font-medium opacity-65">{isRunning ? "Follow the live signal in the pipeline" : "Run in local simulation sandbox"}</span>
        </span>
        <ArrowUpRight size={17} aria-hidden="true" />
      </button>
    </div>
  );
};
