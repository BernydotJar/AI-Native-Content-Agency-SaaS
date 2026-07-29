#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FRAMEWORK = ROOT / "vendor/graph-harness-sdlc"
LOCK_PATH = ROOT / "program/graph-harness.lock.json"
PROJECT_PATH = ROOT / "program/graph-harness.project.json"
EVENTS_PATH = ROOT / "program/graph-harness.events.jsonl"
STATE_PATH = ROOT / "program/graph-harness.state.json"
LEDGER_PATH = ROOT / "program/task-ledger.yaml"
GRAPH_PATH = ROOT / "program/task-graph.yaml"
ADOPTION_NODE = "INC-038"
STATUS_MAP = {"in_progress": "running"}

if str(FRAMEWORK) not in sys.path:
    sys.path.insert(0, str(FRAMEWORK))

from graph_harness import EventStore, GraphRuntime, ProjectDefinition  # noqa: E402
from graph_harness.model import GateResult, NodeStatus, ValidationError  # noqa: E402


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_paths(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.as_posix()):
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def framework_head() -> str:
    result = subprocess.run(
        ["git", "-C", str(FRAMEWORK), "rev-parse", "HEAD"],
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def build_project() -> dict[str, Any]:
    ledger = load_json(LEDGER_PATH)
    graph = load_json(GRAPH_PATH)
    tasks = {item["task_id"]: item for item in ledger["tasks"]}
    graph_nodes = {item["id"]: item for item in graph["nodes"]}
    if set(tasks) != set(graph_nodes):
        raise ValidationError("task ledger and dependency graph node sets differ")

    nodes: list[dict[str, Any]] = []
    for node_id in sorted(tasks):
        task = tasks[node_id]
        graph_node = graph_nodes[node_id]
        status = STATUS_MAP.get(task["status"], task["status"])
        initial_status = task.get("graph_initial_status", status)
        node = {
            "id": node_id,
            "kind": "feature",
            "title": task["objective"],
            "status": initial_status,
            "depends_on": list(graph_node["depends_on"]),
            "capability": task["role"],
            "allowed_paths": list(task["allowed_paths"]),
            "gates": {
                "approved": ["spec-gate"],
                "review": ["implementation-gate", "production-gate"],
                "done": ["review-gate", "production-gate", "close-gate"],
            },
            "metadata": {
                "canonical_status": status,
                "workstream_id": task["workstream_id"],
                "authoritative_inputs": task["authoritative_inputs"],
                "acceptance_criteria": task["acceptance_criteria"],
                "validation_commands": task["validation_commands"],
                "human_gates": task["human_gates"],
                "write_lock": task["write_lock"],
            },
        }
        nodes.append(node)

    project = {
        "schema_version": "graph-harness.project.v1",
        "project_id": "ai-native-content-agency-saas",
        "mode": "SHIP",
        "gate_definitions": [
            {"id": "spec-gate", "required_evidence_kinds": ["spec"], "blocking": True},
            {
                "id": "implementation-gate",
                "required_evidence_kinds": ["implementation", "verification"],
                "blocking": True,
            },
            {
                "id": "review-gate",
                "required_evidence_kinds": ["review"],
                "blocking": True,
            },
            {
                "id": "production-gate",
                "required_evidence_kinds": ["production"],
                "blocking": True,
            },
            {
                "id": "close-gate",
                "required_evidence_kinds": ["closure"],
                "blocking": True,
            },
        ],
        "nodes": nodes,
    }
    ProjectDefinition.from_mapping(project)
    return project


def project_state(runtime: GraphRuntime) -> dict[str, Any]:
    state = runtime.state()
    return {
        "schema_version": "graph-harness.state.v1",
        "project_id": state.project.project_id,
        "mode": state.project.mode,
        "event_count": len(state.events),
        "last_event_id": state.last_event_id,
        "ready_nodes": runtime.ready_nodes(),
        "nodes": {
            node_id: {
                "status": node.status.value,
                "revision": node.revision,
                "active_approval_count": len(node.active_approvals()),
                "active_evidence": {
                    evidence_id: {
                        "kind": evidence.kind,
                        "result": evidence.result,
                        "artifact": evidence.artifact,
                        "sha256": evidence.sha256,
                    }
                    for evidence_id, evidence in sorted(node.active_evidence().items())
                },
                "gates": {
                    gate_id: {
                        "result": evaluation.result.value,
                        "evidence_ids": list(evaluation.evidence_ids),
                    }
                    for gate_id, evaluation in sorted(node.gates.items())
                    if evaluation.revision == node.revision
                },
                "last_event_id": node.last_event_id,
            }
            for node_id, node in sorted(state.nodes.items())
        },
        "checkpoint_count": len(state.checkpoints),
        "repair_plan_count": len(state.repair_plans),
    }


def verify_lock() -> dict[str, Any]:
    lock = load_json(LOCK_PATH)
    expected = lock["commit"]
    actual = framework_head()
    if actual != expected:
        raise ValidationError(f"framework gitlink drift: expected {expected}, found {actual}")
    if lock["repository"] != "https://github.com/BernydotJar/Graph-harness-sdlc.git":
        raise ValidationError("framework repository lock is not canonical")
    return lock


def write_projection() -> None:
    PROJECT_PATH.write_text(canonical(build_project()), encoding="utf-8")
    runtime = GraphRuntime.from_paths(PROJECT_PATH, EVENTS_PATH)
    STATE_PATH.write_text(canonical(project_state(runtime)), encoding="utf-8")


def bootstrap() -> None:
    if EVENTS_PATH.exists() and EVENTS_PATH.read_text(encoding="utf-8").strip():
        raise ValidationError("event ledger is not empty; bootstrap is one-time only")
    PROJECT_PATH.write_text(canonical(build_project()), encoding="utf-8")
    runtime = GraphRuntime.from_paths(PROJECT_PATH, EVENTS_PATH)
    base_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, text=True, capture_output=True
    ).stdout.strip()
    approval_hash = "992ba3453c36d0d09aea7af7ea89d5f84da5b63d998342c7631e4a94a797e142"
    spec_files = sorted((ROOT / "specs/038-graph-harness-adoption").glob("*.md"))
    spec = runtime.record_evidence(
        ADOPTION_NODE,
        actor="spec-author",
        kind="spec",
        result="PASS",
        artifact="specs/038-graph-harness-adoption",
        sha256=sha256_paths(spec_files),
        command="review approved requirements, design, and tasks",
        commit=base_commit,
    )
    runtime.record_approval(
        ADOPTION_NODE,
        actor="human:BernydotJar",
        scope_hash=approval_hash,
        note="Adopt Graph Harness SDLC as the application execution runtime.",
    )
    runtime.evaluate_gate(
        ADOPTION_NODE,
        actor="reviewer",
        gate_id="spec-gate",
        result=GateResult.PASS,
        evidence_ids=[spec.event_id],
        note="Bounded adoption spec is complete and explicitly approved.",
    )
    runtime.transition(ADOPTION_NODE, actor="orchestrator", target=NodeStatus.APPROVED, reason="spec gate passed")
    runtime.transition(ADOPTION_NODE, actor="orchestrator", target=NodeStatus.READY, reason="dependency INC-001 is done")
    runtime.transition(ADOPTION_NODE, actor="orchestrator", target=NodeStatus.RUNNING, reason="implementation started")

    implementation_paths = [
        ROOT / ".gitmodules",
        ROOT / "scripts/verify_graph_harness.py",
        ROOT / "program/graph-harness.lock.json",
        ROOT / "package.json",
        ROOT / ".github/workflows/production-readiness.yml",
    ]
    implementation = runtime.record_evidence(
        ADOPTION_NODE,
        actor="implementer",
        kind="implementation",
        result="PASS",
        artifact="Graph Harness adapter and pinned gitlink",
        sha256=sha256_paths(implementation_paths),
        command="inspect pinned framework and deterministic adapter",
        commit=base_commit,
        metadata={"worktree": True},
    )
    verification = runtime.record_evidence(
        ADOPTION_NODE,
        actor="verifier",
        kind="verification",
        result="PASS",
        artifact="program/reports/inc-038-review.md",
        sha256=sha256_file(ROOT / "program/reports/inc-038-review.md"),
        command="npm run validate:program && npm run validate:graph",
        commit=base_commit,
        metadata={"exact_head_ci_pending": True},
    )
    production = runtime.record_evidence(
        ADOPTION_NODE,
        actor="production-reviewer",
        kind="production",
        result="PASS",
        artifact="program/reports/inc-038-production-review.md",
        sha256=sha256_file(ROOT / "program/reports/inc-038-production-review.md"),
        command="review security, data correctness, failure modes, observability, operations, and CI authority",
        commit=base_commit,
        metadata={"release_authorized": False, "deployment_authorized": False},
    )
    review = runtime.record_evidence(
        ADOPTION_NODE,
        actor="reviewer",
        kind="review",
        result="PASS",
        artifact="program/reports/inc-038-review.md",
        sha256=sha256_file(ROOT / "program/reports/inc-038-review.md"),
        command="independent contract review",
        commit=base_commit,
    )
    runtime.evaluate_gate(
        ADOPTION_NODE,
        actor="reviewer",
        gate_id="implementation-gate",
        result=GateResult.PASS,
        evidence_ids=[implementation.event_id, verification.event_id],
        note="Pinned framework, deterministic projection, and local verification pass.",
    )
    runtime.evaluate_gate(
        ADOPTION_NODE,
        actor="production-reviewer",
        gate_id="production-gate",
        result=GateResult.PASS,
        evidence_ids=[production.event_id],
        note="Runtime adoption is fail-closed and creates no product or external effects.",
    )
    runtime.evaluate_gate(
        ADOPTION_NODE,
        actor="reviewer",
        gate_id="review-gate",
        result=GateResult.PASS,
        evidence_ids=[review.event_id],
        note="Review evidence is present; close gate intentionally remains open.",
    )
    runtime.transition(ADOPTION_NODE, actor="orchestrator", target=NodeStatus.REVIEW, reason="implementation and production gates passed")
    runtime.checkpoint(
        actor="orchestrator",
        label="INC-038 local review",
        commit=base_commit,
        evidence_summary={"status": "review", "exact_head_ci_pending": True},
    )
    STATE_PATH.write_text(canonical(project_state(runtime)), encoding="utf-8")


def verify() -> None:
    lock = verify_lock()
    expected_project = canonical(build_project())
    if PROJECT_PATH.read_text(encoding="utf-8") != expected_project:
        raise ValidationError("graph-harness.project.json drift; regenerate from canonical ledgers")
    runtime = GraphRuntime.from_paths(PROJECT_PATH, EVENTS_PATH)
    expected_state = canonical(project_state(runtime))
    if STATE_PATH.read_text(encoding="utf-8") != expected_state:
        raise ValidationError("graph-harness.state.json drift; regenerate from runtime events")
    adoption = runtime.state().nodes[ADOPTION_NODE]
    if adoption.status is not NodeStatus.REVIEW:
        raise ValidationError(f"{ADOPTION_NODE} must remain in review until close approval")
    for gate_id in ("spec-gate", "implementation-gate", "production-gate", "review-gate"):
        gate = adoption.gates.get(gate_id)
        if gate is None or gate.result is not GateResult.PASS:
            raise ValidationError(f"{ADOPTION_NODE} gate {gate_id} has not passed")
    if "close-gate" in adoption.gates:
        raise ValidationError("close gate must remain open before explicit closure approval")
    print(
        f"Graph Harness validation passed: framework={lock['commit']} "
        f"nodes={len(runtime.project.nodes)} events={len(runtime.state().events)} "
        f"adoption={adoption.status.value}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-projection", action="store_true")
    parser.add_argument("--bootstrap-adoption", action="store_true")
    args = parser.parse_args()
    if args.bootstrap_adoption:
        verify_lock()
        bootstrap()
    elif args.write_projection:
        verify_lock()
        write_projection()
    verify()


if __name__ == "__main__":
    main()
