import type { NodeState } from "../components/PipelineGraph";
import type { RunResponse, RunStepResponse } from "../api/contracts";

export const AGENT_ROLES = [
  "ceo",
  "research",
  "strategist",
  "growth",
  "writer",
  "media",
  "risk",
  "publisher",
] as const;

export type AgentRole = (typeof AGENT_ROLES)[number];

const DEFAULT_NODE_STATE: NodeState = {
  status: "idle",
  progress: 0,
  itemsCount: 0,
  itemsLabel: "artifacts",
};

function visualStatus(status: string): NodeState["status"] {
  if (status === "ready" || status === "completed") return "success";
  if (status === "processing" || status === "running") return "running";
  if (["failed", "blocked", "attention", "rejected"].includes(status)) return "error";
  return "idle";
}

export function isAgentRole(value: string): value is AgentRole {
  return (AGENT_ROLES as readonly string[]).includes(value);
}

export function nodeStatesFromRun(run: RunResponse | null): Record<string, NodeState> {
  const states: Record<string, NodeState> = {
    ingestion: run
      ? { status: "success", progress: 100, itemsCount: 1, itemsLabel: "mission" }
      : { ...DEFAULT_NODE_STATE, itemsLabel: "mission" },
  };

  for (const role of AGENT_ROLES) {
    const step = run?.steps.find((candidate) => candidate.role === role);
    states[role] = step
      ? {
          status: visualStatus(step.status),
          progress: step.progress,
          itemsCount: run?.artifacts.filter((artifact) => artifact.created_by === role).length ?? 0,
          itemsLabel: "artifacts",
        }
      : { ...DEFAULT_NODE_STATE };
  }
  return states;
}

export function activeRoleFromRun(run: RunResponse | null): string {
  if (!run) return "";
  const processing = run.steps.find((step) => ["processing", "running"].includes(step.status));
  if (processing) return processing.role;
  if (run.status === "awaiting_greenlight") return "publisher";
  return "";
}

export function selectedStep(run: RunResponse | null, role: string): RunStepResponse | null {
  if (!run || !isAgentRole(role)) return null;
  return run.steps.find((step) => step.role === role) ?? null;
}

export function isTerminalRun(status: string): boolean {
  return ["completed", "rejected", "failed"].includes(status);
}
