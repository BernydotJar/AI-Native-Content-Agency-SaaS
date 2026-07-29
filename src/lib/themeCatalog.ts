export type ThemeId = "blue" | "red" | "green" | "orange" | "premium";

export interface ThemeDefinition {
  id: ThemeId;
  label: string;
  description: string;
  premium: boolean;
  paidEntitlement?: "theme:premium";
  hue: number;
  saturation: string;
  lightness: string;
  accent: string;
  accentForeground: string;
  background: string;
  panel: string;
  panelSolid: string;
  text: string;
  muted: string;
  border: string;
}

const SHARED_TEXT = "#f4f4f5";
const SHARED_MUTED = "#a1a1aa";
const SHARED_ACCENT_FOREGROUND = "#09090b";

export const DEFAULT_THEME_ID: ThemeId = "blue";

export const THEME_CATALOG: readonly ThemeDefinition[] = [
  {
    id: "blue",
    label: "Tema azul",
    description: "Azul institucional de alto contraste.",
    premium: false,
    hue: 213,
    saturation: "94%",
    lightness: "68%",
    accent: "#60a5fa",
    accentForeground: SHARED_ACCENT_FOREGROUND,
    background: "#070b12",
    panel: "#0a101b",
    panelSolid: "#0b1220",
    text: SHARED_TEXT,
    muted: SHARED_MUTED,
    border: "#334155",
  },
  {
    id: "red",
    label: "Tema rojo",
    description: "Rojo editorial con superficies oscuras neutras.",
    premium: false,
    hue: 350,
    saturation: "95%",
    lightness: "72%",
    accent: "#fb7185",
    accentForeground: SHARED_ACCENT_FOREGROUND,
    background: "#10080b",
    panel: "#160b10",
    panelSolid: "#1c0d13",
    text: SHARED_TEXT,
    muted: SHARED_MUTED,
    border: "#4c1d2a",
  },
  {
    id: "green",
    label: "Tema verde",
    description: "Verde cívico con estados siempre reforzados por texto.",
    premium: false,
    hue: 142,
    saturation: "69%",
    lightness: "58%",
    accent: "#4ade80",
    accentForeground: SHARED_ACCENT_FOREGROUND,
    background: "#07100b",
    panel: "#09160e",
    panelSolid: "#0b1c12",
    text: SHARED_TEXT,
    muted: SHARED_MUTED,
    border: "#14532d",
  },
  {
    id: "orange",
    label: "Tema naranja",
    description: "Naranja de energía operativa y lectura clara.",
    premium: false,
    hue: 29,
    saturation: "96%",
    lightness: "72%",
    accent: "#fdba74",
    accentForeground: SHARED_ACCENT_FOREGROUND,
    background: "#120c07",
    panel: "#181008",
    panelSolid: "#20140a",
    text: SHARED_TEXT,
    muted: SHARED_MUTED,
    border: "#7c2d12",
  },
  {
    id: "premium",
    label: "Tema premium",
    description: "Violeta premium; requiere entitlement de pago emitido por el servidor.",
    premium: true,
    paidEntitlement: "theme:premium",
    hue: 250,
    saturation: "95%",
    lightness: "85%",
    accent: "#c4b5fd",
    accentForeground: SHARED_ACCENT_FOREGROUND,
    background: "#0d0a16",
    panel: "#120e20",
    panelSolid: "#18112a",
    text: SHARED_TEXT,
    muted: SHARED_MUTED,
    border: "#4c1d95",
  },
] as const;

export function getTheme(themeId: ThemeId): ThemeDefinition {
  const theme = THEME_CATALOG.find((candidate) => candidate.id === themeId);
  if (!theme) throw new Error("unknown theme");
  return theme;
}

export function isThemeAvailable(theme: ThemeDefinition, premiumThemeEntitled: boolean): boolean {
  return !theme.premium || premiumThemeEntitled;
}

function channelToLinear(channel: number): number {
  const normalized = channel / 255;
  return normalized <= 0.04045
    ? normalized / 12.92
    : ((normalized + 0.055) / 1.055) ** 2.4;
}

function relativeLuminance(hex: string): number {
  if (!/^#[0-9a-f]{6}$/i.test(hex)) throw new Error("theme colors must use six-digit hex values");
  const red = Number.parseInt(hex.slice(1, 3), 16);
  const green = Number.parseInt(hex.slice(3, 5), 16);
  const blue = Number.parseInt(hex.slice(5, 7), 16);
  return 0.2126 * channelToLinear(red)
    + 0.7152 * channelToLinear(green)
    + 0.0722 * channelToLinear(blue);
}

export function contrastRatio(foregroundHex: string, backgroundHex: string): number {
  const foreground = relativeLuminance(foregroundHex);
  const background = relativeLuminance(backgroundHex);
  const lighter = Math.max(foreground, background);
  const darker = Math.min(foreground, background);
  return (lighter + 0.05) / (darker + 0.05);
}

export function applyTheme(
  themeId: ThemeId,
  root: HTMLElement = document.documentElement,
): ThemeDefinition {
  const theme = getTheme(themeId);
  root.dataset.theme = theme.id;
  root.dataset.themeTier = theme.premium ? "premium" : "free";
  root.style.setProperty("--primary-hue", String(theme.hue));
  root.style.setProperty("--primary-saturation", theme.saturation);
  root.style.setProperty("--primary-lightness", theme.lightness);
  root.style.setProperty("--primary-color", theme.accent);
  root.style.setProperty("--primary-color-raw", `color-mix(in srgb, ${theme.accent} 46%, transparent)`);
  root.style.setProperty("--primary-color-glow", `color-mix(in srgb, ${theme.accent} 18%, transparent)`);
  root.style.setProperty("--theme-accent-foreground", theme.accentForeground);
  root.style.setProperty("--bg-obsidian", theme.background);
  root.style.setProperty("--bg-panel", theme.panel);
  root.style.setProperty("--bg-panel-solid", theme.panelSolid);
  root.style.setProperty("--text-light", theme.text);
  root.style.setProperty("--text-muted", theme.muted);
  root.style.setProperty("--theme-border", theme.border);
  root.style.setProperty("--border-cyber", theme.border);
  root.style.setProperty("--border-cyber-focus", theme.accent);
  return theme;
}
