import { useEffect, useState } from "react";
import { Clapperboard, ExternalLink, RefreshCw, ShieldCheck } from "lucide-react";

type VideoProvider = {
  provider_id: string;
  display_name: string;
  connection: string;
  capabilities: string[];
  suited_for: string;
  configured: boolean;
  configuration_state: "missing_credential" | "configured_execution_disabled" | "worker_not_bound";
  execution_enabled: false;
  requires_human_authorization: boolean;
  credential_environment: string | null;
  setup: string;
  documentation_url: string;
};

type ProviderResponse = { providers: VideoProvider[] };

const STATE_TEXT: Record<VideoProvider["configuration_state"], string> = {
  missing_credential: "Sin credencial",
  configured_execution_disabled: "Credencial en servidor; ejecución pendiente",
  worker_not_bound: "Worker o bridge por conectar",
};

export function VideoProviderSettings({ enabled }: { enabled: boolean }) {
  const [providers, setProviders] = useState<VideoProvider[]>([]);
  const [selectedId, setSelectedId] = useState("heygen");
  const [showSetup, setShowSetup] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    setLoading(true);
    setError("");
    void fetch("/api/v1/video/providers", {
      method: "GET", credentials: "same-origin", signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("No fue posible consultar los proveedores de video.");
        return await response.json() as ProviderResponse;
      })
      .then((data) => {
        if (!controller.signal.aborted) setProviders(data.providers ?? []);
      })
      .catch(() => {
        if (!controller.signal.aborted) setError("El catálogo de video no está disponible.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [enabled, refreshKey]);

  const selected = providers.find((item) => item.provider_id === selectedId) ?? providers[0];

  return (
    <section aria-labelledby="video-provider-settings-title" className="border-t border-white/[0.07] pt-7">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-xl border border-white/[0.08] bg-white/[0.03] text-[var(--primary-color)]">
            <Clapperboard size={17} aria-hidden="true" />
          </span>
          <div>
            <h3 id="video-provider-settings-title" className="text-sm font-bold text-zinc-100">Motores de video</h3>
            <p className="mt-1 text-xs text-zinc-500">Generación local, HeyGen y automatización asistida, separados de modelos de texto.</p>
          </div>
        </div>
        <button type="button" disabled={!enabled || loading} onClick={() => setRefreshKey((x) => x + 1)}
          className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-white/[0.1] px-3 text-xs text-zinc-300 disabled:opacity-50">
          <RefreshCw size={14} aria-hidden="true" /> Actualizar
        </button>
      </div>

      {!enabled ? (
        <p className="mt-4 rounded-xl border border-white/[0.08] p-4 text-xs text-zinc-500">
          Conecta tu espacio para ver los proveedores disponibles.
        </p>
      ) : error ? (
        <p role="status" className="mt-4 text-xs text-red-300">{error}</p>
      ) : loading && !providers.length ? (
        <p role="status" className="mt-4 text-xs text-zinc-400">Consultando motores de video…</p>
      ) : selected ? (
        <div className="mt-4 space-y-3">
          <label className="block text-xs font-semibold text-zinc-300">Motor de video
            <select className="form-control mt-2" value={selected.provider_id}
              onChange={(event) => { setSelectedId(event.target.value); setShowSetup(false); }}>
              {providers.map((provider) => (
                <option key={provider.provider_id} value={provider.provider_id}>{provider.display_name}</option>
              ))}
            </select>
          </label>
          <div className="rounded-2xl border border-white/[0.1] bg-white/[0.025] p-4">
            <p className="text-sm font-semibold text-zinc-100">{selected.display_name}</p>
            <p className="mt-1 text-xs leading-5 text-zinc-400">{selected.suited_for}</p>
            <p className="mt-3 text-[11px] text-amber-200">{STATE_TEXT[selected.configuration_state]}</p>
            <p className="mt-2 text-[10px] leading-5 text-zinc-500">{selected.capabilities.join(" · ")}</p>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <button type="button" aria-expanded={showSetup} onClick={() => setShowSetup((x) => !x)}
                className="min-h-10 rounded-xl border border-white/[0.12] px-3 text-xs font-medium text-zinc-200">
                {showSetup ? "Ocultar conexión" : "Cómo conectar"}
              </button>
              <a href={selected.documentation_url} target="_blank" rel="noopener noreferrer"
                className="inline-flex min-h-10 items-center gap-1.5 text-xs text-zinc-400 hover:text-zinc-100">
                Documentación <ExternalLink size={12} aria-hidden="true" />
              </a>
            </div>
            {showSetup && (
              <div className="mt-3 rounded-xl border border-sky-300/15 bg-sky-300/[0.04] p-3">
                <p className="text-xs leading-5 text-sky-100/90">{selected.setup}</p>
                {selected.credential_environment && (
                  <p className="mt-2 font-mono text-[10px] text-zinc-300">{selected.credential_environment}</p>
                )}
                <p className="mt-2 text-[10px] leading-5 text-zinc-400">
                  Las claves no se introducen en el navegador. La importación segura por tenant requiere un vault cifrado y controles de autorización.
                </p>
              </div>
            )}
          </div>
          <div className="flex items-start gap-2 rounded-xl border border-white/[0.08] p-3 text-[10px] leading-5 text-zinc-400">
            <ShieldCheck size={15} className="mt-0.5 shrink-0" aria-hidden="true" />
            Catálogo de solo lectura. Configurar una credencial no activa generación, publicación ni cargos.
          </div>
        </div>
      ) : (
        <p role="status" className="mt-4 text-xs text-zinc-500">No hay proveedores de video registrados.</p>
      )}
    </section>
  );
}
