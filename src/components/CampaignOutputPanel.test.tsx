import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { RuntimeRun, RuntimeSocialChannel } from "../lib/runtimeApi";
import { CampaignOutputPanel } from "./CampaignOutputPanel";

const RUN: RuntimeRun = {
  run_id: "run-output-001",
  tenant_id: "tenant-alpha",
  status: "awaiting_greenlight",
  agent_states: {},
  artifacts: [
    {
      artifact_id: "copy-001",
      kind: "copy_deck",
      title: "Platform copy deck",
      payload: {
        variants: {
          x: {
            hook: "Una señal puede convertirse en acción.",
            body: "Construye una campaña verificable con un equipo AI-native.",
            cta: "Conoce la propuesta.",
          },
          instagram: {
            hook: "De la señal a la campaña.",
            body: "Estrategia, copy y aprobación en un solo run.",
            cta: "Participa.",
          },
        },
        claims_status: "draft_requires_human_review",
      },
      evidence_ids: ["evidence-1"],
    },
  ],
  greenlight: null,
  sandbox: true,
  external_side_effects_enabled: false,
};

const SOCIAL_CHANNELS: RuntimeSocialChannel[] = [
  {
    channel_id: "x",
    display_name: "X",
    oauth_flow: "oauth_1_0a_user_context",
    configured: false,
    configuration_state: "missing_credentials",
    credentials_configured: false,
    callback_configured: false,
    connection_state: "not_connected",
    oauth_start_available: false,
    oauth_runtime_configured: false,
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
  },
  {
    channel_id: "instagram",
    display_name: "Instagram",
    oauth_flow: "instagram_business_login",
    configured: true,
    configuration_state: "ready_for_authentication",
    credentials_configured: true,
    callback_configured: true,
    connection_state: "not_connected",
    oauth_start_available: false,
    oauth_runtime_configured: false,
    publishing_available: false,
    external_effects_enabled: false,
    credential_location: "server_environment",
    credential_environments: ["AGENCY_INSTAGRAM_APP_ID", "AGENCY_INSTAGRAM_APP_SECRET"],
    redirect_environment: "AGENCY_INSTAGRAM_REDIRECT_URI",
    scopes: ["instagram_business_basic", "instagram_business_content_publish"],
    account_requirement: "Instagram Professional account (Business or Creator)",
    publish_protocol: "POST /media then POST /media_publish",
    supported_content: ["image", "reel", "carousel"],
    requires_media: true,
    connected_account: null,
  },
];

describe("CampaignOutputPanel", () => {
  it("renders channel-ready posts and keeps publication blocked before Greenlight", () => {
    render(<CampaignOutputPanel run={RUN} socialChannels={SOCIAL_CHANNELS} />);

    expect(screen.getByRole("heading", { name: /Posts listos para revisión/i })).toBeInTheDocument();
    expect(screen.getByText("X")).toBeInTheDocument();
    expect(screen.getByText("Instagram")).toBeInTheDocument();
    expect(screen.getByText(/Una señal puede convertirse en acción/i)).toBeInTheDocument();
    expect(screen.getByText(/Vista previa de Instagram/i)).toBeInTheDocument();
    expect(screen.getByText(/Asset visual pendiente/i)).toBeInTheDocument();
    expect(screen.getByText(/Instagram exige imagen, reel o carrusel/i)).toBeInTheDocument();
    expect(screen.getByRole("list", { name: /Estado de publicación para Instagram/i })).toBeInTheDocument();
    expect(screen.getAllByText(/Requiere Greenlight/i)).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: /Publicar/i })).toSatisfy((buttons: HTMLElement[]) =>
      buttons.every((button) => button.hasAttribute("disabled")),
    );
    expect(screen.getByText("Platform copy deck")).not.toBeVisible();
    fireEvent.click(screen.getByText(/Contexto y evidencia/i));
    expect(screen.getByText("Platform copy deck")).toBeVisible();
  });

  it("copies the composed post without enabling external publication", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    render(<CampaignOutputPanel run={RUN} socialChannels={SOCIAL_CHANNELS} />);

    fireEvent.click(screen.getAllByRole("button", { name: /Copiar post/i })[0]);
    expect(writeText).toHaveBeenCalledWith(
      "Una señal puede convertirse en acción.\n\nConstruye una campaña verificable con un equipo AI-native.\n\nConoce la propuesta.",
    );
  });

  it("makes the Instagram account setup path explicit", () => {
    const onOpenSettings = vi.fn();
    render(
      <CampaignOutputPanel
        run={RUN}
        socialChannels={SOCIAL_CHANNELS}
        onOpenSettings={onOpenSettings}
      />,
    );

    expect(screen.getByRole("button", { name: /Configurar X/i })).toBeInTheDocument();
    const authenticateInstagram = screen.getByRole("button", { name: /Autenticar cuenta/i });
    fireEvent.click(authenticateInstagram);
    expect(onOpenSettings).toHaveBeenCalledTimes(1);
  });

  it("shows missing rendered media after Greenlight instead of claiming Instagram is publishable", () => {
    const completed: RuntimeRun = {
      ...RUN,
      status: "completed",
      greenlight: {
        greenlight_id: "greenlight-001",
        decision: "approved",
        reviewer: "approver@example.com",
        note: "Approved",
        approved_artifact_ids: ["copy-001"],
        approved_artifact_hashes: ["hash-001"],
        authorized_channels: ["x", "instagram"],
        authorized_budget_cents: 0,
        fencing_token: 1,
        revoked_at: null,
        revoked_by: "",
        revocation_reason: "",
      },
    };
    render(<CampaignOutputPanel run={completed} socialChannels={SOCIAL_CHANNELS} />);

    expect(screen.getByText("Falta asset visual")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Publicar/i })).toSatisfy((buttons: HTMLElement[]) =>
      buttons.every((button) => button.hasAttribute("disabled")),
    );
  });

  it("shows a bounded empty state before a run exists", () => {
    render(<CampaignOutputPanel run={null} />);
    expect(screen.getByText(/Todavía no hay posts/i)).toBeInTheDocument();
  });
});
