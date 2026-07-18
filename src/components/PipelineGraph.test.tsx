import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PipelineGraph } from "./PipelineGraph";
import type { NodeState } from "./PipelineGraph";

afterEach(cleanup);

const nodeStates: Record<string, NodeState> = {
  ingestion: { status: "idle", progress: 0, itemsCount: 0, itemsLabel: "signals" },
  ceo: { status: "idle", progress: 0, itemsCount: 0, itemsLabel: "briefs" },
  research: { status: "success", progress: 100, itemsCount: 2, itemsLabel: "sources" },
  strategist: { status: "idle", progress: 0, itemsCount: 0, itemsLabel: "plans" },
  growth: { status: "running", progress: 64, itemsCount: 3, itemsLabel: "channels" },
  writer: { status: "idle", progress: 0, itemsCount: 0, itemsLabel: "drafts" },
  media: { status: "idle", progress: 0, itemsCount: 0, itemsLabel: "assets" },
  risk: { status: "idle", progress: 0, itemsCount: 0, itemsLabel: "checks" },
  publisher: { status: "idle", progress: 0, itemsCount: 0, itemsLabel: "campaigns" },
};

describe("PipelineGraph", () => {
  it("renders all nine agent nodes, including Growth, as accessible buttons", () => {
    render(
      <PipelineGraph
        activeStep="growth"
        nodeStates={nodeStates}
        selectedNodeId="growth"
        onNodeSelect={vi.fn()}
      />,
    );

    const nodeButtons = screen.getAllByRole("button");
    const growthButton = screen.getByRole("button", { name: /Growth\. Territory · distribution/i });

    expect(nodeButtons).toHaveLength(9);
    expect(growthButton).toHaveAttribute("aria-pressed", "true");
    expect(growthButton).toHaveAttribute("aria-controls", "agent-detail");
  });

  it("reports a node selection through the public callback", async () => {
    const user = userEvent.setup();
    const onNodeSelect = vi.fn();

    render(
      <PipelineGraph
        activeStep=""
        nodeStates={nodeStates}
        selectedNodeId={null}
        onNodeSelect={onNodeSelect}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Growth\. Territory · distribution/i }));

    expect(onNodeSelect).toHaveBeenCalledOnce();
    expect(onNodeSelect).toHaveBeenCalledWith("growth");
  });

  it("uses a percentage coordinate system for the SVG topology", () => {
    const { container } = render(
      <PipelineGraph
        activeStep=""
        nodeStates={nodeStates}
        selectedNodeId={null}
        onNodeSelect={vi.fn()}
      />,
    );

    const topology = container.querySelector("svg");

    expect(topology).toHaveAttribute("viewBox", "0 0 100 100");
    expect(topology).toHaveAttribute("preserveAspectRatio", "none");
    expect(topology).toHaveAttribute("aria-hidden", "true");
  });
});
