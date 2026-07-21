import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ControlPanel } from "./ControlPanel";

const originalMatchMedia = window.matchMedia;
const originalStartViewTransition = document.startViewTransition;

afterEach(() => {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: originalMatchMedia,
  });
  Object.defineProperty(document, "startViewTransition", {
    configurable: true,
    writable: true,
    value: originalStartViewTransition,
  });
  vi.restoreAllMocks();
});

describe("ControlPanel", () => {
  it("launches the selected video mission with the uploaded filename", async () => {
    const user = userEvent.setup();
    const onRunSimulation = vi.fn();
    const onAccentChange = vi.fn();
    const { container } = render(
      <ControlPanel
        onRunSimulation={onRunSimulation}
        isRunning={false}
        activeTheme="blue"
        premiumThemeEntitled={false}
        onThemeChange={onAccentChange}
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

  it("activates a named free theme with keyboard and accessible pressed state", async () => {
    const user = userEvent.setup();
    const onThemeChange = vi.fn();
    const { rerender } = render(
      <ControlPanel
        onRunSimulation={vi.fn()}
        isRunning={false}
        activeTheme="blue"
        premiumThemeEntitled={false}
        onThemeChange={onThemeChange}
      />,
    );

    const red = screen.getByRole("button", { name: /Tema rojo/i });
    red.focus();
    await user.keyboard("{Enter}");
    expect(onThemeChange).toHaveBeenCalledWith("red");

    rerender(
      <ControlPanel
        onRunSimulation={vi.fn()}
        isRunning={false}
        activeTheme="red"
        premiumThemeEntitled={false}
        onThemeChange={onThemeChange}
      />,
    );
    expect(screen.getByRole("button", { name: /Tema rojo/i })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("status")).toHaveTextContent(/Tema rojo activo/i);
  });

  it("keeps premium discoverable but fail-closed without entitlement", async () => {
    const user = userEvent.setup();
    const onThemeChange = vi.fn();
    render(
      <ControlPanel
        onRunSimulation={vi.fn()}
        isRunning={false}
        activeTheme="blue"
        premiumThemeEntitled={false}
        onThemeChange={onThemeChange}
      />,
    );

    const premium = screen.getByRole("button", { name: /Tema premium/i });
    expect(premium).toHaveAttribute("aria-disabled", "true");
    await user.click(premium);
    expect(onThemeChange).not.toHaveBeenCalled();
    expect(screen.getByRole("status")).toHaveTextContent(/requiere un entitlement de pago/i);
  });

  it("activates premium only when entitlement is present", async () => {
    const user = userEvent.setup();
    const onThemeChange = vi.fn();
    render(
      <ControlPanel
        onRunSimulation={vi.fn()}
        isRunning={false}
        activeTheme="blue"
        premiumThemeEntitled
        onThemeChange={onThemeChange}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Tema premium/i }));
    expect(onThemeChange).toHaveBeenCalledWith("premium");
  });

  it("does not start a view transition when reduced motion is requested", async () => {
    const user = userEvent.setup();
    const onThemeChange = vi.fn();
    const startViewTransition = vi.fn();
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: vi.fn().mockReturnValue({ matches: true }),
    });
    Object.defineProperty(document, "startViewTransition", {
      configurable: true,
      value: startViewTransition,
    });
    render(
      <ControlPanel
        onRunSimulation={vi.fn()}
        isRunning={false}
        activeTheme="blue"
        premiumThemeEntitled={false}
        onThemeChange={onThemeChange}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Tema verde/i }));
    expect(onThemeChange).toHaveBeenCalledWith("green");
    expect(startViewTransition).not.toHaveBeenCalled();
  });

  it("launches a full campaign with five channels and an explicit flight", async () => {
    const user = userEvent.setup();
    const onRunSimulation = vi.fn();
    render(
      <ControlPanel
        onRunSimulation={onRunSimulation}
        isRunning={false}
        activeTheme="blue"
        premiumThemeEntitled={false}
        onThemeChange={vi.fn()}
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
        activeTheme="blue"
        premiumThemeEntitled={false}
        onThemeChange={vi.fn()}
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
        activeTheme="blue"
        premiumThemeEntitled={false}
        onThemeChange={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "X" }));

    expect(screen.getByRole("button", { name: /launch autonomous cycle/i })).toBeDisabled();
    expect(screen.getByText(/X is required for the 3-part thread/i)).toBeInTheDocument();
  });
});
