import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type {
  BrowserRuntimeSession,
  RuntimeApi,
  RuntimeRun,
  RuntimeTrendPilotSeed,
} from "../lib/runtimeApi";
import { RuntimeApiError } from "../lib/runtimeApi";
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

const ADMIN_SESSION: BrowserRuntimeSession = {
  ...SESSION,
  subject_id: "legal.reviewer@example.com",
  role: "admin",
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
  execution: {
    state: "awaiting_greenlight",
    next_station: "publisher",
    lease_owner: "",
    lease_expires_at: null,
    fencing_token: 14,
    attempts: 14,
    checkpointed_at: "2026-07-23T00:00:00+00:00",
    failure_detail: "",
  },
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
    trendRadar: vi.fn(),
    integrations: vi.fn().mockResolvedValue([]),
    socialChannels: vi.fn().mockResolvedValue([]),
    socialPublications: vi.fn().mockResolvedValue([]),
    startSocialOAuth: vi.fn(),
    disconnectSocialChannel: vi.fn().mockResolvedValue(undefined),
    attachPublicationMedia: vi.fn(),
    revokePublicationMedia: vi.fn(),
    publishSocial: vi.fn(),
    revokeSession: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
}

describe("WorkspaceRuntime", () => {
  it("handles each external login request once and stays signed out after logout", async () => {
    const user = userEvent.setup();
    const runtime = api();
    render(<WorkspaceRuntime api={runtime} connectionRequest={1} />);

    await screen.findByRole("dialog", { name: /Conectar este navegador/i });
    await user.type(screen.getByLabelText(/^Usuario$/i), "operator@example.com");
    await user.type(screen.getByLabelText(/^Contraseña$/i), "tenant-alpha-verification-key-2026");
    await user.click(screen.getByRole("button", { name: /Iniciar sesión/i }));

    await screen.findByText(/operator@example.com/i);
    expect(runtime.createSession).toHaveBeenCalledWith(
      "operator@example.com",
      "tenant-alpha-verification-key-2026",
    );
    expect(screen.queryByLabelText(/^Usuario$/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/^Contraseña$/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Ejecutar campaña/i })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: /Desconectar/i }));
    await screen.findByRole("button", { name: /Conectar espacio/i });
    expect(runtime.revokeSession).toHaveBeenCalledWith(SESSION.csrf_token);
    expect(screen.queryByRole("dialog", { name: /Conectar este navegador/i })).not.toBeInTheDocument();
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

  it("accepts a radar seed as an editable no-publication pilot mission", async () => {
    const user = userEvent.setup();
    const runtime = api({ resumeSession: vi.fn().mockResolvedValue(SESSION) });
    const briefSeed: RuntimeTrendPilotSeed = {
      id: "ai:pilot-1",
      source_label: "Radar IA: adopción de inteligencia artificial",
      brief: {
        title: "Piloto de tendencia: IA en Guatemala",
        objective: "Crear borradores verificables sin publicar.",
        audience: "Equipos de tecnología en Guatemala",
        platforms: ["x", "instagram"],
        budget_cents: 0,
        campaign_goal: "trend_response_pilot",
        campaign_type: "commercial",
        publication_mode: "organic",
        locale: "es-GT",
        evidence_claims: [{
          statement: "Una fuente reciente reportó adopción local de IA.",
          source: "Google News RSS · Example",
          locator: "https://example.test/evidence",
          verification_status: "unverified",
        }],
      },
    };

    render(<WorkspaceRuntime api={runtime} briefSeed={briefSeed} />);

    await screen.findByText(/operator@example.com/i);
    expect(screen.getByText(/Modo piloto · brief precargado/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Título de campaña/i)).toHaveValue(
      "Piloto de tendencia: IA en Guatemala",
    );
    expect(screen.getByLabelText(/Resultado esperado/i)).toHaveValue(
      "Crear borradores verificables sin publicar.",
    );

    await user.click(screen.getByRole("button", { name: /Ejecutar campaña/i }));
    expect(runtime.createRun).toHaveBeenCalledWith(
      expect.objectContaining({
        campaign_goal: "trend_response_pilot",
        platforms: ["x", "instagram"],
        budget_cents: 0,
      }),
      SESSION.csrf_token,
      expect.stringMatching(/^run:create:/),
    );
  });

  it("reveals grounded political campaign fields and legal-review warning", async () => {
    const user = userEvent.setup();
    const runtime = api({ resumeSession: vi.fn().mockResolvedValue(SESSION) });
    render(<WorkspaceRuntime api={runtime} />);

    await screen.findByText(/operator@example.com/i);
    await user.selectOptions(screen.getByLabelText(/Tipo de campaña/i), "political");

    expect(screen.getByRole("group", { name: /Contexto político verificable/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/Modo de publicación política/i)).toHaveValue("organic");
    await user.selectOptions(screen.getByLabelText(/Modo de publicación política/i), "paid");
    expect(screen.getByLabelText(/Modo de publicación política/i)).toHaveValue("paid");
    expect(screen.getByText(/autoridad de anuncios separada/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Jurisdicción/i)).toBeRequired();
    expect(screen.getByLabelText(/Afirmación respaldada/i)).toBeRequired();
    expect(screen.getByLabelText(/Revisión legal/i)).toHaveValue("pending");
    expect(screen.getByRole("option", { name: /Aprobada con autoridad/i })).toBeDisabled();
    expect(screen.getByLabelText(/Estado de verificación/i)).toHaveValue("unverified");
    expect(screen.getByRole("option", { name: /Verificada con autoridad/i })).toBeDisabled();
    expect(screen.getByText(/Tu rol puede preparar la afirmación/i)).toBeInTheDocument();
    expect(screen.getByText(/Adjuntar una fuente no la convierte/i)).toBeInTheDocument();
  });

  it("explains that political legal review and Greenlight require different identities", async () => {
    const user = userEvent.setup();
    const runtime = api({
      resumeSession: vi.fn().mockResolvedValue(ADMIN_SESSION),
      approveRun: vi.fn().mockRejectedValue(
        new RuntimeApiError(
          409,
          "political reviewer separation required",
          "request-political-separation-001",
          "political_reviewer_separation_required",
        ),
      ),
    });
    render(<WorkspaceRuntime api={runtime} />);

    await screen.findByText(/legal\.reviewer@example\.com/i);
    await user.click(screen.getByRole("button", { name: /Ejecutar campaña/i }));
    await user.click(await screen.findByRole("button", { name: /Approve artefactos/i }));

    expect(await screen.findByText(/Aprobación independiente requerida/i)).toBeInTheDocument();
    expect(screen.getByText(/identidades diferentes/i)).toBeInTheDocument();
    expect(screen.getByText(/otro aprobador/i)).toBeInTheDocument();
  });

  it("polls a queued run until durable station execution reaches Greenlight", async () => {
    const user = userEvent.setup();
    const queued: RuntimeRun = {
      ...RUN,
      status: "queued",
      agent_states: {
        ceo: { status: "standby", progress: 0, detail: "Awaiting mission", artifact_ids: [] },
      },
      artifacts: [],
      execution: {
        state: "queued",
        next_station: "ceo",
        lease_owner: "",
        lease_expires_at: null,
        fencing_token: 0,
        attempts: 0,
        checkpointed_at: "2026-07-23T00:00:00+00:00",
        failure_detail: "",
      },
    };
    const processing: RuntimeRun = {
      ...queued,
      status: "running",
      agent_states: {
        ceo: { status: "processing", progress: 10, detail: "Interpreting mission constraints", artifact_ids: [] },
      },
      execution: { ...queued.execution, state: "running", fencing_token: 1, attempts: 1 },
    };
    const getRun = vi.fn()
      .mockResolvedValueOnce(processing)
      .mockResolvedValue(RUN);
    const runtime = api({
      resumeSession: vi.fn().mockResolvedValue(SESSION),
      createRun: vi.fn().mockResolvedValue(queued),
      getRun,
    });
    render(<WorkspaceRuntime api={runtime} />);

    await screen.findByText(/operator@example.com/i);
    await user.click(screen.getByRole("button", { name: /Ejecutar campaña/i }));
    expect(await screen.findByText(/checkpoint 0 · próxima estación ceo/i)).toBeInTheDocument();
    await waitFor(() => expect(getRun).toHaveBeenCalled(), { timeout: 1500 });
    await waitFor(() => expect(screen.getByText(/awaiting greenlight/i)).toBeInTheDocument(), { timeout: 2500 });
    expect(getRun.mock.calls.length).toBeGreaterThanOrEqual(2);
  });
});
