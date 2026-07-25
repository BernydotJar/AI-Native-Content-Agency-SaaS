import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

const SOCIAL_CHANNELS: RuntimeSocialChannel[] = [
  {
    channel_id: "x",
    display_name: "X",
    oauth_flow: "oauth_1_0a_user_context",
    configured: false,
    configuration_state: "missing_credentials",
    credentials_configured: false,
    callback_configured: false,
    callback_url: "",
    connection_state: "not_connected",
    oauth_start_available: false,
    oauth_runtime_configured: false,
    publication_runtime_configured: false,
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
  },
  {
    channel_id: "instagram",
    display_name: "Instagram",
    oauth_flow: "instagram_business_login",
    configured: true,
    configuration_state: "ready_for_authentication",
    credentials_configured: true,
    callback_configured: true,
    callback_url: "https://agency.example/api/v1/social-channels/instagram/oauth/callback",
    connection_state: "not_connected",
    oauth_start_available: false,
    oauth_runtime_configured: false,
    publication_runtime_configured: false,
    publication_execution_enabled: false,
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
    expect(screen.getByText(/Instagram exige imagen; adjunta un JPEG 4:5/i)).toBeInTheDocument();
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

  it("requires a second explicit confirmation before publishing X", async () => {
    const completed: RuntimeRun = {
      ...RUN,
      status: "completed",
      greenlight: {
        greenlight_id: "greenlight-publish-001",
        decision: "approved",
        reviewer: "approver@example.com",
        note: "Approved",
        approved_artifact_ids: ["copy-001"],
        approved_artifact_hashes: ["hash-001"],
        authorized_channels: ["x", "instagram"],
        authorized_budget_cents: 0,
        fencing_token: 0,
        revoked_at: null,
        revoked_by: "",
        revocation_reason: "",
      },
    };
    const connectedX: RuntimeSocialChannel = {
      ...SOCIAL_CHANNELS[0],
      configured: true,
      configuration_state: "ready_for_authentication",
      credentials_configured: true,
      callback_configured: true,
      callback_url: "https://agency.example/api/v1/social-channels/x/oauth/callback",
      connection_state: "connected",
      oauth_start_available: false,
      oauth_runtime_configured: true,
      publication_runtime_configured: true,
      publication_execution_enabled: true,
      publishing_available: true,
      external_effects_enabled: true,
      connected_account: {
        account_id: "x-account-001",
        account_username: "approved_x",
        scopes: ["tweet.read", "tweet.write", "users.read"],
        token_expires_at: null,
        connected_at: "2026-07-23T20:30:00+00:00",
        token_storage: "encrypted_server_side",
      },
    };
    const onPublish = vi.fn().mockResolvedValue(undefined);
    render(
      <CampaignOutputPanel
        run={completed}
        socialChannels={[connectedX, SOCIAL_CHANNELS[1]]}
        publicationAllowed
        onPublish={onPublish}
      />,
    );

    const publishButtons = screen.getAllByRole("button", { name: /^Publicar$/i });
    expect(publishButtons[0]).toBeEnabled();
    expect(publishButtons[1]).toBeDisabled();
    fireEvent.click(publishButtons[0]);

    expect(onPublish).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog", { name: /Publicar en X/i })).toBeInTheDocument();
    expect(screen.getByText("@approved_x")).toBeInTheDocument();
    expect(screen.getByText(/intent durable se reservará antes/i)).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: /Confirmar publicación externa/i }),
    );
    await waitFor(() => expect(onPublish).toHaveBeenCalledTimes(1));
    expect(onPublish).toHaveBeenCalledWith(
      "x",
      "copy-001",
      null,
      "",
      expect.stringMatching(/^publish-run-output-001-x-/),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("requires the exact political phrase before publishing an organic post", async () => {
    const completed: RuntimeRun = {
      ...RUN,
      brief: {
        title: "Prueba política orgánica",
        objective: "Verificar confirmación política",
        audience: "ciudadanía",
        platforms: ["x"],
        budget_cents: 0,
        campaign_goal: "technical_verification",
        campaign_type: "political",
        publication_mode: "organic",
      },
      status: "completed",
      greenlight: {
        greenlight_id: "greenlight-political-001",
        decision: "approved",
        reviewer: "independent.approver@example.test",
        note: "Approved",
        approved_artifact_ids: ["copy-001"],
        approved_artifact_hashes: ["hash-001"],
        authorized_channels: ["x"],
        authorized_budget_cents: 0,
        fencing_token: 2,
        revoked_at: null,
        revoked_by: "",
        revocation_reason: "",
      },
    };
    const connectedX: RuntimeSocialChannel = {
      ...SOCIAL_CHANNELS[0],
      configured: true,
      configuration_state: "ready_for_authentication",
      credentials_configured: true,
      callback_configured: true,
      callback_url: "https://agency.example/api/v1/social-channels/x/oauth/callback",
      connection_state: "connected",
      oauth_start_available: false,
      oauth_runtime_configured: true,
      publication_runtime_configured: true,
      publication_execution_enabled: true,
      publishing_available: true,
      external_effects_enabled: true,
      connected_account: {
        account_id: "x-account-political",
        account_username: "political_sandbox",
        scopes: ["tweet.read", "tweet.write", "users.read"],
        token_expires_at: null,
        connected_at: "2026-07-25T18:00:00+00:00",
        token_storage: "encrypted_server_side",
      },
    };
    const onPublish = vi.fn().mockResolvedValue(undefined);
    render(
      <CampaignOutputPanel
        run={completed}
        socialChannels={[connectedX]}
        publicationAllowed
        onPublish={onPublish}
      />,
    );

    const politicalPublish = screen.getAllByRole("button", { name: /^Publicar$/i })
      .find((button) => !button.hasAttribute("disabled"));
    expect(politicalPublish).toBeDefined();
    fireEvent.click(politicalPublish as HTMLButtonElement);
    const requiredPhrase = `PUBLICAR POLITICA ${completed.run_id} x`;
    expect(screen.getByText(requiredPhrase)).toBeInTheDocument();
    const confirm = screen.getByRole("button", { name: /Confirmar publicación externa/i });
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Frase de confirmación política/i), {
      target: { value: "PUBLICAR POLITICA incorrecta x" },
    });
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Frase de confirmación política/i), {
      target: { value: requiredPhrase },
    });
    expect(confirm).toBeEnabled();
    fireEvent.click(confirm);

    await waitFor(() => expect(onPublish).toHaveBeenCalledWith(
      "x",
      "copy-001",
      null,
      requiredPhrase,
      expect.stringMatching(/^publish-run-output-001-x-/),
    ));
  });

  it("keeps paid political media outside the organic publication authority", () => {
    const paid: RuntimeRun = {
      ...RUN,
      brief: {
        title: "Pauta política",
        objective: "Verify paid boundary",
        audience: "ciudadanía",
        platforms: ["x"],
        budget_cents: 0,
        campaign_goal: "technical_verification",
        campaign_type: "political",
        publication_mode: "paid",
      },
      status: "completed",
      greenlight: {
        greenlight_id: "greenlight-paid-001",
        decision: "approved",
        reviewer: "independent.approver@example.test",
        note: "Approved",
        approved_artifact_ids: ["copy-001"],
        approved_artifact_hashes: ["hash-001"],
        authorized_channels: ["x"],
        authorized_budget_cents: 0,
        fencing_token: 2,
        revoked_at: null,
        revoked_by: "",
        revocation_reason: "",
      },
    };
    const connectedX: RuntimeSocialChannel = {
      ...SOCIAL_CHANNELS[0],
      configured: true,
      connection_state: "connected",
      publication_runtime_configured: true,
      publication_execution_enabled: true,
      publishing_available: true,
      connected_account: {
        account_id: "x-account-paid",
        account_username: "paid_sandbox",
        scopes: ["tweet.read", "tweet.write", "users.read"],
        token_expires_at: null,
        connected_at: "2026-07-25T18:00:00+00:00",
        token_storage: "encrypted_server_side",
      },
    };
    render(
      <CampaignOutputPanel
        run={paid}
        socialChannels={[connectedX]}
        publicationAllowed
        onPublish={vi.fn()}
      />,
    );
    expect(screen.getAllByText("Requiere autoridad de anuncios")).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: /^Publicar$/i })).toSatisfy(
      (buttons: HTMLElement[]) => buttons.every((button) => button.hasAttribute("disabled")),
    );
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

  it("restores only a verified Instagram permalink from durable receipts", () => {
    render(
      <CampaignOutputPanel
        run={RUN}
        socialChannels={SOCIAL_CHANNELS}
        publications={[{
          intent_id: "intent-verified-001",
          channel_id: "instagram",
          account_id: "ig-account-001",
          run_id: RUN.run_id,
          artifact_id: "copy-001",
          artifact_hash: "a".repeat(64),
          greenlight_id: "greenlight-001",
          greenlight_fencing_token: 1,
          status: "succeeded",
          execution_fencing_token: 1,
          provider_container_id: "container-001",
          provider_post_id: "post-001",
          receipt: {
            verification_status: "verified",
            permalink: "https://www.instagram.com/p/post-001/",
          },
          replayed: false,
        }]}
      />,
    );
    expect(
      screen.getByRole("link", { name: /Abrir publicación verificada en Instagram/i }),
    ).toHaveAttribute("href", "https://www.instagram.com/p/post-001/");
  });

  it("shows a bounded empty state before a run exists", () => {
    render(<CampaignOutputPanel run={null} />);
    expect(screen.getByText(/Todavía no hay posts/i)).toBeInTheDocument();
  });

  it("requires JPEG, alt text and rights before attaching Instagram media", async () => {
    const onAttachMedia = vi.fn().mockResolvedValue(undefined);
    render(
      <CampaignOutputPanel
        run={RUN}
        socialChannels={SOCIAL_CHANNELS}
        publicationAllowed
        onAttachMedia={onAttachMedia}
      />,
    );

    const upload = screen.getByRole("button", { name: /Adjuntar imagen/i });
    expect(upload).toBeDisabled();
    const file = new File([new Uint8Array([0xff, 0xd8, 0xff, 0xd9])], "campaign.jpg", {
      type: "image/jpeg",
    });
    fireEvent.change(screen.getByLabelText(/Imagen JPEG/i), {
      target: { files: [file] },
    });
    fireEvent.change(screen.getByLabelText(/Texto alternativo/i), {
      target: { value: "Tarjeta accesible de la propuesta." },
    });
    expect(upload).toBeDisabled();
    fireEvent.click(screen.getByLabelText(/Confirmo que tengo derechos/i));
    expect(upload).toBeEnabled();
    fireEvent.click(upload);

    await waitFor(() => expect(onAttachMedia).toHaveBeenCalledTimes(1));
    expect(onAttachMedia).toHaveBeenCalledWith(
      "instagram",
      file,
      "Tarjeta accesible de la propuesta.",
      true,
      expect.stringMatching(/^media:instagram:/),
    );
  });

  it("renders governed Instagram media with its approved alt text", () => {
    const runWithMedia: RuntimeRun = {
      ...RUN,
      artifacts: [
        ...RUN.artifacts,
        {
          artifact_id: "publication-media-001",
          kind: "publication_media",
          title: "Governed Instagram publication image",
          payload: {
            channel: "instagram",
            media_id: "media-001",
            media_url: "https://media.example.test/api/v1/publication-media/public/opaque-token",
            content_type: "image/jpeg",
            byte_size: 12345,
            sha256: "a".repeat(64),
            width: 1080,
            height: 1350,
            alt_text: "Carrusel accesible sobre una propuesta municipal.",
            rights_status: "confirmed",
            rights_attested_by: "media-admin",
            expires_at: "2026-07-26T08:00:00+00:00",
          },
          evidence_ids: [],
        },
      ],
    };

    render(
      <CampaignOutputPanel
        run={runWithMedia}
        socialChannels={SOCIAL_CHANNELS}
        publicationAllowed
      />,
    );

    expect(
      screen.getByRole("img", {
        name: "Carrusel accesible sobre una propuesta municipal.",
      }),
    ).toHaveAttribute(
      "src",
      "https://media.example.test/api/v1/publication-media/public/opaque-token",
    );
    expect(screen.queryByRole("button", { name: /Adjuntar imagen/i })).not.toBeInTheDocument();
    expect(screen.getByText(/Media gobernada/i)).toBeInTheDocument();
  });

});
