import {
  SCHEMA_VERSION,
  type ApprovalCreate,
  type ApprovalDecision,
  type ErrorResponse,
  type GreenlightPolicyVersion,
  type MissionCreate,
  type MissionResponse,
  type RunResponse,
  type RunStart,
} from "./contracts";

export interface ControlPlaneIdentity {
  tenantId: string;
  principalId: string;
}

export interface ControlPlaneClientOptions extends ControlPlaneIdentity {
  baseUrl: string;
  fetchImplementation?: typeof fetch;
  createRequestId?: () => string;
}

export interface ApprovalCommand {
  decision: ApprovalDecision;
  reviewer: string;
  note?: string;
  artifactManifestHash: string;
  policyVersion: GreenlightPolicyVersion;
}

export interface MutableCommandOptions {
  idempotencyKey?: string;
}

const DEVELOPMENT_IDENTIFIER = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/;
const IDEMPOTENCY_KEY = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;

function normalizedBaseUrl(value: string): string {
  return value.trim().replace(/\/+$/, "");
}

function defaultRequestId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

function isErrorResponse(value: unknown): value is ErrorResponse {
  if (!value || typeof value !== "object" || !("error" in value)) return false;
  const error = (value as { error?: unknown }).error;
  return Boolean(
    error
      && typeof error === "object"
      && "code" in error
      && "message" in error
      && typeof (error as { code: unknown }).code === "string"
      && typeof (error as { message: unknown }).message === "string",
  );
}

export class ControlPlaneApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly correlationId: string;
  readonly details: Record<string, unknown>;

  constructor(
    status: number,
    code: string,
    message: string,
    correlationId: string,
    details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "ControlPlaneApiError";
    this.status = status;
    this.code = code;
    this.correlationId = correlationId;
    this.details = details;
  }
}

export function safeControlPlaneError(error: unknown): ControlPlaneApiError {
  if (error instanceof ControlPlaneApiError) return error;
  return new ControlPlaneApiError(
    0,
    "CONTROL_PLANE_UNREACHABLE",
    "The control-plane outcome is unknown. Refresh authoritative state or retry the exact command with its original idempotency key.",
    "unavailable",
  );
}

export class ControlPlaneClient {
  readonly identity: ControlPlaneIdentity;
  readonly baseUrl: string;
  private readonly request: typeof fetch;
  private readonly createRequestId: () => string;

  constructor(options: ControlPlaneClientOptions) {
    if (!DEVELOPMENT_IDENTIFIER.test(options.tenantId)) {
      throw new TypeError("tenantId does not match the development identity contract");
    }
    if (!DEVELOPMENT_IDENTIFIER.test(options.principalId)) {
      throw new TypeError("principalId does not match the development identity contract");
    }
    this.identity = {
      tenantId: options.tenantId,
      principalId: options.principalId,
    };
    this.baseUrl = normalizedBaseUrl(options.baseUrl);
    this.request = options.fetchImplementation ?? fetch.bind(globalThis);
    this.createRequestId = options.createRequestId ?? defaultRequestId;
  }

  createIdempotencyKey(): string {
    return `web-${this.createRequestId()}`;
  }

  createMission(
    input: Omit<MissionCreate, "schema_version">,
    command: MutableCommandOptions = {},
  ): Promise<MissionResponse> {
    return this.send<MissionResponse>("POST", "/api/v1/missions", {
      body: { schema_version: SCHEMA_VERSION, ...input },
      mutable: true,
      idempotencyKey: command.idempotencyKey,
    });
  }

  startRun(missionId: string, command: MutableCommandOptions = {}): Promise<RunResponse> {
    const body: RunStart = { schema_version: SCHEMA_VERSION };
    return this.send<RunResponse>(
      "POST",
      `/api/v1/missions/${encodeURIComponent(missionId)}/runs`,
      { body, mutable: true, idempotencyKey: command.idempotencyKey },
    );
  }

  getRun(runId: string): Promise<RunResponse> {
    return this.send<RunResponse>(
      "GET",
      `/api/v1/runs/${encodeURIComponent(runId)}`,
    );
  }

  decideRun(
    runId: string,
    command: ApprovalCommand,
    options: MutableCommandOptions = {},
  ): Promise<RunResponse> {
    const body: ApprovalCreate = {
      schema_version: SCHEMA_VERSION,
      decision: command.decision,
      reviewer: command.reviewer,
      note: command.note ?? "",
      artifact_manifest_hash: command.artifactManifestHash,
      policy_version: command.policyVersion,
    };
    return this.send<RunResponse>(
      "POST",
      `/api/v1/runs/${encodeURIComponent(runId)}/approvals`,
      { body, mutable: true, idempotencyKey: options.idempotencyKey },
    );
  }

  private async send<ResponseBody>(
    method: "GET" | "POST",
    path: string,
    options: { body?: object; mutable?: boolean; idempotencyKey?: string } = {},
  ): Promise<ResponseBody> {
    const idempotencyKey = options.mutable
      ? options.idempotencyKey ?? this.createIdempotencyKey()
      : undefined;
    if (idempotencyKey && !IDEMPOTENCY_KEY.test(idempotencyKey)) {
      throw new TypeError("idempotencyKey does not match the command-key contract");
    }
    const requestId = idempotencyKey ?? `web-${this.createRequestId()}`;
    const headers = new Headers({
      Accept: "application/json",
      "X-Tenant-ID": this.identity.tenantId,
      "X-Principal-ID": this.identity.principalId,
      "X-Correlation-ID": requestId,
    });
    if (options.body) headers.set("Content-Type", "application/json");
    if (idempotencyKey) headers.set("Idempotency-Key", idempotencyKey);

    let response: Response;
    try {
      response = await this.request(`${this.baseUrl}${path}`, {
        method,
        headers,
        body: options.body ? JSON.stringify(options.body) : undefined,
      });
    } catch {
      throw safeControlPlaneError(undefined);
    }

    const correlationId = response.headers.get("X-Correlation-ID") ?? requestId;
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      if (response.ok) {
        throw new ControlPlaneApiError(
          response.status,
          "INVALID_CONTROL_PLANE_RESPONSE",
          "The control plane returned an unreadable response.",
          correlationId,
        );
      }
    }

    if (!response.ok) {
      if (isErrorResponse(payload)) {
        throw new ControlPlaneApiError(
          response.status,
          payload.error.code,
          payload.error.message,
          payload.error.correlation_id || correlationId,
          payload.error.details,
        );
      }
      throw new ControlPlaneApiError(
        response.status,
        "CONTROL_PLANE_REQUEST_FAILED",
        `The control plane rejected the request with status ${response.status}.`,
        correlationId,
      );
    }

    return payload as ResponseBody;
  }
}

export function createDefaultControlPlaneClient(): ControlPlaneClient {
  return new ControlPlaneClient({
    baseUrl: import.meta.env.VITE_API_BASE_URL ?? "",
    tenantId: import.meta.env.VITE_DEV_TENANT_ID ?? "local-dev",
    principalId: import.meta.env.VITE_DEV_PRINCIPAL_ID ?? "local-operator",
  });
}
