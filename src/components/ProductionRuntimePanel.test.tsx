import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ProductionRuntimePanel } from "./ProductionRuntimePanel";
import { RuntimeApiError } from "../lib/runtimeApi";
import type {
  BrowserRuntimeSession,
  RuntimeApi,
  RuntimeAuditEvent,
  RuntimeRun,
} from "../lib/runtimeApi";

const adminSession: BrowserRuntimeSession = {
  tenant_id: "tenant-alpha",
  subject_id: "admin@example.com",
  role: "admin",
  key_id: "admin-v2",
  csrf_token: "csrf-session-value",
  expires_at: "2026-07-21T20:00:00+00:00",
};

const auditEvents: RuntimeAuditEvent[] = [
  {
    sequence: 1,
    event_id: "audit-session",
    request_id: "request-session",
    action: "session.created",
    resource_type: "browser_session",
    resource_id: "session-1",
    occurred_at: "2026-07-21T12:00:00+00:00",
    actor: "api-key:admin@example.com",
    payload: {},
  },
];

const awaitingRun: RuntimeRun = {
  run_id: "run-123",
  tenant_id: "tenant-alpha",
  status: "awaiting_greenlight",
  agent_states: {
    publisher: {
      status: "waiting_greenlight",
      progress: 0,
      detail: "Manual approval required",
      artifact_ids: [],
    },
  },
  artifacts: [
    {
      artifact_id: "artifact-research",
      kind: "research_dossier",
      title: "Research dossier",
      evidence_ids: ["evidence-1"],
      payload: {
        scholar: {
          reencuadre_cognitivo: "Evidence changes the framing.",
          tension_del_trade_off: "Speed competes with verification.",
          resolucion_operativa: "Ship the smallest governed experiment.",
        },
      },
    },
    {
      artifact_id: "artifact-risk",
      kind: "risk_report",
      title: "Risk report",
      evidence_ids: [],
      payload: { passed: true },
    },
  ],
  greenlight: null,
  sandbox: true,
  external_side_effects_enabled: false,
};

const completedRun: RuntimeRun = {
  ...awaitingRun,
  status: "completed",
  greenlight: {
    greenlight_id: "greenlight-1",
    decision: "approved",
    reviewer: "admin@example.com",
    note: "Approved",
    approved_artifact_ids: ["artifact-research", "artifact-risk"],
    approved_artifact_hashes: ["hash-1", "hash-2"],
    authorized_channels: ["x", "instagram"],
    authorized_budget_cents: 0,
    fencing_token: 1,
    revoked_at: null,
    revoked_by: "",
    revocation_reason: "",
  },
  artifacts: [
    ...awaitingRun.artifacts,
    {
      artifact_id: "artifact-package",
      kind: "campaign_package",
      title: "Sandbox campaign manifest",
      evidence_ids: ["evidence-package"],
      payload: { publication_performed: false },
    },
  ],
};

const revokedRun: RuntimeRun = {
  ...completedRun,
  status: "revoked",
  greenlight: completedRun.greenlight && {
    ...completedRun.greenlight,
    fencing_token: 2,
    revoked_at: "2026-07-21T20:30:00+00:00",
    revoked_by: "admin@example.com",
    revocation_reason: "Campaign paused",
  },
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function buildApi(overrides: Partial<RuntimeApi> = {}): RuntimeApi {
  return {
    createSession: vi.fn().mockResolvedValue(adminSession),
    resumeSession: vi.fn().mockResolvedValue(null),
    createRun: vi.fn().mockResolvedValue(awaitingRun),
    getRun: vi.fn().mockResolvedValue(awaitingRun),
    approveRun: vi.fn().mockResolvedValue(completedRun),
    rejectRun: vi.fn().mockResolvedValue({ ...awaitingRun, status: "rejected" }),
    revokeRun: vi.fn().mockResolvedValue(revokedRun),
    auditEvents: vi.fn().mockResolvedValue(auditEvents),
    revokeSession: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
}

async function signIn(user: ReturnType<typeof userEvent.setup>) {
  const keyInput = await screen.findByLabelText(/Tenant API key/i);
  await user.type(keyInput, "one-time-browser-api-key-value");
  await user.click(screen.getByRole("button", { name: /Open secure session/i }));
  await screen.findByText("admin@example.com");
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ProductionRuntimePanel", () => {
  it("announces session restoration before rendering signed-out controls", async () => {
    const pending = deferred<BrowserRuntimeSession | null>();
    const api = buildApi({ resumeSession: vi.fn(() => pending.promise) });
    render(<ProductionRuntimePanel api={api} />);

    expect(screen.getByRole("status")).toHaveTextContent(/Restoring secure session/i);
    expect(screen.queryByLabelText(/Tenant API key/i)).not.toBeInTheDocument();

    pending.resolve(null);
    expect(await screen.findByLabelText(/Tenant API key/i)).toBeEnabled();
  });

  it("exchanges a one-time key, runs the backend, and approves exact artifacts", async () => {
    const user = userEvent.setup();
    const storageSpy = vi.spyOn(Storage.prototype, "setItem");
    const api = buildApi();
    render(<ProductionRuntimePanel api={api} />);

    await signIn(user);
    expect(api.createSession).toHaveBeenCalledWith("one-time-browser-api-key-value");
    expect(screen.getByText(/tenant-alpha · admin · admin-v2/i)).toBeInTheDocument();
    expect(storageSpy).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: /Run governed campaign/i }));
    expect(api.createRun).toHaveBeenCalledWith(
      expect.objectContaining({ platforms: ["x", "instagram"] }),
      "csrf-session-value",
      expect.stringMatching(/^run:create:/),
    );
    expect(await screen.findByText("awaiting greenlight")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Approve exact artifacts/i }));
    expect(api.approveRun).toHaveBeenCalledWith(
      "run-123",
      "csrf-session-value",
      expect.stringMatching(/^greenlight:approve:run-123:/),
    );
    expect(await screen.findByText(/Sandbox campaign package created/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Revoke Greenlight/i }));
    expect(api.revokeRun).toHaveBeenCalledWith(
      "run-123",
      "csrf-session-value",
      expect.stringMatching(/^greenlight:revoke:run-123:/),
    );
    expect(await screen.findByText(/Greenlight revoked/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Revoke browser session/i }));
    expect(api.revokeSession).toHaveBeenCalledWith("csrf-session-value");
    expect(await screen.findByLabelText(/Tenant API key/i)).toHaveValue("");
    expect(storageSpy).not.toHaveBeenCalled();
  });

  it("renders viewer access as explicitly read-only without invoking mutations", async () => {
    const viewerSession: BrowserRuntimeSession = {
      ...adminSession,
      subject_id: "viewer@example.com",
      role: "viewer",
      key_id: "viewer-v1",
    };
    const api = buildApi({ resumeSession: vi.fn().mockResolvedValue(viewerSession) });
    render(<ProductionRuntimePanel api={api} />);

    expect(await screen.findByText(/Read-only access/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Campaign title/i)).toBeDisabled();
    expect(screen.getByRole("button", { name: /Run governed campaign/i })).toBeDisabled();
    expect(api.createRun).not.toHaveBeenCalled();
  });

  it("allows an operator to create but not decide Greenlight", async () => {
    const user = userEvent.setup();
    const operatorSession: BrowserRuntimeSession = {
      ...adminSession,
      subject_id: "operator@example.com",
      role: "operator",
      key_id: "operator-v2",
    };
    const api = buildApi({ resumeSession: vi.fn().mockResolvedValue(operatorSession) });
    render(<ProductionRuntimePanel api={api} />);

    await screen.findByText("operator@example.com");
    await user.click(screen.getByRole("button", { name: /Run governed campaign/i }));
    expect(await screen.findByText(/Approval requires approver or admin authority/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Approve exact artifacts/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Reject package/i })).not.toBeInTheDocument();
  });

  it("lets an approver load a tenant-scoped run before deciding", async () => {
    const user = userEvent.setup();
    const approverSession: BrowserRuntimeSession = {
      ...adminSession,
      subject_id: "approver@example.com",
      role: "approver",
      key_id: "approver-v1",
    };
    const api = buildApi({
      resumeSession: vi.fn().mockResolvedValue(approverSession),
      getRun: vi.fn().mockResolvedValue(awaitingRun),
    });
    render(<ProductionRuntimePanel api={api} />);

    await screen.findByText("approver@example.com");
    await user.type(screen.getByLabelText(/Existing run ID/i), "run-123");
    await user.click(screen.getByRole("button", { name: /Load governed run/i }));

    expect(api.getRun).toHaveBeenCalledWith("run-123");
    expect(await screen.findByRole("button", { name: /Approve exact artifacts/i })).toBeEnabled();
    expect(screen.getByRole("button", { name: /Run governed campaign/i })).toBeDisabled();
  });

  it("reuses one command key for an ambiguous dependency retry", async () => {
    const user = userEvent.setup();
    const api = buildApi();
    vi.mocked(api.createRun)
      .mockRejectedValueOnce(new RuntimeApiError(503, "service unavailable", "request-run-0001", "service_unavailable"))
      .mockResolvedValueOnce(awaitingRun);
    render(<ProductionRuntimePanel api={api} />);

    await signIn(user);
    const runButton = screen.getByRole("button", { name: /Run governed campaign/i });
    await user.click(runButton);
    expect(await screen.findByText(/Runtime temporarily unavailable/i)).toBeInTheDocument();
    await user.click(runButton);

    const firstKey = vi.mocked(api.createRun).mock.calls[0][2];
    const secondKey = vi.mocked(api.createRun).mock.calls[1][2];
    expect(secondKey).toBe(firstKey);
  });

  it.each([
    [403, "authorization_denied", "Action not permitted"],
    [422, "validation_error", "Check campaign details"],
    [500, "internal_error", "Runtime request failed"],
  ])("classifies status %s without reflecting backend detail", async (status, code, title) => {
    const user = userEvent.setup();
    const api = buildApi({
      createRun: vi.fn().mockRejectedValue(
        new RuntimeApiError(status, "sensitive-internal-detail", `request-${status}`, code),
      ),
    });
    render(<ProductionRuntimePanel api={api} />);

    await signIn(user);
    await user.click(screen.getByRole("button", { name: /Run governed campaign/i }));
    expect(await screen.findByText(title)).toBeInTheDocument();
    expect(screen.queryByText(/sensitive-internal-detail/i)).not.toBeInTheDocument();
    expect(screen.getByText(new RegExp(`request-${status}`, "i"))).toBeInTheDocument();
  });

  it("uses a non-enumerating not-found state for run lookup", async () => {
    const user = userEvent.setup();
    const api = buildApi({
      resumeSession: vi.fn().mockResolvedValue(adminSession),
      getRun: vi.fn().mockRejectedValue(
        new RuntimeApiError(404, "request not permitted", "request-missing-0001", "resource_not_found"),
      ),
    });
    render(<ProductionRuntimePanel api={api} />);

    await screen.findByText("admin@example.com");
    await user.type(screen.getByLabelText(/Existing run ID/i), "run-foreign");
    await user.click(screen.getByRole("button", { name: /Load governed run/i }));
    expect(await screen.findByText(/Run not found/i)).toBeInTheDocument();
    expect(screen.getByText(/outside the current tenant scope/i)).toBeInTheDocument();
    expect(screen.queryByText(/run-foreign/i)).not.toBeInTheDocument();
  });

  it("classifies a rate limit with safe retry guidance and correlation", async () => {
    const user = userEvent.setup();
    const api = buildApi({
      createRun: vi.fn().mockRejectedValue(
        new RuntimeApiError(
          429,
          "authentication temporarily rate limited",
          "request-rate-0001",
          "authentication_rate_limited",
          30,
        ),
      ),
    });
    render(<ProductionRuntimePanel api={api} />);

    await signIn(user);
    await user.click(screen.getByRole("button", { name: /Run governed campaign/i }));
    expect(await screen.findByText(/Too many attempts/i)).toBeInTheDocument();
    expect(screen.getByText(/Try again in about 30 seconds/i)).toBeInTheDocument();
    expect(screen.getByText(/request-rate-0001/i)).toBeInTheDocument();
  });

  it("recovers a stale decision conflict by reloading the current run", async () => {
    const user = userEvent.setup();
    const api = buildApi({
      approveRun: vi.fn().mockRejectedValue(
        new RuntimeApiError(409, "resource state conflict", "request-conflict-0001", "resource_state_conflict"),
      ),
      getRun: vi.fn().mockResolvedValue(completedRun),
    });
    render(<ProductionRuntimePanel api={api} />);

    await signIn(user);
    await user.click(screen.getByRole("button", { name: /Run governed campaign/i }));
    await user.click(await screen.findByRole("button", { name: /Approve exact artifacts/i }));
    expect(await screen.findByText(/Campaign state changed/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Reload current run/i }));
    expect(api.getRun).toHaveBeenCalledWith("run-123");
    expect(await screen.findByText("completed")).toBeInTheDocument();
  });

  it("clears protected state when audit refresh reports an expired session", async () => {
    const user = userEvent.setup();
    const api = buildApi({
      resumeSession: vi.fn().mockResolvedValue(adminSession),
      auditEvents: vi.fn()
        .mockResolvedValueOnce([])
        .mockRejectedValueOnce(
          new RuntimeApiError(401, "authentication required", "request-expired-0001", "authentication_required"),
        ),
    });
    render(<ProductionRuntimePanel api={api} />);

    await screen.findByText("admin@example.com");
    await waitFor(() => expect(api.auditEvents).toHaveBeenCalledTimes(1));
    await user.click(screen.getByRole("button", { name: /Refresh durable audit/i }));

    expect(await screen.findByText(/Session expired/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Tenant API key/i)).toBeEnabled();
    expect(screen.queryByText("admin@example.com")).not.toBeInTheDocument();
  });

  it("keeps the session usable when audit evidence is temporarily degraded", async () => {
    const api = buildApi({
      resumeSession: vi.fn().mockResolvedValue(adminSession),
      auditEvents: vi.fn().mockRejectedValue(
        new RuntimeApiError(503, "service unavailable", "request-audit-0001", "service_unavailable"),
      ),
    });
    render(<ProductionRuntimePanel api={api} />);

    expect(await screen.findByText(/Runtime temporarily unavailable/i)).toBeInTheDocument();
    expect(screen.getByText(/Audit evidence is temporarily unavailable/i)).toBeInTheDocument();
    expect(screen.getByText("admin@example.com")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Run governed campaign/i })).toBeEnabled();
  });

  it("shows audit loading and a distinct empty state", async () => {
    const audit = deferred<RuntimeAuditEvent[]>();
    const api = buildApi({
      resumeSession: vi.fn().mockResolvedValue(adminSession),
      auditEvents: vi.fn(() => audit.promise),
    });
    render(<ProductionRuntimePanel api={api} />);

    expect(await screen.findByText(/Loading audit evidence/i)).toBeInTheDocument();
    audit.resolve([]);
    expect(await screen.findByText(/No mutation evidence yet/i)).toBeInTheDocument();
  });
});
