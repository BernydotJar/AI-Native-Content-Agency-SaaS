import { useCallback, useEffect, useState } from "react";
import { ExternalLink, LoaderCircle, RefreshCw, Search, TrendingUp } from "lucide-react";
import { runtimeApi, RuntimeApiError } from "../lib/runtimeApi";
import type { RuntimeApi, RuntimeTrendSnapshot } from "../lib/runtimeApi";

interface TrendRadarProps {
  sessionActive: boolean;
  api?: RuntimeApi;
}

function readableDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("es-GT", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "America/Guatemala",
  }).format(parsed);
}

export function TrendRadar({ sessionActive, api = runtimeApi }: TrendRadarProps) {
  const [snapshot, setSnapshot] = useState<RuntimeTrendSnapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    if (!sessionActive) return;
    setLoading(true);
    setError("");
    try {
      setSnapshot(await api.trendRadar());
    } catch (caught) {
      setSnapshot(null);
      setError(
        caught instanceof RuntimeApiError && caught.code === "trend_radar_unavailable"
          ? "La fuente de tendencias no respondió con datos verificables. Intenta actualizar más tarde."
          : "No fue posible cargar el radar de tendencias.",
      );
    } finally {
      setLoading(false);
    }
  }, [api, sessionActive]);

  useEffect(() => {
    if (sessionActive) void refresh();
    else {
      setSnapshot(null);
      setError("");
    }
  }, [refresh, sessionActive]);

  return (
    <section aria-labelledby="trend-radar-title" className="trend-radar surface-panel overflow-hidden">
      <header className="flex flex-col gap-4 border-b border-white/[0.07] px-5 py-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-white/[0.08] bg-white/[0.03] text-[var(--primary-color)]">
            <TrendingUp size={17} aria-hidden="true" />
          </span>
          <div>
            <p className="section-kicker">RADAR GRATUITO · GUATEMALA</p>
            <h2 id="trend-radar-title" className="mt-1 text-lg font-bold text-zinc-100">Qué está capturando atención ahora</h2>
            <p className="mt-1 max-w-2xl text-xs leading-5 text-zinc-500">
              Señales públicas de Google Trends para orientar investigación. Son contexto, no una recomendación automática.
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => void refresh()}
          disabled={!sessionActive || loading}
          className="inline-flex min-h-10 items-center justify-center gap-2 rounded-full border border-white/[0.09] px-4 text-xs font-bold text-zinc-300 disabled:cursor-not-allowed disabled:opacity-35"
        >
          {loading ? <LoaderCircle size={13} className="animate-spin" aria-hidden="true" /> : <RefreshCw size={13} aria-hidden="true" />}
          Actualizar radar
        </button>
      </header>

      {!sessionActive ? (
        <div className="trend-radar-empty">
          <Search size={20} aria-hidden="true" />
          <div>
            <p className="text-sm font-bold text-zinc-200">Inicia sesión para investigar señales reales.</p>
            <p className="mt-1 text-xs leading-5 text-zinc-500">El radar consulta una fuente pública en modo lectura y no activa gasto ni publicación.</p>
          </div>
        </div>
      ) : error ? (
        <div role="status" className="trend-radar-empty text-amber-100">
          <Search size={20} aria-hidden="true" />
          <div>
            <p className="text-sm font-bold">Radar temporalmente no disponible</p>
            <p className="mt-1 text-xs leading-5 text-amber-100/70">{error}</p>
          </div>
        </div>
      ) : loading && !snapshot ? (
        <div role="status" className="trend-radar-empty">
          <LoaderCircle size={20} className="animate-spin" aria-hidden="true" />
          <p className="text-sm text-zinc-400">Leyendo señales verificables…</p>
        </div>
      ) : snapshot ? (
        <div>
          <ol className="trend-radar-grid" aria-label="Tendencias actuales en Guatemala">
            {snapshot.trends.map((trend, index) => (
              <li key={`${trend.title}-${trend.published_at}`} className="trend-radar-item">
                <span className="trend-radar-rank">{String(index + 1).padStart(2, "0")}</span>
                <div className="min-w-0">
                  <h3 className="text-sm font-bold leading-6 text-zinc-100">{trend.title}</h3>
                  <p className="mt-1 text-[10px] leading-5 text-zinc-500">
                    {trend.approx_traffic || "Volumen no publicado"}
                    {trend.news_source ? ` · ${trend.news_source}` : ""}
                  </p>
                  <time className="font-mono text-[9px] text-zinc-600" dateTime={trend.published_at}>{readableDate(trend.published_at)}</time>
                </div>
              </li>
            ))}
          </ol>
          <footer className="flex flex-col gap-2 border-t border-white/[0.06] px-5 py-4 text-[10px] text-zinc-500 sm:flex-row sm:items-center sm:justify-between">
            <span>Actualizado {readableDate(snapshot.fetched_at)} · sin resultados sintéticos.</span>
            <a href={snapshot.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-semibold text-zinc-300 hover:text-white">
              Fuente: {snapshot.source} <ExternalLink size={10} aria-hidden="true" />
            </a>
          </footer>
        </div>
      ) : null}
    </section>
  );
}
