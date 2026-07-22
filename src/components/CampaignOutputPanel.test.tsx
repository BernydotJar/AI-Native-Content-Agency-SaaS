import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { RuntimeRun } from "../lib/runtimeApi";
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

describe("CampaignOutputPanel", () => {
  it("renders channel-ready posts and keeps publication blocked before Greenlight", () => {
    render(<CampaignOutputPanel run={RUN} />);

    expect(screen.getByRole("heading", { name: /Posts listos para revisión/i })).toBeInTheDocument();
    expect(screen.getByText("X")).toBeInTheDocument();
    expect(screen.getByText("Instagram")).toBeInTheDocument();
    expect(screen.getByText(/Una señal puede convertirse en acción/i)).toBeInTheDocument();
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
    render(<CampaignOutputPanel run={RUN} />);

    fireEvent.click(screen.getAllByRole("button", { name: /Copiar post/i })[0]);
    expect(writeText).toHaveBeenCalledWith(
      "Una señal puede convertirse en acción.\n\nConstruye una campaña verificable con un equipo AI-native.\n\nConoce la propuesta.",
    );
  });

  it("shows a bounded empty state before a run exists", () => {
    render(<CampaignOutputPanel run={null} />);
    expect(screen.getByText(/Todavía no hay posts/i)).toBeInTheDocument();
  });
});
