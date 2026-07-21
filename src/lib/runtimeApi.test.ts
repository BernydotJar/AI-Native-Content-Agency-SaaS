import { describe, expect, it, vi } from "vitest";
import { createRuntimeApi, RuntimeApiError } from "./runtimeApi";

function jsonResponse(payload: object, status = 200, requestId = "request-test-0001") {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json",
      "X-Request-ID": requestId,
    },
  });
}

describe("runtime API client", () => {
  it("exchanges the API key once and uses cookie credentials plus CSRF", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({
        tenant_id: "tenant-alpha",
        subject_id: "operator@example.com",
        role: "operator",
        key_id: "operator-v2",
        entitlements: ["theme:premium"],
        csrf_token: "csrf-token-123",
        expires_at: "2026-07-21T20:00:00+00:00",
      }, 201))
      .mockResolvedValueOnce(jsonResponse({
        run_id: "run-123",
        tenant_id: "tenant-alpha",
        status: "awaiting_greenlight",
        agent_states: {},
        artifacts: [],
        greenlight: null,
        sandbox: true,
        external_side_effects_enabled: false,
      }, 201));
    const api = createRuntimeApi(fetchMock as typeof fetch);

    await api.createSession("one-time-browser-api-key-value");
    await api.createRun({
      title: "Runtime test",
      objective: "Verify browser session transport",
      audience: "operators",
      platforms: ["x"],
      budget_cents: 0,
      campaign_goal: "verification",
    }, "csrf-token-123", "run-create-client-0001");

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/v1/sessions", expect.objectContaining({
      method: "POST",
      credentials: "include",
      body: JSON.stringify({ api_key: "one-time-browser-api-key-value" }),
    }));
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/v1/runs", expect.objectContaining({
      method: "POST",
      credentials: "include",
      headers: expect.objectContaining({
        "X-CSRF-Token": "csrf-token-123",
        "Idempotency-Key": "run-create-client-0001",
      }),
    }));
    expect(JSON.stringify(fetchMock.mock.calls[1])).not.toContain("one-time-browser-api-key-value");
  });

  it("sends explicit idempotency keys for Greenlight decisions and revocation", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValue(jsonResponse({
        run_id: "run-1",
        tenant_id: "tenant-alpha",
        status: "revoked",
        agent_states: {},
        artifacts: [],
        greenlight: null,
        sandbox: true,
        external_side_effects_enabled: false,
      }));
    const api = createRuntimeApi(fetchMock as typeof fetch);

    await api.approveRun("run-1", "csrf", "approve-key-0001");
    await api.rejectRun("run-1", "csrf", "reject-key-0001");
    await api.revokeRun("run-1", "csrf", "revoke-key-0001");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/v1/runs/run-1/greenlight/approve",
      expect.objectContaining({
        headers: expect.objectContaining({ "Idempotency-Key": "approve-key-0001" }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/runs/run-1/greenlight/reject",
      expect.objectContaining({
        headers: expect.objectContaining({ "Idempotency-Key": "reject-key-0001" }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/v1/runs/run-1/greenlight/revoke",
      expect.objectContaining({
        headers: expect.objectContaining({ "Idempotency-Key": "revoke-key-0001" }),
      }),
    );
  });

  it("resumes an HttpOnly session without a browser-stored API key", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({
      tenant_id: "tenant-alpha",
      subject_id: "operator@example.com",
      role: "operator",
      key_id: "operator-v2",
      entitlements: [],
      csrf_token: "rotated-csrf-token",
      expires_at: "2026-07-21T21:00:00+00:00",
    }));
    const api = createRuntimeApi(fetchMock as typeof fetch);

    await expect(api.resumeSession()).resolves.toEqual(expect.objectContaining({
      tenant_id: "tenant-alpha",
      subject_id: "operator@example.com",
      role: "operator",
      key_id: "operator-v2",
      entitlements: [],
      csrf_token: "rotated-csrf-token",
    }));
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/sessions/current",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("loads the current server-derived identity entitlement", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({
      tenant_id: "tenant-alpha",
      subject_id: "admin@example.com",
      role: "admin",
      key_id: "admin-v2",
      permissions: ["identity:read"],
      entitlements: ["theme:premium"],
      auth_method: "session",
    }));
    const api = createRuntimeApi(fetchMock as typeof fetch);

    await expect(api.currentIdentity()).resolves.toEqual(
      expect.objectContaining({ entitlements: ["theme:premium"] }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/me",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("loads one tenant-scoped run and preserves retry metadata", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({
        run_id: "run-123",
        tenant_id: "tenant-alpha",
        status: "awaiting_greenlight",
        agent_states: {},
        artifacts: [],
        greenlight: null,
        sandbox: true,
        external_side_effects_enabled: false,
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        code: "authentication_rate_limited",
        detail: "authentication temporarily rate limited",
        request_id: "request-rate-0001",
      }), {
        status: 429,
        headers: {
          "Content-Type": "application/json",
          "X-Request-ID": "request-rate-0001",
          "Retry-After": "30",
        },
      }));
    const api = createRuntimeApi(fetchMock as typeof fetch);

    await expect(api.getRun("run-123")).resolves.toEqual(
      expect.objectContaining({ run_id: "run-123" }),
    );
    await expect(api.createSession("invalid-key")).rejects.toEqual(
      expect.objectContaining<Partial<RuntimeApiError>>({
        status: 429,
        code: "authentication_rate_limited",
        requestId: "request-rate-0001",
        retryAfterSeconds: 30,
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/v1/runs/run-123",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("preserves the safe public error code and request correlation", async () => {
    const api = createRuntimeApi(vi.fn().mockResolvedValue(
      jsonResponse({
        code: "request_verification_failed",
        detail: "request verification failed",
        request_id: "request-error-0001",
      }, 403, "request-error-0001"),
    ) as typeof fetch);

    await expect(
      api.rejectRun("run-1", "bad-csrf", "greenlight-reject-client-0001"),
    ).rejects.toEqual(
      expect.objectContaining<Partial<RuntimeApiError>>({
        status: 403,
        code: "request_verification_failed",
        requestId: "request-error-0001",
        message: "request verification failed",
      }),
    );
  });
});
