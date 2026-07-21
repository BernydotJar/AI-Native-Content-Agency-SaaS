import { afterEach, describe, expect, it } from "vitest";
import {
  DEFAULT_THEME_ID,
  THEME_CATALOG,
  applyTheme,
  contrastRatio,
  isThemeAvailable,
} from "./themeCatalog";

afterEach(() => {
  document.documentElement.removeAttribute("data-theme");
  document.documentElement.removeAttribute("data-theme-tier");
  document.documentElement.removeAttribute("style");
});

describe("theme catalog", () => {
  it("defines four free political-neutral themes and one premium theme", () => {
    expect(THEME_CATALOG.map((theme) => theme.id)).toEqual([
      "blue",
      "red",
      "green",
      "orange",
      "premium",
    ]);
    expect(THEME_CATALOG.filter((theme) => !theme.premium)).toHaveLength(4);
    expect(THEME_CATALOG.find((theme) => theme.id === "premium")).toEqual(
      expect.objectContaining({ premium: true, paidEntitlement: "theme:premium" }),
    );
    expect(DEFAULT_THEME_ID).toBe("blue");
  });

  it("fails premium closed without the server-derived entitlement", () => {
    const premium = THEME_CATALOG.find((theme) => theme.id === "premium")!;
    const blue = THEME_CATALOG.find((theme) => theme.id === "blue")!;

    expect(isThemeAvailable(blue, false)).toBe(true);
    expect(isThemeAvailable(premium, false)).toBe(false);
    expect(isThemeAvailable(premium, true)).toBe(true);
  });

  it.each(THEME_CATALOG)("meets contrast contracts for $id", (theme) => {
    expect(contrastRatio(theme.text, theme.background)).toBeGreaterThanOrEqual(7);
    expect(contrastRatio(theme.muted, theme.background)).toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio(theme.accent, theme.background)).toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio(theme.accentForeground, theme.accent)).toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio(theme.accent, theme.panelSolid)).toBeGreaterThanOrEqual(3);
  });

  it("applies semantic tokens and machine-readable theme state", () => {
    applyTheme("red", document.documentElement);

    expect(document.documentElement).toHaveAttribute("data-theme", "red");
    expect(document.documentElement).toHaveAttribute("data-theme-tier", "free");
    expect(document.documentElement.style.getPropertyValue("--primary-color")).toBe("#fb7185");
    expect(document.documentElement.style.getPropertyValue("--bg-obsidian")).toBe("#10080b");
    expect(document.documentElement.style.getPropertyValue("--theme-accent-foreground")).toBe("#09090b");
    expect(document.documentElement.style.getPropertyValue("--text-muted")).toBe("#a1a1aa");
    expect(document.documentElement.style.getPropertyValue("--border-cyber")).toBe("#4c1d2a");
  });
});
