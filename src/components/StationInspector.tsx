import { Activity, FileStack, Radio, ShieldCheck } from "lucide-react";
import type { RuntimeArtifact, RuntimeRun } from "../lib/runtimeApi";

interface StationInspectorProps {
  run: RuntimeRun | null;
  stationId: string | null;
}

const STATION_NAMES: Record<string, string> = {
  ingestion: "Signal ingestion",
  ceo: "Campaign command",
  research: "Research / Scholar",
  strategist: "Channel strategy",
  growth: "Growth routing",
  writer: "Content writer",
  media: "Media production",
  risk: "Risk and policy",
  publisher: "Publisher",
};

function artifactsForStation(run: RuntimeRun, artifactIds: readonly string[]): RuntimeArtifact[] {
  const accepted = new Set(artifactIds);
  return run.artifacts.filter((artifact) => accepted.has(artifact.artifact_id));
}

export function StationInspector({ run, stationId }: StationInspectorProps) {
  const state = stationId ? run?.agent_states[stationId] : null;
  const artifacts = run && state ? artifactsForStation(run, state.artifact_ids) : [];
  const label = stationId ? STATION_NAMES[stationId] ?? stationId.replaceAll("_", " ") : "No station selected";

  return (
    <aside id="agent-detail" aria-labelledby="station-inspector-title" className="surface-panel inspector-panel min-h-[430px] overflow-hidden">
      <header className="border-b border-white/[0.07] px-5 py-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-xl border border-white/[0.08] bg-white/[0.035] text-[var(--primary-color)]">
              <Radio size={16} aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <p className="section-kicker">STATION INSPECTOR</p>
              <h3 id="station-inspector-title" className="mt-1 truncate text-base font-bold text-zinc-100">{label}</h3>
            </div>
          </div>
          <span className="font-mono text-[9px] uppercase text-zinc-600">{stationId ?? "idle"}</span>
        </div>
      </header>

      {!run || !stationId || !state ? (
        <div className="grid min-h-[340px] place-items-center p-8 text-center">
          <div>
            <Activity size={22} className="mx-auto text-zinc-700" aria-hidden="true" />
            <p className="mt-3 text-sm font-semibold text-zinc-300">Selecciona una estación</p>
            <p className="mt-1 max-w-xs text-xs leading-5 text-zinc-600">
              El inspector mostrará el estado y los outputs del run activo.
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-5 p-5">
          <div className="grid grid-cols-[1fr_auto] gap-4 rounded-xl border border-white/[0.07] bg-black/20 p-4">
            <div>
              <p className="font-mono text-[9px] uppercase tracking-[0.12em] text-zinc-600">Current execution</p>
              <p className="mt-2 text-sm font-semibold capitalize text-zinc-100">{state.status.replaceAll("_", " ")}</p>
              <p className="mt-2 text-xs leading-5 text-zinc-500">{state.detail}</p>
            </div>
            <strong className="font-mono text-2xl text-[var(--primary-color)]">{state.progress}%</strong>
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between gap-3">
              <p className="inspector-eyebrow">Generated outputs</p>
              <span className="font-mono text-[9px] text-zinc-600">{artifacts.length}</span>
            </div>
            {artifacts.length === 0 ? (
              <div className="rounded-xl border border-dashed border-white/[0.07] p-4 text-[11px] leading-5 text-zinc-600">
                Esta estación todavía no registró un artefacto durable.
              </div>
            ) : (
              <ul className="space-y-2">
                {artifacts.map((artifact) => (
                  <li key={artifact.artifact_id} className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-3">
                    <div className="flex items-start gap-3">
                      <FileStack size={14} className="mt-0.5 shrink-0 text-[var(--primary-color)]" aria-hidden="true" />
                      <div className="min-w-0">
                        <p className="truncate text-xs font-semibold text-zinc-200">{artifact.title}</p>
                        <p className="mt-1 truncate font-mono text-[9px] text-zinc-600">{artifact.kind} · {artifact.evidence_ids.length} evidence refs</p>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="flex items-center gap-2 border-t border-white/[0.06] pt-4 text-[10px] text-zinc-600">
            <ShieldCheck size={12} className="text-emerald-300" aria-hidden="true" />
            Estado leído del run tenant-scoped; no usa timers del navegador.
          </div>
        </div>
      )}
    </aside>
  );
}
