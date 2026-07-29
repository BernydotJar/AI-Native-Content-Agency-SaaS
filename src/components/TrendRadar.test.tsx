import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { RuntimeApi, RuntimeTrendSnapshot } from "../lib/runtimeApi";
import { RuntimeApiError } from "../lib/runtimeApi";
import { TrendRadar } from "./TrendRadar";

const SNAPSHOT: RuntimeTrendSnapshot = {
  tenant_id: "local-tenant",
  geo: "GT",
  topic: "general",
  source: "Google Trends RSS",
  source_url: "https://trends.google.com/trending/rss?geo=GT",
  fetched_at: "2026-07-28T16:00:00+00:00",
  trends: [{
    title: "Innovación en Guatemala",
    approx_traffic: "2,000+",
    published_at: "Tue, 28 Jul 2026 12:00:00 +0000",
    news_source: "Fuente pública",
    signal_type: "search_trend",
    news_items: [{
      title: "Equipos locales adoptan inteligencia artificial",
      source: "Fuente pública",
      url: "https://example.test/evidence",
    }],
  }],
};

function api(overrides: Partial<RuntimeApi> = {}): RuntimeApi {
  return {
    createSession: vi.fn(),
    resumeSession: vi.fn(),
    currentIdentity: vi.fn(),
    createRun: vi.fn(),
    getRun: vi.fn(),
    approveRun: vi.fn(),
    rejectRun: vi.fn(),
    revokeRun: vi.fn(),
    auditEvents: vi.fn(),
    providerCatalog: vi.fn(),
    trendRadar: vi.fn().mockResolvedValue(SNAPSHOT),
    integrations: vi.fn(),
    socialChannels: vi.fn(),
    socialPublications: vi.fn(),
    startSocialOAuth: vi.fn(),
    disconnectSocialChannel: vi.fn(),
    attachPublicationMedia: vi.fn(),
    revokePublicationMedia: vi.fn(),
    publishSocial: vi.fn(),
    revokeSession: vi.fn(),
    ...overrides,
  };
}

describe("TrendRadar", () => {
  it("keeps the source locked until a session exists", () => {
    const runtime = api();
    render(<TrendRadar sessionActive={false} api={runtime} />);

    expect(screen.getByText(/Inicia sesión para investigar señales reales/i)).toBeInTheDocument();
    expect(runtime.trendRadar).not.toHaveBeenCalled();
  });

  it("renders verified evidence and prepares a no-publication pilot brief", async () => {
    const user = userEvent.setup();
    const onPreparePilot = vi.fn();
    render(<TrendRadar sessionActive api={api()} onPreparePilot={onPreparePilot} />);

    expect(await screen.findByText("Innovación en Guatemala")).toBeInTheDocument();
    expect(screen.getByText(/2,000\+ · Fuente pública · 1 evidencia/i)).toBeInTheDocument();
    await user.click(screen.getByText(/Revisar evidencia/i));
    expect(screen.getByRole("link", { name: /Equipos locales adoptan inteligencia artificial/i })).toHaveAttribute(
      "href",
      "https://example.test/evidence",
    );

    await user.click(screen.getByRole("button", { name: /Preparar piloto/i }));
    expect(onPreparePilot).toHaveBeenCalledWith(expect.objectContaining({
      source_label: expect.stringContaining("Innovación en Guatemala"),
      brief: expect.objectContaining({
        campaign_goal: "trend_response_pilot",
        campaign_type: "commercial",
        publication_mode: "organic",
        platforms: ["x", "instagram"],
        budget_cents: 0,
      }),
    }));
    expect(screen.getByRole("button", { name: /Misión precargada/i })).toBeInTheDocument();
  });

  it("switches among fixed free research lanes without accepting arbitrary queries", async () => {
    const user = userEvent.setup();
    const trendRadar = vi.fn().mockImplementation(async (topic = "general") => ({
      ...SNAPSHOT,
      topic,
      source: topic === "general" ? "Google Trends RSS" : "Google News RSS",
    }));
    render(<TrendRadar sessionActive api={api({ trendRadar })} />);

    await screen.findByText("Innovación en Guatemala");
    await user.click(screen.getByRole("tab", { name: /^IA: IA en Guatemala$/i }));
    expect(trendRadar).toHaveBeenLastCalledWith("ai");
    expect(screen.getByRole("tab", { name: /^IA: IA en Guatemala$/i })).toHaveAttribute("aria-selected", "true");
  });

  it("shows an honest unavailable state without placeholder trends", async () => {
    const runtime = api({
      trendRadar: vi.fn().mockRejectedValue(
        new RuntimeApiError(503, "unavailable", "request-1", "trend_radar_unavailable"),
      ),
    });
    render(<TrendRadar sessionActive api={runtime} />);

    expect(await screen.findByText(/Radar temporalmente no disponible/i)).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: /Señales actuales/i })).not.toBeInTheDocument();
  });
});
