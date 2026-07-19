/** Real network and persistence coverage for the integrated Compose stack. */
import {
  expect,
  test,
  type Page,
  type Response as PlaywrightResponse,
} from "@playwright/test";

import type { RunResponse } from "../src/api/contracts";

const missionPath = "/api/v1/missions";
const runPath = /^\/api\/v1\/missions\/[^/]+\/runs$/;

function apiResponse(
  page: Page,
  method: "GET" | "POST",
  pathMatches: (path: string) => boolean,
): Promise<PlaywrightResponse> {
  return page.waitForResponse((response) => {
    const path = new URL(response.url()).pathname;
    return response.request().method() === method && pathMatches(path);
  });
}

async function responseRun(response: PlaywrightResponse): Promise<RunResponse> {
  expect(response.ok(), await response.text()).toBe(true);
  return response.json() as Promise<RunResponse>;
}

function artifactIds(run: RunResponse): string[] {
  return run.artifacts.map((artifact) => artifact.artifact_id);
}

function evidenceIds(run: RunResponse): string[] {
  return run.evidence.map((evidence) => evidence.evidence_id);
}

async function expectRiskOutput(page: Page, run: RunResponse): Promise<void> {
  const riskArtifact = run.artifacts.find((artifact) => artifact.created_by === "risk");
  if (!riskArtifact) throw new Error("The persisted run omitted its risk artifact");

  const riskEvidence = run.evidence.find((evidence) =>
    riskArtifact.evidence_ids.includes(evidence.evidence_id),
  );
  if (!riskEvidence) throw new Error("The risk artifact omitted linked tool evidence");

  await page.getByRole("button", { name: /^Risk & QA\./ }).click();
  const artifacts = page.getByRole("region", { name: "Artifacts / risk" });
  const inspector = page.locator("#agent-detail");

  await expect(artifacts.getByText(riskArtifact.title, { exact: true })).toBeVisible();
  await expect(
    artifacts.getByText(`${riskArtifact.kind} · #${riskArtifact.ordinal}`, { exact: true }),
  ).toBeVisible();
  await expect(
    inspector.getByText(`${riskEvidence.tool} / ${riskEvidence.operation}`, { exact: true }),
  ).toBeVisible();
  await expect(inspector.getByText(riskEvidence.summary, { exact: true })).toBeVisible();
  expect(riskEvidence.sandbox).toBe(true);
}

async function createAwaitingRun(page: Page, title: string): Promise<RunResponse> {
  await page.goto("/");
  await expect(page.getByText("INTEGRATED API MODE", { exact: true })).toBeVisible();
  await expect(page.getByText("No publication or spend", { exact: true })).toBeVisible();
  await page.getByLabel("Mission title").fill(title);

  const missionResponse = apiResponse(
    page,
    "POST",
    (path) => path === missionPath,
  );
  const startResponse = apiResponse(
    page,
    "POST",
    (path) => runPath.test(path),
  );

  await page.getByRole("button", { name: "Create mission & start run" }).click();
  expect((await missionResponse).ok()).toBe(true);
  const run = await responseRun(await startResponse);

  expect(run.status).toBe("awaiting_greenlight");
  expect(run.external_side_effects).toBe(false);
  expect(run.artifacts.length).toBeGreaterThan(0);
  expect(run.evidence.length).toBeGreaterThan(0);
  await expect(page.getByText("Status awaiting greenlight", { exact: true })).toBeVisible();
  await expect(page.getByText(run.run_id, { exact: true })).toBeVisible();
  await expectRiskOutput(page, run);
  return run;
}

async function reloadPersistedRun(page: Page, expected: RunResponse): Promise<RunResponse> {
  const expectedPath = `/api/v1/runs/${expected.run_id}`;
  const restoredResponse = apiResponse(
    page,
    "GET",
    (path) => path === expectedPath,
  );

  await page.reload();
  const restored = await responseRun(await restoredResponse);

  expect(restored.status).toBe(expected.status);
  expect(restored.version).toBe(expected.version);
  expect(restored.artifact_manifest_hash).toBe(expected.artifact_manifest_hash);
  expect(artifactIds(restored)).toEqual(artifactIds(expected));
  expect(evidenceIds(restored)).toEqual(evidenceIds(expected));
  expect(restored.approval).toEqual(expected.approval);
  await expect(page.getByText(expected.run_id, { exact: true })).toBeVisible();
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();

  const refreshResponse = apiResponse(
    page,
    "GET",
    (path) => path === expectedPath,
  );
  await page.getByRole("button", { name: "Refresh persisted run" }).click();
  const refreshed = await responseRun(await refreshResponse);
  expect(refreshed.version).toBe(expected.version);
  expect(artifactIds(refreshed)).toEqual(artifactIds(expected));
  expect(evidenceIds(refreshed)).toEqual(evidenceIds(expected));
  return restored;
}

test("approves an exact manifest and restores its sandbox package", async ({ page }) => {
  const awaiting = await createAwaitingRun(page, "Playwright approval persistence");
  const note = "Playwright approves sandbox packaging only.";
  await page.getByRole("textbox", { name: "Decision note" }).fill(note);

  const decisionResponse = apiResponse(
    page,
    "POST",
    (path) => path === `/api/v1/runs/${awaiting.run_id}/approvals`,
  );
  await page.getByRole("button", { name: "Approve exact manifest" }).click();
  const completed = await responseRun(await decisionResponse);

  expect(completed.status).toBe("completed");
  expect(completed.approval?.decision).toBe("approved");
  expect(completed.approval?.note).toBe(note);
  expect(completed.external_side_effects).toBe(false);
  expect(completed.artifacts).toHaveLength(awaiting.artifacts.length + 1);
  expect(completed.evidence).toHaveLength(awaiting.evidence.length + 1);

  const campaignPackages = completed.artifacts.filter(
    (artifact) => artifact.kind === "campaign_package",
  );
  expect(campaignPackages).toHaveLength(1);
  expect(campaignPackages[0]?.payload.publication_performed).toBe(false);

  const campaignEvidence = completed.evidence.find((evidence) =>
    campaignPackages[0]?.evidence_ids.includes(evidence.evidence_id),
  );
  expect(campaignEvidence?.sandbox).toBe(true);
  await expect(page.getByText("Status completed", { exact: true })).toBeVisible();

  const greenlight = page.getByRole("region", { name: "Backend Greenlight" });
  await expect(greenlight.getByText("approved", { exact: true })).toBeVisible();
  await expect(greenlight.getByText(note, { exact: true })).toBeVisible();

  await page.getByRole("button", { name: /^Publisher\./ }).click();
  const publisherArtifacts = page.getByRole("region", { name: "Artifacts / publisher" });
  await expect(
    publisherArtifacts.getByText("campaign_package · #8", { exact: true }),
  ).toBeVisible();
  if (campaignEvidence) {
    await expect(
      page.locator("#agent-detail").getByText(
        `${campaignEvidence.tool} / ${campaignEvidence.operation}`,
        { exact: true },
      ),
    ).toBeVisible();
  }

  const restored = await reloadPersistedRun(page, completed);
  expect(restored.artifacts.some((artifact) => artifact.kind === "campaign_package")).toBe(true);
  await page.getByRole("button", { name: /^Publisher\./ }).click();
  await expect(
    page.getByRole("region", { name: "Artifacts / publisher" })
      .getByText("campaign_package · #8", { exact: true }),
  ).toBeVisible();
});

test("rejects an exact manifest and restores the blocked publisher state", async ({ page }) => {
  const awaiting = await createAwaitingRun(page, "Playwright rejection persistence");
  const note = "Playwright rejects this exact sandbox manifest.";
  await page.getByRole("textbox", { name: "Decision note" }).fill(note);

  const decisionResponse = apiResponse(
    page,
    "POST",
    (path) => path === `/api/v1/runs/${awaiting.run_id}/approvals`,
  );
  await page.getByRole("button", { name: "Reject" }).click();
  const rejected = await responseRun(await decisionResponse);

  expect(rejected.status).toBe("rejected");
  expect(rejected.approval?.decision).toBe("rejected");
  expect(rejected.approval?.note).toBe(note);
  expect(rejected.external_side_effects).toBe(false);
  expect(artifactIds(rejected)).toEqual(artifactIds(awaiting));
  expect(evidenceIds(rejected)).toEqual(evidenceIds(awaiting));
  expect(rejected.artifacts.some((artifact) => artifact.kind === "campaign_package")).toBe(false);
  await expect(page.getByText("Status rejected", { exact: true })).toBeVisible();

  const greenlight = page.getByRole("region", { name: "Backend Greenlight" });
  await expect(greenlight.getByText("rejected", { exact: true })).toBeVisible();
  await expect(greenlight.getByText(note, { exact: true })).toBeVisible();

  await page.getByRole("button", { name: /^Publisher\./ }).click();
  await expect(
    page.getByRole("region", { name: "Artifacts / publisher" })
      .getByText("No persisted artifacts for this step", { exact: true }),
  ).toBeVisible();

  const restored = await reloadPersistedRun(page, rejected);
  expect(restored.artifacts.some((artifact) => artifact.kind === "campaign_package")).toBe(false);
  await page.getByRole("button", { name: /^Publisher\./ }).click();
  await expect(
    page.getByRole("region", { name: "Artifacts / publisher" })
      .getByText("No persisted artifacts for this step", { exact: true }),
  ).toBeVisible();
});
