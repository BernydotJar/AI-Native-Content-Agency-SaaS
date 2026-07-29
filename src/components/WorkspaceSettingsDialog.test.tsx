import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { RuntimeProvider, RuntimeSocialChannel } from "../lib/runtimeApi";
import { WorkspaceSettingsDialog } from "./WorkspaceSettingsDialog";


const PROVIDERS: RuntimeProvider[] = [
  {
    provider_id: "openai",
    display_name: "OpenAI",
    protocol: "openai_responses",
    configured: true,
    configuration_state: "ready",
    model: "gpt-5.2",
    endpoint_host: "api.openai.com",
    model_environment: "AGENCY_OPENAI_MODEL",
    base_url_environment: "AGENCY_OPENAI_BASE_URL",
    credential_location: "server_environment",
    recommended_models: ["gpt-5.2"],
  },
  {
    provider_id: "deepseek",
    display_name: "DeepSeek",
    protocol: "openai_compatible",
    configured: false,
    configuration_state: "missing_credential",
    model: "deepseek-v4-flash",
    endpoint_host: "api.deepseek.com",
    model_environment: "AGENCY_DEEPSEEK_MODEL",
    base_url_environment: "AGENCY_DEEPSEEK_BASE_URL",
    credential_location: "server_environment",
    recommended_models: ["deepseek-v4-flash", "deepseek-v4-pro"],
  },
];

const DISCONNECTED: RuntimeSocialChannel = {
  channel_id: "x",
  display_name: "X",
  oauth_flow: "oauth_1_0a_user_context",
  configured: true,
  configuration_state: "ready_for_authentication",
  credentials_configured: true,
  callback_configured: true,
  callback_url: "https://agency.example/api/v1/social-channels/x/oauth/callback",
  connection_state: "not_connected",
  oauth_start_available: true,
  oauth_runtime_configured: true,
  publication_runtime_configured: true,
  publication_execution_enabled: false,
  publishing_available: false,
  external_effects_enabled: false,
  credential_location: "server_environment",
  credential_environments: ["AGENCY_X_CONSUMER_KEY", "AGENCY_X_CONSUMER_SECRET"],
  redirect_environment: "AGENCY_X_REDIRECT_URI",
  scopes: ["tweet.read", "tweet.write", "users.read"],
  account_requirement: "X account authorized by the tenant",
  publish_protocol: "POST /2/tweets",
  supported_content: ["text", "image", "video"],
  requires_media: false,
  connected_account: null,
};

const CONNECTED: RuntimeSocialChannel = {
  ...DISCONNECTED,
  connection_state: "connected",
  oauth_start_available: false,
  connected_account: {
    account_id: "x-account-001",
    account_username: "connected_x",
    scopes: ["tweet.read", "tweet.write", "users.read"],
    token_expires_at: null,
    connected_at: "2026-07-23T08:00:00+00:00",
    token_storage: "encrypted_server_side",
  },
};

function props(channel: RuntimeSocialChannel, role: "viewer" | "admin") {
  return {
    open: true,
    onClose: vi.fn(),
    activeTheme: "blue" as const,
    premiumThemeEntitled: false,
    onThemeChange: vi.fn(),
    providers: PROVIDERS,
    gateway: {
      execution_enabled: false,
      selected_provider: "",
      execution_available: false,
      durable_outbound_receipt: false,
      automatic_run_integration: false,
    },
    integrations: [{
      integration_id: "video-use",
      display_name: "Video Use",
      review_status: "reviewed_disabled",
      activation_allowed: false,
      execution_available: false,
      external_effects_enabled: false,
    }],
    socialChannels: [channel],
    providerLoading: false,
    providerError: "",
    sessionActive: true,
    sessionRole: role,
    socialActionChannel: null,
    socialActionError: "",
    socialNotice: "",
    onConnectSocial: vi.fn(),
    onDisconnectSocial: vi.fn(),
    onRefreshProviders: vi.fn(),
  };
}

describe("WorkspaceSettingsDialog social accounts", () => {
  it("lets an admin start OAuth and never asks for a token in the browser", () => {
    const input = props(DISCONNECTED, "admin");
    render(<WorkspaceSettingsDialog {...input} />);

    fireEvent.click(screen.getByRole("button", { name: /Conectar cuenta/i }));
    expect(input.onConnectSocial).toHaveBeenCalledWith("x");
    expect(screen.queryByLabelText(/access token|consumer secret|app secret/i)).not.toBeInTheDocument();
    expect(screen.getByText(/token storage cifrado/i)).toBeInTheDocument();
    expect(screen.getByText("https://agency.example/api/v1/social-channels/x/oauth/callback")).toBeInTheDocument();
  });

  it("shows connected metadata and lets an admin disconnect", () => {
    const input = props(CONNECTED, "admin");
    render(<WorkspaceSettingsDialog {...input} />);

    expect(screen.getByText("@connected_x")).toBeInTheDocument();
    expect(screen.getByText(/tokens cifrados server-side/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Desconectar/i }));
    expect(input.onDisconnectSocial).toHaveBeenCalledWith("x");
  });

  it("keeps social mutations hidden from a viewer", () => {
    render(<WorkspaceSettingsDialog {...props(DISCONNECTED, "viewer")} />);
    expect(screen.queryByRole("button", { name: /Conectar cuenta/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Desconectar/i })).not.toBeInTheDocument();
  });

  it("centralizes provider setup and keeps reviewed integrations explicit", () => {
    render(<WorkspaceSettingsDialog {...props(DISCONNECTED, "admin")} />);

    const selector = screen.getByLabelText(/Proveedor de modelos/i);
    fireEvent.change(selector, { target: { value: "deepseek" } });
    expect(screen.getByRole("heading", { name: "DeepSeek" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Configurar proveedor/i }));
    expect(screen.getByText(/secret manager del servidor/i)).toBeInTheDocument();
    expect(screen.getByText(/Nunca pegues credenciales en esta pantalla/i)).toBeInTheDocument();
    expect(screen.getByText("Video Use")).toBeInTheDocument();
    expect(screen.getByText(/Revisada · deshabilitada/i)).toBeInTheDocument();
  });
});
