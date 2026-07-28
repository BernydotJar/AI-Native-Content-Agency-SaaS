import { useCallback, useEffect, useState } from "react";
import {
  ArrowRight,
  BookOpen,
  ExternalLink,
  LoaderCircle,
  RefreshCw,
  Search,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";
import { runtimeApi, RuntimeApiError } from "../lib/runtimeApi";
import type {
  RuntimeApi,
  RuntimeTrendItem,
  RuntimeTrendPilotSeed,
  RuntimeTrendSnapshot,
  RuntimeTrendTopic,
} from "../lib/runtimeApi";

interface TrendRadarProps {
  sessionActive: boolean;
  api?: RuntimeApi;
  onPreparePilot?: (seed: RuntimeTrendPilotSeed) => void;
}

const TOPICS: Array<{ id: RuntimeTrendTopic; label: string; description: string }> = [
  { id: "general", label: "Ahora", description: "Búsquedas en ascenso" },
  { id: "ai", label: "IA", description: "IA en Guatemala" },
  { id: "marketing", label: "Marketing", description: "Marcas y audiencias" },
  { id: "business", label: "Negocios", description: "Emprendimiento local" },
];

const AUDIENCES: Record<RuntimeTrendTopic, string> = {
  general: "Personas en Guatemala que siguen temas de actualidad y conversación digital",
  ai: "Personas y equipos en Guatemala interesados en inteligencia artificial y tecnología aplicada",
  marketing: "Equipos de marketing, creadores y marcas que operan en Guatemala",
  business: "Emprendedores, pequeñas empresas y profesionales de negocios en Guatemala",
};

function readableDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("es-GT", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "America/Guatemala",
  }).format(parsed);
}

function clipped(value: string, maximum: number): string {
  const normalized = value.trim();
  return normalized.length <= maximum
    ? normalized
    : `${normalized.slice(0, Math.max(0, maximum - 1)).trimEnd()}…`;
}

function buildTrendPilotSeed(
  snapshot: RuntimeTrendSnapshot,
  trend: RuntimeTrendItem,
): RuntimeTrendPilotSeed {
  const primary = trend.news_items[0];
  const locator = primary?.url || snapshot.source_url;
  const source = primary?.source
    ? `${snapshot.source} · ${primary.source}`
    : snapshot.source;
  const traffic = trend.approx_traffic || "volumen no publicado";
  const statement = trend.signal_type === "search_trend"
    ? `Google Trends registró “${trend.title}” entre las búsquedas en ascenso en Guatemala, con tráfico aproximado ${traffic}.`
    : `${trend.news_source || snapshot.source} publicó una señal reciente relacionada con “${trend.title}”.`;

  return {
    id: `${snapshot.topic}:${trend.published_at}:${trend.title}`,
    source_label: `Radar ${TOPICS.find((topic) => topic.id === snapshot.topic)?.label ?? snapshot.topic}: ${trend.title}`,
    brief: {
      title: clipped(`Piloto de tendencia: ${trend.title}`, 200),
      objective: clipped(
        `Crear un piloto editorial informativo sobre “${trend.title}”. Contrastar la señal con la evidencia enlazada, separar hechos de interpretación y producir borradores para X e Instagram. No publicar: esta corrida es únicamente para evaluar la interfaz, el flujo y la calidad editorial.`,
        4000,
      ),
      audience: AUDIENCES[snapshot.topic],
      platforms: ["x", "instagram"],
      budget_cents: 0,
      campaign_goal: "trend_response_pilot",
      campaign_type: "commercial",
      publication_mode: "organic",
      locale: "es-GT",
      jurisdiction: "",
      office: "",
      candidate_name: "",
      locality: "Guatemala",
      problem: "",
      proposal: "",
      desired_action: "",
      disclosure: "Piloto editorial; no publicado.",
      legal_review_status: "pending",
      legal_reviewed_by: "",
      evidence_claims: [{
        statement: clipped(statement, 2000),
        source: clipped(source, 500),
        locator,
        verification_status: "unverified",
      }],
    },
  };
}

export function TrendRadar({
  sessionActive,
  api = runtimeApi,
  onPreparePilot,
}: TrendRadarProps) {
  const [topic, setTopic] = useState<RuntimeTrendTopic>("general");
  const [snapshot, setSnapshot] = useState<RuntimeTrendSnapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectedPilotId, setSelectedPilotId] = useState("");

  const refresh = useCallback(async (nextTopic: RuntimeTrendTopic = topic) => {
    if (!sessionActive) return;
    setLoading(true);
    setError("");
    try {
      setSnapshot(await api.trendRadar(nextTopic));
    } catch (caught) {
      setSnapshot(null);
      setError(
        caught instanceof RuntimeApiError && caught.code === "trend_radar_unavailable"
          ? "La fuente de investigación no respondió con datos verificables. Intenta actualizar más tarde."
          : "No fue posible cargar el radar de tendencias.",
      );
    } finally {
      setLoading(false);
    }
  }, [api, sessionActive, topic]);

  useEffect(() => {
    if (sessionActive) void refresh(topic);
    else {
      setSnapshot(null);
      setError("");
      setSelectedPilotId("");
    }
  }, [refresh, sessionActive, topic]);

  const changeTopic = (nextTopic: RuntimeTrendTopic) => {
    if (nextTopic === topic) return;
    setTopic(nextTopic);
    setSnapshot(null);
    setSelectedPilotId("");
  };

  const preparePilot = (trend: RuntimeTrendItem) => {
    if (!snapshot || !onPreparePilot) return;
    const seed = buildTrendPilotSeed(snapshot, trend);
    setSelectedPilotId(seed.id);
    onPreparePilot(seed);
  };

  return (
    <section aria-labelledby="trend-radar-title" className="trend-radar surface-panel overflow-hidden">
      <header className="flex flex-col gap-4 border-b border-white/[0.07] px-5 py-5 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-start gap-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-white/[0.08] bg-white/[0.03] text-[var(--primary-color)]">
            <TrendingUp size={17} aria-hidden="true" />
          </span>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <p className="section-kicker">RADAR GRATUITO · GUATEMALA</p>
              <span className="inline-flex items-center gap-1 rounded-full border border-sky-300/20 bg-sky-300/[0.06] px-2 py-1 font-mono text-[8px] uppercase tracking-[0.12em] text-sky-100">
                <ShieldCheck size={10} aria-hidden="true" /> Piloto sin publicación
              </span>
            </div>
            <h2 id="trend-radar-title" className="mt-1 text-lg font-bold text-zinc-100">Investiga una señal y conviértela en misión</h2>
            <p className="mt-1 max-w-3xl text-xs leading-5 text-zinc-500">
              Google Trends y Google News en modo lectura, sin API key. Seleccionar una señal sólo precarga un brief: no consume créditos de X ni publica contenido.
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => void refresh(topic)}
          disabled={!sessionActive || loading}
          className="inline-flex min-h-10 items-center justify-center gap-2 rounded-full border border-white/[0.09] px-4 text-xs font-bold text-zinc-300 disabled:cursor-not-allowed disabled:opacity-35"
        >
          {loading ? <LoaderCircle size={13} className="animate-spin" aria-hidden="true" /> : <RefreshCw size={13} aria-hidden="true" />}
          Actualizar señales
        </button>
      </header>

      <div className="trend-topic-tabs" role="tablist" aria-label="Líneas de investigación">
        {TOPICS.map((candidate) => (
          <button
            key={candidate.id}
            type="button"
            role="tab"
            aria-label={`${candidate.label}: ${candidate.description}`}
            aria-selected={topic === candidate.id}
            onClick={() => changeTopic(candidate.id)}
            disabled={!sessionActive || loading}
            className="trend-topic-tab"
          >
            <span>{candidate.label}</span>
            <small>{candidate.description}</small>
          </button>
        ))}
      </div>

      {!sessionActive ? (
        <div className="trend-radar-empty">
          <Search size={20} aria-hidden="true" />
          <div>
            <p className="text-sm font-bold text-zinc-200">Inicia sesión para investigar señales reales.</p>
            <p className="mt-1 text-xs leading-5 text-zinc-500">El radar consulta fuentes públicas en modo lectura y no activa gasto ni publicación.</p>
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
          <ol className="trend-radar-grid" aria-label="Señales actuales para contenido en Guatemala">
            {snapshot.trends.map((trend, index) => {
              const pilotId = `${snapshot.topic}:${trend.published_at}:${trend.title}`;
              const selected = selectedPilotId === pilotId;
              return (
                <li key={pilotId} className={`trend-radar-item ${selected ? "trend-radar-item--selected" : ""}`}>
                  <span className="trend-radar-rank">{String(index + 1).padStart(2, "0")}</span>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <h3 className="max-w-2xl text-sm font-bold leading-6 text-zinc-100">{trend.title}</h3>
                      <span className="rounded-full border border-white/[0.08] px-2 py-1 font-mono text-[8px] uppercase tracking-[0.08em] text-zinc-500">
                        {trend.signal_type === "search_trend" ? "Búsqueda" : "Noticia"}
                      </span>
                    </div>
                    <p className="mt-1 text-[10px] leading-5 text-zinc-500">
                      {trend.approx_traffic || "Sin volumen publicado"}
                      {trend.news_source ? ` · ${trend.news_source}` : ""}
                      {trend.news_items.length > 0 ? ` · ${trend.news_items.length} evidencia${trend.news_items.length === 1 ? "" : "s"}` : ""}
                    </p>
                    <time className="font-mono text-[9px] text-zinc-600" dateTime={trend.published_at}>{readableDate(trend.published_at)}</time>

                    {trend.news_items.length > 0 && (
                      <details className="trend-evidence mt-3">
                        <summary><BookOpen size={11} aria-hidden="true" /> Revisar evidencia</summary>
                        <ul>
                          {trend.news_items.map((item) => (
                            <li key={item.url}>
                              <a href={item.url} target="_blank" rel="noreferrer">
                                <span>{item.title}</span>
                                <small>{item.source}</small>
                                <ExternalLink size={10} aria-hidden="true" />
                              </a>
                            </li>
                          ))}
                        </ul>
                      </details>
                    )}

                    <button
                      type="button"
                      onClick={() => preparePilot(trend)}
                      disabled={!onPreparePilot}
                      className="trend-pilot-button mt-4"
                    >
                      {selected ? "Misión precargada" : "Preparar piloto"}
                      <ArrowRight size={12} aria-hidden="true" />
                    </button>
                  </div>
                </li>
              );
            })}
          </ol>
          <footer className="flex flex-col gap-2 border-t border-white/[0.06] px-5 py-4 text-[10px] text-zinc-500 sm:flex-row sm:items-center sm:justify-between">
            <span>Actualizado {readableDate(snapshot.fetched_at)} · datos reales, sin resultados sintéticos.</span>
            <a href={snapshot.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-semibold text-zinc-300 hover:text-white">
              Fuente: {snapshot.source} <ExternalLink size={10} aria-hidden="true" />
            </a>
          </footer>
        </div>
      ) : null}
    </section>
  );
}
