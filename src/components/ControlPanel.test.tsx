import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ControlPanel } from "./ControlPanel";

describe("ControlPanel", () => {
  it("launches the selected video mission with the uploaded filename", async () => {
    const user = userEvent.setup();
    const onRunSimulation = vi.fn();
    const onAccentChange = vi.fn();
    const { container } = render(
      <ControlPanel
        onRunSimulation={onRunSimulation}
        isRunning={false}
        onAccentChange={onAccentChange}
      />,
    );

    await user.click(screen.getByRole("button", { name: /video ready-to-publish/i }));
    const fileInput = container.querySelector<HTMLInputElement>('input[type="file"]');
    expect(fileInput).not.toBeNull();
    await user.upload(fileInput!, new File(["demo"], "founder-story.mp4", { type: "video/mp4" }));
    await user.selectOptions(screen.getByRole("combobox", { name: /target surface/i }), "Instagram");
    await user.click(screen.getByRole("button", { name: /launch autonomous cycle/i }));

    expect(onRunSimulation).toHaveBeenCalledWith(1, {
      videoName: "founder-story.mp4",
      platform: "Instagram",
    });
  });

  it("updates the accent with an accessible pressed state", async () => {
    const user = userEvent.setup();
    const onAccentChange = vi.fn();
    render(
      <ControlPanel
        onRunSimulation={vi.fn()}
        isRunning={false}
        onAccentChange={onAccentChange}
      />,
    );

    const violet = screen.getByRole("button", { name: /cambiar acento a neon violet/i });
    await user.click(violet);

    expect(onAccentChange).toHaveBeenCalledWith(260);
    expect(violet).toHaveAttribute("aria-pressed", "true");
  });

  it("launches a full campaign with five channels and an explicit flight", async () => {
    const user = userEvent.setup();
    const onRunSimulation = vi.fn();
    render(
      <ControlPanel
        onRunSimulation={onRunSimulation}
        isRunning={false}
        onAccentChange={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: /launch autonomous cycle/i }));

    expect(onRunSimulation).toHaveBeenCalledWith(3, expect.objectContaining({
      channels: ["X", "LinkedIn", "Facebook", "Instagram", "TikTok"],
      durationDays: 7,
      budget: 3500,
    }));
  });

  it("blocks a paid campaign when no Meta surface is selected", async () => {
    const user = userEvent.setup();
    render(
      <ControlPanel
        onRunSimulation={vi.fn()}
        isRunning={false}
        onAccentChange={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Facebook" }));
    await user.click(screen.getByRole("button", { name: "Instagram" }));

    expect(screen.getByRole("button", { name: /launch autonomous cycle/i })).toBeDisabled();
    expect(screen.getByText(/required for paid media/i)).toBeInTheDocument();
  });

  it("blocks a full campaign when X is not selected", async () => {
    const user = userEvent.setup();
    render(
      <ControlPanel
        onRunSimulation={vi.fn()}
        isRunning={false}
        onAccentChange={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "X" }));

    expect(screen.getByRole("button", { name: /launch autonomous cycle/i })).toBeDisabled();
    expect(screen.getByText(/X is required for the 3-part thread/i)).toBeInTheDocument();
  });
});
