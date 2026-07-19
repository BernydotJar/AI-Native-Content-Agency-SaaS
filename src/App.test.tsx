import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DemoApp } from "./control-plane/DemoApp";

afterEach(() => {
  vi.useRealTimers();
});

describe("explicit legacy demo campaign approval gate", () => {
  it("holds Publisher until approval and cancels pending work when approval is revoked", () => {
    vi.useFakeTimers();
    render(<DemoApp />);

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
    render(<DemoApp />);

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
    render(<DemoApp />);

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
    render(<DemoApp />);

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
