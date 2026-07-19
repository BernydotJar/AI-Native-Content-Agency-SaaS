/** Container-restart persistence proof kept separate from decision-path tests. */
import { execFile } from "node:child_process";
import { promisify } from "node:util";

import { expect, test } from "@playwright/test";

import type { RunResponse } from "../src/api/contracts";

const execFileAsync = promisify(execFile);

test("restores the same PostgreSQL run after the API container restarts", async ({
  page,
  request,
}) => {
  test.setTimeout(180_000);
  test.skip(
    process.env.E2E_RESTART_PERSISTENCE !== "1",
    "the restart scenario requires the Compose-owned stack lifecycle",
  );
  const composeProject = process.env.COMPOSE_PROJECT_NAME ?? "";
  if (!/^agency-e2e-[a-z0-9_-]+$/.test(composeProject)) {
    throw new Error(
      "restart persistence requires an owned disposable agency-e2e-* Compose project",
    );
  }

  await page.goto("/");
  await page.getByLabel("Mission title").fill("Playwright container restart persistence");
  const startResponse = page.waitForResponse((response) => {
    const path = new URL(response.url()).pathname;
    return (
      response.request().method() === "POST" &&
      /^\/api\/v1\/missions\/[^/]+\/runs$/.test(path)
    );
  });
  await page.getByRole("button", { name: "Create mission & start run" }).click();
  const startedResponse = await startResponse;
  expect(startedResponse.status(), await startedResponse.text()).toBe(201);
  const started = (await startedResponse.json()) as RunResponse;
  expect(started.status).toBe("awaiting_greenlight");
  expect(started.external_side_effects).toBe(false);

  // `compose start app` traverses the completed one-shot migration dependency
  // and can report failure even after the application is healthy. Restart only
  // the already-created app service; readiness below proves it came back.
  await execFileAsync("docker", ["compose", "restart", "--timeout", "10", "app"], {
    timeout: 60_000,
  });

  await expect
    .poll(
      async () => {
        try {
          return (await request.get("/readyz")).status();
        } catch {
          return 0;
        }
      },
      { timeout: 90_000 },
    )
    .toBe(200);

  const restoredResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      new URL(response.url()).pathname === `/api/v1/runs/${started.run_id}`,
  );
  await page.reload();
  const restoredHttp = await restoredResponse;
  expect(restoredHttp.status(), await restoredHttp.text()).toBe(200);
  const restored = (await restoredHttp.json()) as RunResponse;
  expect(restored.run_id).toBe(started.run_id);
  expect(restored.version).toBe(started.version);
  expect(restored.artifact_manifest_hash).toBe(started.artifact_manifest_hash);
  expect(restored.artifacts).toEqual(started.artifacts);
  expect(restored.evidence).toEqual(started.evidence);
  expect(restored.external_side_effects).toBe(false);
  await expect(page.getByText(started.run_id, { exact: true })).toBeVisible();
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();
});
