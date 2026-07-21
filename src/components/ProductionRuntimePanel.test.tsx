import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ProductionRuntimePanel } from "./ProductionRuntimePanel";
import { RuntimeApiError } from "../lib/runtimeApi";
import type { RuntimeApi, RuntimeAuditEvent, RuntimeRun } from "../lib/runtimeApi";

const session = {
  tenant_id: "tenant-alpha",
  subject_id: "operator@example.com",
  role: "admin" as const,
  key_id: "operator-v2",
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
    actor: "api-key:operator@example.com",
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
    reviewer: "war-room-operator",
    note: "Approved",
    approved_artifact_ids: ["artifact-research", "artifact-risk"],
    approved_artifact_hashes: ["hash-1", "hash-2"],
    authorized_channels: ["x", "instagram"],
    authorized_budget_cents: 0,
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

function buildApi(): RuntimeApi {
  return {
    createSession: vi.fn().mockResolvedValue(session),
    resumeSession: vi.fn().mockResolvedValue(null),
    createRun: vi.fn().mockResolvedValue(awaitingRun),
    approveRun: vi.fn().mockResolvedValue(completedRun),
    rejectRun: vi.fn().mockResolvedValue({ ...awaitingRun, status: "rejected" }),
    auditEvents: vi.fn().mockResolvedValue(auditEvents),
    revokeSession: vi.fn().mockResolvedValue(undefined),
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ProductionRuntimePanel", () => {
  it("exchanges a one-time key, runs the backend, and approves exact artifacts", async () => {
    const user = userEvent.setup();
    const storageSpy = vi.spyOn(Storage.prototype, "setItem");
    const api = buildApi();
    render(<ProductionRuntimePanel api={api} />);

    const keyInput = screen.getByLabelText(/Tenant API key/i);
    await user.type(keyInput, "one-time-browser-api-key-value");
    await user.click(screen.getByRole("button", { name: /Open secure session/i }));

    expect(api.createSession).toHaveBeenCalledWith("one-time-browser-api-key-value");
    expect(screen.queryByLabelText(/Tenant API key/i)).not.toBeInTheDocument();
    expect(screen.getByText("operator@example.com")).toBeInTheDocument();
    expect(screen.getByText(/tenant-alpha · admin · operator-v2/i)).toBeInTheDocument();
    expect(storageSpy).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: /Run governed campaign/i }));
    expect(api.createRun).toHaveBeenCalledWith(
      expect.objectContaining({ platforms: ["x", "instagram"] }),
      "csrf-session-value",
    );
    expect(await screen.findByText("awaiting greenlight")).toBeInTheDocument();
    expect(screen.getByText("Reencuadre Cognitivo")).toBeInTheDocument();
    expect(screen.getByText("Tensión del Trade-off")).toBeInTheDocument();
    expect(screen.getByText("Resolución Operativa")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Approve exact artifacts/i }));
    expect(api.approveRun).toHaveBeenCalledWith("run-123", "csrf-session-value");
    expect(await screen.findByText(/Sandbox campaign package created/i)).toBeInTheDocument();
    expect(screen.getByText("completed")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Revoke browser session/i }));
    expect(api.revokeSession).toHaveBeenCalledWith("csrf-session-value");
    expect(await screen.findByLabelText(/Tenant API key/i)).toHaveValue("");
    expect(storageSpy).not.toHaveBeenCalled();
  });

  it("clears the API key and surfaces the correlated request on failure", async () => {
    const user = userEvent.setup();
    const api = buildApi();
    vi.mocked(api.createSession).mockRejectedValue(
      new RuntimeApiError(401, "invalid session credential", "request-login-0001"),
    );
    render(<ProductionRuntimePanel api={api} />);

    const keyInput = screen.getByLabelText(/Tenant API key/i);
    await user.type(keyInput, "invalid-browser-api-key-value");
    await user.click(screen.getByRole("button", { name: /Open secure session/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "invalid session credential · request request-login-0001",
    );
    expect(keyInput).toHaveValue("");
  });
});
