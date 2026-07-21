import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { runtimeApi } from "./lib/runtimeApi";

afterEach(() => {
  vi.useRealTimers();
  document.documentElement.removeAttribute("data-theme");
  document.documentElement.removeAttribute("data-theme-tier");
  document.documentElement.removeAttribute("style");
  vi.restoreAllMocks();
});

describe("campaign approval gate", () => {
  it("holds Publisher until approval and cancels pending work when approval is revoked", () => {
    vi.useFakeTimers();
    render(<App />);

    const lockedGate = screen.getByRole("button", { name: "Awaiting QA" });
    expect(lockedGate).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: /launch autonomous cycle/i }));
    act(() => vi.advanceTimersByTime(18 * 1200 + 10));

    expect(screen.getByRole("button", { name: /Publisher.*Standby, 0%/i })).toBeInTheDocument();
    const pendingGate = screen.getByRole("button", { name: "Pending" });
    expect(pendingGate).toBeEnabled();

    fireEvent.click(pendingGate);
    act(() => vi.advanceTimersByTime(0.25 * 1200 + 10));

    expect(screen.getByRole("button", { name: /Publisher.*Processing, 30%/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Approved" }));

    expect(screen.getByRole("button", { name: /Publisher.*Attention, 30%/i })).toBeInTheDocument();
  });

  it("builds the writer pack from the operator thesis instead of a fixed template", () => {
    vi.useFakeTimers();
    render(<App />);

    fireEvent.change(screen.getByRole("textbox", { name: /campaign thesis/i }), {
      target: { value: "Why reversible AI experiments beat platform bets" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: /audience/i }), {
      target: { value: "AI product leaders" },
    });
    fireEvent.click(screen.getByRole("button", { name: /launch autonomous cycle/i }));
    act(() => vi.advanceTimersByTime(12 * 1200 + 10));

    fireEvent.click(screen.getByRole("button", { name: /Writer.*Complete/i }));
    fireEvent.click(screen.getByRole("tab", { name: /Outputs/i }));

    expect(screen.getByText(/1\/3 AI product leaders/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Why reversible AI experiments beat platform bets/i).length).toBeGreaterThan(1);
    expect(screen.getByText(/Newsletter \/ Scholar Edition/i)).toBeInTheDocument();
    expect(screen.queryByText(/1\/5/)).not.toBeInTheDocument();
  });

  it("recalls operator memory and enabled skills during the next campaign", () => {
    vi.useFakeTimers();
    render(<App />);

    fireEvent.click(screen.getByRole("switch", { name: /Activar Churn Prevention/i }));
    fireEvent.change(screen.getByRole("textbox", { name: /Add session memory flag/i }), {
      target: { value: "Use cautious claims and reversible experiments" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Store flag/i }));
    fireEvent.click(screen.getByRole("button", { name: /launch autonomous cycle/i }));
    act(() => vi.advanceTimersByTime(7 * 1200 + 10));

    expect(screen.getByText(/Skills:.*churn-prevention/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Research.*Complete/i }));
    expect(screen.getByText(/Memoria recuperada: Use cautious claims and reversible experiments/i)).toBeInTheDocument();
  });

  it("stores CEO feedback before a completed run can be replaced", () => {
    vi.useFakeTimers();
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: /launch autonomous cycle/i }));
    act(() => vi.advanceTimersByTime(18 * 1200 + 10));
    fireEvent.click(screen.getByRole("button", { name: "Pending" }));
    act(() => vi.advanceTimersByTime(3 * 1200 + 10));

    expect(screen.getByText(/Synthetic Meta metrics → CEO feedback/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /launch autonomous cycle/i }));
    act(() => vi.advanceTimersByTime(6 * 1200 + 10));
    fireEvent.click(screen.getByRole("button", { name: /Research.*Complete/i }));

    expect(screen.getByText(/Memoria recuperada: Priorizar el hook/i)).toBeInTheDocument();
  });
});

describe("accessible theme application", () => {
  it("unlocks premium only from the server-issued session entitlement", async () => {
    vi.spyOn(runtimeApi, "resumeSession").mockResolvedValue({
      tenant_id: "tenant-premium",
      subject_id: "premium@example.com",
      role: "viewer",
      key_id: "premium-v1",
      entitlements: ["theme:premium"],
      csrf_token: "csrf-premium",
      expires_at: "2026-07-22T00:00:00+00:00",
    });
    vi.spyOn(runtimeApi, "auditEvents").mockResolvedValue([]);
    vi.spyOn(runtimeApi, "currentIdentity").mockResolvedValue({
      tenant_id: "tenant-premium", subject_id: "premium@example.com", role: "viewer",
      key_id: "premium-v1", permissions: ["identity:read", "runs:read", "audit:read"],
      entitlements: ["theme:premium"], auth_method: "session",
    });
    render(<App />);

    await screen.findByText("premium@example.com");
    const premium = screen.getByRole("button", { name: /Tema premium/i });
    expect(premium).toHaveAttribute("aria-disabled", "false");
    fireEvent.click(premium);

    expect(document.documentElement).toHaveAttribute("data-theme", "premium");
    expect(document.documentElement).toHaveAttribute("data-theme-tier", "premium");
  });

  it("falls back to the free default when the server revokes premium", async () => {
    vi.spyOn(runtimeApi, "resumeSession").mockResolvedValue({
      tenant_id: "tenant-premium", subject_id: "premium@example.com", role: "viewer",
      key_id: "premium-v1", entitlements: ["theme:premium"], csrf_token: "csrf-premium",
      expires_at: "2026-07-22T00:00:00+00:00",
    });
    vi.spyOn(runtimeApi, "auditEvents").mockResolvedValue([]);
    vi.spyOn(runtimeApi, "currentIdentity")
      .mockResolvedValueOnce({
        tenant_id: "tenant-premium", subject_id: "premium@example.com", role: "viewer",
        key_id: "premium-v1", permissions: [], entitlements: ["theme:premium"], auth_method: "session",
      })
      .mockResolvedValueOnce({
        tenant_id: "tenant-premium", subject_id: "premium@example.com", role: "viewer",
        key_id: "premium-v1", permissions: [], entitlements: [], auth_method: "session",
      });
    render(<App />);

    await screen.findByText("premium@example.com");
    fireEvent.click(screen.getByRole("button", { name: /Tema premium/i }));
    expect(document.documentElement).toHaveAttribute("data-theme", "premium");
    fireEvent.click(screen.getByRole("button", { name: /Refresh durable audit/i }));
    await waitFor(() => expect(document.documentElement).toHaveAttribute("data-theme", "blue"));
  });

  it("keeps premium fail-closed without a server entitlement and stores nothing", () => {
    const storageSpy = vi.spyOn(Storage.prototype, "setItem");
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: /Tema premium/i }));

    expect(document.documentElement).toHaveAttribute("data-theme", "blue");
    expect(screen.getByText(/requiere un entitlement de pago/i)).toBeInTheDocument();
    expect(storageSpy).not.toHaveBeenCalled();
  });

  it("applies a named free theme to semantic document tokens", () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: /Tema naranja/i }));

    expect(document.documentElement).toHaveAttribute("data-theme", "orange");
    expect(document.documentElement).toHaveAttribute("data-theme-tier", "free");
    expect(document.documentElement.style.getPropertyValue("--primary-color")).toBe("#fdba74");
  });
});
