#!/usr/bin/env python3
"""Validate production-foundation governance artifacts as executable evidence."""

from __future__ import annotations

import argparse
import csv
import fnmatch
import json
import re
from pathlib import Path
from typing import Any, Mapping

import yaml

from scripts.eval_harness import (
    CatalogError,
    load_catalog,
    traceability_requirement_ids,
    traceability_statuses,
    validate_catalog_coverage,
    validate_report,
)


ROOT = Path(__file__).resolve().parents[1]
REQUIREMENT_PATTERN = re.compile(
    r"^\| ((?:APP|SEC|DLV|GCP|GOV)-\d{3}) \|", re.MULTILINE
)
RISK_PATTERN = re.compile(r"^\| (RISK-\d{3}) \|", re.MULTILINE)
REQUIRED_AGENT_FILES = (
    "agent/current-state.md",
    "agent/task-graph.yaml",
    "agent/task-ledger.yaml",
    "agent/requirements-traceability.csv",
    "agent/decision-log.md",
    "agent/evidence-register.jsonl",
    "agent/eval-catalog.json",
    "agent/eval-results.json",
    "agent/critique-findings.json",
    "agent/risk-register.md",
    "agent/open-issues.md",
)
REQUIRED_TASK_KEYS = {
    "task_id",
    "role",
    "objective",
    "inputs",
    "dependencies",
    "allowed_paths",
    "read_only_paths",
    "write_lock",
    "expected_outputs",
    "acceptance_criteria",
    "validation",
    "prohibited_actions",
    "status",
    "owner",
}
TASK_STRING_KEYS = {"task_id", "role", "objective", "status", "owner"}
TASK_LIST_KEYS = REQUIRED_TASK_KEYS - TASK_STRING_KEYS
TASK_NONEMPTY_LIST_KEYS = TASK_LIST_KEYS - {"dependencies", "write_lock"}
TASK_STATUSES = {
    "TODO",
    "IN_PROGRESS",
    "PASS",
    "PARTIAL",
    "FAILED",
    "BLOCKED",
}
ACTIVE_TASK_STATUSES = {"IN_PROGRESS"}
MANDATORY_PHASE_TASKS = (
    "TASK-BACKEND-PRODUCER-003",
    "TASK-E2E-CI-PRODUCER-003",
    "TASK-BACKEND-CRITIC-003",
    "TASK-BACKEND-FIXER-006",
    "EVAL-INC-004",
    "APPLY-DEV-001",
    "VERIFY-DEV-001",
)
TRACE_STATUSES = {
    "PASS",
    "FAIL",
    "BLOCKED",
    "PARTIAL",
    "OUT_OF_SCOPE",
    "DEFERRED_WITH_REASON",
    "BLOCKED_BY_EXTERNAL_DEPENDENCY",
}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


class _UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects silently overwritten governance fields."""


def _construct_unique_mapping(
    loader: _UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _read_yaml(path: Path) -> Any:
    return yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)


def _unique_nonempty(values: list[str], label: str) -> tuple[bool, str]:
    if not values or any(not value for value in values):
        return False, f"{label} contains a blank value or is empty"
    if len(set(values)) != len(values):
        return False, f"{label} contains duplicates"
    return True, f"{label} contains {len(values)} unique values"


def _task_contract_check(ledger: Mapping[str, Any]) -> tuple[bool, str]:
    tasks = ledger.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        return False, "task ledger has no tasks"
    errors: list[str] = []
    identifiers: list[str] = []
    task_records: list[Mapping[str, Any]] = []
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            errors.append(f"tasks[{index}] is not an object")
            continue
        task_records.append(task)
        task_id = task.get("task_id")
        identifiers.append(task_id.strip() if isinstance(task_id, str) else "")
        missing = sorted(REQUIRED_TASK_KEYS - set(task))
        if missing:
            errors.append(f"{task.get('task_id', index)} missing {','.join(missing)}")
        context = str(task_id or index)
        for key in TASK_STRING_KEYS:
            if key not in task:
                continue
            if not isinstance(task[key], str) or not task[key].strip():
                errors.append(f"{context}.{key} must be a non-empty string")
        if isinstance(task.get("status"), str) and task["status"] not in TASK_STATUSES:
            errors.append(f"{context}.status is invalid: {task['status']}")
        for key in TASK_LIST_KEYS:
            if key not in task:
                continue
            value = task[key]
            if not isinstance(value, list):
                errors.append(f"{context}.{key} is not a list")
                continue
            if key in TASK_NONEMPTY_LIST_KEYS and not value:
                errors.append(f"{context}.{key} must not be empty")
            if any(not isinstance(item, str) or not item.strip() for item in value):
                errors.append(f"{context}.{key} contains a blank or non-string value")
            normalized = [item.strip() for item in value if isinstance(item, str)]
            if len(set(normalized)) != len(normalized):
                errors.append(f"{context}.{key} contains duplicates")
    unique, detail = _unique_nonempty(identifiers, "task IDs")
    if not unique:
        errors.append(detail)
    declared = set(identifiers)
    for task in task_records:
        task_id = str(task.get("task_id", ""))
        dependencies = task.get("dependencies", [])
        if not isinstance(dependencies, list):
            continue
        unknown = sorted(
            dependency
            for dependency in dependencies
            if isinstance(dependency, str) and dependency not in declared
        )
        if unknown:
            errors.append(f"{task_id}.dependencies unknown: {','.join(unknown)}")
        if task_id in dependencies:
            errors.append(f"{task_id}.dependencies contains itself")
    return not errors, "; ".join(errors) if errors else detail


def _cycle(adjacency: Mapping[str, set[str]]) -> list[str]:
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def visit(node: str) -> list[str]:
        if node in visiting:
            return stack[stack.index(node) :] + [node]
        if node in visited:
            return []
        visiting.add(node)
        stack.append(node)
        for successor in sorted(adjacency.get(node, set())):
            found = visit(successor)
            if found:
                return found
        stack.pop()
        visiting.remove(node)
        visited.add(node)
        return []

    for node in sorted(adjacency):
        found = visit(node)
        if found:
            return found
    return []


def _graph_check(
    graph: Mapping[str, Any], ledger: Mapping[str, Any]
) -> tuple[bool, str]:
    task_ids = {
        str(task["task_id"])
        for task in ledger.get("tasks", [])
        if isinstance(task, dict)
    }
    edges = graph.get("edges")
    critical_path = graph.get("critical_path")
    if (
        not isinstance(edges, list)
        or not edges
        or not isinstance(critical_path, list)
        or not critical_path
    ):
        return False, "task graph edges and critical_path must be non-empty lists"
    if any(not isinstance(item, str) or not item.strip() for item in critical_path):
        return False, "task graph critical_path contains blank or non-string tasks"
    if len(set(critical_path)) != len(critical_path):
        return False, "task graph critical_path contains duplicates"
    referenced = set(str(item) for item in critical_path)
    edge_pairs: set[tuple[str, str]] = set()
    for edge in edges:
        if not isinstance(edge, dict) or "from" not in edge or "to" not in edge:
            return False, "task graph contains a malformed edge"
        source = edge["from"]
        target = edge["to"]
        if (
            not isinstance(source, str)
            or not source.strip()
            or not isinstance(target, str)
            or not target.strip()
        ):
            return False, "task graph contains a blank or non-string edge endpoint"
        pair = (source, target)
        if source == target:
            return False, f"task graph contains self-edge {source}"
        if pair in edge_pairs:
            return False, f"task graph contains duplicate edge {source}->{target}"
        edge_pairs.add(pair)
        referenced.update(pair)
    unknown = sorted(referenced - task_ids)
    if unknown:
        return False, f"task graph references unknown tasks: {','.join(unknown)}"

    adjacency = {task_id: set() for task_id in task_ids}
    for source, target in edge_pairs:
        adjacency[source].add(target)
    for task in ledger.get("tasks", []):
        if not isinstance(task, dict) or not isinstance(task.get("dependencies"), list):
            continue
        target = str(task.get("task_id", ""))
        for source in task["dependencies"]:
            if isinstance(source, str) and source in task_ids and target in task_ids:
                adjacency[source].add(target)
    cycle = _cycle(adjacency)
    if cycle:
        return False, f"task graph contains a cycle: {' -> '.join(cycle)}"
    return (
        True,
        f"task graph references {len(referenced)} declared tasks and is acyclic",
    )


def _critical_path_check(graph: Mapping[str, Any]) -> tuple[bool, str]:
    critical_path = graph.get("critical_path")
    edges = graph.get("edges")
    if not isinstance(critical_path, list) or not isinstance(edges, list):
        return False, "task graph edges and critical_path must be lists"
    edge_pairs = {
        (edge.get("from"), edge.get("to")) for edge in edges if isinstance(edge, dict)
    }
    missing = [
        f"{source}->{target}"
        for source, target in zip(critical_path, critical_path[1:])
        if (source, target) not in edge_pairs
    ]
    if missing:
        return False, f"critical_path is missing ordered edges: {','.join(missing)}"
    return True, f"critical_path has {max(len(critical_path) - 1, 0)} ordered edges"


def _reachable(adjacency: Mapping[str, set[str]], source: str, target: str) -> bool:
    pending = [source]
    visited: set[str] = set()
    while pending:
        node = pending.pop()
        if node == target:
            return True
        if node in visited:
            continue
        visited.add(node)
        pending.extend(sorted(adjacency.get(node, set()) - visited))
    return False


def _mandatory_phase_chain_check(graph: Mapping[str, Any]) -> tuple[bool, str]:
    critical_path = graph.get("critical_path")
    edges = graph.get("edges")
    if not isinstance(critical_path, list) or not isinstance(edges, list):
        return False, "task graph edges and critical_path must be lists"
    positions = {task_id: index for index, task_id in enumerate(critical_path)}
    missing = [task_id for task_id in MANDATORY_PHASE_TASKS if task_id not in positions]
    if missing:
        return (
            False,
            f"mandatory phase tasks absent from critical_path: {','.join(missing)}",
        )
    ordered_positions = [positions[task_id] for task_id in MANDATORY_PHASE_TASKS]
    if ordered_positions != sorted(ordered_positions):
        return (
            False,
            "mandatory Producer/Tests/Critique/Fixer/Evaluator/Apply/Post-Apply phases are out of order",
        )
    adjacency: dict[str, set[str]] = {}
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        source = edge.get("from")
        target = edge.get("to")
        if isinstance(source, str) and isinstance(target, str):
            adjacency.setdefault(source, set()).add(target)
    disconnected = [
        f"{source}->{target}"
        for source, target in zip(MANDATORY_PHASE_TASKS, MANDATORY_PHASE_TASKS[1:])
        if not _reachable(adjacency, source, target)
    ]
    if disconnected:
        return False, f"mandatory phase chain is disconnected: {','.join(disconnected)}"
    return (
        True,
        "mandatory Producer -> Tests -> Critique -> Fixer -> Independent Evaluator -> Apply Gate -> Post-Apply chain is ordered",
    )


def _locks_overlap(first: str, second: str) -> bool:
    first = first.strip().removeprefix("./").rstrip("/")
    second = second.strip().removeprefix("./").rstrip("/")
    if not first or not second or first.lower() == "none" or second.lower() == "none":
        return False
    if (
        first == second
        or fnmatch.fnmatchcase(first, second)
        or fnmatch.fnmatchcase(second, first)
    ):
        return True

    def static_prefix(pattern: str) -> str:
        wildcard_positions = [
            position for token in "*[?" if (position := pattern.find(token)) >= 0
        ]
        end = min(wildcard_positions) if wildcard_positions else len(pattern)
        return pattern[:end].rstrip("/")

    first_prefix = static_prefix(first)
    second_prefix = static_prefix(second)
    return bool(
        first_prefix
        and second_prefix
        and (
            first_prefix == second_prefix
            or first_prefix.startswith(second_prefix + "/")
            or second_prefix.startswith(first_prefix + "/")
        )
    )


def _active_write_lock_check(ledger: Mapping[str, Any]) -> tuple[bool, str]:
    active: list[tuple[str, list[str]]] = []
    for task in ledger.get("tasks", []):
        if not isinstance(task, dict) or task.get("status") not in ACTIVE_TASK_STATUSES:
            continue
        locks = task.get("write_lock", [])
        if isinstance(locks, list):
            active.append(
                (
                    str(task.get("task_id", "")),
                    [lock for lock in locks if isinstance(lock, str)],
                )
            )
    conflicts: list[str] = []
    for index, (first_id, first_locks) in enumerate(active):
        for second_id, second_locks in active[index + 1 :]:
            for first_lock in first_locks:
                for second_lock in second_locks:
                    if _locks_overlap(first_lock, second_lock):
                        conflicts.append(
                            f"{first_id}:{first_lock}<->{second_id}:{second_lock}"
                        )
    if conflicts:
        return False, f"active write-lock conflicts: {','.join(conflicts)}"
    return True, f"{len(active)} active tasks have non-conflicting write locks"


def evaluate(root: Path = ROOT, *, validate_evals: bool = True) -> dict[str, Any]:
    checks: dict[str, tuple[bool, str]] = {}
    missing_files = [
        relative for relative in REQUIRED_AGENT_FILES if not (root / relative).is_file()
    ]
    checks["required_governance_files_exist"] = (
        not missing_files,
        "all required governance files exist"
        if not missing_files
        else f"missing files: {','.join(missing_files)}",
    )

    spec_text = (root / "docs/specs/production-foundation-v1.md").read_text(
        encoding="utf-8"
    )
    spec_ids = REQUIREMENT_PATTERN.findall(spec_text)
    spec_unique, spec_detail = _unique_nonempty(spec_ids, "spec requirement IDs")
    traced_ids = traceability_requirement_ids(
        root / "agent/requirements-traceability.csv"
    )
    checks["spec_requirement_ids_are_unique"] = (spec_unique, spec_detail)
    checks["spec_and_traceability_match"] = (
        set(spec_ids) == traced_ids,
        "spec and traceability IDs match exactly"
        if set(spec_ids) == traced_ids
        else "spec/traceability mismatch missing={} extra={}".format(
            ",".join(sorted(set(spec_ids) - traced_ids)) or "none",
            ",".join(sorted(traced_ids - set(spec_ids))) or "none",
        ),
    )

    with (root / "agent/requirements-traceability.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        trace_rows = list(csv.DictReader(handle))
    invalid_status = sorted(
        {
            str(row.get("status", ""))
            for row in trace_rows
            if str(row.get("status", "")) not in TRACE_STATUSES
        }
    )
    incomplete_rows = [
        str(row.get("requirement_id", "<blank>"))
        for row in trace_rows
        if not str(row.get("owner", "")).strip()
        or not str(row.get("authoritative_evidence", "")).strip()
    ]
    checks["traceability_status_vocabulary_is_strict"] = (
        not invalid_status,
        "traceability uses the strict status vocabulary"
        if not invalid_status
        else f"invalid statuses: {','.join(invalid_status)}",
    )
    checks["traceability_rows_have_owner_and_evidence"] = (
        not incomplete_rows,
        "every traced requirement has an owner and evidence"
        if not incomplete_rows
        else f"incomplete rows: {','.join(incomplete_rows)}",
    )

    ledger = _read_yaml(root / "agent/task-ledger.yaml")
    graph = _read_yaml(root / "agent/task-graph.yaml")
    checks["subagent_contracts_are_complete"] = _task_contract_check(ledger)
    checks["task_graph_is_referentially_complete"] = _graph_check(graph, ledger)
    checks["critical_path_edges_are_strictly_ordered"] = _critical_path_check(graph)
    checks["mandatory_phase_chain_is_enforced"] = _mandatory_phase_chain_check(graph)
    checks["active_write_locks_do_not_overlap"] = _active_write_lock_check(ledger)

    evidence: list[dict[str, Any]] = []
    evidence_error = ""
    try:
        for line_number, raw_line in enumerate(
            (root / "agent/evidence-register.jsonl")
            .read_text(encoding="utf-8")
            .splitlines(),
            start=1,
        ):
            if raw_line.strip():
                item = json.loads(raw_line)
                if not isinstance(item, dict):
                    raise ValueError(f"line {line_number} is not an object")
                evidence.append(item)
    except (json.JSONDecodeError, ValueError) as exc:
        evidence_error = str(exc)
    evidence_ids = [str(item.get("evidence_id", "")) for item in evidence]
    evidence_unique, evidence_detail = _unique_nonempty(evidence_ids, "evidence IDs")
    evidence_fields_ok = all(
        {"evidence_id", "timestamp", "type", "result", "summary", "sensitive"}
        <= set(item)
        and item.get("sensitive") is False
        for item in evidence
    )
    checks["evidence_register_is_structured_and_unique"] = (
        not evidence_error and evidence_unique and evidence_fields_ok,
        evidence_error
        or (
            evidence_detail
            if evidence_fields_ok
            else "evidence fields or sensitive flag are invalid"
        ),
    )

    findings = _read_json(root / "agent/critique-findings.json").get("findings", [])
    finding_ids = [
        str(item.get("finding_id", "")) for item in findings if isinstance(item, dict)
    ]
    finding_unique, finding_detail = _unique_nonempty(finding_ids, "finding IDs")
    finding_fields_ok = all(
        isinstance(item, dict)
        and {"finding_id", "severity", "status", "target", "description"} <= set(item)
        for item in findings
    )
    checks["critique_findings_are_structured_and_unique"] = (
        finding_unique and finding_fields_ok,
        finding_detail
        if finding_fields_ok
        else "finding records are missing required fields",
    )

    risk_ids = RISK_PATTERN.findall(
        (root / "agent/risk-register.md").read_text(encoding="utf-8")
    )
    checks["risk_ids_are_unique"] = _unique_nonempty(risk_ids, "risk IDs")

    adr_files = sorted((root / "docs/adr").glob("[0-9][0-9][0-9][0-9]-*.md"))
    checks["required_architecture_decisions_exist"] = (
        len(adr_files) >= 9,
        f"found {len(adr_files)} numbered architecture decisions",
    )

    if validate_evals:
        try:
            catalog = load_catalog(root / "agent/eval-catalog.json")
            validate_catalog_coverage(
                catalog, root / "agent/requirements-traceability.csv"
            )
            validate_report(
                _read_json(root / "agent/eval-results.json"),
                catalog,
                traceability_statuses(root / "agent/requirements-traceability.csv"),
                root=root,
            )
        except (CatalogError, OSError, json.JSONDecodeError) as exc:
            checks["eval_catalog_and_results_cover_every_requirement"] = (
                False,
                str(exc),
            )
        else:
            checks["eval_catalog_and_results_cover_every_requirement"] = (
                True,
                f"catalog and results cover {len(traced_ids)} requirements",
            )

    failed = sorted(name for name, (passed, _) in checks.items() if not passed)
    return {
        "evaluation_id": "GOVERNANCE-STATIC-001",
        "status": "PASS" if not failed else "FAIL",
        "checks": [
            {"name": name, "status": "PASS" if passed else "FAIL", "evidence": detail}
            for name, (passed, detail) in sorted(checks.items())
        ],
        "failed_checks": failed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-eval-results",
        action="store_true",
        help="validate governance inputs before generating a replacement result file",
    )
    args = parser.parse_args()
    try:
        report = evaluate(validate_evals=not args.skip_eval_results)
    except (CatalogError, OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        report = {
            "evaluation_id": "GOVERNANCE-STATIC-001",
            "status": "FAIL",
            "failed_checks": ["governance_artifact_parse"],
            "error": str(exc),
        }
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
