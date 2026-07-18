import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SIMULATION_TOOL_CATALOG } from "../lib/simulationRuntime";
import { ToolFabricPanel } from "./ToolFabricPanel";

describe("ToolFabricPanel", () => {
  it("renders every sandbox tool and all four trend signals without live claims", () => {
    render(<ToolFabricPanel />);

    for (const tool of SIMULATION_TOOL_CATALOG) {
      expect(screen.getByRole("heading", { name: tool.label })).toBeInTheDocument();
    }
    expect(screen.getAllByText("Mock")).toHaveLength(8);
    expect(screen.getAllByRole("progressbar")).toHaveLength(4);
    expect(screen.getByText(/Ninguna tarjeta representa una conexión activa/i)).toBeInTheDocument();
  });
});
