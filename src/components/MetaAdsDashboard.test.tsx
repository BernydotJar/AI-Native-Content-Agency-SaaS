import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { MetaAdsDashboard } from "./MetaAdsDashboard";
import type { MetaAdsCampaign } from "./MetaAdsDashboard";

const campaign = (
  id: string,
  spent: number,
  conversions: number,
  cac: number,
): MetaAdsCampaign => ({
  id,
  name: `Sandbox ${id}`,
  budget: 500,
  spent,
  ctr: 2,
  cac,
  impressions: 1000,
  conversions,
  status: "active",
  targeting: {
    demographics: "Test audience",
    interests: ["Systems"],
    locations: ["Sandbox"],
  },
});

describe("MetaAdsDashboard", () => {
  it("derives aggregate CAC from total spend and conversions", () => {
    render(
      <MetaAdsDashboard
        campaigns={[campaign("a", 100, 10, 10), campaign("b", 100, 2, 50)]}
        isSyncing={false}
        onSync={vi.fn()}
      />,
    );

    expect(screen.getByText("$16.67")).toBeInTheDocument();
    expect(screen.getAllByRole("progressbar")).toHaveLength(2);
  });

  it("keeps the adapter action explicitly simulated", async () => {
    const user = userEvent.setup();
    const onSync = vi.fn();
    render(<MetaAdsDashboard campaigns={[]} isSyncing={false} onSync={onSync} />);

    await user.click(screen.getByRole("button", { name: /Simular sincronización/i }));

    expect(onSync).toHaveBeenCalledOnce();
    expect(screen.getByText(/sin gasto ni conexión externa/i)).toBeInTheDocument();
  });
});
