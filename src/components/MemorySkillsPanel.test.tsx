import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { MemorySkillsPanel } from "./MemorySkillsPanel";

describe("MemorySkillsPanel", () => {
  it("exposes controlled skills and submits an operator memory flag", async () => {
    const user = userEvent.setup();
    const onToggleSkill = vi.fn();
    const onAddMemoryFlag = vi.fn();
    render(
      <MemorySkillsPanel
        enabledSkills={{
          "scholar-nlp": true,
          "ai-seo": true,
          "churn-prevention": false,
          "brand-guard": true,
        }}
        memoryFlags={[]}
        onToggleSkill={onToggleSkill}
        onAddMemoryFlag={onAddMemoryFlag}
      />,
    );

    await user.click(screen.getByRole("switch", { name: /Activar Churn Prevention/i }));
    expect(onToggleSkill).toHaveBeenCalledWith("churn-prevention");

    await user.type(
      screen.getByRole("textbox", { name: /Add session memory flag/i }),
      "  Prefer reversible experiments over certainty.  ",
    );
    await user.click(screen.getByRole("button", { name: /Store flag/i }));

    expect(onAddMemoryFlag).toHaveBeenCalledWith("Prefer reversible experiments over certainty.");
  });
});
