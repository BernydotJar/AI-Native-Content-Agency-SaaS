import { Cpu, Sparkles } from "lucide-react";

interface CinematicHeroProps {
  sessionActive: boolean;
  tenantId?: string;
  completedStations: number;
  totalStations: number;
  readyProviders: number;
  totalProviders: number;
  deliverables: number;
  runStatus?: string;
  selectedProvider?: string;
}

export function CinematicHero({
  sessionActive,
  tenantId,
  completedStations,
  totalStations,
  readyProviders,
  totalProviders,
  deliverables,
  runStatus,
  selectedProvider,
}: CinematicHeroProps) {
  const normalizedRunStatus = runStatus?.replaceAll("_", " ") ?? "standby";

  return (
    <section aria-labelledby="hero-title" className="hero-stage">
      <div className="hero-copy">
        <div className="coordinate-tag">
          <span>OPS / CAMPAIGN-01</span>
          <i />
          <span>{sessionActive ? tenantId ?? "TENANT ACTIVE" : "SESSION OFFLINE"}</span>
        </div>

        <p className="mt-8 flex items-center gap-2 font-mono text-[10px] font-semibold uppercase tracking-[0.22em] text-[var(--primary-color)]">
          <Sparkles size={13} aria-hidden="true" /> AI-native campaign operations
        </p>
        <h1 id="hero-title" className="hero-title">
          Convierte una señal en una <span>campaña completa.</span>
        </h1>
        <p className="mt-5 max-w-2xl text-sm leading-7 text-zinc-400 sm:text-base sm:leading-8">
          Define el resultado, ejecuta las estaciones y aprueba entregables desde un único run gobernado.
        </p>

        <div className="mt-7 grid max-w-2xl grid-cols-2 gap-px overflow-hidden rounded-xl border border-white/[0.07] bg-white/[0.07] sm:grid-cols-4">
          <div className="hero-stat"><strong>{String(totalStations).padStart(2, "0")}</strong><span>stations</span></div>
          <div className="hero-stat"><strong>{String(completedStations).padStart(2, "0")}</strong><span>complete</span></div>
          <div className="hero-stat"><strong>{readyProviders}/{totalProviders || 5}</strong><span>providers</span></div>
          <div className="hero-stat"><strong>{String(deliverables).padStart(2, "0")}</strong><span>outputs</span></div>
        </div>
      </div>

      <div className="orchestration-visual" aria-hidden="true">
        <div className="orchestration-halo" />
        <div className="orbit-ring orbit-ring--outer"><span /><span /><span /></div>
        <div className="orbit-ring orbit-ring--inner"><span /><span /></div>
        <div className="orchestration-core">
          <Cpu size={24} />
          <strong>{String(completedStations).padStart(2, "0")}</strong>
          <small>{normalizedRunStatus.toUpperCase()}</small>
        </div>
        <span className="orbit-tag orbit-tag--one">{sessionActive ? "SCHOLAR / READY" : "SCHOLAR / STANDBY"}</span>
        <span className="orbit-tag orbit-tag--two">{selectedProvider ? selectedProvider.toUpperCase() : "MODEL / OFF"}</span>
        <span className="orbit-tag orbit-tag--three">GREENLIGHT / HUMAN</span>
      </div>
    </section>
  );
}
