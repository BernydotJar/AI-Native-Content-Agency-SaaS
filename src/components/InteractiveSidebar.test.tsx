import type { ComponentProps } from "react";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { InteractiveSidebar } from "./InteractiveSidebar";

afterEach(cleanup);

type SidebarNodeData = NonNullable<ComponentProps<typeof InteractiveSidebar>["nodeData"]>;

const nodeData: SidebarNodeData = {
  id: "media",
  name: "Media Studio",
  role: "Video · image · motion",
  status: "success",
  progress: 100,
  logs: [
    {
      sender: "MediaAgent",
      message: "Generated a visual system map.",
      timestamp: "10:42:00",
    },
  ],
  files: [
    {
      name: "campaign-brief.md",
      type: "text/markdown",
      size: "12 KB",
    },
  ],
  assets: [
    {
      name: "Kleppmann trade-off map",
      type: "image",
      content: "sandbox://generated/trade-off-map.png",
      previewUrl: "sandbox://generated/trade-off-map.png",
    },
  ],
};

const renderSidebar = (
  overrides: Partial<ComponentProps<typeof InteractiveSidebar>> = {},
) => {
  const props: ComponentProps<typeof InteractiveSidebar> = {
    nodeData,
    onClose: vi.fn(),
    isApproved: false,
    onApproveToggle: vi.fn(),
    ...overrides,
  };

  return {
    ...render(<InteractiveSidebar {...props} />),
    props,
  };
};

describe("InteractiveSidebar", () => {
  it("exposes Activity and Outputs as accessible tabs", async () => {
    const user = userEvent.setup();
    renderSidebar();

    const activityTab = screen.getByRole("tab", { name: "Activity" });
    const outputsTab = screen.getByRole("tab", { name: /Outputs 1/ });

    expect(screen.getAllByRole("tab")).toHaveLength(2);
    expect(activityTab).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel")).toHaveAccessibleName("Activity");

    await user.click(outputsTab);

    expect(outputsTab).toHaveAttribute("aria-selected", "true");
    expect(activityTab).toHaveAttribute("aria-selected", "false");
    expect(screen.getByRole("tabpanel")).toHaveAccessibleName(/Outputs 1/);
  });

  it("renders the generated image output in the Outputs panel", async () => {
    const user = userEvent.setup();
    renderSidebar();

    await user.click(screen.getByRole("tab", { name: /Outputs 1/ }));

    expect(screen.getByRole("heading", { name: "Kleppmann trade-off map" })).toBeInTheDocument();
    expect(screen.getByText("Trade-off system map / generated concept")).toBeInTheDocument();
  });

  it("provides accessible close and approval controls", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const onApproveToggle = vi.fn();
    renderSidebar({ onClose, onApproveToggle });

    const closeButton = screen.getByRole("button", { name: "Cerrar detalle del agente" });
    const approvalButton = screen.getByRole("button", { name: "Pending" });

    expect(approvalButton).toHaveAttribute("aria-pressed", "false");

    await user.click(closeButton);
    await user.click(approvalButton);

    expect(onClose).toHaveBeenCalledOnce();
    expect(onApproveToggle).toHaveBeenCalledOnce();
  });
});
