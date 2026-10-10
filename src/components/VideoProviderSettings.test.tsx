import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { VideoProviderSettings } from "./VideoProviderSettings";

afterEach(() => {
  vi.unstubAllGlobals();
});

const catalog = {
  providers: [
    {
      provider_id: "heygen",
      display_name: "HeyGen",
      connection: "hosted_api",
      capabilities: ["avatar_video", "prompt_to_video"],
      suited_for: "Presenters and product explainers",
      configured: true,
      configuration_state: "configured_execution_disabled",
      execution_enabled: false,
      requires_human_authorization: true,
      credential_environment: "HEYGEN_API_KEY",
      setup: "Configure your server secret",
      documentation_url: "https://www.heygen.com/api-pricing",
    },
    {
      provider_id: "freevideo",
      display_name: "FreeVideo / ComfyUI",
      connection: "local_gpu_worker",
      capabilities: ["text_to_video"],
      suited_for: "GPU worker",
      configured: false,
      configuration_state: "worker_not_bound",
      execution_enabled: false,
      requires_human_authorization: true,
      credential_environment: null,
      setup: "Bind GPU worker",
      documentation_url: "https://github.com/FlashML-org/FreeVideo",
    },
  ],
};

describe("VideoProviderSettings", () => {
  it("does not fetch or ask for secrets when the session is disconnected", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<VideoProviderSettings enabled={false} />);
    expect(screen.getByText(/Conecta tu espacio/i)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.queryByLabelText(/API key/i)).not.toBeInTheDocument();
  });

  it("shows video engine setup from the server without triggering paid generation", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true, json: async () => catalog,
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<VideoProviderSettings enabled={true} />);
    await screen.findByText("Presenters and product explainers");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/video/providers",
      expect.objectContaining({ method: "GET", credentials: "same-origin" }),
    );
    expect(screen.getByText(/ejecución pendiente/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cómo conectar" }));
    expect(screen.getByText("HEYGEN_API_KEY")).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: /Motor de video/i }), {
      target: { value: "freevideo" },
    });
    expect(screen.getByText("GPU worker")).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
  });
});
