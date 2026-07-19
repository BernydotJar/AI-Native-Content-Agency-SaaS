import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
});

describe("runtime mode boundary", () => {
  it("selects the persisted API experience by default", () => {
    vi.stubEnv("VITE_RUNTIME_MODE", "");
    render(<App />);

    expect(screen.getByText("INTEGRATED API MODE")).toBeInTheDocument();
    expect(screen.queryByText("LEGACY DEMO MODE")).not.toBeInTheDocument();
  });

  it("selects the isolated timer simulation only when explicitly configured", () => {
    vi.stubEnv("VITE_RUNTIME_MODE", "demo");
    render(<App />);

    expect(screen.getByText("LEGACY DEMO MODE")).toBeInTheDocument();
    expect(screen.queryByText("INTEGRATED API MODE")).not.toBeInTheDocument();
  });
});
