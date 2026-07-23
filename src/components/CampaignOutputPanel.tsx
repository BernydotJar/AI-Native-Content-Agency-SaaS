import { useMemo, useState } from "react";
import {
  Camera,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleDashed,
  Clipboard,
  FileText,
  KeyRound,
  Send,
  Settings2,
  ShieldCheck,
} from "lucide-react";
import type {
  RuntimePlatform,
  RuntimeRun,
  RuntimeSocialChannel,
} from "../lib/runtimeApi";

interface CampaignOutputPanelProps {
  run: RuntimeRun | null;
  socialChannels?: readonly RuntimeSocialChannel[];
  onOpenSettings?: () => void;
}

interface ChannelDraft {
  platform: RuntimePlatform;
  hook: string;
  body: string;
  cta: string;
  text: string;
}

interface ReadinessStep {
  label: string;
  detail: string;
  state: "complete" | "pending" | "blocked" | "optional";
}

const PLATFORM_LABELS: Record<RuntimePlatform, string> = {
  x: "X",
  facebook: "Facebook",
  instagram: "Instagram",
  tiktok: "TikTok",
};

function asObject(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function asText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function draftsFromRun(run: RuntimeRun | null): ChannelDraft[] {
  const deck = run?.artifacts.find((artifact) => artifact.kind === "copy_deck");
  const variants = asObject(deck?.payload.variants);
  if (!variants) return [];
  return Object.entries(variants).flatMap(([platform, raw]) => {
    if (!(platform in PLATFORM_LABELS)) return [];
    const variant = asObject(raw);
    if (!variant) return [];
    const hook = asText(variant.hook);
    const body = asText(variant.body);
    const cta = asText(variant.cta);
    const text = [hook, body, cta].filter(Boolean).join("\n\n");
    return text ? [{ platform: platform as RuntimePlatform, hook, body, cta, text }] : [];
  });
}

function hasRenderedMedia(run: RuntimeRun): boolean {
  return run.artifacts.some((artifact) => {
    if (["rendered_media", "media_asset", "published_media"].includes(artifact.kind)) return true;
    return artifact.kind === "media_plan" && artifact.payload.media_rendered === true;
  });
}

function activeGreenlight(run: RuntimeRun, platform: RuntimePlatform): boolean {
  return run.greenlight?.decision === "approved"
    && run.greenlight.revoked_at === null
    && run.greenlight.authorized_channels.includes(platform);
}

function readinessSteps(
  run: RuntimeRun,
  draft: ChannelDraft,
  channel: RuntimeSocialChannel | undefined,
): ReadinessStep[] {
  const mediaReady = hasRenderedMedia(run);
  const greenlightReady = activeGreenlight(run, draft.platform);
  const terminalBlock = ["rejected", "revoked", "failed"].includes(run.status);
  const accountConnected = channel?.connection_state === "connected";

  return [
    {
      label: "Copy",
      detail: "Borrador versionado",
      state: "complete",
    },
    {
      label: "Asset",
      detail: channel?.requires_media
        ? mediaReady ? "Media renderizada" : "Imagen, reel o carrusel pendiente"
        : "Opcional para este canal",
      state: channel?.requires_media
        ? mediaReady ? "complete" : "pending"
        : "optional",
    },
    {
      label: "Greenlight",
      detail: terminalBlock
        ? "Decisión bloqueada o revocada"
        : greenlightReady ? "Aprobación activa" : "Revisión humana pendiente",
      state: terminalBlock ? "blocked" : greenlightReady ? "complete" : "pending",
    },
    {
      label: "Cuenta",
      detail: !channel
        ? "Integración no preparada"
        : accountConnected
          ? "Cuenta autorizada"
          : channel.configured
            ? "Credenciales listas; falta autenticar"
            : channel.configuration_state === "missing_redirect_uri"
              ? "Falta callback OAuth"
              : "Faltan credenciales server-side",
      state: accountConnected ? "complete" : "pending",
    },
    {
      label: "Publicación",
      detail: channel?.publishing_available && run.external_side_effects_enabled
        ? "Efecto externo disponible"
        : "Bloqueada hasta OAuth y receipt durable",
      state: channel?.publishing_available && run.external_side_effects_enabled
        ? "complete"
        : "blocked",
    },
  ];
}

function publicationLabel(
  run: RuntimeRun,
  platform: RuntimePlatform,
  channel: RuntimeSocialChannel | undefined,
): string {
  if (["rejected", "revoked", "failed"].includes(run.status)) return "Publicación bloqueada";
  if (run.status === "awaiting_greenlight") return "Requiere Greenlight";
  if (!activeGreenlight(run, platform)) return "Canal no autorizado";
  if (channel?.requires_media && !hasRenderedMedia(run)) return "Falta asset visual";
  if (!channel) return "Integración no preparada";
  if (!channel.configured) return `Configura ${channel.display_name}`;
  if (channel.connection_state !== "connected") return "Lista para autenticar";
  if (!channel.publishing_available || !run.external_side_effects_enabled) {
    return "Publicación aún deshabilitada";
  }
  return "Listo para publicar";
}

function StepIcon({ state }: { state: ReadinessStep["state"] }) {
  if (state === "complete") {
    return <CheckCircle2 size={13} className="text-emerald-300" aria-hidden="true" />;
  }
  if (state === "blocked") {
    return <ShieldCheck size={13} className="text-red-200" aria-hidden="true" />;
  }
  return <CircleDashed size={13} className="text-amber-200" aria-hidden="true" />;
}

function ChannelPreview({ draft, run }: { draft: ChannelDraft; run: RuntimeRun }) {
  if (draft.platform === "instagram") {
    const mediaReady = hasRenderedMedia(run);
    return (
      <div className="overflow-hidden rounded-2xl border border-white/[0.08] bg-zinc-950">
        <div className="flex items-center gap-2 border-b border-white/[0.07] px-4 py-3">
          <span className="grid h-7 w-7 place-items-center rounded-full border border-fuchsia-300/20 bg-fuchsia-300/[0.08] text-fuchsia-100">
            <Camera size={13} aria-hidden="true" />
          </span>
          <div>
            <p className="text-[11px] font-bold text-zinc-100">Vista previa de Instagram</p>
            <p className="font-mono text-[8px] uppercase tracking-[0.1em] text-zinc-600">Professional account</p>
          </div>
        </div>
        <div className="grid aspect-square place-items-center bg-[radial-gradient(circle_at_30%_20%,rgba(217,70,239,0.16),transparent_42%),radial-gradient(circle_at_80%_75%,rgba(59,130,246,0.12),transparent_45%),#09090b] p-6 text-center">
          {mediaReady ? (
            <div>
              <CheckCircle2 size={26} className="mx-auto text-emerald-300" aria-hidden="true" />
              <p className="mt-3 text-xs font-bold text-zinc-100">Asset visual listo</p>
            </div>
          ) : (
            <div>
              <Camera size={28} className="mx-auto text-zinc-600" aria-hidden="true" />
              <p className="mt-3 text-xs font-bold text-zinc-300">Asset visual pendiente</p>
              <p className="mx-auto mt-1 max-w-52 text-[10px] leading-4 text-zinc-600">Instagram exige imagen, reel o carrusel antes de publicar.</p>
            </div>
          )}
        </div>
        <div className="space-y-2 p-4">
          {draft.hook && <p className="text-xs font-bold leading-5 text-zinc-100">{draft.hook}</p>}
          {draft.body && <p className="whitespace-pre-wrap text-[11px] leading-5 text-zinc-300">{draft.body}</p>}
          {draft.cta && <p className="text-[11px] font-semibold text-fuchsia-200">{draft.cta}</p>}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3 rounded-2xl border border-white/[0.07] bg-white/[0.02] p-4">
      <p className="font-mono text-[8px] uppercase tracking-[0.1em] text-zinc-600">Vista previa de {PLATFORM_LABELS[draft.platform]}</p>
      {draft.hook && <p className="text-sm font-bold leading-6 text-zinc-100">{draft.hook}</p>}
      {draft.body && <p className="whitespace-pre-wrap text-xs leading-6 text-zinc-300">{draft.body}</p>}
      {draft.cta && <p className="text-xs font-semibold text-[var(--primary-color)]">{draft.cta}</p>}
    </div>
  );
}

export function CampaignOutputPanel({
  run,
  socialChannels = [],
  onOpenSettings,
}: CampaignOutputPanelProps) {
  const [copied, setCopied] = useState<RuntimePlatform | null>(null);
  const [copyError, setCopyError] = useState("");
  const drafts = useMemo(() => draftsFromRun(run), [run]);
  const evidenceCount = new Set(run?.artifacts.flatMap((artifact) => artifact.evidence_ids) ?? []).size;
  const channelMap = useMemo(
    () => new Map(socialChannels.map((channel) => [channel.channel_id, channel])),
    [socialChannels],
  );

  const copyDraft = async (draft: ChannelDraft) => {
    try {
      await navigator.clipboard.writeText(draft.text);
      setCopied(draft.platform);
      setCopyError("");
    } catch {
      setCopied(null);
      setCopyError("No se pudo copiar el borrador. Selecciona el texto manualmente.");
    }
  };

  return (
    <section id="campaign-output" aria-labelledby="campaign-output-title" className="surface-panel overflow-hidden">
      <header className="flex flex-col gap-4 border-b border-white/[0.07] px-5 py-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-xl border border-white/[0.08] bg-white/[0.03] text-[var(--primary-color)]">
            <FileText size={16} aria-hidden="true" />
          </span>
          <div>
            <p className="section-kicker">03 / OUTPUT</p>
            <h2 id="campaign-output-title" className="mt-1 text-lg font-bold text-zinc-100">Posts listos para revisión</h2>
            <p className="mt-1 text-[11px] leading-5 text-zinc-500">Resultado visible por canal: copy, asset, Greenlight, cuenta y publicación.</p>
          </div>
        </div>
        {run && <span className="rounded-full border border-white/[0.08] px-3 py-1.5 font-mono text-[9px] uppercase text-zinc-400">{run.status.replaceAll("_", " ")}</span>}
      </header>

      {!run ? (
        <div className="grid min-h-52 place-items-center p-8 text-center">
          <div>
            <Send size={22} className="mx-auto text-zinc-700" aria-hidden="true" />
            <p className="mt-3 text-sm font-semibold text-zinc-300">Todavía no hay posts</p>
            <p className="mt-1 text-xs leading-5 text-zinc-600">Ejecuta una misión o abre un run para ver el resultado final por canal.</p>
          </div>
        </div>
      ) : drafts.length === 0 ? (
        <div role="status" className="m-5 rounded-xl border border-amber-300/15 bg-amber-300/[0.04] p-5 text-xs leading-6 text-amber-100">
          Writer no produjo un copy deck utilizable para esta ejecución.
        </div>
      ) : (
        <div className="p-5">
          <div className="grid gap-5 xl:grid-cols-2">
            {drafts.map((draft) => {
              const channel = draft.platform === "x" || draft.platform === "instagram"
                ? channelMap.get(draft.platform)
                : undefined;
              const label = publicationLabel(run, draft.platform, channel);
              const steps = readinessSteps(run, draft, channel);
              const canPublish = label === "Listo para publicar";
              return (
                <article key={draft.platform} className="rounded-2xl border border-white/[0.08] bg-black/20 p-4">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-[var(--primary-color)]">{PLATFORM_LABELS[draft.platform]}</p>
                      <h3 className="mt-1 text-sm font-bold text-zinc-100">Resultado de publicación</h3>
                    </div>
                    <span className="self-start rounded-full border border-white/[0.1] px-2.5 py-1 font-mono text-[9px] uppercase text-zinc-400">{label}</span>
                  </div>

                  <div className="mt-4">
                    <ChannelPreview draft={draft} run={run} />
                  </div>

                  <ol aria-label={`Estado de publicación para ${PLATFORM_LABELS[draft.platform]}`} className="mt-4 grid gap-2 sm:grid-cols-5">
                    {steps.map((step) => (
                      <li key={step.label} className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-3">
                        <div className="flex items-center gap-2">
                          <StepIcon state={step.state} />
                          <p className="text-[10px] font-bold text-zinc-200">{step.label}</p>
                        </div>
                        <p className="mt-2 text-[9px] leading-4 text-zinc-600">{step.detail}</p>
                      </li>
                    ))}
                  </ol>

                  <div className="mt-4 flex flex-wrap gap-2">
                    <button type="button" onClick={() => void copyDraft(draft)} className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-white/[0.1] px-3 text-xs font-semibold text-zinc-200">
                      {copied === draft.platform ? <Check size={13} aria-hidden="true" /> : <Clipboard size={13} aria-hidden="true" />}
                      {copied === draft.platform ? "Copiado" : "Copiar post"}
                    </button>
                    {(draft.platform === "x" || draft.platform === "instagram") && onOpenSettings && (
                      <button type="button" onClick={onOpenSettings} className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-white/[0.1] px-3 text-xs font-semibold text-zinc-200">
                        {channel?.configured ? <KeyRound size={13} aria-hidden="true" /> : <Settings2 size={13} aria-hidden="true" />}
                        {channel?.configured ? "Autenticar cuenta" : `Configurar ${PLATFORM_LABELS[draft.platform]}`}
                      </button>
                    )}
                    <button type="button" disabled={!canPublish} className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-[var(--primary-color)] px-3 text-xs font-extrabold text-black disabled:cursor-not-allowed disabled:opacity-35" title={label}>
                      <Send size={13} aria-hidden="true" /> Publicar
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
          {copyError && <p role="alert" className="mt-4 text-xs text-red-200">{copyError}</p>}
          <details className="mt-5 rounded-xl border border-white/[0.07] bg-white/[0.02] p-4">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-xs font-semibold text-zinc-300">
              <span className="inline-flex items-center gap-2"><ShieldCheck size={14} className="text-[var(--primary-color)]" aria-hidden="true" /> Contexto y evidencia</span>
              <span className="inline-flex items-center gap-2 font-mono text-[9px] text-zinc-600">{evidenceCount} evidencias · {run.artifacts.length} artefactos <ChevronDown size={13} aria-hidden="true" /></span>
            </summary>
            <div className="mt-4 grid gap-2 border-t border-white/[0.06] pt-4 sm:grid-cols-2 lg:grid-cols-3">
              {run.artifacts.map((artifact) => (
                <div key={artifact.artifact_id} className="rounded-lg border border-white/[0.06] bg-black/20 p-3">
                  <p className="text-[11px] font-semibold text-zinc-300">{artifact.title}</p>
                  <p className="mt-1 font-mono text-[9px] text-zinc-600">{artifact.kind}</p>
                </div>
              ))}
            </div>
          </details>
        </div>
      )}
    </section>
  );
}
