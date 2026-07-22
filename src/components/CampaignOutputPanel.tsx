import { useMemo, useState } from "react";
import { Check, ChevronDown, Clipboard, FileText, Send, ShieldCheck } from "lucide-react";
import type { RuntimePlatform, RuntimeRun } from "../lib/runtimeApi";

interface CampaignOutputPanelProps {
  run: RuntimeRun | null;
}

interface ChannelDraft {
  platform: RuntimePlatform;
  hook: string;
  body: string;
  cta: string;
  text: string;
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

function publicationLabel(run: RuntimeRun, platform: RuntimePlatform): string {
  if (run.status === "awaiting_greenlight") return "Requiere Greenlight";
  if (["rejected", "revoked", "failed"].includes(run.status)) return "Publicación bloqueada";
  const authorized = run.greenlight?.decision === "approved"
    && run.greenlight.revoked_at === null
    && run.greenlight.authorized_channels.includes(platform);
  if (!authorized) return "Canal no autorizado";
  return run.external_side_effects_enabled ? "Listo para publicar" : "Aprobado · conectar canal";
}

export function CampaignOutputPanel({ run }: CampaignOutputPanelProps) {
  const [copied, setCopied] = useState<RuntimePlatform | null>(null);
  const [copyError, setCopyError] = useState("");
  const drafts = useMemo(() => draftsFromRun(run), [run]);
  const evidenceCount = new Set(run?.artifacts.flatMap((artifact) => artifact.evidence_ids) ?? []).size;

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
            <p className="mt-1 text-[11px] leading-5 text-zinc-500">Copy versionado por canal, Greenlight y estado de publicación.</p>
          </div>
        </div>
        {run && <span className="rounded-full border border-white/[0.08] px-3 py-1.5 font-mono text-[9px] uppercase text-zinc-400">{run.status.replaceAll("_", " ")}</span>}
      </header>

      {!run ? (
        <div className="grid min-h-52 place-items-center p-8 text-center">
          <div>
            <Send size={22} className="mx-auto text-zinc-700" aria-hidden="true" />
            <p className="mt-3 text-sm font-semibold text-zinc-300">Todavía no hay posts</p>
            <p className="mt-1 text-xs leading-5 text-zinc-600">Ejecuta una misión o abre un run para ver el copy final por canal.</p>
          </div>
        </div>
      ) : drafts.length === 0 ? (
        <div role="status" className="m-5 rounded-xl border border-amber-300/15 bg-amber-300/[0.04] p-5 text-xs leading-6 text-amber-100">
          Writer no produjo un copy deck utilizable para esta ejecución.
        </div>
      ) : (
        <div className="p-5">
          <div className="grid gap-4 xl:grid-cols-2">
            {drafts.map((draft) => {
              const label = publicationLabel(run, draft.platform);
              const canPublish = label === "Listo para publicar";
              return (
                <article key={draft.platform} className="rounded-2xl border border-white/[0.08] bg-black/20 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-[var(--primary-color)]">{PLATFORM_LABELS[draft.platform]}</p>
                      <h3 className="mt-1 text-sm font-bold text-zinc-100">Borrador de publicación</h3>
                    </div>
                    <span className="rounded-full border border-white/[0.1] px-2.5 py-1 font-mono text-[9px] uppercase text-zinc-400">{label}</span>
                  </div>
                  <div className="mt-4 space-y-3 rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                    {draft.hook && <p className="text-sm font-bold leading-6 text-zinc-100">{draft.hook}</p>}
                    {draft.body && <p className="whitespace-pre-wrap text-xs leading-6 text-zinc-300">{draft.body}</p>}
                    {draft.cta && <p className="text-xs font-semibold text-[var(--primary-color)]">{draft.cta}</p>}
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <button type="button" onClick={() => void copyDraft(draft)} className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-white/[0.1] px-3 text-xs font-semibold text-zinc-200">
                      {copied === draft.platform ? <Check size={13} aria-hidden="true" /> : <Clipboard size={13} aria-hidden="true" />}
                      {copied === draft.platform ? "Copiado" : "Copiar post"}
                    </button>
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
