import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { runtimeApi } from "./lib/runtimeApi";
import type { BrowserRuntimeSession, RuntimeProvider } from "./lib/runtimeApi";

const SESSION: BrowserRuntimeSession = {
  tenant_id: "tenant-alpha",
  subject_id: "operator@example.com",
  role: "operator",
  key_id: "operator-v1",
  entitlements: [],
  csrf_token: "csrf-session-value",
  expires_at: "2026-07-22T20:00:00+00:00",
};

const PROVIDERS: RuntimeProvider[] = [
  ["openai", "OpenAI", true, "ready", "gpt-5.2"],
  ["anthropic", "Anthropic", false, "missing_credential", ""],
  ["deepseek", "DeepSeek", true, "ready", "deepseek-v4-flash"],
  ["moonshot", "Moonshot / Kimi", true, "ready", "kimi-k3"],
  ["llama", "Llama", false, "missing_endpoint", "llama-4-maverick"],
].map(([provider_id, display_name, configured, configuration_state, model]) => ({
  provider_id: provider_id as RuntimeProvider["provider_id"],
  display_name: String(display_name),
  protocol: provider_id === "anthropic" ? "anthropic_messages" : provider_id === "openai" ? "openai_responses" : "openai_compatible",
  configured: Boolean(configured),
  configuration_state: configuration_state as RuntimeProvider["configuration_state"],
  model: String(model),
  endpoint_host: configured ? `${provider_id}.example.test` : "",
  model_environment: `AGENCY_${String(provider_id).toUpperCase()}_MODEL`,
  base_url_environment: `AGENCY_${String(provider_id).toUpperCase()}_BASE_URL`,
  credential_location: "server_environment",
  recommended_models: [String(model || `${provider_id}-recommended`)],
}));

beforeEach(() => {
  vi.spyOn(runtimeApi, "resumeSession").mockResolvedValue(null);
  vi.spyOn(runtimeApi, "auditEvents").mockResolvedValue([]);
  vi.spyOn(runtimeApi, "currentIdentity").mockResolvedValue({
    tenant_id: SESSION.tenant_id,
    subject_id: SESSION.subject_id,
    role: SESSION.role,
    key_id: SESSION.key_id,
    permissions: ["identity:read", "runs:read", "runs:create", "audit:read"],
    entitlements: [],
    auth_method: "session",
  });
  vi.spyOn(runtimeApi, "providerCatalog").mockResolvedValue({
    tenant_id: "tenant-alpha",
    providers: PROVIDERS,
    gateway: {
      execution_enabled: false,
      selected_provider: "",
      execution_available: false,
      durable_outbound_receipt: false,
      automatic_run_integration: false,
    },
  });
  vi.spyOn(runtimeApi, "integrations").mockResolvedValue([{
    integration_id: "video-use",
    display_name: "Video Use",
    review_status: "reviewed_disabled",
    activation_allowed: false,
    execution_available: false,
    external_effects_enabled: false,
  }]);
});

afterEach(() => {
  document.documentElement.removeAttribute("data-theme");
  document.documentElement.removeAttribute("data-theme-tier");
  document.documentElement.removeAttribute("style");
  vi.restoreAllMocks();
});

describe("product workspace shell", () => {
  it("prioritizes governed command and hides infrequent configuration", async () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: /Convierte una señal en una campaña completa/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Define la misión. Ejecuta el sistema/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Lanza una campaña gobernada/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Mapa de orquestación de ocho estaciones/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Campaign command/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Posts listos para revisión/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Tema azul/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Credencial del tenant/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Memory & Skills Console/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Mock$/i)).not.toBeInTheDocument();
    expect(screen.queryByText("Video Use")).not.toBeInTheDocument();
    expect(screen.queryByText("DeepSeek")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Configuración/i }));
    expect(screen.getByRole("dialog", { name: /Administración del espacio/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Tema azul/i })).toBeInTheDocument();
  });

  it("mounts the one-time tenant credential only inside the connection dialog", async () => {
    render(<App />);

    const connect = await screen.findByRole("button", { name: /Conectar espacio/i });
    expect(screen.queryByLabelText(/Credencial del tenant/i)).not.toBeInTheDocument();

    fireEvent.click(connect);
    expect(screen.getByRole("dialog", { name: /Conectar este navegador/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/Credencial del tenant/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Cerrar diálogo de conexión/i }));
    expect(screen.queryByLabelText(/Credencial del tenant/i)).not.toBeInTheDocument();
  });

  it("shows five server-derived providers after a secure session is restored", async () => {
    vi.mocked(runtimeApi.resumeSession).mockResolvedValue(SESSION);
    render(<App />);

    await screen.findByText(/tenant-alpha conectado/i);
    await waitFor(() => expect(runtimeApi.providerCatalog).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: /Configuración/i }));

    expect(screen.getByText("OpenAI")).toBeInTheDocument();
    expect(screen.getByText("Anthropic")).toBeInTheDocument();
    expect(screen.getByText("DeepSeek")).toBeInTheDocument();
    expect(screen.getByText("Moonshot / Kimi")).toBeInTheDocument();
    expect(screen.getByText("Llama")).toBeInTheDocument();
    expect(screen.queryByLabelText(/OpenAI API key/i)).not.toBeInTheDocument();
    expect(screen.getByText(/3\/5 listos/i)).toBeInTheDocument();
    expect(screen.getByText(/Gateway de inferencia deshabilitado/i)).toBeInTheDocument();
    expect(screen.getByText("Video Use")).toBeInTheDocument();
  });

  it("keeps premium appearance server-entitled and outside the command flow", async () => {
    vi.mocked(runtimeApi.resumeSession).mockResolvedValue({
      ...SESSION,
      entitlements: ["theme:premium"],
    });
    vi.mocked(runtimeApi.currentIdentity).mockResolvedValue({
      tenant_id: SESSION.tenant_id,
      subject_id: SESSION.subject_id,
      role: SESSION.role,
      key_id: SESSION.key_id,
      permissions: [],
      entitlements: ["theme:premium"],
      auth_method: "session",
    });
    render(<App />);

    await screen.findByText(/tenant-alpha conectado/i);
    fireEvent.click(screen.getByRole("button", { name: /Configuración/i }));
    const premium = screen.getByRole("button", { name: /Tema premium/i });
    expect(premium).toHaveAttribute("aria-disabled", "false");
    fireEvent.click(premium);

    expect(document.documentElement).toHaveAttribute("data-theme", "premium");
    expect(document.documentElement).toHaveAttribute("data-theme-tier", "premium");
  });
});
