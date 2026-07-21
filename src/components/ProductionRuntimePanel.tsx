import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import {
  CheckCircle2,
  KeyRound,
  LogOut,
  Play,
  RefreshCw,
  ServerCog,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import {
  RuntimeApiError,
  runtimeApi,
} from "../lib/runtimeApi";
import type {
  BrowserRuntimeSession,
  RuntimeApi,
  RuntimeAuditEvent,
  RuntimeBrief,
  RuntimePlatform,
  RuntimeRun,
} from "../lib/runtimeApi";

interface ProductionRuntimePanelProps {
  api?: RuntimeApi;
}

const PLATFORM_OPTIONS: Array<{ id: RuntimePlatform; label: string }> = [
  { id: "x", label: "X" },
  { id: "facebook", label: "Facebook" },
  { id: "tiktok", label: "TikTok" },
  { id: "instagram", label: "Instagram" },
];

const DEFAULT_BRIEF: RuntimeBrief = {
  title: "Evidence-led campaign",
  objective: "Explain how an AI-native content operating model creates governed growth",
  audience: "growth and brand leaders",
  platforms: ["x", "instagram"],
  budget_cents: 0,
  campaign_goal: "qualified_demand",
};

function messageFromError(error: unknown): string {
  if (error instanceof RuntimeApiError) {
    return error.requestId
      ? `${error.message} · request ${error.requestId}`
      : error.message;
  }
  return error instanceof Error ? error.message : "Unexpected runtime error";
}

function scholarFromRun(run: RuntimeRun | null) {
  const research = run?.artifacts.find((artifact) => artifact.kind === "research_dossier");
  const scholar = research?.payload.scholar;
  if (!scholar || typeof scholar !== "object" || Array.isArray(scholar)) return null;
  const values = scholar as Record<string, unknown>;
  const reframe = values.reencuadre_cognitivo;
  const tradeoff = values.tension_del_trade_off;
  const resolution = values.resolucion_operativa;
  if (typeof reframe !== "string" || typeof tradeoff !== "string" || typeof resolution !== "string") {
    return null;
  }
  return { reframe, tradeoff, resolution };
}

export function ProductionRuntimePanel({ api = runtimeApi }: ProductionRuntimePanelProps) {
  const [apiKey, setApiKey] = useState("");
  const [session, setSession] = useState<BrowserRuntimeSession | null>(null);
  const [brief, setBrief] = useState<RuntimeBrief>(DEFAULT_BRIEF);
  const [run, setRun] = useState<RuntimeRun | null>(null);
  const [auditEvents, setAuditEvents] = useState<RuntimeAuditEvent[]>([]);
  const [busyAction, setBusyAction] = useState<string>("");
  const [error, setError] = useState("");

  const scholar = useMemo(() => scholarFromRun(run), [run]);
  const packageArtifact = run?.artifacts.find((artifact) => artifact.kind === "campaign_package");

  useEffect(() => {
    let active = true;
    void api.resumeSession()
      .then((resumed) => {
        if (active && resumed) setSession(resumed);
      })
      .catch((caught) => {
        if (active) setError(messageFromError(caught));
      });
    return () => {
      active = false;
    };
  }, [api]);

  const refreshAudit = async () => {
    const events = await api.auditEvents();
    setAuditEvents(events);
  };

  const openSession = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!apiKey.trim()) return;
    setBusyAction("session");
    setError("");
    try {
      const opened = await api.createSession(apiKey.trim());
      setSession(opened);
      setRun(null);
      await refreshAudit();
    } catch (caught) {
      setSession(null);
      setError(messageFromError(caught));
    } finally {
      setApiKey("");
      setBusyAction("");
    }
  };

  const launchRun = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!session || brief.platforms.length === 0) return;
    setBusyAction("run");
    setError("");
    try {
      const created = await api.createRun(brief, session.csrf_token);
      setRun(created);
      await refreshAudit();
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusyAction("");
    }
  };

  const decide = async (decision: "approve" | "reject") => {
    if (!session || !run) return;
    setBusyAction(decision);
    setError("");
    try {
      const decided = decision === "approve"
        ? await api.approveRun(run.run_id, session.csrf_token)
        : await api.rejectRun(run.run_id, session.csrf_token);
      setRun(decided);
      await refreshAudit();
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusyAction("");
    }
  };

  const closeSession = async () => {
    if (!session) return;
    setBusyAction("logout");
    setError("");
    try {
      await api.revokeSession(session.csrf_token);
      setSession(null);
      setRun(null);
      setAuditEvents([]);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusyAction("");
    }
  };

  const togglePlatform = (platform: RuntimePlatform) => {
    setBrief((current) => ({
      ...current,
      platforms: current.platforms.includes(platform)
        ? current.platforms.filter((item) => item !== platform)
        : [...current.platforms, platform],
    }));
  };

  return (
    <section aria-labelledby="production-runtime-title" className="surface-panel overflow-hidden">
      <header className="flex flex-col gap-4 border-b border-white/[0.07] px-4 py-5 sm:px-6 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-3">
          <span className="grid h-11 w-11 place-items-center rounded-xl border border-emerald-300/15 bg-emerald-300/[0.07] text-emerald-300">
            <ServerCog size={18} aria-hidden="true" />
          </span>
          <div>
            <p className="section-kicker">03 / PRODUCTION RUNTIME</p>
            <h2 id="production-runtime-title" className="mt-1 text-lg font-bold text-zinc-100">
              Ejecuta el backend gobernado, no la simulación del navegador.
            </h2>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 font-mono text-[9px] uppercase tracking-[0.1em]">
          <span className="rounded-full border border-emerald-300/15 bg-emerald-300/[0.06] px-3 py-1.5 text-emerald-300">
            HttpOnly session
          </span>
          <span className="rounded-full border border-white/[0.08] px-3 py-1.5 text-zinc-500">
            No external effects
          </span>
        </div>
      </header>

      <div className="grid gap-0 xl:grid-cols-[minmax(300px,0.7fr)_minmax(0,1.3fr)]">
        <div className="border-b border-white/[0.07] p-4 sm:p-6 xl:border-b-0 xl:border-r">
          {!session ? (
            <form onSubmit={openSession} className="space-y-4">
              <div>
                <div className="flex items-center gap-2 text-sm font-semibold text-zinc-200">
                  <KeyRound size={15} className="text-[var(--primary-color)]" aria-hidden="true" />
                  Secure tenant exchange
                </div>
                <p className="mt-2 text-xs leading-6 text-zinc-500">
                  La key se envía una sola vez al mismo origen. El backend responde con una cookie HttpOnly; no se guarda en localStorage ni en el bundle.
                </p>
              </div>
              <label className="block text-xs font-semibold text-zinc-300">
                Tenant API key
                <input
                  type="password"
                  autoComplete="current-password"
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  className="mt-2 w-full rounded-xl border border-white/[0.09] bg-black/30 px-3 py-3 font-mono text-xs text-zinc-100 outline-none transition focus:border-[var(--primary-color)]"
                  required
                  minLength={24}
                />
              </label>
              <button
                type="submit"
                disabled={busyAction === "session" || apiKey.trim().length < 24}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-[var(--primary-color)] px-4 py-3 text-xs font-extrabold text-black transition disabled:cursor-not-allowed disabled:opacity-40"
              >
                <ShieldCheck size={15} aria-hidden="true" />
                {busyAction === "session" ? "Opening session…" : "Open secure session"}
              </button>
            </form>
          ) : (
            <div className="space-y-5">
              <div className="rounded-xl border border-emerald-300/15 bg-emerald-300/[0.05] p-4">
                <p className="font-mono text-[9px] uppercase tracking-[0.12em] text-emerald-300">Authenticated tenant</p>
                <p className="mt-2 break-all text-sm font-bold text-zinc-100">{session.tenant_id}</p>
                <p className="mt-1 text-[11px] text-zinc-500">
                  Session expires {new Date(session.expires_at).toLocaleString()}.
                </p>
              </div>
              <button
                type="button"
                onClick={closeSession}
                disabled={busyAction === "logout"}
                className="flex w-full items-center justify-center gap-2 rounded-xl border border-white/[0.09] px-4 py-2.5 text-xs font-semibold text-zinc-300 transition hover:border-red-300/30 hover:text-red-200 disabled:opacity-40"
              >
                <LogOut size={14} aria-hidden="true" />
                Revoke browser session
              </button>
              <div className="border-t border-white/[0.07] pt-5">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-bold text-zinc-200">Durable audit</p>
                    <p className="mt-1 text-[11px] text-zinc-500">Mutation evidence for this tenant.</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => void refreshAudit()}
                    className="rounded-lg border border-white/[0.08] p-2 text-zinc-400 hover:text-zinc-100"
                    aria-label="Refresh durable audit"
                  >
                    <RefreshCw size={13} aria-hidden="true" />
                  </button>
                </div>
                <ol className="mt-3 max-h-56 space-y-2 overflow-y-auto" aria-label="Durable audit events">
                  {auditEvents.length === 0 ? (
                    <li className="rounded-lg border border-dashed border-white/[0.08] p-3 text-[11px] text-zinc-600">No mutation evidence yet.</li>
                  ) : auditEvents.map((item) => (
                    <li key={item.event_id} className="rounded-lg border border-white/[0.06] bg-black/20 p-3">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono text-[10px] text-[var(--primary-color)]">{item.action}</span>
                        <span className="font-mono text-[9px] text-zinc-600">#{item.sequence}</span>
                      </div>
                      <p className="mt-1 truncate text-[10px] text-zinc-500">{item.request_id}</p>
                    </li>
                  ))}
                </ol>
              </div>
            </div>
          )}
        </div>

        <div className="p-4 sm:p-6">
          <form onSubmit={launchRun} className="grid gap-4 lg:grid-cols-2">
            <label className="text-xs font-semibold text-zinc-300">
              Campaign title
              <input
                value={brief.title}
                onChange={(event) => setBrief((current) => ({ ...current, title: event.target.value }))}
                className="mt-2 w-full rounded-xl border border-white/[0.09] bg-black/30 px-3 py-2.5 text-sm text-zinc-100 outline-none focus:border-[var(--primary-color)]"
                disabled={!session}
                required
              />
            </label>
            <label className="text-xs font-semibold text-zinc-300">
              Target segment
              <input
                value={brief.audience}
                onChange={(event) => setBrief((current) => ({ ...current, audience: event.target.value }))}
                className="mt-2 w-full rounded-xl border border-white/[0.09] bg-black/30 px-3 py-2.5 text-sm text-zinc-100 outline-none focus:border-[var(--primary-color)]"
                disabled={!session}
                required
              />
            </label>
            <label className="text-xs font-semibold text-zinc-300 lg:col-span-2">
              Objective
              <textarea
                value={brief.objective}
                onChange={(event) => setBrief((current) => ({ ...current, objective: event.target.value }))}
                className="mt-2 min-h-24 w-full resize-y rounded-xl border border-white/[0.09] bg-black/30 px-3 py-2.5 text-sm leading-6 text-zinc-100 outline-none focus:border-[var(--primary-color)]"
                disabled={!session}
                required
              />
            </label>
            <fieldset className="lg:col-span-2" disabled={!session}>
              <legend className="text-xs font-semibold text-zinc-300">Platforms</legend>
              <div className="mt-2 flex flex-wrap gap-2">
                {PLATFORM_OPTIONS.map((platform) => (
                  <label key={platform.id} className="flex cursor-pointer items-center gap-2 rounded-lg border border-white/[0.08] px-3 py-2 text-xs text-zinc-400 has-[:checked]:border-[var(--primary-color)] has-[:checked]:text-zinc-100">
                    <input
                      type="checkbox"
                      checked={brief.platforms.includes(platform.id)}
                      onChange={() => togglePlatform(platform.id)}
                      className="accent-[var(--primary-color)]"
                    />
                    {platform.label}
                  </label>
                ))}
              </div>
            </fieldset>
            <button
              type="submit"
              disabled={!session || Boolean(busyAction) || brief.platforms.length === 0}
              className="flex items-center justify-center gap-2 rounded-xl border border-[var(--primary-color)]/40 bg-[var(--primary-color)]/10 px-4 py-3 text-xs font-extrabold text-[var(--primary-color)] transition hover:bg-[var(--primary-color)]/15 disabled:cursor-not-allowed disabled:opacity-35 lg:col-span-2"
            >
              <Play size={14} aria-hidden="true" />
              {busyAction === "run" ? "Running eight stations…" : "Run governed campaign"}
            </button>
          </form>

          {error && (
            <p role="alert" className="mt-4 rounded-xl border border-red-300/20 bg-red-300/[0.06] p-3 text-xs text-red-200">
              {error}
            </p>
          )}

          <div className="mt-6" aria-live="polite">
            {!run ? (
              <div className="rounded-xl border border-dashed border-white/[0.08] p-6 text-center text-xs leading-6 text-zinc-600">
                Open a tenant session to execute the persistent backend. The cinematic simulator above remains side-effect free and independent.
              </div>
            ) : (
              <div className="space-y-5">
                <div className="flex flex-col gap-3 rounded-xl border border-white/[0.08] bg-black/20 p-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="font-mono text-[9px] uppercase tracking-[0.12em] text-zinc-500">Run / {run.run_id}</p>
                    <p className="mt-2 text-sm font-bold text-zinc-100">{run.status.replaceAll("_", " ")}</p>
                  </div>
                  <span className="rounded-full border border-amber-300/20 bg-amber-300/[0.06] px-3 py-1.5 font-mono text-[9px] uppercase text-amber-200">
                    publication=false
                  </span>
                </div>

                {scholar && (
                  <div className="grid gap-3 lg:grid-cols-3">
                    {[
                      ["Reencuadre Cognitivo", scholar.reframe],
                      ["Tensión del Trade-off", scholar.tradeoff],
                      ["Resolución Operativa", scholar.resolution],
                    ].map(([title, content]) => (
                      <article key={title} className="rounded-xl border border-white/[0.07] bg-white/[0.025] p-4">
                        <h3 className="text-xs font-bold text-[var(--primary-color)]">{title}</h3>
                        <p className="mt-2 text-[11px] leading-5 text-zinc-400">{content}</p>
                      </article>
                    ))}
                  </div>
                )}

                <div>
                  <p className="text-xs font-bold text-zinc-200">Versioned artifacts</p>
                  <ul className="mt-3 grid gap-2 sm:grid-cols-2">
                    {run.artifacts.map((artifact) => (
                      <li key={artifact.artifact_id} className="rounded-lg border border-white/[0.06] bg-black/20 p-3">
                        <p className="text-xs font-semibold text-zinc-300">{artifact.title}</p>
                        <p className="mt-1 truncate font-mono text-[9px] text-zinc-600">{artifact.kind} · {artifact.artifact_id}</p>
                      </li>
                    ))}
                  </ul>
                </div>

                {run.status === "awaiting_greenlight" && (
                  <div className="grid gap-3 sm:grid-cols-2">
                    <button
                      type="button"
                      onClick={() => void decide("approve")}
                      disabled={Boolean(busyAction)}
                      className="flex items-center justify-center gap-2 rounded-xl bg-emerald-300 px-4 py-3 text-xs font-extrabold text-emerald-950 disabled:opacity-40"
                    >
                      <CheckCircle2 size={15} aria-hidden="true" /> Approve exact artifacts
                    </button>
                    <button
                      type="button"
                      onClick={() => void decide("reject")}
                      disabled={Boolean(busyAction)}
                      className="flex items-center justify-center gap-2 rounded-xl border border-red-300/25 bg-red-300/[0.06] px-4 py-3 text-xs font-bold text-red-200 disabled:opacity-40"
                    >
                      <XCircle size={15} aria-hidden="true" /> Reject package
                    </button>
                  </div>
                )}

                {packageArtifact && (
                  <div className="rounded-xl border border-emerald-300/15 bg-emerald-300/[0.05] p-4 text-xs text-emerald-100">
                    Sandbox campaign package created. External publication remained disabled.
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
