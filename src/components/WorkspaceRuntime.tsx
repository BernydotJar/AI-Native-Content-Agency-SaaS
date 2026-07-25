import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  CircleDot,
  KeyRound,
  LoaderCircle,
  LockKeyhole,
  LogOut,
  Play,
  RefreshCw,
  Search,
  ShieldCheck,
  X,
  XCircle,
} from "lucide-react";
import { RuntimeApiError, runtimeApi } from "../lib/runtimeApi";
import { useModalDialog } from "../lib/useModalDialog";
import type {
  BrowserRuntimeSession,
  RuntimeApi,
  RuntimeAuditEvent,
  RuntimeBrief,
  RuntimePlatform,
  RuntimeRun,
} from "../lib/runtimeApi";

interface WorkspaceRuntimeProps {
  api?: RuntimeApi;
  onSessionChange?: (session: BrowserRuntimeSession | null) => void;
  onRunChange?: (run: RuntimeRun | null) => void;
  onEntitlementsChange?: (entitlements: readonly string[]) => void;
}

type SessionPhase = "restoring" | "signed_out" | "authenticated";
type NoticeKind = "info" | "warning" | "error";

interface OperatorNotice {
  title: string;
  detail: string;
  kind: NoticeKind;
  requestId?: string;
  canReload?: boolean;
}

const PLATFORM_OPTIONS: Array<{ id: RuntimePlatform; label: string }> = [
  { id: "x", label: "X" },
  { id: "facebook", label: "Facebook" },
  { id: "tiktok", label: "TikTok" },
  { id: "instagram", label: "Instagram" },
];

const DEFAULT_BRIEF: RuntimeBrief = {
  title: "Campaña verificable",
  objective: "Explicar una propuesta con evidencia y aprobación humana",
  audience: "audiencia definida por el operador",
  platforms: ["x", "instagram"],
  budget_cents: 0,
  campaign_goal: "participacion_informada",
  campaign_type: "commercial",
  locale: "es-GT",
  jurisdiction: "",
  office: "",
  candidate_name: "",
  locality: "",
  problem: "",
  proposal: "",
  desired_action: "",
  disclosure: "",
  legal_review_status: "pending",
  legal_reviewed_by: "",
  evidence_claims: [],
};

const ROLE_CAPABILITIES: Record<
  BrowserRuntimeSession["role"],
  { canCreate: boolean; canDecide: boolean; label: string }
> = {
  viewer: { canCreate: false, canDecide: false, label: "Viewer" },
  operator: { canCreate: true, canDecide: false, label: "Operator" },
  approver: { canCreate: false, canDecide: true, label: "Approver" },
  admin: { canCreate: true, canDecide: true, label: "Administrator" },
};

const ignoreSession = () => undefined;
const ignoreRun = () => undefined;
const ignoreEntitlements = () => undefined;

function newCommandKey(scope: string): string {
  const bytes = new Uint8Array(16);
  globalThis.crypto.getRandomValues(bytes);
  return `${scope}:${Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("")}`;
}

function noticeFromError(error: unknown, canReload = false): OperatorNotice {
  if (!(error instanceof RuntimeApiError)) {
    return {
      title: "Runtime no disponible",
      detail: "La operación no pudo confirmarse. No se asumió ninguna acción adicional.",
      kind: "error",
      canReload,
    };
  }
  const requestId = error.requestId || undefined;
  switch (error.status) {
    case 401:
      return {
        title: "La sesión expiró",
        detail: "Vuelve a conectar el espacio de trabajo antes de continuar.",
        kind: "warning",
        requestId,
      };
    case 403:
      return {
        title: "Acción no permitida",
        detail: "Tu rol actual no permite esta operación.",
        kind: "warning",
        requestId,
      };
    case 404:
      return {
        title: "Ejecución no encontrada",
        detail: "La ejecución no está disponible o pertenece a otro tenant.",
        kind: "warning",
        requestId,
        canReload,
      };
    case 409:
      return {
        title: "El estado de la ejecución cambió",
        detail: "Recarga la ejecución antes de aplicar otra decisión.",
        kind: "warning",
        requestId,
        canReload: true,
      };
    case 422:
      return {
        title: "Revisa los datos de la misión",
        detail: "Uno o más campos de la misión están incompletos o son inválidos.",
        kind: "warning",
        requestId,
      };
    case 429:
      return {
        title: "Demasiados intentos",
        detail: "Espera antes de intentar conectarte nuevamente.",
        kind: "warning",
        requestId,
      };
    case 503:
      return {
        title: "Runtime temporalmente no disponible",
        detail: "El reintento conservará la misma identidad de comando.",
        kind: "error",
        requestId,
        canReload,
      };
    default:
      return {
        title: "La solicitud al runtime falló",
        detail: "El runtime no confirmó la operación.",
        kind: "error",
        requestId,
        canReload,
      };
  }
}

export function WorkspaceRuntime({
  api = runtimeApi,
  onSessionChange = ignoreSession,
  onRunChange = ignoreRun,
  onEntitlementsChange = ignoreEntitlements,
}: WorkspaceRuntimeProps) {
  const [sessionPhase, setSessionPhase] = useState<SessionPhase>("restoring");
  const [session, setSession] = useState<BrowserRuntimeSession | null>(null);
  const [connectionOpen, setConnectionOpen] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [brief, setBrief] = useState<RuntimeBrief>(DEFAULT_BRIEF);
  const [run, setRun] = useState<RuntimeRun | null>(null);
  const [runLookupId, setRunLookupId] = useState("");
  const [auditEvents, setAuditEvents] = useState<RuntimeAuditEvent[]>([]);
  const [busyAction, setBusyAction] = useState("");
  const [notice, setNotice] = useState<OperatorNotice | null>(null);
  const commandKeys = useRef(new Map<string, string>());
  const connectButtonRef = useRef<HTMLButtonElement>(null);
  const connectionDialogRef = useRef<HTMLElement>(null);
  const credentialInputRef = useRef<HTMLInputElement>(null);

  const capabilities = session ? ROLE_CAPABILITIES[session.role] : null;
  const canCreate = Boolean(capabilities?.canCreate);
  const canDecide = Boolean(capabilities?.canDecide);

  useEffect(() => onSessionChange(session), [onSessionChange, session]);
  useEffect(() => onRunChange(run), [onRunChange, run]);

  const closeConnection = () => {
    setConnectionOpen(false);
    setApiKey("");
  };

  useModalDialog({
    open: connectionOpen,
    onClose: closeConnection,
    dialogRef: connectionDialogRef,
    initialFocusRef: credentialInputRef,
    returnFocusRef: connectButtonRef,
  });

  const commandKey = (scope: string) => {
    const existing = commandKeys.current.get(scope);
    if (existing) return existing;
    const created = newCommandKey(scope);
    commandKeys.current.set(scope, created);
    return created;
  };

  const clearCommandKey = (scope: string) => commandKeys.current.delete(scope);

  const clearProtectedState = useCallback(() => {
    setSession(null);
    setRun(null);
    setRunLookupId("");
    setAuditEvents([]);
    setSessionPhase("signed_out");
    commandKeys.current.clear();
    onEntitlementsChange([]);
  }, [onEntitlementsChange]);

  const handleFailure = useCallback((caught: unknown, canReload = false) => {
    if (caught instanceof RuntimeApiError && caught.status === 401) {
      clearProtectedState();
    }
    setNotice(noticeFromError(caught, canReload));
  }, [clearProtectedState]);

  const refreshWorkspace = useCallback(async () => {
    const [events, identity] = await Promise.all([api.auditEvents(), api.currentIdentity()]);
    setAuditEvents(events);
    onEntitlementsChange(identity.entitlements);
  }, [api, onEntitlementsChange]);

  const activeRunId = run?.run_id ?? "";
  const activeRunStatus = run?.status ?? "";

  useEffect(() => {
    if (!session || !activeRunId || !["queued", "running"].includes(activeRunStatus)) return;
    let active = true;
    let polling = false;
    const refreshRun = async () => {
      if (polling) return;
      polling = true;
      try {
        const refreshed = await api.getRun(activeRunId);
        if (!active) return;
        setRun(refreshed);
        if (!["queued", "running"].includes(refreshed.status)) {
          await refreshWorkspace();
        }
      } catch (caught) {
        if (active) handleFailure(caught, true);
      } finally {
        polling = false;
      }
    };
    const timer = window.setInterval(() => void refreshRun(), 400);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [activeRunId, activeRunStatus, api, handleFailure, refreshWorkspace, session]);

  useEffect(() => {
    let active = true;
    void api.resumeSession()
      .then(async (resumed) => {
        if (!active) return;
        if (!resumed) {
          setSessionPhase("signed_out");
          onEntitlementsChange([]);
          return;
        }
        setSession(resumed);
        setSessionPhase("authenticated");
        onEntitlementsChange(resumed.entitlements);
        try {
          const [events, identity] = await Promise.all([api.auditEvents(), api.currentIdentity()]);
          if (!active) return;
          setAuditEvents(events);
          onEntitlementsChange(identity.entitlements);
        } catch (caught) {
          if (!active) return;
          handleFailure(caught);
        }
      })
      .catch((caught) => {
        if (!active) return;
        setSessionPhase("signed_out");
        if (!(caught instanceof RuntimeApiError) || caught.status !== 404) {
          setNotice(noticeFromError(caught));
        }
      });
    return () => {
      active = false;
    };
  }, [api, handleFailure, onEntitlementsChange]);

  const openSession = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const credential = apiKey.trim();
    if (credential.length < 24) return;
    setBusyAction("connect");
    setNotice(null);
    try {
      const opened = await api.createSession(credential);
      setSession(opened);
      setSessionPhase("authenticated");
      onEntitlementsChange(opened.entitlements);
      commandKeys.current.clear();
      await refreshWorkspace();
      setConnectionOpen(false);
    } catch (caught) {
      clearProtectedState();
      handleFailure(caught);
    } finally {
      setApiKey("");
      setBusyAction("");
    }
  };

  const closeSession = async () => {
    if (!session) return;
    setBusyAction("disconnect");
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

  const updateBrief = (patch: Partial<RuntimeBrief>) => {
    clearCommandKey("run:create");
    setBrief((current) => ({ ...current, ...patch }));
  };

  const updateEvidenceClaim = (
    field: "statement" | "source" | "locator" | "verification_status",
    value: string,
  ) => {
    const current = brief.evidence_claims?.[0] ?? {
      statement: "",
      source: "",
      locator: "",
      verification_status: "unverified" as const,
    };
    updateBrief({ evidence_claims: [{ ...current, [field]: value }] });
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

  const launchRun = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!session || !canCreate || brief.platforms.length === 0) return;
    setBusyAction("run");
    setNotice(null);
    try {
      const created = await api.createRun(brief, session.csrf_token, commandKey("run:create"));
      setRun(created);
      setRunLookupId(created.run_id);
      clearCommandKey("run:create");
      await refreshWorkspace();
    } catch (caught) {
      handleFailure(caught, Boolean(run));
    } finally {
      setBusyAction("");
    }
  };

  const loadRun = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!session || !runLookupId.trim()) return;
    setBusyAction("load");
    setNotice(null);
    try {
      const loaded = await api.getRun(runLookupId.trim());
      setRun(loaded);
      setRunLookupId(loaded.run_id);
    } catch (caught) {
      handleFailure(caught, Boolean(run));
    } finally {
      setBusyAction("");
    }
  };

  const reloadRun = async () => {
    if (!run) return;
    setBusyAction("reload");
    try {
      const loaded = await api.getRun(run.run_id);
      setRun(loaded);
      await refreshWorkspace();
      setNotice(null);
    } catch (caught) {
      handleFailure(caught, true);
    } finally {
      setBusyAction("");
    }
  };

  const decide = async (decision: "approve" | "reject") => {
    if (!session || !run || !canDecide) return;
    const scope = `greenlight:${decision}:${run.run_id}`;
    setBusyAction(decision);
    setNotice(null);
    try {
      const decided = decision === "approve"
        ? await api.approveRun(run.run_id, session.csrf_token, commandKey(scope))
        : await api.rejectRun(run.run_id, session.csrf_token, commandKey(scope));
      setRun(decided);
      clearCommandKey(scope);
      await refreshWorkspace();
    } catch (caught) {
      handleFailure(caught, true);
    } finally {
      setBusyAction("");
    }
  };

  const revoke = async () => {
    if (!session || !run || !canDecide) return;
    const scope = `greenlight:revoke:${run.run_id}`;
    setBusyAction("revoke");
    setNotice(null);
    try {
      const revoked = await api.revokeRun(run.run_id, session.csrf_token, commandKey(scope));
      setRun(revoked);
      clearCommandKey(scope);
      await refreshWorkspace();
    } catch (caught) {
      handleFailure(caught, true);
    } finally {
      setBusyAction("");
    }
  };

  return (
    <section aria-labelledby="mission-workspace-title" className="surface-panel overflow-hidden">
      <header className="flex flex-col gap-4 border-b border-white/[0.07] px-5 py-5 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="section-kicker">01 / COMANDO</p>
          <h2 id="mission-workspace-title" className="mt-1 text-xl font-bold text-zinc-100">
            Lanza una campaña gobernada
          </h2>
          <p className="mt-1 max-w-2xl text-xs leading-5 text-zinc-500">
            Define el resultado, ejecuta las ocho estaciones y revisa los artefactos versionados antes de Greenlight.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {sessionPhase === "restoring" ? (
            <span role="status" className="inline-flex min-h-10 items-center gap-2 rounded-full border border-white/[0.08] px-3 text-xs text-zinc-400">
              <LoaderCircle size={13} className="animate-spin" aria-hidden="true" /> Restaurando sesión
            </span>
          ) : session ? (
            <>
              <span className="inline-flex min-h-10 items-center gap-2 rounded-full border border-emerald-300/20 bg-emerald-300/[0.06] px-3 text-xs text-emerald-200">
                <CircleDot size={12} aria-hidden="true" /> {session.subject_id} · {capabilities?.label}
              </span>
              <button
                type="button"
                onClick={() => void closeSession()}
                disabled={busyAction === "disconnect"}
                className="inline-flex min-h-10 items-center gap-2 rounded-full border border-white/[0.09] px-3 text-xs text-zinc-300 hover:border-red-300/30 hover:text-red-200 disabled:opacity-40"
              >
                <LogOut size={13} aria-hidden="true" /> Desconectar
              </button>
            </>
          ) : (
            <button
              ref={connectButtonRef}
              type="button"
              onClick={() => setConnectionOpen(true)}
              className="inline-flex min-h-10 items-center gap-2 rounded-full bg-[var(--primary-color)] px-4 text-xs font-extrabold text-black"
            >
              <KeyRound size={13} aria-hidden="true" /> Conectar espacio
            </button>
          )}
        </div>
      </header>

      {notice && (
        <div
          role={notice.kind === "error" ? "alert" : "status"}
          className={`mx-5 mt-5 rounded-xl border p-4 text-xs ${
            notice.kind === "error"
              ? "border-red-300/20 bg-red-300/[0.05] text-red-100"
              : notice.kind === "warning"
                ? "border-amber-300/20 bg-amber-300/[0.05] text-amber-100"
                : "border-sky-300/20 bg-sky-300/[0.05] text-sky-100"
          }`}
        >
          <div className="flex items-start gap-3">
            <AlertTriangle size={15} className="mt-0.5 shrink-0" aria-hidden="true" />
            <div className="min-w-0 flex-1">
              <p className="font-bold">{notice.title}</p>
              <p className="mt-1 leading-5 opacity-80">{notice.detail}</p>
              {notice.requestId && <p className="mt-2 break-all font-mono text-[10px] opacity-60">Solicitud {notice.requestId}</p>}
              {notice.canReload && run && (
                <button type="button" onClick={() => void reloadRun()} className="mt-3 inline-flex min-h-9 items-center gap-2 rounded-lg border border-current/25 px-3 font-semibold">
                  <RefreshCw size={12} aria-hidden="true" /> Recargar ejecución
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="grid gap-0 xl:grid-cols-[minmax(360px,0.78fr)_minmax(0,1.22fr)]">
        <form onSubmit={launchRun} className="border-b border-white/[0.07] p-5 xl:border-b-0 xl:border-r">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-1">
            <label className="text-xs font-semibold text-zinc-300">
              Tipo de campaña
              <select
                value={brief.campaign_type ?? "commercial"}
                onChange={(event) => updateBrief({ campaign_type: event.target.value as "commercial" | "political" })}
                disabled={!session || !canCreate}
                className="form-control mt-2"
              >
                <option value="commercial">Marca / comercial</option>
                <option value="political">Política / electoral</option>
              </select>
            </label>
            <label className="text-xs font-semibold text-zinc-300">
              Idioma y región
              <input
                value={brief.locale ?? "es-GT"}
                onChange={(event) => updateBrief({ locale: event.target.value })}
                disabled={!session || !canCreate}
                className="form-control mt-2"
                required
              />
            </label>
            <label className="text-xs font-semibold text-zinc-300">
              Título de campaña
              <input
                value={brief.title}
                onChange={(event) => updateBrief({ title: event.target.value })}
                disabled={!session || !canCreate}
                className="form-control mt-2"
                required
              />
            </label>
            <label className="text-xs font-semibold text-zinc-300">
              Segmento objetivo
              <input
                value={brief.audience}
                onChange={(event) => updateBrief({ audience: event.target.value })}
                disabled={!session || !canCreate}
                className="form-control mt-2"
                required
              />
            </label>
          </div>
          <label className="mt-4 block text-xs font-semibold text-zinc-300">
            Resultado esperado
            <textarea
              value={brief.objective}
              onChange={(event) => updateBrief({ objective: event.target.value })}
              disabled={!session || !canCreate}
              className="form-control mt-2 min-h-28 resize-y py-3"
              required
            />
          </label>
          {(brief.campaign_type ?? "commercial") === "political" && (
            <fieldset className="mt-4 grid gap-4 rounded-2xl border border-amber-300/15 bg-amber-300/[0.03] p-4 sm:grid-cols-2">
              <legend className="px-2 text-xs font-bold text-amber-100">Contexto político verificable</legend>
              {([
                ["jurisdiction", "Jurisdicción"],
                ["office", "Cargo"],
                ["candidate_name", "Candidato o candidatura"],
                ["locality", "Territorio"],
                ["problem", "Problema público"],
                ["proposal", "Propuesta concreta"],
                ["desired_action", "Acción ciudadana"],
                ["disclosure", "Disclosure"],
              ] as const).map(([field, label]) => (
                <label key={field} className="text-xs font-semibold text-zinc-300">
                  {label}
                  <textarea
                    value={String(brief[field] ?? "")}
                    onChange={(event) => updateBrief({ [field]: event.target.value })}
                    disabled={!session || !canCreate}
                    className="form-control mt-2 min-h-20 resize-y"
                    required
                  />
                </label>
              ))}
              <label className="text-xs font-semibold text-zinc-300 sm:col-span-2">
                Afirmación respaldada
                <textarea
                  value={brief.evidence_claims?.[0]?.statement ?? ""}
                  onChange={(event) => updateEvidenceClaim("statement", event.target.value)}
                  disabled={!session || !canCreate}
                  className="form-control mt-2 min-h-20 resize-y"
                  required
                />
              </label>
              <label className="text-xs font-semibold text-zinc-300">
                Fuente
                <input
                  value={brief.evidence_claims?.[0]?.source ?? ""}
                  onChange={(event) => updateEvidenceClaim("source", event.target.value)}
                  disabled={!session || !canCreate}
                  className="form-control mt-2"
                  required
                />
              </label>
              <label className="text-xs font-semibold text-zinc-300">
                Página, sección o locator
                <input
                  value={brief.evidence_claims?.[0]?.locator ?? ""}
                  onChange={(event) => updateEvidenceClaim("locator", event.target.value)}
                  disabled={!session || !canCreate}
                  className="form-control mt-2"
                  required
                />
              </label>
              <label className="text-xs font-semibold text-zinc-300">
                Revisión legal
                <select
                  value={brief.legal_review_status ?? "pending"}
                  onChange={(event) => updateBrief({ legal_review_status: event.target.value as "pending" | "approved" })}
                  disabled={!session || !canCreate}
                  className="form-control mt-2"
                >
                  <option value="pending">Pendiente</option>
                  <option value="approved" disabled={!canDecide}>Aprobada con autoridad</option>
                </select>
              </label>
              <div className="rounded-xl border border-white/[0.08] p-3 text-[11px] leading-5 text-zinc-400">
                {canDecide
                  ? "Si apruebas la revisión legal, el servidor registra tu identidad autenticada."
                  : "Tu rol no puede aprobar la revisión legal."}
              </div>
              <label className="text-xs font-semibold text-zinc-300">
                Estado de verificación
                <select
                  value={brief.evidence_claims?.[0]?.verification_status ?? "unverified"}
                  onChange={(event) => updateEvidenceClaim("verification_status", event.target.value)}
                  disabled={!session || !canCreate}
                  className="form-control mt-2"
                >
                  <option value="unverified">Pendiente de verificación</option>
                  <option value="verified" disabled={!canDecide}>Verificada con autoridad de aprobación</option>
                </select>
              </label>
              <div className="rounded-xl border border-white/[0.08] p-3 text-[11px] leading-5 text-zinc-400">
                {canDecide
                  ? "Al marcarla verificada, el servidor registra tu identidad autenticada como revisor."
                  : "Tu rol puede preparar la afirmación, pero no marcarla como verificada."}
              </div>
              <p className="text-[11px] leading-5 text-amber-100/70 sm:col-span-2">
                Adjuntar una fuente no la convierte en evidencia verificada. El sistema no infiere cumplimiento legal.
              </p>
            </fieldset>
          )}
          <fieldset className="mt-4" disabled={!session || !canCreate}>
            <legend className="text-xs font-semibold text-zinc-300">Canales de entrega</legend>
            <div className="mt-2 flex flex-wrap gap-2">
              {PLATFORM_OPTIONS.map((platform) => (
                <label key={platform.id} className="flex min-h-10 cursor-pointer items-center gap-2 rounded-lg border border-white/[0.08] px-3 text-xs text-zinc-400 has-[:checked]:border-[var(--primary-color)] has-[:checked]:text-zinc-100">
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
            className="mt-5 flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-[var(--primary-color)] px-4 text-sm font-extrabold text-black disabled:cursor-not-allowed disabled:opacity-35"
          >
            <Play size={15} aria-hidden="true" />
            {busyAction === "run" ? "Encolando campaña gobernada…" : "Ejecutar campaña"}
          </button>
          {!session && sessionPhase !== "restoring" && (
            <p className="mt-3 text-center text-[11px] leading-5 text-zinc-500">
              Conéctate una sola vez para crear una sesión HttpOnly segura. Después, el campo de credencial desaparece del espacio de trabajo.
            </p>
          )}
          {session && !canCreate && (
            <p role="status" className="mt-3 rounded-lg border border-sky-300/15 bg-sky-300/[0.04] p-3 text-[11px] leading-5 text-sky-100">
              Este rol puede inspeccionar ejecuciones, pero no puede crear una.
            </p>
          )}
        </form>

        <div className="p-5">
          <form onSubmit={loadRun} className="flex flex-col gap-2 sm:flex-row">
            <label className="min-w-0 flex-1 text-xs font-semibold text-zinc-300">
              Abrir una ejecución existente
              <input
                value={runLookupId}
                onChange={(event) => setRunLookupId(event.target.value)}
                disabled={!session}
                placeholder="run-…"
                className="form-control mt-2 font-mono text-xs"
              />
            </label>
            <button
              type="submit"
              disabled={!session || !runLookupId.trim() || Boolean(busyAction)}
              className="mt-auto inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-white/[0.1] px-4 text-xs font-bold text-zinc-200 disabled:opacity-35"
            >
              <Search size={14} aria-hidden="true" /> {busyAction === "load" ? "Abriendo…" : "Abrir ejecución"}
            </button>
          </form>

          <div className="mt-5" aria-live="polite">
            {!run ? (
              <div className="grid min-h-72 place-items-center rounded-xl border border-dashed border-white/[0.08] p-8 text-center">
                <div>
                  <LockKeyhole size={22} className="mx-auto text-zinc-600" aria-hidden="true" />
                  <p className="mt-3 text-sm font-semibold text-zinc-300">No hay una ejecución activa</p>
                  <p className="mx-auto mt-1 max-w-sm text-xs leading-5 text-zinc-600">
                    Crea una misión o abre una ejecución del tenant para inspeccionar entregables y el estado de Greenlight.
                  </p>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex flex-col gap-3 rounded-xl border border-white/[0.08] bg-black/20 p-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="font-mono text-[10px] text-zinc-500">{run.run_id}</p>
                    <p className="mt-1 text-base font-bold capitalize text-zinc-100">{run.status.replaceAll("_", " ")}</p>
                    {["queued", "running"].includes(run.status) && (
                      <p className="mt-1 font-mono text-[10px] text-sky-200/80">
                        checkpoint {run.execution.fencing_token} · próxima estación {run.execution.next_station}
                      </p>
                    )}
                  </div>
                  <span className="rounded-full border border-white/[0.08] px-3 py-1.5 font-mono text-[9px] uppercase text-zinc-400">
                    {run.artifacts.length} artefactos
                  </span>
                </div>

                <a href="#campaign-output" className="inline-flex min-h-10 items-center justify-center rounded-xl border border-[var(--primary-color)]/30 px-4 text-xs font-bold text-[var(--primary-color)]">
                  Ver posts y estado de publicación
                </a>

                {run.status === "awaiting_greenlight" && canDecide && (
                  <div className="grid gap-2 sm:grid-cols-2">
                    <button type="button" onClick={() => void decide("approve")} disabled={Boolean(busyAction)} className="flex min-h-11 items-center justify-center gap-2 rounded-xl bg-emerald-300 px-4 text-xs font-extrabold text-emerald-950 disabled:opacity-40">
                      <CheckCircle2 size={14} aria-hidden="true" /> Approve artefactos
                    </button>
                    <button type="button" onClick={() => void decide("reject")} disabled={Boolean(busyAction)} className="flex min-h-11 items-center justify-center gap-2 rounded-xl border border-red-300/25 px-4 text-xs font-bold text-red-200 disabled:opacity-40">
                      <XCircle size={14} aria-hidden="true" /> Rechazar ejecución
                    </button>
                  </div>
                )}
                {run.status === "awaiting_greenlight" && !canDecide && (
                  <div role="status" className="rounded-xl border border-sky-300/15 bg-sky-300/[0.04] p-4 text-xs leading-5 text-sky-100">
                    La ejecución está pausada para un aprobador o administrador.
                  </div>
                )}
                {run.status === "completed" && run.greenlight?.revoked_at === null && canDecide && (
                  <button type="button" onClick={() => void revoke()} disabled={Boolean(busyAction)} className="flex min-h-11 w-full items-center justify-center gap-2 rounded-xl border border-amber-300/25 px-4 text-xs font-bold text-amber-100 disabled:opacity-40">
                    <XCircle size={14} aria-hidden="true" /> Revocar Greenlight
                  </button>
                )}
              </div>
            )}
          </div>

          {session && (
            <details className="mt-5 rounded-xl border border-white/[0.07] bg-white/[0.02] p-3">
              <summary className="flex cursor-pointer list-none items-center justify-between text-xs font-semibold text-zinc-300">
                Detalles de sesión y auditoría
                <ChevronDown size={14} aria-hidden="true" />
              </summary>
              <div className="mt-3 border-t border-white/[0.06] pt-3 text-[11px] leading-5 text-zinc-500">
                <p>{session.tenant_id} · {session.role} · expires {new Date(session.expires_at).toLocaleString()}</p>
                <p className="mt-1">{auditEvents.length} eventos de auditoría durables cargados.</p>
              </div>
            </details>
          )}
        </div>
      </div>

      {connectionOpen && !session && (
        <div className="fixed inset-0 z-[100] grid place-items-center bg-black/70 p-4 backdrop-blur-sm" role="presentation">
          <section ref={connectionDialogRef} role="dialog" aria-modal="true" aria-labelledby="connect-workspace-title" className="w-full max-w-md rounded-2xl border border-white/[0.12] bg-zinc-950 p-5 shadow-2xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="section-kicker">Conexión segura</p>
                <h2 id="connect-workspace-title" className="mt-1 text-lg font-bold text-zinc-100">Conectar este navegador</h2>
              </div>
              <button type="button" onClick={closeConnection} className="grid min-h-10 min-w-10 place-items-center rounded-lg border border-white/[0.08] text-zinc-400" aria-label="Cerrar diálogo de conexión">
                <X size={15} aria-hidden="true" />
              </button>
            </div>
            <p className="mt-3 text-xs leading-6 text-zinc-500">
              Ingresa la credencial del tenant una sola vez. El servidor la intercambia por una sesión HttpOnly del mismo origen y el campo desaparece del espacio de trabajo.
            </p>
            <form onSubmit={openSession} className="mt-5">
              <label className="text-xs font-semibold text-zinc-300">
                Credencial del tenant
                <input
                  ref={credentialInputRef}
                  type="password"
                  autoComplete="current-password"
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  minLength={24}
                  required
                  className="form-control mt-2 font-mono text-xs"
                />
              </label>
              <button type="submit" disabled={busyAction === "connect" || apiKey.trim().length < 24} className="mt-4 flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-[var(--primary-color)] px-4 text-xs font-extrabold text-black disabled:opacity-40">
                <ShieldCheck size={14} aria-hidden="true" /> {busyAction === "connect" ? "Conectando…" : "Crear sesión segura"}
              </button>
            </form>
          </section>
        </div>
      )}
    </section>
  );
}
