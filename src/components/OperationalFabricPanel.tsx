import { Cable, CheckCircle2, CircleOff, Cpu, ShieldAlert } from "lucide-react";
import type { RuntimeIntegrationSummary, RuntimeProvider, RuntimeRun } from "../lib/runtimeApi";

interface OperationalFabricPanelProps {
  providers: readonly RuntimeProvider[];
  integrations: readonly RuntimeIntegrationSummary[];
  sessionActive: boolean;
  loading: boolean;
  run: RuntimeRun | null;
}

export function OperationalFabricPanel({
  providers,
  integrations,
  sessionActive,
  loading,
  run,
}: OperationalFabricPanelProps) {
  const readyProviders = providers.filter((provider) => provider.configured);
  const stations = Object.entries(run?.agent_states ?? {});

  return (
    <section aria-labelledby="operational-fabric-title" className="surface-panel p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-xl border border-white/[0.08] bg-white/[0.03] text-[var(--primary-color)]">
            <Cable size={16} aria-hidden="true" />
          </span>
          <div>
            <p className="section-kicker">03 / FABRIC OPERACIONAL</p>
            <h2 id="operational-fabric-title" className="mt-1 text-base font-bold text-zinc-100">Capacidades del runtime y entregables por estación</h2>
          </div>
        </div>
        <span className="rounded-full border border-white/[0.08] px-3 py-1.5 font-mono text-[9px] uppercase text-zinc-500">
          {readyProviders.length}/{providers.length || 5} proveedores listos
        </span>
      </div>

      {!sessionActive ? (
        <div className="mt-5 rounded-xl border border-dashed border-white/[0.08] p-5 text-xs leading-6 text-zinc-500">
          Conecta el espacio para inspeccionar proveedores administrados por el servidor, integraciones revisadas y entregables del tenant.
        </div>
      ) : loading && providers.length === 0 ? (
        <div role="status" className="mt-5 rounded-xl border border-white/[0.08] p-5 text-xs text-zinc-500">Cargando fabric operacional…</div>
      ) : (
        <div className="mt-5 space-y-5">
          <div>
            <div className="flex items-center gap-2 text-xs font-bold text-zinc-200">
              <Cpu size={14} className="text-[var(--primary-color)]" aria-hidden="true" /> Runtimes de modelos
            </div>
            <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {providers.map((provider) => (
                <article key={provider.provider_id} className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="text-xs font-bold text-zinc-100">{provider.display_name}</h3>
                      <p className="mt-1 font-mono text-[9px] text-zinc-600">{provider.model || "modelo no seleccionado"}</p>
                    </div>
                    {provider.configured ? (
                      <CheckCircle2 size={14} className="shrink-0 text-emerald-300" aria-label="Listo" />
                    ) : (
                      <CircleOff size={14} className="shrink-0 text-amber-300" aria-label="No listo" />
                    )}
                  </div>
                  <p className="mt-3 text-[10px] capitalize text-zinc-500">{provider.configuration_state.replaceAll("_", " ")}</p>
                </article>
              ))}
            </div>
          </div>

          <div className="border-t border-white/[0.06] pt-5">
            <div className="flex items-center gap-2 text-xs font-bold text-zinc-200">
              <ShieldAlert size={14} className="text-[var(--primary-color)]" aria-hidden="true" /> Capacidades externas revisadas
            </div>
            {integrations.length === 0 ? (
              <p className="mt-3 rounded-lg border border-dashed border-white/[0.07] p-3 text-[11px] text-zinc-600">No hay una integración externa revisada registrada.</p>
            ) : (
              <div className="mt-3 space-y-2">
                {integrations.map((integration) => (
                  <article key={integration.integration_id} className="flex flex-col gap-2 rounded-xl border border-white/[0.07] bg-black/20 p-3 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <h3 className="text-xs font-bold text-zinc-200">{integration.display_name}</h3>
                      <p className="mt-1 font-mono text-[9px] text-zinc-600">{integration.integration_id}</p>
                    </div>
                    <span className="rounded-full border border-amber-300/20 bg-amber-300/[0.05] px-3 py-1 font-mono text-[9px] uppercase text-amber-100">
                      {integration.review_status.replaceAll("_", " ")}
                    </span>
                  </article>
                ))}
              </div>
            )}
          </div>

          <div className="border-t border-white/[0.06] pt-5">
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs font-bold text-zinc-200">Estado de entregables por estación</p>
              <span className="font-mono text-[9px] text-zinc-600">{stations.length} estaciones observadas</span>
            </div>
            {stations.length === 0 ? (
              <p className="mt-3 text-[11px] leading-5 text-zinc-600">Ejecuta una misión para poblar el estado real de las estaciones y sus artefactos.</p>
            ) : (
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {stations.map(([station, state]) => (
                  <div key={station} className="flex items-center justify-between gap-3 rounded-lg border border-white/[0.06] bg-white/[0.015] px-3 py-2.5">
                    <div className="min-w-0">
                      <p className="truncate text-[11px] font-semibold capitalize text-zinc-300">{station.replaceAll("_", " ")}</p>
                      <p className="mt-0.5 truncate text-[9px] text-zinc-600">{state.detail}</p>
                    </div>
                    <span className="shrink-0 font-mono text-[9px] text-zinc-500">{state.progress}%</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
