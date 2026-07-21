import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  KeyRound,
  LoaderCircle,
  LogOut,
  Play,
  RefreshCw,
  ServerCog,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { RuntimeApiError, runtimeApi } from "../lib/runtimeApi";
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

type SessionPhase = "restoring" | "signed_out" | "authenticated";
type AuditPhase = "idle" | "loading" | "ready" | "error";
type NoticeKind = "info" | "warning" | "error";

interface OperatorNotice {
  title: string;
  detail: string;
  kind: NoticeKind;
  requestId?: string;
  retryAfterSeconds?: number;
  canReloadRun?: boolean;
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

const ROLE_CAPABILITIES: Record<
  BrowserRuntimeSession["role"],
  { canCreate: boolean; canDecide: boolean; label: string }
> = {
  viewer: { canCreate: false, canDecide: false, label: "Read-only access" },
  operator: { canCreate: true, canDecide: false, label: "Run operator access" },
  approver: { canCreate: false, canDecide: true, label: "Approval-only access" },
  admin: { canCreate: true, canDecide: true, label: "Administrative access" },
};

function newCommandKey(scope: string): string {
  const bytes = new Uint8Array(16);
  globalThis.crypto.getRandomValues(bytes);
  const suffix = Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("");
  return `${scope}:${suffix}`;
}

function noticeFromError(error: unknown, canReloadRun = false): OperatorNotice {
  if (!(error instanceof RuntimeApiError)) {
    return {
      title: "Unexpected runtime failure",
      detail: "The runtime request could not be completed.",
      kind: "error",
      canReloadRun,
    };
  }

  const shared = {
    requestId: error.requestId || undefined,
    retryAfterSeconds: error.retryAfterSeconds || undefined,
  };
  switch (error.status) {
    case 401:
      return {
        ...shared,
        title: "Session expired",
        detail: "Open a new secure session before continuing.",
        kind: "warning",
      };
    case 403:
      return {
        ...shared,
        title: "Action not permitted",
        detail: "Your current access is read-only for this action.",
        kind: "warning",
      };
    case 404:
      return {
        ...shared,
        title: "Run not found",
        detail: "The run is unavailable or outside the current tenant scope.",
        kind: "warning",
        canReloadRun,
      };
    case 409:
      return {
        ...shared,
        title: "Campaign state changed",
        detail: "Reload the current run before making another decision.",
        kind: "warning",
        canReloadRun,
      };
    case 422:
      return {
        ...shared,
        title: "Check campaign details",
        detail: "One or more fields are incomplete or invalid.",
        kind: "warning",
      };
    case 429:
      return {
        ...shared,
        title: "Too many attempts",
        detail: "The runtime is protecting this tenant from repeated requests.",
        kind: "warning",
      };
    case 503:
      return {
        ...shared,
        title: "Runtime temporarily unavailable",
        detail: "The request was not confirmed. Retrying will reuse the same command key.",
        kind: "error",
        canReloadRun,
      };
    default:
      return {
        ...shared,
        title: "Runtime request failed",
        detail: "The runtime did not confirm the operation.",
        kind: "error",
        canReloadRun,
      };
  }
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
  const [sessionPhase, setSessionPhase] = useState<SessionPhase>("restoring");
  const [session, setSession] = useState<BrowserRuntimeSession | null>(null);
  const [brief, setBrief] = useState<RuntimeBrief>(DEFAULT_BRIEF);
  const [run, setRun] = useState<RuntimeRun | null>(null);
  const [runLookupId, setRunLookupId] = useState("");
  const [auditEvents, setAuditEvents] = useState<RuntimeAuditEvent[]>([]);
  const [auditPhase, setAuditPhase] = useState<AuditPhase>("idle");
  const [busyAction, setBusyAction] = useState<string>("");
  const [notice, setNotice] = useState<OperatorNotice | null>(null);
  const commandKeys = useRef(new Map<string, string>());

  const capabilities = session ? ROLE_CAPABILITIES[session.role] : null;
  const canCreate = Boolean(capabilities?.canCreate);
  const canDecide = Boolean(capabilities?.canDecide);

  const commandKey = (scope: string) => {
    const existing = commandKeys.current.get(scope);
    if (existing) return existing;
    const created = newCommandKey(scope);
    commandKeys.current.set(scope, created);
    return created;
  };

  const clearCommandKey = (scope: string) => {
    commandKeys.current.delete(scope);
  };

  const clearProtectedState = () => {
    setSession(null);
    setRun(null);
    setRunLookupId("");
    setAuditEvents([]);
    setAuditPhase("idle");
    setSessionPhase("signed_out");
    commandKeys.current.clear();
  };

  const handleFailure = (caught: unknown, canReloadRun = false) => {
    if (caught instanceof RuntimeApiError && caught.status === 401) {
      clearProtectedState();
    }
    const nextNotice = noticeFromError(caught, canReloadRun);
    setNotice(nextNotice);
    return nextNotice;
  };

  const refreshAudit = async () => {
    setAuditPhase("loading");
    try {
      const events = await api.auditEvents();
      setAuditEvents(events);
      setAuditPhase("ready");
    } catch (caught) {
      setAuditPhase("error");
      handleFailure(caught);
    }
  };

  useEffect(() => {
    let active = true;
    setSessionPhase("restoring");
    void api.resumeSession()
      .then((resumed) => {
        if (!active) return;
        if (!resumed) {
          setSessionPhase("signed_out");
          return;
        }
        setSession(resumed);
        setSessionPhase("authenticated");
        setAuditPhase("loading");
        void api.auditEvents()
          .then((events) => {
            if (!active) return;
            setAuditEvents(events);
            setAuditPhase("ready");
          })
          .catch((caught) => {
            if (!active) return;
            if (caught instanceof RuntimeApiError && caught.status === 401) {
              setSession(null);
              setRun(null);
              setAuditEvents([]);
              setAuditPhase("idle");
              setSessionPhase("signed_out");
              commandKeys.current.clear();
            } else {
              setAuditPhase("error");
            }
            setNotice(noticeFromError(caught));
          });
      })
      .catch((caught) => {
        if (!active) return;
        setSessionPhase("signed_out");
        setNotice(noticeFromError(caught));
      });
    return () => {
      active = false;
    };
  }, [api]);

  const updateBrief = (patch: Partial<RuntimeBrief>) => {
    clearCommandKey("run:create");
    setBrief((current) => ({ ...current, ...patch }));
  };

  const scholar = useMemo(() => scholarFromRun(run), [run]);
  const packageArtifact = run?.artifacts.find((artifact) => artifact.kind === "campaign_package");

  const openSession = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!apiKey.trim()) return;
    setBusyAction("session");
    setNotice(null);
    try {
      const opened = await api.createSession(apiKey.trim());
      setSession(opened);
      setSessionPhase("authenticated");
      setRun(null);
      commandKeys.current.clear();
      await refreshAudit();
    } catch (caught) {
      clearProtectedState();
      if (caught instanceof RuntimeApiError && caught.status === 401) {
        setNotice({
          title: "Secure session unavailable",
          detail: "A secure session could not be opened. Ask a tenant administrator to confirm your access.",
          kind: "warning",
          requestId: caught.requestId || undefined,
        });
      } else {
        setNotice(noticeFromError(caught));
      }
    } finally {
      setApiKey("");
      setBusyAction("");
    }
  };

  const launchRun = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!session || !canCreate || brief.platforms.length === 0) return;
    setBusyAction("run");
    setNotice(null);
    const scope = "run:create";
    try {
      const created = await api.createRun(brief, session.csrf_token, commandKey(scope));
      setRun(created);
      clearCommandKey(scope);
      await refreshAudit();
    } catch (caught) {
      handleFailure(caught, Boolean(run));
    } finally {
      setBusyAction("");
    }
  };

  const decide = async (decision: "approve" | "reject") => {
    if (!session || !run || !canDecide) return;
    setBusyAction(decision);
    setNotice(null);
    const scope = `greenlight:${decision}:${run.run_id}`;
    try {
      const key = commandKey(scope);
      const decided = decision === "approve"
        ? await api.approveRun(run.run_id, session.csrf_token, key)
        : await api.rejectRun(run.run_id, session.csrf_token, key);
      setRun(decided);
      clearCommandKey(scope);
      await refreshAudit();
    } catch (caught) {
      handleFailure(caught, true);
    } finally {
      setBusyAction("");
    }
  };

  const revokeGreenlight = async () => {
    if (!session || !run || run.status !== "completed" || !canDecide) return;
    const scope = `greenlight:revoke:${run.run_id}`;
    setBusyAction("revoke");
    setNotice(null);
    try {
      const revoked = await api.revokeRun(run.run_id, session.csrf_token, commandKey(scope));
      setRun(revoked);
      clearCommandKey(scope);
      await refreshAudit();
    } catch (caught) {
      handleFailure(caught, true);
    } finally {
      setBusyAction("");
    }
  };

  const loadRun = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const requestedRunId = runLookupId.trim();
    if (!session || !requestedRunId) return;
    setBusyAction("load-run");
    setNotice(null);
    try {
      const current = await api.getRun(requestedRunId);
      setRun(current);
      setRunLookupId(current.run_id);
    } catch (caught) {
      handleFailure(caught, Boolean(run));
    } finally {
      setBusyAction("");
    }
  };

  const reloadRun = async () => {
    if (!run) return;
    setBusyAction("refresh-run");
    setNotice(null);
    try {
      const current = await api.getRun(run.run_id);
      setRun(current);
      await refreshAudit();
    } catch (caught) {
      handleFailure(caught, true);
    } finally {
      setBusyAction("");
    }
  };

  const closeSession = async () => {
    if (!session) return;
    setBusyAction("logout");
    setNotice(null);
    try {
      await api.revokeSession(session.csrf_token);
      clearProtectedState();
    } catch (caught) {
      handleFailure(caught);
    } finally {
      setBusyAction("");
    }
  };

  const togglePlatform = (platform: RuntimePlatform) => {
    clearCommandKey("run:create");
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

      {notice && (
        <div
          role={notice.kind === "error" ? "alert" : "status"}
          className={`mx-4 mt-4 rounded-xl border p-4 text-xs sm:mx-6 ${
            notice.kind === "error"
              ? "border-red-300/20 bg-red-300/[0.06] text-red-100"
              : notice.kind === "warning"
                ? "border-amber-300/20 bg-amber-300/[0.06] text-amber-100"
                : "border-sky-300/20 bg-sky-300/[0.06] text-sky-100"
          }`}
        >
          <div className="flex gap-3">
            <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
            <div className="min-w-0 flex-1">
              <p className="font-bold">{notice.title}</p>
              <p className="mt-1 leading-5 opacity-80">{notice.detail}</p>
              {notice.retryAfterSeconds && (
                <p className="mt-2 font-mono text-[10px]">Try again in about {notice.retryAfterSeconds} seconds.</p>
              )}
              {notice.requestId && (
                <p className="mt-2 break-all font-mono text-[10px] opacity-70">Request ID: {notice.requestId}</p>
              )}
              {notice.canReloadRun && run && (
                <button
                  type="button"
                  onClick={() => void reloadRun()}
                  disabled={busyAction === "refresh-run"}
                  className="mt-3 inline-flex min-h-10 items-center gap-2 rounded-lg border border-current/25 px-3 py-2 font-semibold disabled:opacity-40"
                >
                  <RefreshCw size={13} aria-hidden="true" />
                  {busyAction === "refresh-run" ? "Reloading current run…" : "Reload current run"}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="grid gap-0 xl:grid-cols-[minmax(300px,0.7fr)_minmax(0,1.3fr)]">
        <div className="border-b border-white/[0.07] p-4 sm:p-6 xl:border-b-0 xl:border-r">
          {sessionPhase === "restoring" ? (
            <div role="status" className="rounded-xl border border-white/[0.08] bg-white/[0.025] p-5 text-sm text-zinc-300">
              <div className="flex items-center gap-3">
                <LoaderCircle size={17} className="animate-spin text-[var(--primary-color)]" aria-hidden="true" />
                <div>
                  <p className="font-semibold">Restoring secure session…</p>
                  <p className="mt-1 text-xs leading-5 text-zinc-500">Checking the same-origin HttpOnly session. No browser credential is read.</p>
                </div>
              </div>
            </div>
          ) : !session ? (
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
                className="flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-[var(--primary-color)] px-4 py-3 text-xs font-extrabold text-black transition disabled:cursor-not-allowed disabled:opacity-40"
              >
                <ShieldCheck size={15} aria-hidden="true" />
                {busyAction === "session" ? "Opening session…" : "Open secure session"}
              </button>
            </form>
          ) : (
            <div className="space-y-5">
              <div className="rounded-xl border border-emerald-300/15 bg-emerald-300/[0.05] p-4">
                <p className="font-mono text-[9px] uppercase tracking-[0.12em] text-emerald-300">Authenticated tenant</p>
                <p className="mt-2 break-all text-sm font-bold text-zinc-100">{session.subject_id}</p>
                <p className="mt-1 text-[11px] text-zinc-400">
                  {session.tenant_id} · {session.role} · {session.key_id}
                </p>
                <p className="mt-1 text-[11px] text-zinc-500">
                  Session expires {new Date(session.expires_at).toLocaleString()}.
                </p>
              </div>
              {capabilities && (
                <div className="rounded-xl border border-white/[0.08] bg-white/[0.025] p-4">
                  <p className="text-xs font-bold text-zinc-200">{capabilities.label}</p>
                  <p className="mt-1 text-[11px] leading-5 text-zinc-500">
                    {canCreate ? "You can create governed campaign runs." : "Campaign creation is disabled for this role."}{" "}
                    {canDecide ? "You can decide and revoke Greenlight." : "Greenlight decisions require approver or admin authority."}
                  </p>
                </div>
              )}
              <button
                type="button"
                onClick={closeSession}
                disabled={busyAction === "logout"}
                className="flex min-h-11 w-full items-center justify-center gap-2 rounded-xl border border-white/[0.09] px-4 py-2.5 text-xs font-semibold text-zinc-300 transition hover:border-red-300/30 hover:text-red-200 disabled:opacity-40"
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
                    disabled={auditPhase === "loading"}
                    className="grid min-h-11 min-w-11 place-items-center rounded-lg border border-white/[0.08] p-2 text-zinc-400 hover:text-zinc-100 disabled:opacity-40"
                    aria-label="Refresh durable audit"
                  >
                    <RefreshCw size={13} className={auditPhase === "loading" ? "animate-spin" : ""} aria-hidden="true" />
                  </button>
                </div>
                <ol className="mt-3 max-h-56 space-y-2 overflow-y-auto" aria-label="Durable audit events" aria-live="polite">
                  {auditPhase === "loading" ? (
                    <li className="rounded-lg border border-white/[0.08] p-3 text-[11px] text-zinc-400">Loading audit evidence…</li>
                  ) : auditPhase === "error" ? (
                    <li className="rounded-lg border border-red-300/15 bg-red-300/[0.04] p-3 text-[11px] text-red-200">Audit evidence is temporarily unavailable.</li>
                  ) : auditEvents.length === 0 ? (
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
          {session && (
            <form onSubmit={loadRun} className="mb-5 flex flex-col gap-3 rounded-xl border border-white/[0.08] bg-white/[0.02] p-4 sm:flex-row sm:items-end">
              <label className="min-w-0 flex-1 text-xs font-semibold text-zinc-300">
                Existing run ID
                <input
                  value={runLookupId}
                  onChange={(event) => setRunLookupId(event.target.value)}
                  className="mt-2 w-full rounded-xl border border-white/[0.09] bg-black/30 px-3 py-2.5 font-mono text-xs text-zinc-100 outline-none focus:border-[var(--primary-color)]"
                  placeholder="run-…"
                  required
                />
              </label>
              <button
                type="submit"
                disabled={Boolean(busyAction) || runLookupId.trim().length === 0}
                className="flex min-h-11 items-center justify-center gap-2 rounded-xl border border-white/[0.1] px-4 py-2.5 text-xs font-bold text-zinc-200 transition hover:border-[var(--primary-color)]/40 disabled:opacity-40"
              >
                <RefreshCw size={14} aria-hidden="true" />
                {busyAction === "load-run" ? "Loading governed run…" : "Load governed run"}
              </button>
            </form>
          )}
          <form onSubmit={launchRun} className="grid gap-4 lg:grid-cols-2">
            <label className="text-xs font-semibold text-zinc-300">
              Campaign title
              <input
                value={brief.title}
                onChange={(event) => updateBrief({ title: event.target.value })}
                className="mt-2 w-full rounded-xl border border-white/[0.09] bg-black/30 px-3 py-2.5 text-sm text-zinc-100 outline-none focus:border-[var(--primary-color)]"
                disabled={!session || !canCreate}
                required
              />
            </label>
            <label className="text-xs font-semibold text-zinc-300">
              Target segment
              <input
                value={brief.audience}
                onChange={(event) => updateBrief({ audience: event.target.value })}
                className="mt-2 w-full rounded-xl border border-white/[0.09] bg-black/30 px-3 py-2.5 text-sm text-zinc-100 outline-none focus:border-[var(--primary-color)]"
                disabled={!session || !canCreate}
                required
              />
            </label>
            <label className="text-xs font-semibold text-zinc-300 lg:col-span-2">
              Objective
              <textarea
                value={brief.objective}
                onChange={(event) => updateBrief({ objective: event.target.value })}
                className="mt-2 min-h-24 w-full resize-y rounded-xl border border-white/[0.09] bg-black/30 px-3 py-2.5 text-sm leading-6 text-zinc-100 outline-none focus:border-[var(--primary-color)]"
                disabled={!session || !canCreate}
                required
              />
            </label>
            <fieldset className="lg:col-span-2" disabled={!session || !canCreate}>
              <legend className="text-xs font-semibold text-zinc-300">Platforms</legend>
              <div className="mt-2 flex flex-wrap gap-2">
                {PLATFORM_OPTIONS.map((platform) => (
                  <label key={platform.id} className="flex min-h-11 cursor-pointer items-center gap-2 rounded-lg border border-white/[0.08] px-3 py-2 text-xs text-zinc-400 has-[:checked]:border-[var(--primary-color)] has-[:checked]:text-zinc-100">
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
              disabled={!session || !canCreate || Boolean(busyAction) || brief.platforms.length === 0}
              className="flex min-h-11 items-center justify-center gap-2 rounded-xl border border-[var(--primary-color)]/40 bg-[var(--primary-color)]/10 px-4 py-3 text-xs font-extrabold text-[var(--primary-color)] transition hover:bg-[var(--primary-color)]/15 disabled:cursor-not-allowed disabled:opacity-35 lg:col-span-2"
            >
              <Play size={14} aria-hidden="true" />
              {busyAction === "run" ? "Running eight stations…" : "Run governed campaign"}
            </button>
          </form>

          <div className="mt-6" aria-live="polite">
            {!run ? (
              <div className="rounded-xl border border-dashed border-white/[0.08] p-6 text-center text-xs leading-6 text-zinc-600">
                {session && !canCreate
                  ? "This role can inspect governed evidence but cannot create a campaign run."
                  : "Open a tenant session to execute the persistent backend. The cinematic simulator above remains side-effect free and independent."}
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

                {run.status === "awaiting_greenlight" && canDecide && (
                  <div className="grid gap-3 sm:grid-cols-2">
                    <button
                      type="button"
                      onClick={() => void decide("approve")}
                      disabled={Boolean(busyAction)}
                      className="flex min-h-11 items-center justify-center gap-2 rounded-xl bg-emerald-300 px-4 py-3 text-xs font-extrabold text-emerald-950 disabled:opacity-40"
                    >
                      <CheckCircle2 size={15} aria-hidden="true" /> Approve exact artifacts
                    </button>
                    <button
                      type="button"
                      onClick={() => void decide("reject")}
                      disabled={Boolean(busyAction)}
                      className="flex min-h-11 items-center justify-center gap-2 rounded-xl border border-red-300/25 bg-red-300/[0.06] px-4 py-3 text-xs font-bold text-red-200 disabled:opacity-40"
                    >
                      <XCircle size={15} aria-hidden="true" /> Reject package
                    </button>
                  </div>
                )}

                {run.status === "awaiting_greenlight" && !canDecide && (
                  <div role="status" className="rounded-xl border border-sky-300/20 bg-sky-300/[0.05] p-4 text-xs text-sky-100">
                    Approval requires approver or admin authority. The run remains safely paused at Greenlight.
                  </div>
                )}

                {run.status === "completed" && run.greenlight?.revoked_at === null && canDecide && (
                  <div className="rounded-xl border border-amber-300/20 bg-amber-300/[0.05] p-4">
                    <p className="text-xs font-semibold text-amber-100">Greenlight active · fence {run.greenlight.fencing_token}</p>
                    <p className="mt-1 text-[11px] leading-5 text-amber-100/70">
                      Revocation preserves the decision history and invalidates every prior effect token.
                    </p>
                    <button
                      type="button"
                      onClick={() => void revokeGreenlight()}
                      disabled={Boolean(busyAction)}
                      className="mt-3 flex min-h-11 w-full items-center justify-center gap-2 rounded-xl border border-amber-300/30 px-4 py-3 text-xs font-bold text-amber-100 transition hover:bg-amber-300/[0.08] disabled:opacity-40"
                    >
                      <XCircle size={15} aria-hidden="true" />
                      {busyAction === "revoke" ? "Revoking Greenlight…" : "Revoke Greenlight"}
                    </button>
                  </div>
                )}

                {run.status === "revoked" && run.greenlight && (
                  <div className="rounded-xl border border-red-300/20 bg-red-300/[0.06] p-4 text-xs text-red-100">
                    Greenlight revoked. Fence {run.greenlight.fencing_token}; publication remains disabled.
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
