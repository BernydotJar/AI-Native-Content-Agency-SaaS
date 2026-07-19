import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ControlPlaneClient } from "../api/client";
import { jsonResponse, missionFixture, runFixture } from "../test/controlPlaneFixtures";
import { IntegratedApp } from "./IntegratedApp";

afterEach(() => {
  cleanup();
});

function clientFor(request: typeof fetch) {
  let requestNumber = 0;
  return new ControlPlaneClient({
    baseUrl: "http://control-plane.test",
    tenantId: "tenant-a",
    principalId: "operator-a",
    fetchImplementation: request,
    createRequestId: () => `command-${++requestNumber}`,
  });
}

describe("IntegratedApp", () => {
  it("creates a mission, starts the persisted run and approves the exact backend manifest", async () => {
    const request = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(missionFixture(), 201))
      .mockResolvedValueOnce(jsonResponse(runFixture(), 201))
      .mockResolvedValueOnce(jsonResponse(runFixture("completed", "approved")));
    const user = userEvent.setup();
    render(<IntegratedApp client={clientFor(request)} storage={null} pollIntervalMs={0} />);

    expect(screen.getByText("INTEGRATED API MODE")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /create mission & start run/i }));

    expect(await screen.findByText(/awaiting greenlight/i)).toBeInTheDocument();
    expect(screen.getByText("risk_report · #7")).toBeInTheDocument();
    expect(screen.getByText(/Fixture policy inspection/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /approve exact manifest/i }));
    expect(await screen.findByText("Ship the sandbox manifest.")).toBeInTheDocument();

    const approvalCall = request.mock.calls[2];
    const headers = new Headers(approvalCall[1]?.headers);
    const body = JSON.parse(String(approvalCall[1]?.body));
    expect(headers.get("X-Tenant-ID")).toBe("tenant-a");
    expect(headers.get("X-Principal-ID")).toBe("operator-a");
    expect(headers.get("Idempotency-Key")).toBe("web-command-3");
    expect(body).toMatchObject({
      schema_version: "v1",
      decision: "approved",
      reviewer: "operator-a",
      artifact_manifest_hash: "a".repeat(64),
      policy_version: "greenlight.v1",
    });
  });

  it("offers a backend rejection using the same exact manifest boundary", async () => {
    const request = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(missionFixture(), 201))
      .mockResolvedValueOnce(jsonResponse(runFixture(), 201))
      .mockResolvedValueOnce(jsonResponse(runFixture("rejected", "rejected")));
    const user = userEvent.setup();
    render(<IntegratedApp client={clientFor(request)} storage={null} pollIntervalMs={0} />);

    await user.click(screen.getByRole("button", { name: /create mission & start run/i }));
    await user.type(await screen.findByRole("textbox", { name: /decision note/i }), "Claims need revision.");
    await user.click(screen.getByRole("button", { name: /^reject$/i }));

    expect(await screen.findByText("Revise the claims.")).toBeInTheDocument();
    expect(JSON.parse(String(request.mock.calls[2][1]?.body))).toMatchObject({
      decision: "rejected",
      artifact_manifest_hash: "a".repeat(64),
      policy_version: "greenlight.v1",
    });
  });

  it("restores only the opaque run ID and reconnects through backend GET", async () => {
    const storage = {
      getItem: vi.fn(() => "run-fixture-1"),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    };
    const request = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(runFixture()))
      .mockRejectedValueOnce(new Error("private transport detail"))
      .mockResolvedValueOnce(jsonResponse(runFixture()));
    const user = userEvent.setup();
    render(<IntegratedApp client={clientFor(request)} storage={storage} pollIntervalMs={0} />);

    expect(await screen.findByText("run-fixture-1")).toBeInTheDocument();
    expect(request.mock.calls[0][0]).toBe("http://control-plane.test/api/v1/runs/run-fixture-1");
    expect(new Headers(request.mock.calls[0][1]?.headers).get("Idempotency-Key")).toBeNull();

    await user.click(screen.getByRole("button", { name: /refresh persisted run/i }));
    expect(await screen.findByText("CONTROL_PLANE_UNREACHABLE")).toBeInTheDocument();
    expect(screen.queryByText(/private transport detail/i)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /reconnect/i }));
    await waitFor(() => expect(request).toHaveBeenCalledTimes(3));
    expect(screen.queryByText("CONTROL_PLANE_UNREACHABLE")).not.toBeInTheDocument();
  });

  it("polls for backend responses without fabricating intermediate progress", async () => {
    const storage = {
      getItem: vi.fn(() => "run-fixture-1"),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    };
    const request = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(runFixture("running")))
      .mockResolvedValueOnce(jsonResponse(runFixture("completed", "approved")));
    render(<IntegratedApp client={clientFor(request)} storage={storage} pollIntervalMs={10} />);

    expect(await screen.findByText(/Status running/i)).toBeInTheDocument();
    expect(screen.queryByText("Ship the sandbox manifest.")).not.toBeInTheDocument();

    expect(await screen.findByText("Ship the sandbox manifest.")).toBeInTheDocument();
    expect(request).toHaveBeenCalledTimes(2);
    expect(request.mock.calls.every(([url]) => String(url).endsWith("/api/v1/runs/run-fixture-1"))).toBe(true);
  });

  it("renders structured backend errors but never their detail payload", async () => {
    const request = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({
      schema_version: "v1",
      error: {
        code: "REQUEST_VALIDATION_FAILED",
        message: "Request did not match the versioned API contract",
        correlation_id: "corr-visible",
        details: { secret: "must-not-render" },
      },
    }, 422));
    const user = userEvent.setup();
    render(<IntegratedApp client={clientFor(request)} storage={null} pollIntervalMs={0} />);

    await user.click(screen.getByRole("button", { name: /create mission & start run/i }));

    expect(await screen.findByText("REQUEST_VALIDATION_FAILED")).toBeInTheDocument();
    expect(screen.getByText(/Correlation corr-visible/i)).toBeInTheDocument();
    expect(screen.queryByText(/must-not-render/i)).not.toBeInTheDocument();
  });

  it("reuses the same start key after an ambiguous response loss", async () => {
    const request = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(missionFixture(), 201))
      .mockRejectedValueOnce(new Error("response lost after durable commit"))
      .mockResolvedValueOnce(jsonResponse(runFixture(), 201));
    const user = userEvent.setup();
    render(<IntegratedApp client={clientFor(request)} storage={null} pollIntervalMs={0} />);

    await user.click(screen.getByRole("button", { name: /create mission & start run/i }));
    expect(await screen.findByText("CONTROL_PLANE_UNREACHABLE")).toBeInTheDocument();

    const firstStartKey = new Headers(request.mock.calls[1][1]?.headers)
      .get("Idempotency-Key");
    await user.click(screen.getByRole("button", { name: /retry start/i }));
    expect(await screen.findByText("run-fixture-1")).toBeInTheDocument();
    const retryStartKey = new Headers(request.mock.calls[2][1]?.headers)
      .get("Idempotency-Key");

    expect(firstStartKey).toBe("web-command-2");
    expect(retryStartKey).toBe(firstStartKey);
  });

  it("replays the exact Greenlight command after an ambiguous gateway timeout", async () => {
    const gatewayTimeout = jsonResponse({
      schema_version: "v1",
      error: {
        code: "GATEWAY_TIMEOUT",
        message: "The upstream response deadline expired.",
        correlation_id: "corr-timeout",
        details: {},
      },
    }, 504);
    const request = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(missionFixture(), 201))
      .mockResolvedValueOnce(jsonResponse(runFixture(), 201))
      .mockResolvedValueOnce(gatewayTimeout)
      .mockResolvedValueOnce(jsonResponse(runFixture("completed", "approved")));
    const user = userEvent.setup();
    render(<IntegratedApp client={clientFor(request)} storage={null} pollIntervalMs={0} />);

    await user.click(screen.getByRole("button", { name: /create mission & start run/i }));
    await user.click(await screen.findByRole("button", { name: /approve exact manifest/i }));
    expect(await screen.findByText("GATEWAY_TIMEOUT")).toBeInTheDocument();

    const firstApprovalKey = new Headers(request.mock.calls[2][1]?.headers)
      .get("Idempotency-Key");
    await user.click(screen.getByRole("button", { name: /retry exact approval/i }));
    expect(await screen.findByText("Ship the sandbox manifest.")).toBeInTheDocument();
    const replayKey = new Headers(request.mock.calls[3][1]?.headers)
      .get("Idempotency-Key");

    expect(firstApprovalKey).toBe("web-command-3");
    expect(replayKey).toBe(firstApprovalKey);
    expect(request.mock.calls[3][1]?.body).toBe(request.mock.calls[2][1]?.body);
  });

  it("ignores a stale poll response after a newer run becomes active", async () => {
    let resolveStaleResponse!: (response: Response) => void;
    const staleResponse = new Promise<Response>((resolve) => {
      resolveStaleResponse = resolve;
    });
    const newRun = { ...runFixture(), run_id: "run-new" };
    const staleRun = { ...runFixture(), run_id: "run-stale" };
    const request = vi.fn<typeof fetch>().mockImplementation((input, init) => {
      const url = String(input);
      if (init?.method === "GET" || url.endsWith("/api/v1/runs/run-stale")) {
        return staleResponse;
      }
      if (url.endsWith("/api/v1/missions")) {
        return Promise.resolve(jsonResponse(missionFixture(), 201));
      }
      if (url.endsWith("/runs")) {
        return Promise.resolve(jsonResponse(newRun, 201));
      }
      return Promise.reject(new Error(`Unexpected request ${url}`));
    });
    const storage = {
      getItem: vi.fn(() => "run-stale"),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    };
    const user = userEvent.setup();
    render(<IntegratedApp client={clientFor(request)} storage={storage} pollIntervalMs={0} />);

    await user.click(screen.getByRole("button", { name: /create mission & start run/i }));
    expect(await screen.findByText("run-new")).toBeInTheDocument();

    resolveStaleResponse(jsonResponse(staleRun));
    await waitFor(() => expect(request).toHaveBeenCalledTimes(3));
    expect(screen.getByText("run-new")).toBeInTheDocument();
    expect(screen.queryByText("run-stale")).not.toBeInTheDocument();
  });

  it("ignores a stale restore failure after a newer run becomes active", async () => {
    let rejectStaleResponse!: (reason: Error) => void;
    const staleResponse = new Promise<Response>((_, reject) => {
      rejectStaleResponse = reject;
    });
    const newRun = { ...runFixture(), run_id: "run-new" };
    const request = vi.fn<typeof fetch>().mockImplementation((input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/runs/run-stale")) {
        return staleResponse;
      }
      if (url.endsWith("/api/v1/missions")) {
        return Promise.resolve(jsonResponse(missionFixture(), 201));
      }
      if (url.endsWith("/runs")) {
        return Promise.resolve(jsonResponse(newRun, 201));
      }
      return Promise.reject(new Error(`Unexpected request ${url}`));
    });
    const storage = {
      getItem: vi.fn(() => "run-stale"),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    };
    const user = userEvent.setup();
    render(<IntegratedApp client={clientFor(request)} storage={storage} pollIntervalMs={0} />);

    await user.click(screen.getByRole("button", { name: /create mission & start run/i }));
    expect(await screen.findByText("run-new")).toBeInTheDocument();

    rejectStaleResponse(new Error("late failure for restored run"));
    await waitFor(() => expect(request).toHaveBeenCalledTimes(3));
    expect(screen.getByText("run-new")).toBeInTheDocument();
    expect(screen.getByText("API connected")).toBeInTheDocument();
    expect(screen.queryByText("CONTROL_PLANE_UNREACHABLE")).not.toBeInTheDocument();
  });

  it("ignores a stale polling failure after a newer run becomes active", async () => {
    let rejectStalePoll!: (reason: Error) => void;
    const stalePoll = new Promise<Response>((_, reject) => {
      rejectStalePoll = reject;
    });
    const staleRunning = { ...runFixture("running"), run_id: "run-stale" };
    const newRun = { ...runFixture(), run_id: "run-new" };
    let staleGetCount = 0;
    const request = vi.fn<typeof fetch>().mockImplementation((input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/runs/run-stale")) {
        staleGetCount += 1;
        return staleGetCount === 1
          ? Promise.resolve(jsonResponse(staleRunning))
          : stalePoll;
      }
      if (url.endsWith("/api/v1/missions")) {
        return Promise.resolve(jsonResponse(missionFixture(), 201));
      }
      if (url.endsWith("/runs")) {
        return Promise.resolve(jsonResponse(newRun, 201));
      }
      if (url.endsWith("/api/v1/runs/run-new")) {
        return Promise.resolve(jsonResponse(newRun));
      }
      return Promise.reject(new Error(`Unexpected request ${url}`));
    });
    const storage = {
      getItem: vi.fn(() => "run-stale"),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    };
    const user = userEvent.setup();
    render(<IntegratedApp client={clientFor(request)} storage={storage} pollIntervalMs={10} />);

    expect(await screen.findByText(/Status running/i)).toBeInTheDocument();
    await waitFor(() => expect(staleGetCount).toBeGreaterThanOrEqual(2));
    await user.click(screen.getByRole("button", { name: /create mission & start run/i }));
    expect(await screen.findByText("run-new")).toBeInTheDocument();

    rejectStalePoll(new Error("late polling failure"));
    await waitFor(() => expect(screen.getByText("API connected")).toBeInTheDocument());
    expect(screen.queryByText("CONTROL_PLANE_UNREACHABLE")).not.toBeInTheDocument();
  });
});
