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

export interface RuntimeEvidenceClaim {
  statement: string;
  source: string;
  locator: string;
  verification_status?: "unverified" | "verified";
  reviewed_by?: string;
}

export interface RuntimeBrief {
  title: string;
  objective: string;
  audience: string;
  platforms: RuntimePlatform[];
  budget_cents: number;
  campaign_goal: string;
  campaign_type?: "commercial" | "political";
  locale?: string;
  jurisdiction?: string;
  office?: string;
  candidate_name?: string;
  locality?: string;
  problem?: string;
  proposal?: string;
  desired_action?: string;
  disclosure?: string;
  legal_review_status?: "pending" | "approved";
  legal_reviewed_by?: string;
  evidence_claims?: RuntimeEvidenceClaim[];
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

export interface RuntimeRunExecution {
  state: "inline" | "queued" | "leased" | "running" | "awaiting_greenlight" | "completed" | "failed";
  next_station: string;
  lease_owner: string;
  lease_expires_at: string | null;
  fencing_token: number;
  attempts: number;
  checkpointed_at: string | null;
  failure_detail: string;
}

export interface RuntimeRun {
  run_id: string;
  tenant_id: string;
  status: "queued" | "running" | "awaiting_greenlight" | "completed" | "rejected" | "revoked" | "failed";
  agent_states: Record<string, RuntimeAgentState>;
  artifacts: RuntimeArtifact[];
  greenlight: RuntimeGreenlight | null;
  sandbox: boolean;
  external_side_effects_enabled: boolean;
  execution: RuntimeRunExecution;
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

export type ProviderConfigurationState =
  | "ready"
  | "missing_credential"
  | "missing_model"
  | "missing_endpoint";

export interface RuntimeProvider {
  provider_id: "openai" | "anthropic" | "deepseek" | "moonshot" | "llama";
  display_name: string;
  protocol: "openai_responses" | "anthropic_messages" | "openai_compatible";
  configured: boolean;
  configuration_state: ProviderConfigurationState;
  model: string;
  endpoint_host: string;
  model_environment: string;
  base_url_environment: string;
  credential_location: "server_environment";
  recommended_models: string[];
}

export interface RuntimeProviderGatewayStatus {
  execution_enabled: boolean;
  selected_provider: string;
  execution_available: boolean;
  durable_outbound_receipt: boolean;
  automatic_run_integration: boolean;
}

export interface RuntimeProviderCatalog {
  tenant_id: string;
  providers: RuntimeProvider[];
  gateway: RuntimeProviderGatewayStatus;
}

export interface RuntimeIntegrationSummary {
  integration_id: string;
  display_name: string;
  review_status: string;
  activation_allowed: boolean;
  execution_available: boolean;
  external_effects_enabled: boolean;
  [key: string]: unknown;
}

export type SocialChannelConfigurationState =
  | "missing_credentials"
  | "missing_redirect_uri"
  | "ready_for_authentication";

export interface RuntimeSocialConnectedAccount {
  account_id: string;
  account_username: string;
  scopes: string[];
  token_expires_at: string | null;
  connected_at: string;
  token_storage: "encrypted_server_side";
}

export interface RuntimeSocialOAuthStart {
  channel_id: "x" | "instagram";
  authorization_url: string;
  expires_at: string;
}

export interface RuntimeSocialChannel {
  channel_id: "x" | "instagram";
  display_name: string;
  oauth_flow: string;
  configured: boolean;
  configuration_state: SocialChannelConfigurationState;
  credentials_configured: boolean;
  callback_configured: boolean;
  callback_url: string;
  connection_state: "not_connected" | "connected";
  oauth_start_available: boolean;
  oauth_runtime_configured: boolean;
  publication_runtime_configured: boolean;
  publication_execution_enabled: boolean;
  publishing_available: boolean;
  external_effects_enabled: boolean;
  credential_location: "server_environment";
  credential_environments: string[];
  redirect_environment: string;
  scopes: string[];
  account_requirement: string;
  publish_protocol: string;
  supported_content: string[];
  requires_media: boolean;
  connected_account: RuntimeSocialConnectedAccount | null;
}

export interface RuntimeSocialPublication {
  intent_id: string;
  channel_id: "x" | "instagram";
  account_id: string;
  run_id: string;
  artifact_id: string;
  artifact_hash: string;
  greenlight_id: string;
  greenlight_fencing_token: number;
  status: "pending" | "succeeded" | "unknown" | "failed" | "revoked";
  execution_fencing_token: number;
  provider_container_id: string | null;
  provider_post_id: string | null;
  receipt: Record<string, unknown>;
  replayed: boolean;
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
  providerCatalog(): Promise<RuntimeProviderCatalog>;
  integrations(): Promise<RuntimeIntegrationSummary[]>;
  socialChannels(): Promise<RuntimeSocialChannel[]>;
  socialPublications(runId: string): Promise<RuntimeSocialPublication[]>;
  startSocialOAuth(
    channelId: RuntimeSocialChannel["channel_id"],
    csrfToken: string,
  ): Promise<RuntimeSocialOAuthStart>;
  disconnectSocialChannel(
    channelId: RuntimeSocialChannel["channel_id"],
    csrfToken: string,
  ): Promise<void>;
  attachPublicationMedia(
    runId: string,
    channelId: RuntimeSocialChannel["channel_id"],
    file: File,
    altText: string,
    rightsConfirmed: boolean,
    csrfToken: string,
    idempotencyKey: string,
  ): Promise<RuntimeRun>;
  revokePublicationMedia(
    runId: string,
    mediaId: string,
    reason: string,
    csrfToken: string,
    idempotencyKey: string,
  ): Promise<RuntimeRun>;
  publishSocial(
    runId: string,
    channelId: RuntimeSocialChannel["channel_id"],
    artifactId: string,
    mediaArtifactId: string | null,
    greenlightId: string,
    greenlightFencingToken: number,
    csrfToken: string,
    idempotencyKey: string,
  ): Promise<RuntimeSocialPublication>;
  revokeSession(csrfToken: string): Promise<void>;
}

type FetchLike = typeof fetch;

function encodeBase64UrlUtf8(value: string): string {
  const bytes = new TextEncoder().encode(value);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return globalThis.btoa(binary)
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
}

async function responseJson<T>(response: Response): Promise<T> {
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

async function requestBinaryJson<T>(
  fetchImpl: FetchLike,
  path: string,
  body: BodyInit,
  headers: Record<string, string>,
): Promise<T> {
  const response = await fetchImpl(path, {
    method: "POST",
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...headers,
    },
    body,
  });
  return responseJson<T>(response);
}

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
          Prefer: "respond-async",
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
    providerCatalog() {
      return requestJson<RuntimeProviderCatalog>(fetchImpl, "/api/v1/providers");
    },
    async integrations() {
      const payload = await requestJson<{ integrations: RuntimeIntegrationSummary[] }>(fetchImpl, "/api/v1/integrations");
      return payload.integrations;
    },
    async socialChannels() {
      const payload = await requestJson<{ channels: RuntimeSocialChannel[] }>(fetchImpl, "/api/v1/social-channels");
      return payload.channels;
    },
    async socialPublications(runId) {
      const payload = await requestJson<{ publications: RuntimeSocialPublication[] }>(
        fetchImpl,
        `/api/v1/runs/${encodeURIComponent(runId)}/social-publications`,
      );
      return payload.publications;
    },
    startSocialOAuth(channelId, csrfToken) {
      return requestJson<RuntimeSocialOAuthStart>(
        fetchImpl,
        `/api/v1/social-channels/${encodeURIComponent(channelId)}/oauth/start`,
        {
          method: "POST",
          headers: { "X-CSRF-Token": csrfToken },
        },
      );
    },
    async disconnectSocialChannel(channelId, csrfToken) {
      await requestJson<{ disconnected: boolean }>(
        fetchImpl,
        `/api/v1/social-channels/${encodeURIComponent(channelId)}/connection`,
        {
          method: "DELETE",
          headers: { "X-CSRF-Token": csrfToken },
        },
      );
    },
    attachPublicationMedia(
      runId,
      channelId,
      file,
      altText,
      rightsConfirmed,
      csrfToken,
      idempotencyKey,
    ) {
      return requestBinaryJson<RuntimeRun>(
        fetchImpl,
        `/api/v1/runs/${encodeURIComponent(runId)}/publication-media/${encodeURIComponent(channelId)}`,
        file,
        {
          "Content-Type": file.type || "image/jpeg",
          "X-CSRF-Token": csrfToken,
          "Idempotency-Key": idempotencyKey,
          "X-Media-Alt-Text-Base64": encodeBase64UrlUtf8(altText),
          "X-Media-Rights-Confirmed": rightsConfirmed ? "true" : "false",
        },
      );
    },
    revokePublicationMedia(runId, mediaId, reason, csrfToken, idempotencyKey) {
      return requestJson<RuntimeRun>(
        fetchImpl,
        `/api/v1/runs/${encodeURIComponent(runId)}/publication-media/${encodeURIComponent(mediaId)}`,
        {
          method: "DELETE",
          headers: {
            "X-CSRF-Token": csrfToken,
            "Idempotency-Key": idempotencyKey,
          },
          body: JSON.stringify({ reason }),
        },
      );
    },
    publishSocial(
      runId,
      channelId,
      artifactId,
      mediaArtifactId,
      greenlightId,
      greenlightFencingToken,
      csrfToken,
      idempotencyKey,
    ) {
      return requestJson<RuntimeSocialPublication>(
        fetchImpl,
        `/api/v1/runs/${encodeURIComponent(runId)}/social-publications/${encodeURIComponent(channelId)}`,
        {
          method: "POST",
          headers: {
            "X-CSRF-Token": csrfToken,
            "Idempotency-Key": idempotencyKey,
          },
          body: JSON.stringify({
            artifact_id: artifactId,
            media_artifact_id: mediaArtifactId,
            greenlight_id: greenlightId,
            greenlight_fencing_token: greenlightFencingToken,
          }),
        },
      );
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
