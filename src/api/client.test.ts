import { describe, expect, it, vi } from "vitest";
import { ControlPlaneApiError, ControlPlaneClient } from "./client";
import { jsonResponse, missionFixture, runFixture } from "../test/controlPlaneFixtures";

function buildClient(fetchImplementation: typeof fetch, ids = ["request-1", "request-2", "request-3"]) {
  let index = 0;
  return new ControlPlaneClient({
    baseUrl: "http://control-plane.test/",
    tenantId: "tenant-a",
    principalId: "operator-a",
    fetchImplementation,
    createRequestId: () => ids[index++] ?? `request-${index}`,
  });
}

describe("ControlPlaneClient", () => {
  it("sends identity, correlation and a fresh idempotency key on every command", async () => {
    const request = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(missionFixture(), 201))
      .mockResolvedValueOnce(jsonResponse(runFixture(), 201))
      .mockResolvedValueOnce(jsonResponse(runFixture("completed", "approved")));
    const client = buildClient(request);

    await client.createMission({
      title: "Mission",
      objective: "Objective",
      audience: "Audience",
      platforms: ["x"],
      budget_cents: 100,
      source_asset: "sandbox://fixture",
      campaign_goal: "awareness",
    });
    await client.startRun("mission-fixture-1");
    await client.decideRun("run-fixture-1", {
      decision: "approved",
      reviewer: "operator-a",
      artifactManifestHash: "a".repeat(64),
      policyVersion: "greenlight.v1",
    });

    expect(request).toHaveBeenCalledTimes(3);
    const expectedPaths = [
      "/api/v1/missions",
      "/api/v1/missions/mission-fixture-1/runs",
      "/api/v1/runs/run-fixture-1/approvals",
    ];
    request.mock.calls.forEach(([url, init], index) => {
      const headers = new Headers(init?.headers);
      expect(url).toBe(`http://control-plane.test${expectedPaths[index]}`);
      expect(headers.get("X-Tenant-ID")).toBe("tenant-a");
      expect(headers.get("X-Principal-ID")).toBe("operator-a");
      expect(headers.get("X-Correlation-ID")).toBe(`web-request-${index + 1}`);
      expect(headers.get("Idempotency-Key")).toBe(`web-request-${index + 1}`);
    });
    expect(new Set(request.mock.calls.map(([, init]) => new Headers(init?.headers).get("Idempotency-Key"))).size).toBe(3);
  });

  it("keeps GET read-only while preserving tenant and principal context", async () => {
    const request = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(runFixture()));
    const client = buildClient(request);

    await client.getRun("run fixture/1");

    const [url, init] = request.mock.calls[0];
    const headers = new Headers(init?.headers);
    expect(url).toBe("http://control-plane.test/api/v1/runs/run%20fixture%2F1");
    expect(headers.get("Idempotency-Key")).toBeNull();
    expect(headers.get("X-Tenant-ID")).toBe("tenant-a");
  });

  it("reuses a caller-owned key when retrying an ambiguous mutable command", async () => {
    const request = vi.fn<typeof fetch>()
      .mockRejectedValueOnce(new Error("response lost after commit"))
      .mockResolvedValueOnce(jsonResponse(runFixture(), 201));
    const client = buildClient(request, ["logical-start"]);
    const idempotencyKey = client.createIdempotencyKey();

    await expect(client.startRun("mission-fixture-1", { idempotencyKey })).rejects.toMatchObject({
      code: "CONTROL_PLANE_UNREACHABLE",
    });
    await client.startRun("mission-fixture-1", { idempotencyKey });

    expect(request).toHaveBeenCalledTimes(2);
    expect(request.mock.calls.map(([, init]) => (
      new Headers(init?.headers).get("Idempotency-Key")
    ))).toEqual(["web-logical-start", "web-logical-start"]);
    expect(request.mock.calls.map(([, init]) => (
      new Headers(init?.headers).get("X-Correlation-ID")
    ))).toEqual(["web-logical-start", "web-logical-start"]);
  });

  it("rejects an invalid caller-owned idempotency key before transport", async () => {
    const request = vi.fn<typeof fetch>();
    const client = buildClient(request);

    await expect(client.startRun("mission-fixture-1", { idempotencyKey: "spaces are invalid" }))
      .rejects.toThrow(/command-key contract/);
    expect(request).not.toHaveBeenCalled();
  });

  it("supports same-origin API paths for the default deployment topology", async () => {
    const request = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(runFixture()));
    const client = new ControlPlaneClient({
      baseUrl: "",
      tenantId: "tenant-a",
      principalId: "operator-a",
      fetchImplementation: request,
      createRequestId: () => "same-origin",
    });

    await client.getRun("run-fixture-1");

    expect(request.mock.calls[0][0]).toBe("/api/v1/runs/run-fixture-1");
  });

  it("surfaces the structured backend error envelope without rewriting it", async () => {
    const request = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({
      schema_version: "v1",
      error: {
        code: "REQUEST_VALIDATION_FAILED",
        message: "Request did not match the versioned API contract",
        correlation_id: "corr-safe",
        details: { issues: [{ location: ["body", "title"] }] },
      },
    }, 422));
    const client = buildClient(request);

    const failure = await client.createMission({
      title: "",
      objective: "Objective",
      audience: "Audience",
      platforms: ["x"],
      budget_cents: 0,
      source_asset: "sandbox://fixture",
      campaign_goal: "awareness",
    }).catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(ControlPlaneApiError);
    expect(failure).toMatchObject({
      status: 422,
      code: "REQUEST_VALIDATION_FAILED",
      correlationId: "corr-safe",
    });
  });

  it("redacts transport exceptions behind a stable safe error", async () => {
    const request = vi.fn<typeof fetch>().mockRejectedValue(new Error("token=must-not-render"));
    const client = buildClient(request);

    await expect(client.getRun("run-1")).rejects.toMatchObject({
      code: "CONTROL_PLANE_UNREACHABLE",
      correlationId: "unavailable",
      message: "The control-plane outcome is unknown. Refresh authoritative state or retry the exact command with its original idempotency key.",
    });
    await expect(client.getRun("run-1")).rejects.not.toThrow(/must-not-render/);
  });
});
