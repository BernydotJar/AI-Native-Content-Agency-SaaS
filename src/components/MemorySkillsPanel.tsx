import { useState } from "react";
import type { FormEvent } from "react";
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  Database,
  Eye,
  Flag,
  Globe2,
  History,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

const MEMORY_LOOP = [
  { label: "Observe", detail: "Captura señales", icon: Eye },
  { label: "Store", detail: "Comprime contexto", icon: Database },
  { label: "Search", detail: "Recupera patrones", icon: Search },
  { label: "Recall", detail: "Inyecta memoria", icon: History },
] as const;

const SIMULATED_MEMORIES = [
  {
    id: "mem-tone",
    title: "Dirección visual cinematográfica",
    observation:
      "Priorizar obsidiana, profundidad por capas y un único foco luminoso por escena.",
    provenance: "Brand review · Risk Agent · Sesión actual",
    confidence: 96,
    recency: "Observada hace 2 min",
  },
  {
    id: "mem-audience",
    title: "Audiencia técnica senior",
    observation:
      "Escribir para engineering leaders y founders que valoran trade-offs verificables.",
    provenance: "Campaign brief · CEO Agent · Caso 3",
    confidence: 89,
    recency: "Observada hace 8 min",
  },
  {
    id: "mem-framework",
    title: "Patrón persuasivo preferido",
    observation:
      "Abrir con reencuadre, sostener la tensión técnica y cerrar con resolución operativa.",
    provenance: "Scholar output · Research Agent · Kleppmann",
    confidence: 84,
    recency: "Observada hace 14 min",
  },
] as const;

const SKILLS = [
  {
    id: "scholar-nlp",
    name: "Scholar NLP",
    description: "Reencuadre, trade-off y resolución operativa.",
    icon: BookOpen,
    defaultEnabled: true,
  },
  {
    id: "ai-seo",
    name: "AI-SEO",
    description: "Optimiza descubrimiento semántico y respuestas generativas.",
    icon: Globe2,
    defaultEnabled: true,
  },
  {
    id: "churn-prevention",
    name: "Churn Prevention",
    description: "Activa señales de retención y contenido preventivo.",
    icon: RefreshCw,
    defaultEnabled: false,
  },
  {
    id: "brand-guard",
    name: "Brand Guard",
    description: "Audita consistencia, tono y riesgo antes de publicar.",
    icon: ShieldCheck,
    defaultEnabled: true,
  },
] as const;

export type SkillId = (typeof SKILLS)[number]["id"];

export interface SessionMemoryFlag {
  id: string;
  content: string;
  provenance: string;
  confidence: number;
}

interface MemorySkillsPanelProps {
  enabledSkills: Record<SkillId, boolean>;
  memoryFlags: readonly SessionMemoryFlag[];
  onToggleSkill: (skillId: SkillId) => void;
  onAddMemoryFlag: (content: string) => void;
}

export function MemorySkillsPanel({
  enabledSkills,
  memoryFlags,
  onToggleSkill,
  onAddMemoryFlag,
}: MemorySkillsPanelProps) {
  const [flagDraft, setFlagDraft] = useState("");

  const handleFlagSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalized = flagDraft.trim().replace(/\s+/g, " ");
    if (!normalized) return;
    onAddMemoryFlag(normalized);
    setFlagDraft("");
  };

  const activeSkillCount = Object.values(enabledSkills).filter(Boolean).length;

  return (
    <section
      aria-labelledby="memory-skills-title"
      className="relative overflow-hidden rounded-2xl border border-white/10 bg-zinc-950/80 text-zinc-100 shadow-[0_24px_70px_rgba(0,0,0,0.45)]"
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_12%_0%,rgba(56,189,248,0.10),transparent_34%),radial-gradient(circle_at_92%_100%,rgba(139,92,246,0.08),transparent_38%)]"
      />

      <div className="relative flex flex-col gap-6 p-5 sm:p-6">
        <header className="flex flex-col gap-3 border-b border-white/5 pb-5 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3">
            <div className="mt-0.5 rounded-xl border border-sky-400/20 bg-sky-400/10 p-2.5 text-sky-300">
              <Sparkles aria-hidden="true" size={18} />
            </div>
            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-[0.18em] text-sky-300">
                Memoria simulada
              </p>
              <h2 id="memory-skills-title" className="text-lg font-semibold tracking-tight text-white">
                Memory &amp; Skills Console
              </h2>
              <p className="mt-1 max-w-xl text-sm leading-6 text-zinc-400">
                Esta consola usa estado de sesión en el navegador. El runtime Python incluye memoria
                SQLite persistente, pero no hay transporte API conectado en esta demo.
              </p>
            </div>
          </div>

          <span className="inline-flex w-fit items-center gap-2 rounded-full border border-amber-300/20 bg-amber-300/10 px-3 py-1.5 text-xs font-medium text-amber-200">
            <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-amber-300" />
            Simulación local
          </span>
        </header>

        <div aria-labelledby="memory-loop-title">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <h3 id="memory-loop-title" className="text-sm font-semibold text-zinc-100">
                Loop de memoria simulado
              </h3>
              <p className="mt-0.5 text-xs text-zinc-500">Observe → Store → Search → Recall</p>
            </div>
            <span className="font-mono text-xs text-zinc-500">MEM://LOOP-01</span>
          </div>

          <ol className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {MEMORY_LOOP.map((step, index) => {
              const Icon = step.icon;

              return (
                <li
                  key={step.label}
                  className="relative min-h-24 rounded-xl border border-white/[0.07] bg-white/[0.025] p-3"
                >
                  <div className="mb-3 flex items-center justify-between">
                    <span className="rounded-lg bg-white/5 p-2 text-sky-300">
                      <Icon aria-hidden="true" size={15} />
                    </span>
                    <span className="font-mono text-xs text-zinc-600">0{index + 1}</span>
                  </div>
                  <p className="text-sm font-semibold text-zinc-200">{step.label}</p>
                  <p className="mt-0.5 text-xs leading-5 text-zinc-500">{step.detail}</p>

                  {index < MEMORY_LOOP.length - 1 && (
                    <ArrowRight
                      aria-hidden="true"
                      size={14}
                      className="absolute -right-2 top-1/2 z-10 hidden -translate-y-1/2 text-zinc-600 sm:block"
                    />
                  )}
                </li>
              );
            })}
          </ol>

          <p className="mt-2 flex items-center justify-end gap-1.5 text-xs text-zinc-500">
            <RefreshCw aria-hidden="true" size={12} />
            Recall alimenta el siguiente ciclo Observe
          </p>
        </div>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(280px,0.75fr)]">
          <div aria-labelledby="simulated-memories-title">
            <div className="mb-3 flex items-end justify-between gap-3">
              <div>
                <h3 id="simulated-memories-title" className="text-sm font-semibold text-zinc-100">
                  Memorias simuladas
                </h3>
                <p className="mt-0.5 text-xs text-zinc-500">
                  Provenance y confianza visibles para cada observación.
                </p>
              </div>
              <span className="rounded-full border border-white/10 px-2.5 py-1 text-xs text-zinc-400">
                {3 + memoryFlags.length} registros
              </span>
            </div>

            <form onSubmit={handleFlagSubmit} className="mb-3 rounded-xl border border-white/[0.07] bg-black/20 p-3">
              <label htmlFor="memory-flag" className="flex items-center gap-2 text-xs font-semibold text-zinc-300">
                <Flag size={13} className="text-sky-300" aria-hidden="true" />
                Add session memory flag
              </label>
              <div className="mt-2 flex flex-col gap-2 sm:flex-row">
                <input
                  id="memory-flag"
                  name="memory-flag"
                  type="text"
                  maxLength={180}
                  value={flagDraft}
                  onChange={(event) => setFlagDraft(event.target.value)}
                  placeholder="E.g. Avoid certainty; show the operating trade-off."
                  className="min-h-11 min-w-0 flex-1 rounded-xl border border-white/10 bg-zinc-950/80 px-3 text-sm text-zinc-200 outline-none placeholder:text-zinc-600 focus:border-sky-300/40 focus:ring-2 focus:ring-sky-400/20"
                />
                <button
                  type="submit"
                  disabled={!flagDraft.trim()}
                  className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-sky-300/20 bg-sky-400/10 px-4 text-xs font-bold text-sky-200 transition-colors hover:bg-sky-400/15 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <Plus size={14} aria-hidden="true" /> Store flag
                </button>
              </div>
              <p className="mt-2 text-[11px] leading-5 text-zinc-500">
                Stored for this browser session and recalled by the next full-campaign simulation.
              </p>
            </form>

            <div className="flex flex-col gap-2.5">
              {SIMULATED_MEMORIES.map((memory) => (
                <article
                  key={memory.id}
                  className="rounded-xl border border-white/[0.07] bg-black/20 p-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h4 className="text-sm font-semibold text-zinc-100">{memory.title}</h4>
                        <span className="rounded-full border border-sky-400/15 bg-sky-400/[0.07] px-2 py-0.5 text-xs font-medium text-sky-300">
                          Simulada
                        </span>
                      </div>
                      <p className="mt-2 text-sm leading-6 text-zinc-300">{memory.observation}</p>
                    </div>
                    <div className="flex items-center gap-1.5 text-emerald-300">
                      <CheckCircle2 aria-hidden="true" size={14} />
                      <span className="text-sm font-semibold">{memory.confidence}%</span>
                    </div>
                  </div>

                  <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/5">
                    <div
                      role="progressbar"
                      aria-label={`Confianza de la memoria simulada ${memory.title}`}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-valuenow={memory.confidence}
                      className="h-full rounded-full bg-gradient-to-r from-sky-500 to-emerald-400"
                      style={{ width: `${memory.confidence}%` }}
                    />
                  </div>

                  <dl className="mt-3 grid gap-2 border-t border-white/5 pt-3 text-xs sm:grid-cols-[1fr_auto]">
                    <div className="min-w-0">
                      <dt className="font-medium text-zinc-500">Provenance simulada</dt>
                      <dd className="mt-0.5 truncate text-zinc-400" title={memory.provenance}>
                        {memory.provenance}
                      </dd>
                    </div>
                    <div className="sm:text-right">
                      <dt className="font-medium text-zinc-500">Recencia</dt>
                      <dd className="mt-0.5 text-zinc-400">{memory.recency}</dd>
                    </div>
                  </dl>
                </article>
              ))}
              {memoryFlags.map((memory) => (
                <article key={memory.id} className="rounded-xl border border-sky-400/15 bg-sky-400/[0.035] p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h4 className="text-sm font-semibold text-zinc-100">Operator memory flag</h4>
                        <span className="rounded-full border border-amber-300/15 bg-amber-300/[0.07] px-2 py-0.5 text-xs font-medium text-amber-200">Session</span>
                      </div>
                      <p className="mt-2 text-sm leading-6 text-zinc-300">{memory.content}</p>
                    </div>
                    <span className="text-sm font-semibold text-emerald-300">{memory.confidence}%</span>
                  </div>
                  <dl className="mt-3 border-t border-white/5 pt-3 text-xs">
                    <dt className="font-medium text-zinc-500">Provenance</dt>
                    <dd className="mt-0.5 text-zinc-400">{memory.provenance}</dd>
                  </dl>
                </article>
              ))}
            </div>
          </div>

          <div aria-labelledby="skills-title">
            <div className="mb-3 flex items-end justify-between gap-3">
              <div>
                <h3 id="skills-title" className="text-sm font-semibold text-zinc-100">
                  Skills simulados
                </h3>
                <p className="mt-0.5 text-xs text-zinc-500">Modifican el próximo pack del Caso 3.</p>
              </div>
              <span aria-live="polite" className="text-xs font-medium text-sky-300">
                {activeSkillCount}/4 activos
              </span>
            </div>

            <div className="flex flex-col gap-2">
              {SKILLS.map((skill) => {
                const Icon = skill.icon;
                const isEnabled = enabledSkills[skill.id];

                return (
                  <button
                    key={skill.id}
                    type="button"
                    role="switch"
                    aria-checked={isEnabled}
                    aria-label={`${isEnabled ? "Desactivar" : "Activar"} ${skill.name}, skill simulado`}
                    onClick={() => onToggleSkill(skill.id)}
                    className="group flex min-h-16 w-full items-center gap-3 rounded-xl border border-white/[0.07] bg-white/[0.025] p-3 text-left transition-colors hover:border-white/15 hover:bg-white/[0.045] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/70 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
                  >
                    <span
                      className={`rounded-lg p-2 transition-colors ${
                        isEnabled
                          ? "bg-sky-400/10 text-sky-300"
                          : "bg-white/5 text-zinc-500 group-hover:text-zinc-400"
                      }`}
                    >
                      <Icon aria-hidden="true" size={16} />
                    </span>

                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-semibold text-zinc-200">{skill.name}</span>
                      <span className="mt-0.5 block text-xs leading-5 text-zinc-500">
                        {skill.description}
                      </span>
                    </span>

                    <span
                      aria-hidden="true"
                      className={`relative h-6 w-11 shrink-0 rounded-full border transition-colors ${
                        isEnabled
                          ? "border-sky-300/30 bg-sky-400/25"
                          : "border-white/10 bg-zinc-900"
                      }`}
                    >
                      <span
                        className={`absolute top-1/2 h-4 w-4 -translate-y-1/2 rounded-full shadow-sm transition-all ${
                          isEnabled ? "left-6 bg-sky-200" : "left-1 bg-zinc-500"
                        }`}
                      />
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
