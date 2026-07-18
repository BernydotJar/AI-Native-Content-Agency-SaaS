import {
  Activity,
  AtSign,
  Camera,
  Cable,
  Check,
  Clapperboard,
  FlaskConical,
  Gauge,
  Layers3,
  MessageCircleMore,
  Music2,
  PackageCheck,
  Radar,
  ShieldCheck,
  Sparkles,
  Wrench,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import {
  SIMULATION_TOOL_CATALOG,
  TREND_SIGNALS,
} from "../lib/simulationRuntime";

type ToolCategory = (typeof SIMULATION_TOOL_CATALOG)[number]["category"];
type TrendPlatform = (typeof TREND_SIGNALS)[number]["platform"];

interface VisualToken {
  label: string;
  icon: LucideIcon;
  badgeClassName: string;
  iconClassName: string;
}

const CATEGORY_TOKENS: Record<ToolCategory, VisualToken> = {
  sensor: {
    label: "Sensor",
    icon: Radar,
    badgeClassName: "border-cyan-300/20 bg-cyan-300/[0.08] text-cyan-200",
    iconClassName: "border-cyan-300/15 bg-cyan-300/[0.08] text-cyan-200",
  },
  "mcp-adapter": {
    label: "MCP adapter",
    icon: Cable,
    badgeClassName: "border-violet-300/20 bg-violet-300/[0.08] text-violet-200",
    iconClassName: "border-violet-300/15 bg-violet-300/[0.08] text-violet-200",
  },
  media: {
    label: "Media",
    icon: Clapperboard,
    badgeClassName: "border-fuchsia-300/20 bg-fuchsia-300/[0.08] text-fuchsia-200",
    iconClassName: "border-fuchsia-300/15 bg-fuchsia-300/[0.08] text-fuchsia-200",
  },
  packaging: {
    label: "Packaging",
    icon: PackageCheck,
    badgeClassName: "border-amber-300/20 bg-amber-300/[0.08] text-amber-200",
    iconClassName: "border-amber-300/15 bg-amber-300/[0.08] text-amber-200",
  },
};

const PLATFORM_TOKENS: Record<
  TrendPlatform,
  Pick<VisualToken, "icon" | "badgeClassName" | "iconClassName">
> = {
  X: {
    icon: AtSign,
    badgeClassName: "border-slate-300/20 bg-slate-300/[0.08] text-slate-200",
    iconClassName: "border-slate-300/15 bg-slate-300/[0.08] text-slate-200",
  },
  Facebook: {
    icon: MessageCircleMore,
    badgeClassName: "border-blue-300/20 bg-blue-300/[0.08] text-blue-200",
    iconClassName: "border-blue-300/15 bg-blue-300/[0.08] text-blue-200",
  },
  TikTok: {
    icon: Music2,
    badgeClassName: "border-pink-300/20 bg-pink-300/[0.08] text-pink-200",
    iconClassName: "border-pink-300/15 bg-pink-300/[0.08] text-pink-200",
  },
  Instagram: {
    icon: Camera,
    badgeClassName: "border-orange-300/20 bg-orange-300/[0.08] text-orange-200",
    iconClassName: "border-orange-300/15 bg-orange-300/[0.08] text-orange-200",
  },
};

function formatCapability(capability: string) {
  return capability.replaceAll("-", " ");
}

export function ToolFabricPanel() {
  return (
    <section
      aria-labelledby="tool-fabric-title"
      className="relative isolate overflow-hidden rounded-2xl border border-white/10 bg-[#09090b]/90 text-zinc-100 shadow-[0_28px_90px_rgba(0,0,0,0.52)]"
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_8%_0%,rgba(34,211,238,0.10),transparent_27%),radial-gradient(circle_at_96%_100%,rgba(168,85,247,0.08),transparent_34%)]"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 -z-10 opacity-30 [background-image:radial-gradient(rgba(255,255,255,0.18)_0.7px,transparent_0.7px)] [background-size:18px_18px] [mask-image:linear-gradient(to_bottom,black,transparent_55%)]"
      />

      <div className="relative p-5 sm:p-6 lg:p-8">
        <header className="flex flex-col gap-5 border-b border-white/[0.07] pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="flex max-w-3xl items-start gap-3.5">
            <span className="mt-0.5 rounded-xl border border-cyan-300/15 bg-cyan-300/[0.08] p-2.5 text-cyan-200 shadow-[0_0_32px_rgba(34,211,238,0.08)]">
              <Layers3 aria-hidden="true" size={19} />
            </span>
            <div>
              <p className="mb-1.5 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-cyan-200">
                <Sparkles aria-hidden="true" size={12} />
                Tool fabric
              </p>
              <h2
                id="tool-fabric-title"
                className="text-xl font-semibold tracking-[-0.025em] text-white sm:text-2xl"
              >
                Contratos de ejecución, sin ficción operativa
              </h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-400">
                Catálogo determinístico para la demostración. Ninguna tarjeta representa una
                conexión activa, una llamada remota ni una operación sobre cuentas reales.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2" aria-label="Estado del catálogo">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-300/20 bg-amber-300/[0.08] px-3 py-1.5 text-xs font-semibold text-amber-200">
              <FlaskConical aria-hidden="true" size={13} />
              Sandbox local
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-300/20 bg-emerald-300/[0.08] px-3 py-1.5 text-xs font-semibold text-emerald-200">
              <ShieldCheck aria-hidden="true" size={13} />
              Sin side effects
            </span>
          </div>
        </header>

        <div className="mt-6" aria-labelledby="tool-contracts-title">
          <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="font-mono text-[0.68rem] uppercase tracking-[0.18em] text-zinc-500">
                Contracts / 08
              </p>
              <h3 id="tool-contracts-title" className="mt-1 text-base font-semibold text-white">
                Tool contracts simulados
              </h3>
            </div>
            <p className="flex items-center gap-1.5 text-xs text-zinc-500">
              <Wrench aria-hidden="true" size={13} />
              Capacidades descriptivas; no ejecutan proveedores externos
            </p>
          </div>

          <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {SIMULATION_TOOL_CATALOG.map((tool, index) => {
              const category = CATEGORY_TOKENS[tool.category];
              const CategoryIcon = category.icon;

              return (
                <li key={tool.id} className="min-w-0">
                  <article
                    aria-labelledby={`tool-${tool.id}`}
                    className="group flex h-full min-h-64 flex-col rounded-xl border border-white/[0.08] bg-black/25 p-4 transition-colors duration-200 hover:border-white/[0.16] hover:bg-white/[0.035]"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <span className={`rounded-lg border p-2 ${category.iconClassName}`}>
                        <CategoryIcon aria-hidden="true" size={16} />
                      </span>
                      <span className="font-mono text-[0.65rem] tracking-[0.14em] text-zinc-600">
                        {String(index + 1).padStart(2, "0")}
                      </span>
                    </div>

                    <div className="mt-4 flex flex-wrap items-center gap-1.5">
                      <span
                        className={`rounded-full border px-2 py-0.5 text-[0.65rem] font-semibold uppercase tracking-[0.1em] ${category.badgeClassName}`}
                      >
                        {category.label}
                      </span>
                      <span className="rounded-full border border-amber-300/15 bg-amber-300/[0.06] px-2 py-0.5 text-[0.65rem] font-semibold uppercase tracking-[0.1em] text-amber-200">
                        Mock
                      </span>
                    </div>

                    <h4
                      id={`tool-${tool.id}`}
                      className="mt-3 text-sm font-semibold leading-5 text-zinc-100"
                    >
                      {tool.label}
                    </h4>
                    <p className="mt-1.5 text-xs leading-5 text-zinc-500">{tool.description}</p>

                    <div className="mt-4 border-t border-white/[0.06] pt-3">
                      <p className="text-[0.65rem] font-semibold uppercase tracking-[0.14em] text-zinc-600">
                        Capabilities
                      </p>
                      <ul className="mt-2 flex flex-wrap gap-1.5" aria-label={`Capacidades de ${tool.label}`}>
                        {tool.capabilities.map((capability) => (
                          <li
                            key={capability}
                            className="rounded-md border border-white/[0.07] bg-white/[0.025] px-2 py-1 font-mono text-[0.65rem] text-zinc-400"
                          >
                            {formatCapability(capability)}
                          </li>
                        ))}
                      </ul>
                    </div>

                    <dl className="mt-auto grid grid-cols-2 gap-2 pt-4 text-[0.68rem]">
                      <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-2.5 py-2">
                        <dt className="text-zinc-600">Entorno</dt>
                        <dd className="mt-0.5 flex items-center gap-1 text-zinc-300">
                          <Check aria-hidden="true" size={11} className="text-emerald-300" />
                          Sandbox
                        </dd>
                      </div>
                      <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-2.5 py-2">
                        <dt className="text-zinc-600">Side effects</dt>
                        <dd className="mt-0.5 flex items-center gap-1 text-zinc-300">
                          <ShieldCheck aria-hidden="true" size={11} className="text-emerald-300" />
                          Ninguno
                        </dd>
                      </div>
                    </dl>
                  </article>
                </li>
              );
            })}
          </ul>
        </div>

        <div
          className="mt-7 border-t border-white/[0.07] pt-6"
          aria-labelledby="trend-signals-title"
        >
          <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="font-mono text-[0.68rem] uppercase tracking-[0.18em] text-zinc-500">
                Signal fixtures / 04
              </p>
              <h3 id="trend-signals-title" className="mt-1 text-base font-semibold text-white">
                Momentum social simulado
              </h3>
            </div>
            <p className="flex items-center gap-1.5 text-xs text-zinc-500">
              <Activity aria-hidden="true" size={13} />
              Valores fijos de demo · no son datos live
            </p>
          </div>

          <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {TREND_SIGNALS.map((signal) => {
              const platform = PLATFORM_TOKENS[signal.platform];
              const PlatformIcon = platform.icon;

              return (
                <li key={signal.id}>
                  <article
                    aria-labelledby={`trend-${signal.id}`}
                    className="h-full rounded-xl border border-white/[0.08] bg-white/[0.025] p-4"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span
                        className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${platform.badgeClassName}`}
                      >
                        <PlatformIcon aria-hidden="true" size={13} />
                        {signal.platform}
                      </span>
                      <span className="font-mono text-sm font-semibold tabular-nums text-white">
                        {signal.momentum}
                        <span className="ml-0.5 text-[0.65rem] font-normal text-zinc-600">/100</span>
                      </span>
                    </div>

                    <h4
                      id={`trend-${signal.id}`}
                      className="mt-4 text-sm font-semibold leading-5 text-zinc-100"
                    >
                      {signal.topic}
                    </h4>
                    <p className="mt-1.5 text-xs leading-5 text-zinc-500">{signal.nativeFormat}</p>

                    <div className="mt-4">
                      <div className="mb-1.5 flex items-center justify-between text-[0.65rem] uppercase tracking-[0.12em] text-zinc-600">
                        <span>Momentum</span>
                        <span>Mock signal</span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                        <div
                          role="progressbar"
                          aria-label={`Momentum simulado de ${signal.platform}: ${signal.topic}`}
                          aria-valuemin={0}
                          aria-valuemax={100}
                          aria-valuenow={signal.momentum}
                          className="h-full rounded-full bg-gradient-to-r from-cyan-400 via-sky-400 to-violet-400 shadow-[0_0_16px_rgba(56,189,248,0.35)]"
                          style={{ width: `${signal.momentum}%` }}
                        />
                      </div>
                    </div>

                    <p className="mt-3 border-t border-white/[0.06] pt-3 text-[0.7rem] leading-5 text-zinc-600">
                      {signal.audienceBehavior}
                    </p>
                  </article>
                </li>
              );
            })}
          </ul>

          <div className="mt-4 flex flex-col gap-2 rounded-xl border border-dashed border-amber-300/15 bg-amber-300/[0.035] px-4 py-3 text-xs leading-5 text-zinc-400 sm:flex-row sm:items-center sm:justify-between">
            <p className="flex items-start gap-2">
              <Gauge aria-hidden="true" size={14} className="mt-0.5 shrink-0 text-amber-200" />
              El momentum compara fixtures locales; no mide alcance, engagement ni actividad de
              plataformas reales.
            </p>
            <span className="shrink-0 font-mono text-[0.65rem] uppercase tracking-[0.14em] text-amber-200/80">
              Source state: mock
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}
