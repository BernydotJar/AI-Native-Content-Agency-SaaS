export type RuntimePlatform = "x" | "facebook" | "tiktok" | "instagram";

export interface BrowserRuntimeSession {
  tenant_id: string;
  subject_id: string;
  role: "viewer" | "operator" | "approver" | "admin";
  key_id: string;
  entitlements: string[];
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
  fencing_token: number;
  revoked_at: string | null;
  revoked_by: string;
  revocation_reason: string;
}

export interface RuntimeRun {
  run_id: string;
  tenant_id: string;
  status: "running" | "awaiting_greenlight" | "completed" | "rejected" | "revoked" | "failed";
  agent_states: Record<string, RuntimeAgentState>;
  artifacts: RuntimeArtifact[];
  greenlight: RuntimeGreenlight | null;
  sandbox: boolean;
  external_side_effects_enabled: boolean;
}


export interface RuntimeIdentity {
  tenant_id: string;
  subject_id: string;
  role: "viewer" | "operator" | "approver" | "admin";
  key_id: string;
  permissions: string[];
  entitlements: string[];
  auth_method: "bearer" | "session";
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
  readonly code: string;
  readonly requestId: string;
  readonly retryAfterSeconds: number;

  constructor(
    status: number,
    message: string,
    requestId = "",
    code = "request_failed",
    retryAfterSeconds = 0,
  ) {
    super(message);
    this.name = "RuntimeApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

export interface RuntimeApi {
  createSession(apiKey: string): Promise<BrowserRuntimeSession>;
  resumeSession(): Promise<BrowserRuntimeSession | null>;
  currentIdentity(): Promise<RuntimeIdentity>;
  createRun(brief: RuntimeBrief, csrfToken: string, idempotencyKey: string): Promise<RuntimeRun>;
  getRun(runId: string): Promise<RuntimeRun>;
  approveRun(runId: string, csrfToken: string, idempotencyKey: string): Promise<RuntimeRun>;
  rejectRun(runId: string, csrfToken: string, idempotencyKey: string): Promise<RuntimeRun>;
  revokeRun(runId: string, csrfToken: string, idempotencyKey: string): Promise<RuntimeRun>;
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
  const payload = await response.json().catch(() => ({})) as Record<string, unknown>;
  if (!response.ok) {
    const detail = typeof payload.detail === "string"
      ? payload.detail
      : `Runtime request failed with status ${response.status}`;
    const code = typeof payload.code === "string" ? payload.code : "request_failed";
    const requestId = response.headers.get("X-Request-ID")
      ?? (typeof payload.request_id === "string" ? payload.request_id : "");
    const retryAfterHeader = response.headers.get("Retry-After");
    const retryAfterSeconds = retryAfterHeader && /^\d+$/.test(retryAfterHeader)
      ? Number.parseInt(retryAfterHeader, 10)
      : 0;
    throw new RuntimeApiError(
      response.status,
      detail,
      requestId,
      code,
      retryAfterSeconds > 0 ? retryAfterSeconds : 0,
    );
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
    currentIdentity() {
      return requestJson<RuntimeIdentity>(fetchImpl, "/api/v1/me");
    },
    createRun(brief, csrfToken, idempotencyKey) {
      return requestJson<RuntimeRun>(fetchImpl, "/api/v1/runs", {
        method: "POST",
        headers: {
          "X-CSRF-Token": csrfToken,
          "Idempotency-Key": idempotencyKey,
        },
        body: JSON.stringify(brief),
      });
    },
    getRun(runId) {
      return requestJson<RuntimeRun>(
        fetchImpl,
        `/api/v1/runs/${encodeURIComponent(runId)}`,
      );
    },
    approveRun(runId, csrfToken, idempotencyKey) {
      return requestJson<RuntimeRun>(
        fetchImpl,
        `/api/v1/runs/${encodeURIComponent(runId)}/greenlight/approve`,
        {
          method: "POST",
          headers: {
            "X-CSRF-Token": csrfToken,
            "Idempotency-Key": idempotencyKey,
          },
          body: JSON.stringify({
            reviewer: "war-room-operator",
            note: "Approved from the production runtime console.",
          }),
        },
      );
    },
    rejectRun(runId, csrfToken, idempotencyKey) {
      return requestJson<RuntimeRun>(
        fetchImpl,
        `/api/v1/runs/${encodeURIComponent(runId)}/greenlight/reject`,
        {
          method: "POST",
          headers: {
            "X-CSRF-Token": csrfToken,
            "Idempotency-Key": idempotencyKey,
          },
          body: JSON.stringify({
            reviewer: "war-room-operator",
            note: "Rejected from the production runtime console.",
          }),
        },
      );
    },
    revokeRun(runId, csrfToken, idempotencyKey) {
      return requestJson<RuntimeRun>(
        fetchImpl,
        `/api/v1/runs/${encodeURIComponent(runId)}/greenlight/revoke`,
        {
          method: "POST",
          headers: {
            "X-CSRF-Token": csrfToken,
            "Idempotency-Key": idempotencyKey,
          },
          body: JSON.stringify({
            reviewer: "authenticated-subject",
            reason: "Revoked from the production runtime console.",
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
