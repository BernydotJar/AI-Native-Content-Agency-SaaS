#!/usr/bin/env python3
"""Fail-closed validation for program state and product version surfaces."""

from __future__ import annotations

import argparse
import ast
import configparser
import csv
import json
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

TASK_STATES = {
    "pending",
    "spec_ready",
    "approved",
    "in_progress",
    "review",
    "done",
    "blocked",
    "superseded",
}
AUDIT_CLASSIFICATIONS = {
    "proven",
    "contradicted",
    "incomplete",
    "weak_evidence",
    "missing",
    "not_applicable_with_justification",
}
FINDING_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}
FINDING_STATUSES = {"OPEN", "IN_PROGRESS", "CLOSED", "BLOCKED_EXTERNAL", "ACCEPTED"}
REQUIRED_DOMAINS = {
    "governance",
    "product",
    "engineering",
    "data",
    "security",
    "ux",
    "operations",
    "delivery",
    "testing",
    "legal",
    "integrations",
    "supply_chain",
}
REQUIRED_FILES = {
    "program/current-state.md",
    "program/product-roadmap.md",
    "program/release-plan.md",
    "program/architecture.md",
    "program/constitution.md",
    "program/task-ledger.yaml",
    "program/task-graph.yaml",
    "program/decision-log.md",
    "program/requirements-traceability.csv",
    "program/evidence-register.jsonl",
    "program/eval-results.json",
    "program/critique-findings.json",
    "program/risk-register.md",
    "program/open-issues.md",
    "program/skill-usage-register.md",
    "program/documentation-evidence.md",
    "program/session-metrics.json",
    "program/reports/completion-audit-001.md",
    "specs/001-program-baseline/spec.md",
    "specs/001-program-baseline/plan.md",
    "specs/001-program-baseline/tasks.md",
    "specs/002-backup-restore/spec.md",
}
TRACEABILITY_COLUMNS = {
    "requirement_id",
    "domain",
    "requirement",
    "classification",
    "authoritative_evidence",
    "next_action",
    "owner",
}
TASK_CONTRACT_FIELDS = {
    "task_id",
    "workstream_id",
    "role",
    "objective",
    "context",
    "authoritative_inputs",
    "dependencies",
    "allowed_paths",
    "read_only_paths",
    "prohibited_paths",
    "write_lock",
    "expected_outputs",
    "acceptance_criteria",
    "validation_commands",
    "human_gates",
    "status",
}
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


class ProgramValidationError(ValueError):
    """Raised when a program-state invariant is violated."""


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProgramValidationError(f"{path}: invalid JSON-compatible content: {error}") from error


def non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def unique_ids(items: Sequence[Mapping[str, Any]], key: str, label: str) -> set[str]:
    identifiers: set[str] = set()
    for index, item in enumerate(items):
        identifier = item.get(key)
        if not non_empty_string(identifier):
            raise ProgramValidationError(f"{label}[{index}].{key}: required non-empty string")
        if identifier in identifiers:
            raise ProgramValidationError(f"{label}: duplicate {key} {identifier!r}")
        identifiers.add(identifier)
    return identifiers


def validate_required_files(root: Path) -> None:
    missing = sorted(path for path in REQUIRED_FILES if not (root / path).is_file())
    if missing:
        raise ProgramValidationError("missing required program files: " + ", ".join(missing))


def validate_task_ledger(data: Mapping[str, Any]) -> set[str]:
    if data.get("schema_version") != "program-task-ledger.v1":
        raise ProgramValidationError("program/task-ledger.yaml: unsupported schema_version")
    workstreams = data.get("workstreams")
    tasks = data.get("tasks")
    if not isinstance(workstreams, list) or not workstreams:
        raise ProgramValidationError("program/task-ledger.yaml: workstreams must be a non-empty list")
    if not isinstance(tasks, list) or not tasks:
        raise ProgramValidationError("program/task-ledger.yaml: tasks must be a non-empty list")

    workstream_ids = unique_ids(workstreams, "id", "workstreams")
    expected_workstreams = {f"WS-{number:02d}" for number in range(1, 13)}
    if workstream_ids != expected_workstreams:
        raise ProgramValidationError(
            "program/task-ledger.yaml: workstream coverage mismatch "
            f"missing={sorted(expected_workstreams - workstream_ids)} "
            f"extra={sorted(workstream_ids - expected_workstreams)}"
        )
    for index, workstream in enumerate(workstreams):
        status = workstream.get("status")
        if status not in TASK_STATES:
            raise ProgramValidationError(f"workstreams[{index}].status: invalid state {status!r}")
        if not non_empty_string(workstream.get("next_ready_task")):
            raise ProgramValidationError(f"workstreams[{index}].next_ready_task: required")

    task_ids = unique_ids(tasks, "task_id", "tasks")
    for index, task in enumerate(tasks):
        missing_fields = sorted(TASK_CONTRACT_FIELDS - set(task))
        if missing_fields:
            raise ProgramValidationError(f"tasks[{index}]: missing contract fields {missing_fields}")
        if task.get("workstream_id") not in workstream_ids:
            raise ProgramValidationError(
                f"tasks[{index}].workstream_id: unknown {task.get('workstream_id')!r}"
            )
        if task.get("status") not in TASK_STATES:
            raise ProgramValidationError(f"tasks[{index}].status: invalid {task.get('status')!r}")
        for field in (
            "authoritative_inputs",
            "dependencies",
            "allowed_paths",
            "read_only_paths",
            "prohibited_paths",
            "expected_outputs",
            "acceptance_criteria",
            "validation_commands",
            "human_gates",
        ):
            if not isinstance(task.get(field), list):
                raise ProgramValidationError(f"tasks[{index}].{field}: must be a list")
        unknown_dependencies = sorted(set(task["dependencies"]) - task_ids)
        if unknown_dependencies:
            raise ProgramValidationError(
                f"tasks[{index}].dependencies: unknown tasks {unknown_dependencies}"
            )

    unknown_next = sorted(
        {item["next_ready_task"] for item in workstreams} - task_ids
    )
    if unknown_next:
        raise ProgramValidationError(f"workstreams: unknown next_ready_task values {unknown_next}")
    return task_ids


def validate_task_graph(data: Mapping[str, Any], task_ids: set[str]) -> None:
    if data.get("schema_version") != "program-task-graph.v1":
        raise ProgramValidationError("program/task-graph.yaml: unsupported schema_version")
    nodes = data.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise ProgramValidationError("program/task-graph.yaml: nodes must be a non-empty list")
    node_ids = unique_ids(nodes, "id", "nodes")
    if node_ids != task_ids:
        raise ProgramValidationError(
            "program/task-graph.yaml: node/task mismatch "
            f"missing={sorted(task_ids - node_ids)} extra={sorted(node_ids - task_ids)}"
        )

    dependencies: dict[str, tuple[str, ...]] = {}
    for index, node in enumerate(nodes):
        if node.get("status") not in TASK_STATES:
            raise ProgramValidationError(f"nodes[{index}].status: invalid {node.get('status')!r}")
        depends_on = node.get("depends_on")
        if not isinstance(depends_on, list):
            raise ProgramValidationError(f"nodes[{index}].depends_on: must be a list")
        unknown = sorted(set(depends_on) - node_ids)
        if unknown:
            raise ProgramValidationError(f"nodes[{index}].depends_on: unknown nodes {unknown}")
        if node["id"] in depends_on:
            raise ProgramValidationError(f"nodes[{index}].depends_on: self dependency")
        dependencies[node["id"]] = tuple(depends_on)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str, path: tuple[str, ...]) -> None:
        if node_id in visiting:
            cycle = " -> ".join((*path, node_id))
            raise ProgramValidationError(f"program/task-graph.yaml: dependency cycle {cycle}")
        if node_id in visited:
            return
        visiting.add(node_id)
        for dependency in dependencies[node_id]:
            visit(dependency, (*path, node_id))
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in sorted(node_ids):
        visit(node_id, ())

    blockers = data.get("blockers")
    if not isinstance(blockers, list):
        raise ProgramValidationError("program/task-graph.yaml: blockers must be a list")
    required = {
        "id",
        "category",
        "evidence",
        "attempted_resolutions",
        "retry_count",
        "affected_workstreams",
        "independent_work_remaining",
        "exact_resume_condition",
    }
    for index, blocker in enumerate(blockers):
        missing = sorted(required - set(blocker))
        if missing:
            raise ProgramValidationError(f"blockers[{index}]: missing fields {missing}")
        if not non_empty_string(blocker.get("exact_resume_condition")):
            raise ProgramValidationError(f"blockers[{index}].exact_resume_condition: required")


def load_traceability(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if set(reader.fieldnames or ()) != TRACEABILITY_COLUMNS:
                raise ProgramValidationError(
                    f"{path}: columns must equal {sorted(TRACEABILITY_COLUMNS)}"
                )
            return list(reader)
    except OSError as error:
        raise ProgramValidationError(f"{path}: {error}") from error


def validate_traceability(rows: Sequence[Mapping[str, str]]) -> None:
    if not rows:
        raise ProgramValidationError("traceability: at least one requirement is required")
    unique_ids(rows, "requirement_id", "traceability")
    domains: set[str] = set()
    for index, row in enumerate(rows):
        classification = row.get("classification")
        if classification not in AUDIT_CLASSIFICATIONS:
            raise ProgramValidationError(
                f"traceability[{index}].classification: invalid {classification!r}"
            )
        domain = row.get("domain", "")
        if domain not in REQUIRED_DOMAINS:
            raise ProgramValidationError(f"traceability[{index}].domain: invalid {domain!r}")
        domains.add(domain)
        for field in ("requirement", "authoritative_evidence", "next_action", "owner"):
            if not non_empty_string(row.get(field)):
                raise ProgramValidationError(f"traceability[{index}].{field}: required")
    missing_domains = sorted(REQUIRED_DOMAINS - domains)
    if missing_domains:
        raise ProgramValidationError(f"traceability: missing domains {missing_domains}")


def validate_evidence_jsonl(path: Path) -> None:
    required = {
        "artifact",
        "commit",
        "environment",
        "gate",
        "limitations",
        "observed",
        "result",
        "scope",
        "timestamp",
    }
    count = 0
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        count += 1
        try:
            item = json.loads(line)
        except json.JSONDecodeError as error:
            raise ProgramValidationError(f"{path}:{line_number}: invalid JSON: {error}") from error
        missing = sorted(required - set(item))
        if missing:
            raise ProgramValidationError(f"{path}:{line_number}: missing fields {missing}")
        if not all(non_empty_string(item[field]) for field in required):
            raise ProgramValidationError(f"{path}:{line_number}: required fields must be non-empty")
    if count == 0:
        raise ProgramValidationError(f"{path}: at least one evidence record is required")


def validate_findings(data: Mapping[str, Any]) -> None:
    if data.get("schema_version") != "program-critique-findings.v1":
        raise ProgramValidationError("program/critique-findings.json: unsupported schema_version")
    findings = data.get("findings")
    if not isinstance(findings, list):
        raise ProgramValidationError("program/critique-findings.json: findings must be a list")
    unique_ids(findings, "id", "findings")
    for index, finding in enumerate(findings):
        if finding.get("severity") not in FINDING_SEVERITIES:
            raise ProgramValidationError(f"findings[{index}].severity: invalid")
        if finding.get("status") not in FINDING_STATUSES:
            raise ProgramValidationError(f"findings[{index}].status: invalid")
        for field in ("description", "evidence", "owner"):
            if not non_empty_string(finding.get(field)):
                raise ProgramValidationError(f"findings[{index}].{field}: required")


def version_from_module(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for statement in tree.body:
        if not isinstance(statement, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == "VERSION" for target in statement.targets):
            value = ast.literal_eval(statement.value)
            if isinstance(value, str):
                return value
    raise ProgramValidationError(f"{path}: VERSION string assignment not found")


def validate_versions(root: Path) -> str:
    package = read_json(root / "package.json")
    lock = read_json(root / "package-lock.json")
    config = configparser.ConfigParser()
    config.read(root / "backend/setup.cfg", encoding="utf-8")
    try:
        setup_version = config["metadata"]["version"].strip()
    except KeyError as error:
        raise ProgramValidationError("backend/setup.cfg: metadata.version missing") from error

    chart_text = (root / "infra/helm/ai-native-content-agency/Chart.yaml").read_text(
        encoding="utf-8"
    )
    chart_version = re.search(r"(?m)^version:\s*([^\s]+)\s*$", chart_text)
    app_version = re.search(r'(?m)^appVersion:\s*"?([^"\s]+)"?\s*$', chart_text)
    docker_text = (root / "Dockerfile").read_text(encoding="utf-8")
    oci_version = re.search(r'org\.opencontainers\.image\.version="([^"]+)"', docker_text)
    values = {
        "package.json": package.get("version"),
        "package-lock.json": lock.get("version"),
        "package-lock root package": (lock.get("packages") or {}).get("", {}).get("version"),
        "backend/setup.cfg": setup_version,
        "backend/agency_runtime/version.py": version_from_module(
            root / "backend/agency_runtime/version.py"
        ),
        "Helm chart version": chart_version.group(1) if chart_version else None,
        "Helm appVersion": app_version.group(1) if app_version else None,
        "OCI label": oci_version.group(1) if oci_version else None,
    }
    if any(not isinstance(value, str) for value in values.values()):
        raise ProgramValidationError(f"version surfaces missing: {values}")
    if len(set(values.values())) != 1:
        raise ProgramValidationError(f"version drift: {values}")
    version = next(iter(values.values()))
    if not VERSION_PATTERN.fullmatch(version):
        raise ProgramValidationError(f"invalid semantic version {version!r}")

    api_text = (root / "backend/agency_runtime/api.py").read_text(encoding="utf-8")
    metrics_text = (root / "backend/agency_runtime/observability.py").read_text(
        encoding="utf-8"
    )
    if "version=VERSION" not in api_text:
        raise ProgramValidationError("backend/agency_runtime/api.py: FastAPI must use VERSION")
    if "from .version import VERSION" not in metrics_text:
        raise ProgramValidationError("observability metrics must import shared VERSION")
    return version


def validate_documents(root: Path) -> None:
    current_state = (root / "program/current-state.md").read_text(encoding="utf-8")
    if "DENY_RELEASE" not in current_state or "DENY_APPLY" not in current_state:
        raise ProgramValidationError(
            "program/current-state.md: DENY_RELEASE and DENY_APPLY must remain explicit"
        )
    readme = (root / "README.md").read_text(encoding="utf-8")
    banned = {
        "sin fetch, WebSocket ni llamada al backend": "frontend transport claim is stale",
        "falta PostgreSQL, identidad individual": "PostgreSQL/identity gap claim is stale",
        "PostgreSQL, almacenamiento de objetos y sincronización cloud": "PostgreSQL is implemented",
    }
    for text, reason in banned.items():
        if text in readme:
            raise ProgramValidationError(f"README.md: {reason}: {text!r}")
    if "program/current-state.md" not in readme:
        raise ProgramValidationError("README.md: must link to program/current-state.md")


def validate_eval_results(data: Mapping[str, Any]) -> None:
    if data.get("schema_version") != "program-eval-results.v1":
        raise ProgramValidationError("program/eval-results.json: unsupported schema_version")
    results = data.get("results")
    if not isinstance(results, list) or not results:
        raise ProgramValidationError("program/eval-results.json: results required")
    unique_ids(results, "id", "eval results")
    commit = data.get("source_commit")
    if not non_empty_string(commit) or not re.fullmatch(r"[0-9a-f]{7,40}", commit):
        raise ProgramValidationError("program/eval-results.json: invalid source_commit")


def validate_session_metrics(data: Mapping[str, Any]) -> None:
    if data.get("schema_version") != "program-session-metrics.v1":
        raise ProgramValidationError("program/session-metrics.json: unsupported schema_version")
    for field in (
        "frontend_tests_passed",
        "frontend_tests_failed",
        "baseline_ci_jobs_passed",
        "baseline_ci_jobs_failed",
        "critical_findings_open",
        "high_findings_open_or_blocked",
        "commits_created",
        "pushes_verified",
    ):
        value = data.get(field)
        if not isinstance(value, int) or value < 0:
            raise ProgramValidationError(f"program/session-metrics.json: {field} must be >= 0")


def validate_repository(root: Path) -> dict[str, Any]:
    validate_required_files(root)
    task_ids = validate_task_ledger(read_json(root / "program/task-ledger.yaml"))
    validate_task_graph(read_json(root / "program/task-graph.yaml"), task_ids)
    rows = load_traceability(root / "program/requirements-traceability.csv")
    validate_traceability(rows)
    validate_evidence_jsonl(root / "program/evidence-register.jsonl")
    validate_findings(read_json(root / "program/critique-findings.json"))
    validate_eval_results(read_json(root / "program/eval-results.json"))
    validate_session_metrics(read_json(root / "program/session-metrics.json"))
    version = validate_versions(root)
    validate_documents(root)
    return {
        "status": "pass",
        "version": version,
        "requirements": len(rows),
        "tasks": len(task_ids),
        "required_files": len(REQUIRED_FILES),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON result")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = validate_repository(args.root.resolve())
    except (ProgramValidationError, OSError) as error:
        if args.json:
            print(json.dumps({"status": "fail", "error": str(error)}, sort_keys=True))
        else:
            print(f"program_state=fail\nerror={error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print("program_state=pass")
        print(f"version={result['version']}")
        print(f"requirements={result['requirements']}")
        print(f"tasks={result['tasks']}")
        print(f"required_files={result['required_files']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
