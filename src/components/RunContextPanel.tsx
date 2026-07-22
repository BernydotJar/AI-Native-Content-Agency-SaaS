import { BrainCircuit, CheckCircle2, FileStack, Route } from "lucide-react";
import type { RuntimeRun } from "../lib/runtimeApi";

interface RunContextPanelProps {
  run: RuntimeRun | null;
}

function asObject(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

export function RunContextPanel({ run }: RunContextPanelProps) {
  const research = run?.artifacts.find((artifact) => artifact.kind === "research_dossier") ?? null;
  const strategy = run?.artifacts.find((artifact) => artifact.kind === "channel_strategy") ?? null;
  const risk = run?.artifacts.find((artifact) => artifact.kind === "risk_report") ?? null;
  const scholar = asObject(research?.payload.scholar);
  const evidenceCount = new Set(run?.artifacts.flatMap((artifact) => artifact.evidence_ids) ?? []).size;
  const completedStations = Object.values(run?.agent_states ?? {}).filter((state) => state.progress === 100).length;

  return (
    <section aria-labelledby="run-context-title" className="surface-panel p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-xl border border-white/[0.08] bg-white/[0.03] text-[var(--primary-color)]">
            <BrainCircuit size={16} aria-hidden="true" />
          </span>
          <div>
            <p className="section-kicker">02 / CONTEXTO APLICADO</p>
            <h2 id="run-context-title" className="mt-1 text-base font-bold text-zinc-100">Qué utilizó y produjo la ejecución</h2>
          </div>
        </div>
        {run && <span className="rounded-full border border-white/[0.08] px-3 py-1.5 font-mono text-[9px] uppercase text-zinc-500">{run.status.replaceAll("_", " ")}</span>}
      </div>

      {!run ? (
        <div className="mt-5 rounded-xl border border-dashed border-white/[0.08] p-5 text-xs leading-6 text-zinc-500">
          El contexto aparece después de una ejecución gobernada. El operador ve evidencia aplicada, decisiones y entregables; no el algoritmo interno de almacenamiento.
        </div>
      ) : (
        <div className="mt-5 space-y-4">
          <div className="grid grid-cols-3 gap-2">
            <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-3">
              <strong className="block text-lg text-zinc-100">{completedStations}</strong>
              <span className="text-[10px] text-zinc-500">estaciones completas</span>
            </div>
            <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-3">
              <strong className="block text-lg text-zinc-100">{evidenceCount}</strong>
              <span className="text-[10px] text-zinc-500">registros de evidencia</span>
            </div>
            <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-3">
              <strong className="block text-lg text-zinc-100">{run.artifacts.length}</strong>
              <span className="text-[10px] text-zinc-500">entregables versionados</span>
            </div>
          </div>

          {scholar && (
            <article className="rounded-xl border border-white/[0.07] bg-black/20 p-4">
              <div className="flex items-center gap-2 text-xs font-bold text-zinc-200">
                <Route size={14} className="text-[var(--primary-color)]" aria-hidden="true" /> Contexto de decisión
              </div>
              <dl className="mt-3 space-y-3 text-[11px] leading-5">
                <div>
                  <dt className="font-mono text-[9px] uppercase tracking-[0.12em] text-zinc-600">Reencuadre</dt>
                  <dd className="mt-1 text-zinc-400">{String(scholar.reencuadre_cognitivo ?? "No disponible")}</dd>
                </div>
                <div>
                  <dt className="font-mono text-[9px] uppercase tracking-[0.12em] text-zinc-600">Tensión</dt>
                  <dd className="mt-1 text-zinc-400">{String(scholar.tension_del_trade_off ?? "No disponible")}</dd>
                </div>
                <div>
                  <dt className="font-mono text-[9px] uppercase tracking-[0.12em] text-zinc-600">Resolución</dt>
                  <dd className="mt-1 text-zinc-400">{String(scholar.resolucion_operativa ?? "No disponible")}</dd>
                </div>
              </dl>
            </article>
          )}

          <div className="grid gap-2 sm:grid-cols-2">
            <article className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4">
              <div className="flex items-center gap-2 text-xs font-bold text-zinc-200">
                <FileStack size={14} className="text-[var(--primary-color)]" aria-hidden="true" /> Estrategia aplicada
              </div>
              <p className="mt-2 text-[11px] leading-5 text-zinc-500">
                {strategy ? strategy.title : "No hay un artefacto de estrategia para esta ejecución."}
              </p>
            </article>
            <article className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4">
              <div className="flex items-center gap-2 text-xs font-bold text-zinc-200">
                <CheckCircle2 size={14} className="text-[var(--primary-color)]" aria-hidden="true" /> Límite de riesgo
              </div>
              <p className="mt-2 text-[11px] leading-5 text-zinc-500">
                {risk ? risk.title : "La evidencia de riesgo aún no ha sido producida."}
              </p>
            </article>
          </div>
        </div>
      )}
    </section>
  );
}
