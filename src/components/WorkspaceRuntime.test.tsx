import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type {
  BrowserRuntimeSession,
  RuntimeApi,
  RuntimeRun,
} from "../lib/runtimeApi";
import { WorkspaceRuntime } from "./WorkspaceRuntime";

const SESSION: BrowserRuntimeSession = {
  tenant_id: "tenant-alpha",
  subject_id: "operator@example.com",
  role: "operator",
  key_id: "operator-v1",
  entitlements: [],
  csrf_token: "csrf-value",
  expires_at: "2026-07-22T20:00:00+00:00",
};

const RUN: RuntimeRun = {
  run_id: "run-product-workspace-001",
  tenant_id: "tenant-alpha",
  status: "awaiting_greenlight",
  agent_states: {
    research: {
      status: "ready",
      progress: 100,
      detail: "Research complete",
      artifact_ids: ["artifact-research"],
    },
  },
  artifacts: [
    {
      artifact_id: "artifact-research",
      kind: "research_dossier",
      title: "Research dossier",
      payload: {
        scholar: {
          reencuadre_cognitivo: "Reframe the campaign around evidence.",
          tension_del_trade_off: "Speed and certainty remain in tension.",
          resolucion_operativa: "Ship the reversible option first.",
        },
      },
      evidence_ids: ["evidence-1"],
    },
  ],
  greenlight: null,
  sandbox: true,
  external_side_effects_enabled: false,
};

function api(overrides: Partial<RuntimeApi> = {}): RuntimeApi {
  return {
    createSession: vi.fn().mockResolvedValue(SESSION),
    resumeSession: vi.fn().mockResolvedValue(null),
    currentIdentity: vi.fn().mockResolvedValue({
      tenant_id: SESSION.tenant_id,
      subject_id: SESSION.subject_id,
      role: SESSION.role,
      key_id: SESSION.key_id,
      permissions: ["identity:read", "runs:read", "runs:create", "audit:read"],
      entitlements: [],
      auth_method: "session",
    }),
    createRun: vi.fn().mockResolvedValue(RUN),
    getRun: vi.fn().mockResolvedValue(RUN),
    approveRun: vi.fn().mockResolvedValue({ ...RUN, status: "completed" }),
    rejectRun: vi.fn().mockResolvedValue({ ...RUN, status: "rejected" }),
    revokeRun: vi.fn().mockResolvedValue({ ...RUN, status: "revoked" }),
    auditEvents: vi.fn().mockResolvedValue([]),
    providerCatalog: vi.fn().mockResolvedValue({
      tenant_id: "tenant-alpha",
      providers: [],
      gateway: {
        execution_enabled: false,
        selected_provider: "",
        execution_available: false,
        durable_outbound_receipt: false,
        automatic_run_integration: false,
      },
    }),
    integrations: vi.fn().mockResolvedValue([]),
    revokeSession: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
}

describe("WorkspaceRuntime", () => {
  it("exchanges the credential once and removes it after session creation", async () => {
    const user = userEvent.setup();
    const runtime = api();
    render(<WorkspaceRuntime api={runtime} />);

    await user.click(await screen.findByRole("button", { name: /Conectar espacio/i }));
    const credential = screen.getByLabelText(/Credencial del tenant/i);
    await user.type(credential, "tenant-alpha-verification-key-2026");
    await user.click(screen.getByRole("button", { name: /Crear sesión segura/i }));

    await screen.findByText(/operator@example.com/i);
    expect(runtime.createSession).toHaveBeenCalledWith("tenant-alpha-verification-key-2026");
    expect(screen.queryByLabelText(/Credencial del tenant/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Ejecutar campaña/i })).toBeEnabled();
  });

  it("renders versioned outputs from the governed runtime and reports the run upward", async () => {
    const user = userEvent.setup();
    const onRunChange = vi.fn();
    const runtime = api({ resumeSession: vi.fn().mockResolvedValue(SESSION) });
    render(<WorkspaceRuntime api={runtime} onRunChange={onRunChange} />);

    await screen.findByText(/operator@example.com/i);
    await user.click(screen.getByRole("button", { name: /Ejecutar campaña/i }));

    expect(await screen.findByText(/run-product-workspace-001/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Ver posts y estado de publicación/i })).toHaveAttribute("href", "#campaign-output");
    expect(screen.queryByText(/Speed and certainty remain in tension/i)).not.toBeInTheDocument();
    await waitFor(() => expect(onRunChange).toHaveBeenLastCalledWith(RUN));
  });
});
