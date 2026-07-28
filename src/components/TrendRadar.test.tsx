import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { RuntimeApi } from "../lib/runtimeApi";
import { RuntimeApiError } from "../lib/runtimeApi";
import { TrendRadar } from "./TrendRadar";

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
    trendRadar: vi.fn().mockResolvedValue({
      tenant_id: "local-tenant",
      geo: "GT",
      source: "Google Trends RSS",
      source_url: "https://trends.google.com/trending/rss?geo=GT",
      fetched_at: "2026-07-28T16:00:00+00:00",
      trends: [{
        title: "Innovación en Guatemala",
        approx_traffic: "2,000+",
        published_at: "Tue, 28 Jul 2026 12:00:00 +0000",
        news_source: "Fuente pública",
      }],
    }),
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

  it("renders only verified trends and their source", async () => {
    render(<TrendRadar sessionActive api={api()} />);

    expect(await screen.findByText("Innovación en Guatemala")).toBeInTheDocument();
    expect(screen.getByText(/2,000\+ · Fuente pública/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Fuente: Google Trends RSS/i })).toHaveAttribute(
      "href",
      "https://trends.google.com/trending/rss?geo=GT",
    );
  });

  it("shows an honest unavailable state without placeholder trends", async () => {
    const runtime = api({
      trendRadar: vi.fn().mockRejectedValue(
        new RuntimeApiError(503, "unavailable", "request-1", "trend_radar_unavailable"),
      ),
    });
    render(<TrendRadar sessionActive api={runtime} />);

    expect(await screen.findByText(/Radar temporalmente no disponible/i)).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: /Tendencias actuales/i })).not.toBeInTheDocument();
  });
});
