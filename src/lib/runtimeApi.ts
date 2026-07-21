export type RuntimePlatform = "x" | "facebook" | "tiktok" | "instagram";

export interface BrowserRuntimeSession {
  tenant_id: string;
  subject_id: string;
  role: "viewer" | "operator" | "approver" | "admin";
  key_id: string;
  csrf_token: string;
  expires_at: string;
}

export interface RuntimeBrief {
  title: string;
  objective: string;
  audience: string;
  platforms: RuntimePlatform[];
  budget_cents: number;
  campaign_goal: string;
}

export interface RuntimeArtifact {
  artifact_id: string;
  kind: string;
  title: string;
  payload: Record<string, unknown>;
  evidence_ids: string[];
}

export interface RuntimeAgentState {
  status: string;
  progress: number;
  detail: string;
  artifact_ids: string[];
}

export interface RuntimeGreenlight {
  greenlight_id: string;
  decision: "approved" | "rejected";
  reviewer: string;
  note: string;
  approved_artifact_ids: string[];
  approved_artifact_hashes: string[];
  authorized_channels: RuntimePlatform[];
  authorized_budget_cents: number;
}

export interface RuntimeRun {
  run_id: string;
  tenant_id: string;
  status: "running" | "awaiting_greenlight" | "completed" | "rejected" | "failed";
  agent_states: Record<string, RuntimeAgentState>;
  artifacts: RuntimeArtifact[];
  greenlight: RuntimeGreenlight | null;
  sandbox: boolean;
  external_side_effects_enabled: boolean;
}

export interface RuntimeAuditEvent {
  sequence: number;
  event_id: string;
  request_id: string;
  action: string;
  resource_type: string;
  resource_id: string;
  occurred_at: string;
  actor: string;
  payload: Record<string, unknown>;
}

interface AuditPage {
  events: RuntimeAuditEvent[];
  next_after_sequence: number;
  has_more: boolean;
}

export class RuntimeApiError extends Error {
  readonly status: number;
  readonly requestId: string;

  constructor(status: number, message: string, requestId = "") {
    super(message);
    this.name = "RuntimeApiError";
    this.status = status;
    this.requestId = requestId;
  }
}

export interface RuntimeApi {
  createSession(apiKey: string): Promise<BrowserRuntimeSession>;
  resumeSession(): Promise<BrowserRuntimeSession | null>;
  createRun(brief: RuntimeBrief, csrfToken: string): Promise<RuntimeRun>;
  approveRun(runId: string, csrfToken: string): Promise<RuntimeRun>;
  rejectRun(runId: string, csrfToken: string): Promise<RuntimeRun>;
  auditEvents(): Promise<RuntimeAuditEvent[]>;
  revokeSession(csrfToken: string): Promise<void>;
}

type FetchLike = typeof fetch;

async function requestJson<T>(
  fetchImpl: FetchLike,
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetchImpl(path, {
    ...init,
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
  });
  const requestId = response.headers.get("X-Request-ID") ?? "";
  const payload = await response.json().catch(() => ({})) as Record<string, unknown>;
  if (!response.ok) {
    const detail = typeof payload.detail === "string"
      ? payload.detail
      : `Runtime request failed with status ${response.status}`;
    throw new RuntimeApiError(response.status, detail, requestId);
  }
  return payload as T;
}

export function createRuntimeApi(fetchImpl: FetchLike = fetch): RuntimeApi {
  return {
    createSession(apiKey) {
      return requestJson<BrowserRuntimeSession>(fetchImpl, "/api/v1/sessions", {
        method: "POST",
        body: JSON.stringify({ api_key: apiKey }),
      });
    },
    async resumeSession() {
      try {
        return await requestJson<BrowserRuntimeSession>(fetchImpl, "/api/v1/sessions/current");
      } catch (error) {
        if (error instanceof RuntimeApiError && error.status === 401) return null;
        throw error;
      }
    },
    createRun(brief, csrfToken) {
      return requestJson<RuntimeRun>(fetchImpl, "/api/v1/runs", {
        method: "POST",
        headers: { "X-CSRF-Token": csrfToken },
        body: JSON.stringify(brief),
      });
    },
    approveRun(runId, csrfToken) {
      return requestJson<RuntimeRun>(
        fetchImpl,
        `/api/v1/runs/${encodeURIComponent(runId)}/greenlight/approve`,
        {
          method: "POST",
          headers: { "X-CSRF-Token": csrfToken },
          body: JSON.stringify({
            reviewer: "war-room-operator",
            note: "Approved from the production runtime console.",
          }),
        },
      );
    },
    rejectRun(runId, csrfToken) {
      return requestJson<RuntimeRun>(
        fetchImpl,
        `/api/v1/runs/${encodeURIComponent(runId)}/greenlight/reject`,
        {
          method: "POST",
          headers: { "X-CSRF-Token": csrfToken },
          body: JSON.stringify({
            reviewer: "war-room-operator",
            note: "Rejected from the production runtime console.",
          }),
        },
      );
    },
    async auditEvents() {
      const page = await requestJson<AuditPage>(fetchImpl, "/api/v1/audit-events?limit=100");
      return page.events;
    },
    async revokeSession(csrfToken) {
      await requestJson<{ status: string }>(fetchImpl, "/api/v1/sessions/current", {
        method: "DELETE",
        headers: { "X-CSRF-Token": csrfToken },
      });
    },
  };
}

export const runtimeApi = createRuntimeApi();
