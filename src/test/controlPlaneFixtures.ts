import type {
  AgentRole,
  ApprovalDecision,
  ApprovalResponse,
  ArtifactResponse,
  MissionResponse,
  RunResponse,
  RunStatus,
  RunStepResponse,
} from "../api/contracts";

const TIMESTAMP = "2026-07-18T12:00:00Z";
const ROLES: readonly AgentRole[] = ["ceo", "research", "strategist", "growth", "writer", "media", "risk", "publisher"];

export function missionFixture(
  overrides: Partial<MissionResponse> = {},
): MissionResponse {
  return {
    schema_version: "v1",
    mission_id: "mission-fixture-1",
    tenant_id: "tenant-a",
    created_by: "operator-a",
    title: "Evidence-led operating model launch",
    objective: "Explain a reversible decision system.",
    audience: "Engineering leaders",
    platforms: ["x", "facebook", "tiktok", "instagram"],
    budget_cents: 350_000,
    source_asset: "sandbox://web/mission-brief",
    campaign_goal: "qualified_demand",
    created_at: TIMESTAMP,
    version: 1,
    ...overrides,
  };
}

export function runFixture(
  status: RunStatus = "awaiting_greenlight",
  decision: ApprovalDecision | null = null,
): RunResponse {
  const approval: ApprovalResponse | null = decision
    ? {
        schema_version: "v1" as const,
        approval_id: `approval-${decision}`,
        decision,
        reviewer: "operator-a",
        note: decision === "approved" ? "Ship the sandbox manifest." : "Revise the claims.",
        artifact_manifest_hash: "a".repeat(64),
        policy_version: "greenlight.v1",
        principal_id: "operator-a",
        decided_at: TIMESTAMP,
      }
    : null;
  const steps: RunStepResponse[] = ROLES.map((role, index) => ({
    schema_version: "v1",
    step_id: `step-${role}`,
    role,
    sequence: index + 1,
    status: role === "publisher"
      ? status === "completed" ? "ready" : status === "rejected" ? "blocked" : "waiting_greenlight"
      : "ready",
    progress: role === "publisher" && status === "awaiting_greenlight" ? 0 : 100,
    detail: role === "publisher"
      ? status === "awaiting_greenlight" ? "Manual Greenlight is required." : "Decision persisted."
      : `${role} artifact persisted.`,
    updated_at: TIMESTAMP,
  }));
  const artifacts: ArtifactResponse[] = [
    {
      schema_version: "v1",
      artifact_id: "artifact-risk-1",
      kind: "risk_report",
      title: "Pre-Greenlight risk report",
      created_by: "risk",
      payload: { passed: true, human_greenlight_required: true },
      evidence_ids: ["evidence-risk-1"],
      ordinal: 7,
      created_at: TIMESTAMP,
    },
    ...(status === "completed" ? [{
      schema_version: "v1" as const,
      artifact_id: "artifact-package-1",
      kind: "campaign_package",
      title: "Sandbox campaign manifest",
      created_by: "publisher" as const,
      payload: { publication_performed: false },
      evidence_ids: [],
      ordinal: 8,
      created_at: TIMESTAMP,
    }] : []),
  ];

  return {
    schema_version: "v1",
    run_id: "run-fixture-1",
    mission_id: "mission-fixture-1",
    tenant_id: "tenant-a",
    status,
    artifact_manifest_hash: "a".repeat(64),
    policy_version: "greenlight.v1",
    external_side_effects: false,
    started_at: TIMESTAMP,
    completed_at: status === "awaiting_greenlight" ? null : TIMESTAMP,
    version: decision ? 2 : 1,
    steps,
    artifacts,
    evidence: [{
      schema_version: "v1",
      evidence_id: "evidence-risk-1",
      tool: "github_codebase",
      operation: "inspect_fixture",
      sandbox: true,
      summary: "Fixture policy inspection; no GitHub request.",
      payload: { changes_performed: false },
      references: ["sandbox://github_codebase/inspect_fixture"],
      created_at: TIMESTAMP,
    }],
    events: [{
      schema_version: "v1",
      event_id: "event-risk-1",
      sequence: 14,
      timestamp: TIMESTAMP,
      role: "risk",
      action: "artifact_ready",
      status: "ready",
      detail: "Risk passed; Greenlight remains required.",
      artifact_ids: ["artifact-risk-1"],
      evidence_ids: ["evidence-risk-1"],
    }],
    audit_events: [{
      schema_version: "v1",
      audit_id: "audit-run-started-1",
      principal_id: "operator-a",
      action: "run.started",
      payload: { mission_id: "mission-fixture-1", external_side_effects: false },
      correlation_id: "corr-run-started",
      occurred_at: TIMESTAMP,
    }],
    approval,
  };
}

export function jsonResponse(body: unknown, status = 200, correlation = "corr-fixture"): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      "X-Correlation-ID": correlation,
    },
  });
}
