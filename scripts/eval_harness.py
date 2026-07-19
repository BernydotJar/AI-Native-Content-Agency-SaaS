#!/usr/bin/env python3
"""Execute the production-foundation evaluation catalog and emit strict results.

The catalog is deliberately data-driven: every requirement in the traceability
matrix must name one or more executable gates, or an explicit external blocker.
An omitted command, missing executable, timeout, or malformed result fails
closed instead of becoming implied evidence.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "agent" / "eval-catalog.json"
DEFAULT_TRACEABILITY = ROOT / "agent" / "requirements-traceability.csv"
RESULT_SCHEMA_VERSION = 1
RESULT_STATUSES = {"PASS", "FAIL", "BLOCKED", "NOT_RUN"}
SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}
EVALUATORS = {"deterministic", "llm-judge", "human", "red-team"}
TRACEABILITY_STATUSES = {"PASS", "PARTIAL", "BLOCKED_BY_EXTERNAL_DEPENDENCY"}
REPORT_KEYS = {
    "schema_version",
    "catalog_id",
    "generated_at",
    "source_commit",
    "source_tree_sha256",
    "source_file_count",
    "status",
    "apply_recommendation",
    "summary",
    "hard_gates",
    "evaluations",
}
SUMMARY_KEYS = {
    "requirements_total",
    "requirements_passed",
    "requirements_failed",
    "requirements_blocked",
    "requirements_not_run",
    "completed_requirements_pass_rate",
    "open_critical",
    "open_high",
}
HARD_GATES = {
    "critical_failures_allowed": 0,
    "high_failures_allowed": 0,
    "required_tests_pass_rate": 100,
    "required_completed_requirement_coverage": 100,
    "untraced_changes_allowed": 0,
}
EVAL_KEYS = {
    "eval_id",
    "requirement_id",
    "target",
    "evaluator",
    "status",
    "severity",
    "evidence",
    "expected",
    "actual",
    "required_fix",
    "reproducibility",
}
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
EVIDENCE_GATE_PATTERN = re.compile(
    r"^(?P<gate_id>[A-Za-z0-9_-]+)="
    r"(?P<status>PASS|FAIL|BLOCKED|NOT_RUN) "
    r"exit=(?P<exit>n/a|-?[0-9]+) "
    r"duration=(?P<duration>[0-9]+\.[0-9]{3})s "
    r"output_sha256=(?P<digest>[0-9a-f]{64})$"
)
TOKEN_PATTERN = re.compile(
    r"(?i)(authorization:\s*bearer\s+\S+|gh[pousr]_[A-Za-z0-9]{20,}|"
    r"AIza[0-9A-Za-z_-]{20,}|xox[baprs]-[0-9A-Za-z-]{20,})"
)
MACOS_PERSONAL_PREFIX = "/" + "Users" + "/"
WINDOWS_PERSONAL_PREFIX = "C:" + "\\" + "Users" + "\\"
PERSONAL_PATH_PATTERN = re.compile(
    rf"(?:{re.escape(MACOS_PERSONAL_PREFIX)}[^/\s]+|"
    rf"[A-Za-z]:{re.escape(WINDOWS_PERSONAL_PREFIX[2:])}[^\\\s]+)"
)


class CatalogError(ValueError):
    """The checked-in evaluation catalog is incomplete or invalid."""


@dataclass(frozen=True)
class GateResult:
    gate_id: str
    status: str
    exit_code: int | None
    duration_seconds: float
    output_sha256: str
    output_excerpt: str
    command: tuple[str, ...]


def _redact(value: str) -> str:
    value = TOKEN_PATTERN.sub("[REDACTED]", value)
    return PERSONAL_PATH_PATTERN.sub("[WORKSPACE]", value)


def _require_string(record: Mapping[str, Any], key: str, context: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CatalogError(f"{context}.{key} must be a non-empty string")
    return value.strip()


def load_catalog(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogError(f"cannot load evaluation catalog {path}: {exc}") from exc
    if (
        not isinstance(raw, dict)
        or type(raw.get("schema_version")) is not int
        or raw.get("schema_version") != RESULT_SCHEMA_VERSION
    ):
        raise CatalogError("catalog schema_version must be 1")
    _require_string(raw, "catalog_id", "catalog")
    gates = raw.get("gates")
    requirements = raw.get("requirements")
    if not isinstance(gates, list) or not gates:
        raise CatalogError("catalog.gates must be a non-empty list")
    if not isinstance(requirements, list) or not requirements:
        raise CatalogError("catalog.requirements must be a non-empty list")

    gate_ids: set[str] = set()
    for index, gate in enumerate(gates):
        context = f"gates[{index}]"
        if not isinstance(gate, dict):
            raise CatalogError(f"{context} must be an object")
        gate_id = _require_string(gate, "gate_id", context)
        if gate_id in gate_ids:
            raise CatalogError(f"duplicate gate_id: {gate_id}")
        gate_ids.add(gate_id)
        gate_type = _require_string(gate, "type", context)
        if gate_type == "command":
            command = gate.get("command")
            if (
                not isinstance(command, list)
                or not command
                or not all(isinstance(part, str) and part for part in command)
            ):
                raise CatalogError(f"{context}.command must be a non-empty string array")
            timeout = gate.get("timeout_seconds", 600)
            if not isinstance(timeout, int) or timeout < 1 or timeout > 3600:
                raise CatalogError(f"{context}.timeout_seconds must be between 1 and 3600")
            cwd = gate.get("cwd", ".")
            if (
                not isinstance(cwd, str)
                or not cwd
                or Path(cwd).is_absolute()
                or ".." in Path(cwd).parts
            ):
                raise CatalogError(f"{context}.cwd must be a safe repository-relative path")
        elif gate_type == "external_blocker":
            _require_string(gate, "actual", context)
            _require_string(gate, "required_fix", context)
            _require_string(gate, "reproducibility", context)
        else:
            raise CatalogError(f"{context}.type must be command or external_blocker")

    requirement_ids: set[str] = set()
    for index, requirement in enumerate(requirements):
        context = f"requirements[{index}]"
        if not isinstance(requirement, dict):
            raise CatalogError(f"{context} must be an object")
        requirement_id = _require_string(requirement, "requirement_id", context)
        if requirement_id in requirement_ids:
            raise CatalogError(f"duplicate requirement_id: {requirement_id}")
        requirement_ids.add(requirement_id)
        _require_string(requirement, "target", context)
        _require_string(requirement, "expected", context)
        _require_string(requirement, "required_fix", context)
        severity = _require_string(requirement, "severity", context)
        if severity not in SEVERITIES:
            raise CatalogError(f"{context}.severity is invalid: {severity}")
        referenced = requirement.get("gate_ids")
        if (
            not isinstance(referenced, list)
            or not referenced
            or not all(isinstance(gate_id, str) and gate_id for gate_id in referenced)
        ):
            raise CatalogError(f"{context}.gate_ids must be a non-empty string array")
        unknown = sorted(set(referenced) - gate_ids)
        if unknown:
            raise CatalogError(f"{context} references unknown gates: {', '.join(unknown)}")
    return raw


def traceability_statuses(path: Path) -> dict[str, str]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError as exc:
        raise CatalogError(f"cannot load traceability matrix {path}: {exc}") from exc
    if not rows or not {"requirement_id", "status"}.issubset(rows[0]):
        raise CatalogError("traceability matrix requires requirement_id and status columns")
    identifiers = [str(row.get("requirement_id", "")).strip() for row in rows]
    if "" in identifiers:
        raise CatalogError("traceability matrix contains a blank requirement_id")
    if len(set(identifiers)) != len(rows):
        raise CatalogError("traceability matrix contains duplicate requirement IDs")
    statuses = {
        identifier: str(row.get("status", "")).strip()
        for identifier, row in zip(identifiers, rows, strict=True)
    }
    invalid = sorted(
        f"{identifier}={status}"
        for identifier, status in statuses.items()
        if status not in TRACEABILITY_STATUSES
    )
    if invalid:
        raise CatalogError(
            "traceability matrix contains invalid statuses: {}".format(", ".join(invalid))
        )
    return statuses


def traceability_requirement_ids(path: Path) -> set[str]:
    return set(traceability_statuses(path))


def validate_catalog_coverage(catalog: Mapping[str, Any], traceability_path: Path) -> None:
    traced = traceability_requirement_ids(traceability_path)
    catalogued = {item["requirement_id"] for item in catalog["requirements"]}
    missing = sorted(traced - catalogued)
    extra = sorted(catalogued - traced)
    if missing or extra:
        raise CatalogError(
            "catalog/traceability mismatch; missing={} extra={}".format(
                ",".join(missing) or "none", ",".join(extra) or "none"
            )
        )


def _command_environment(extra: Mapping[str, Any] | None, root: Path = ROOT) -> dict[str, str]:
    environment = os.environ.copy()
    environment.setdefault("RTK_TELEMETRY_DISABLED", "1")
    environment.setdefault("PYTHONPYCACHEPREFIX", "/tmp/agency-eval-pycache")
    environment.setdefault("UV_CACHE_DIR", "/tmp/agency-eval-uv-cache")
    local_bin = root / "backend" / ".venv" / "bin"
    if local_bin.is_dir():
        environment["PATH"] = os.pathsep.join((str(local_bin), environment.get("PATH", "")))
    if extra:
        for key, value in extra.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise CatalogError("gate env keys and values must be strings")
            environment[key] = value
    return environment


def run_gate(gate: Mapping[str, Any], root: Path = ROOT) -> GateResult:
    gate_id = str(gate["gate_id"])
    if gate["type"] == "external_blocker":
        reproduction = str(gate["reproducibility"])
        return GateResult(
            gate_id=gate_id,
            status="BLOCKED",
            exit_code=None,
            duration_seconds=0.0,
            output_sha256=hashlib.sha256(reproduction.encode()).hexdigest(),
            output_excerpt=_redact(str(gate["actual"])),
            command=(),
        )

    command = tuple(str(part) for part in gate["command"])
    command_cwd = root / str(gate.get("cwd", "."))
    started = time.monotonic()
    exit_code: int | None = None
    status = "FAIL"
    try:
        completed = subprocess.run(
            command,
            cwd=command_cwd,
            env=_command_environment(gate.get("env"), root),
            capture_output=True,
            text=True,
            timeout=int(gate.get("timeout_seconds", 600)),
            check=False,
        )
        exit_code = completed.returncode
        combined = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
        status = "PASS" if completed.returncode == 0 else "FAIL"
    except FileNotFoundError as exc:
        combined = f"required executable unavailable: {exc.filename}"
        status = "NOT_RUN"
    except subprocess.TimeoutExpired as exc:
        stdout = (
            exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else exc.stdout
        )
        stderr = (
            exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else exc.stderr
        )
        combined = "\n".join(part for part in (stdout, stderr, "command timed out") if part)
        status = "FAIL"
    duration = round(time.monotonic() - started, 3)
    safe_output = _redact(combined.strip())
    digest = hashlib.sha256(safe_output.encode("utf-8")).hexdigest()
    excerpt = safe_output[-4000:] if safe_output else "command produced no output"
    return GateResult(
        gate_id=gate_id,
        status=status,
        exit_code=exit_code,
        duration_seconds=duration,
        output_sha256=digest,
        output_excerpt=excerpt,
        command=command,
    )


def _status_for(results: Iterable[GateResult]) -> str:
    return _status_for_claims(result.status for result in results)


def _status_for_claims(claims: Iterable[str]) -> str:
    statuses = set(claims)
    if "FAIL" in statuses:
        return "FAIL"
    if "NOT_RUN" in statuses:
        return "NOT_RUN"
    if "BLOCKED" in statuses:
        return "BLOCKED"
    return "PASS"


def _evaluation_status(gate_status: str, trace_status: str) -> str:
    """Derive one requirement result from executable and trace evidence."""
    if gate_status in {"FAIL", "NOT_RUN"}:
        return gate_status
    if trace_status == "BLOCKED_BY_EXTERNAL_DEPENDENCY" or gate_status == "BLOCKED":
        return "BLOCKED"
    if trace_status == "PARTIAL":
        return "FAIL"
    return "PASS"


def _reproduction(gates: Sequence[Mapping[str, Any]]) -> str:
    procedures: list[str] = []
    for gate in gates:
        if gate["type"] == "command":
            command = " ".join(str(part) for part in gate["command"])
            cwd = str(gate.get("cwd", "."))
            procedures.append(command if cwd == "." else f"cd {cwd} && {command}")
        else:
            procedures.append(str(gate["reproducibility"]))
    return " && ".join(procedures)


def build_evaluations(
    catalog: Mapping[str, Any],
    gate_results: Mapping[str, GateResult],
    trace_statuses: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    gates_by_id = {gate["gate_id"]: gate for gate in catalog["gates"]}
    evaluations: list[dict[str, Any]] = []
    for requirement in catalog["requirements"]:
        selected_gates = [gates_by_id[gate_id] for gate_id in requirement["gate_ids"]]
        selected_results = [gate_results[gate_id] for gate_id in requirement["gate_ids"]]
        gate_status = _status_for(selected_results)
        trace_status = (
            trace_statuses.get(requirement["requirement_id"], "PASS")
            if trace_statuses is not None
            else "PASS"
        )
        status = _evaluation_status(gate_status, trace_status)
        evidence = f"TRACEABILITY={trace_status}; " + "; ".join(
            (
                f"{result.gate_id}={result.status}"
                f" exit={result.exit_code if result.exit_code is not None else 'n/a'}"
                f" duration={result.duration_seconds:.3f}s"
                f" output_sha256={result.output_sha256}"
            )
            for result in selected_results
        )
        actual = f"traceability status is {trace_status}; " + "; ".join(
            f"{result.gate_id}: {result.output_excerpt[-500:]}" for result in selected_results
        )
        evaluator = (
            "deterministic"
            if all(gate["type"] == "command" for gate in selected_gates)
            else "llm-judge"
        )
        evaluations.append(
            {
                "eval_id": f"EVAL-{requirement['requirement_id']}",
                "requirement_id": requirement["requirement_id"],
                "target": requirement["target"],
                "evaluator": evaluator,
                "status": status,
                "severity": requirement["severity"],
                "evidence": evidence,
                "expected": requirement["expected"],
                "actual": actual,
                "required_fix": "" if status == "PASS" else requirement["required_fix"],
                "reproducibility": _reproduction(selected_gates),
            }
        )
    return evaluations


def _source_commit(root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    commit = completed.stdout.strip()
    if completed.returncode != 0 or not COMMIT_PATTERN.fullmatch(commit):
        return "unavailable"
    return commit


def _source_tree_digest(root: Path) -> tuple[str, int]:
    """Hash the evaluated repository content without recursively hashing the result."""
    completed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return "unavailable", 0
    digest = hashlib.sha256()
    count = 0
    for raw_path in sorted(part for part in completed.stdout.split(b"\0") if part):
        relative = raw_path.decode("utf-8", errors="surrogateescape")
        if relative == "agent/eval-results.json":
            continue
        path = root / relative
        if not path.is_file():
            continue
        digest.update(raw_path)
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
        count += 1
    return digest.hexdigest(), count


def _source_commit_matches_provenance(root: Path, claimed: Any) -> bool:
    """Accept HEAD, or an ancestor separated only by the generated result file.

    A checked-in report cannot contain the hash of the commit that contains the
    report itself. The canonical two-commit lifecycle is therefore: commit the
    evaluated source, generate the report, then commit only eval-results.json.
    The content digest still binds every evaluated source file exactly.
    """
    if not isinstance(claimed, str) or not COMMIT_PATTERN.fullmatch(claimed):
        return False
    current = _source_commit(root)
    if current == "unavailable":
        return False
    if claimed == current:
        return True
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", claimed, current],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if ancestor.returncode != 0:
        return False
    changed = subprocess.run(
        ["git", "diff", "--name-only", "-z", claimed, current],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if changed.returncode != 0:
        return False
    paths = {
        raw.decode("utf-8", errors="surrogateescape") for raw in changed.stdout.split(b"\0") if raw
    }
    return bool(paths) and paths <= {"agent/eval-results.json"}


def _report_aggregates(
    evaluations: Sequence[Mapping[str, Any]],
) -> tuple[str, dict[str, Any]]:
    counts = {status: 0 for status in sorted(RESULT_STATUSES)}
    for evaluation in evaluations:
        counts[evaluation["status"]] += 1
    open_critical = sum(
        item["status"] != "PASS" and item["severity"] == "CRITICAL" for item in evaluations
    )
    open_high = sum(item["status"] != "PASS" and item["severity"] == "HIGH" for item in evaluations)
    if counts["FAIL"] or counts["NOT_RUN"] or open_critical or open_high:
        overall = "FAIL"
    elif counts["BLOCKED"]:
        overall = "BLOCKED"
    else:
        overall = "PASS"
    completed = counts["PASS"] + counts["FAIL"]
    pass_rate = round((counts["PASS"] / completed) * 100, 2) if completed else 0.0
    summary = {
        "requirements_total": len(evaluations),
        "requirements_passed": counts["PASS"],
        "requirements_failed": counts["FAIL"],
        "requirements_blocked": counts["BLOCKED"],
        "requirements_not_run": counts["NOT_RUN"],
        "completed_requirements_pass_rate": pass_rate,
        "open_critical": open_critical,
        "open_high": open_high,
    }
    return overall, summary


def build_report(
    catalog: Mapping[str, Any],
    evaluations: list[dict[str, Any]],
    *,
    root: Path = ROOT,
) -> dict[str, Any]:
    overall, summary = _report_aggregates(evaluations)
    source_tree_sha256, source_file_count = _source_tree_digest(root)
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "catalog_id": catalog["catalog_id"],
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_commit": _source_commit(root),
        "source_tree_sha256": source_tree_sha256,
        "source_file_count": source_file_count,
        "status": overall,
        "apply_recommendation": "DENY_APPLY",
        "summary": summary,
        "hard_gates": dict(HARD_GATES),
        "evaluations": evaluations,
    }


def _require_exact_keys(record: Mapping[str, Any], expected: set[str], context: str) -> None:
    missing = expected - set(record)
    extra = set(record) - expected
    if missing or extra:
        raise CatalogError(
            f"{context} schema mismatch; missing={sorted(missing)} extra={sorted(extra)}"
        )


def _validate_generated_at(value: Any) -> None:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise CatalogError("results.generated_at must be a UTC ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise CatalogError("results.generated_at must be a UTC ISO-8601 timestamp") from exc
    if parsed.tzinfo != timezone.utc:
        raise CatalogError("results.generated_at must be UTC")


def _parse_evidence(
    evidence: str,
    gates: Sequence[Mapping[str, Any]],
    trace_status: str,
    context: str,
) -> list[str]:
    parts = evidence.split("; ")
    expected_trace = f"TRACEABILITY={trace_status}"
    if not parts or parts[0] != expected_trace:
        raise CatalogError(f"{context}.evidence trace status is not catalog-bound")
    if len(parts) != len(gates) + 1:
        raise CatalogError(f"{context}.evidence gate set is not catalog-bound")
    statuses: list[str] = []
    for gate, claim in zip(gates, parts[1:], strict=True):
        match = EVIDENCE_GATE_PATTERN.fullmatch(claim)
        if match is None:
            raise CatalogError(f"{context}.evidence contains a malformed gate claim")
        gate_id = str(gate["gate_id"])
        if match.group("gate_id") != gate_id:
            raise CatalogError(f"{context}.evidence gate set is not catalog-bound")
        status = match.group("status")
        exit_claim = match.group("exit")
        if gate["type"] == "external_blocker":
            if status not in {"BLOCKED", "NOT_RUN"} or exit_claim != "n/a":
                raise CatalogError(f"{context}.evidence cannot override external blocker {gate_id}")
        else:
            if status == "BLOCKED":
                raise CatalogError(f"{context}.evidence command gate {gate_id} cannot be BLOCKED")
            if status == "PASS" and exit_claim != "0":
                raise CatalogError(f"{context}.evidence PASS gate {gate_id} must exit zero")
            if status == "NOT_RUN" and exit_claim != "n/a":
                raise CatalogError(f"{context}.evidence NOT_RUN gate {gate_id} must use exit=n/a")
            if status == "FAIL" and exit_claim == "0":
                raise CatalogError(f"{context}.evidence FAIL gate {gate_id} cannot exit zero")
        statuses.append(status)
    return statuses


def _validate_actual_trace_and_gates(
    actual: str,
    gates: Sequence[Mapping[str, Any]],
    trace_status: str,
    context: str,
) -> None:
    prefix = f"traceability status is {trace_status}; "
    if not actual.startswith(prefix):
        raise CatalogError(f"{context}.actual trace status is not catalog-bound")
    cursor = len(prefix)
    for index, gate in enumerate(gates):
        token = f"{gate['gate_id']}: " if index == 0 else f"; {gate['gate_id']}: "
        position = actual.find(token, cursor)
        if position != cursor:
            raise CatalogError(f"{context}.actual gate set is not catalog-bound")
        cursor = position + len(token)
        if index + 1 < len(gates):
            next_token = f"; {gates[index + 1]['gate_id']}: "
            next_position = actual.find(next_token, cursor)
            if next_position < cursor:
                raise CatalogError(f"{context}.actual gate set is not catalog-bound")
            cursor = next_position


def validate_report(
    report: Mapping[str, Any],
    catalog: Mapping[str, Any],
    trace_statuses: Mapping[str, str],
    *,
    root: Path = ROOT,
) -> None:
    _require_exact_keys(report, REPORT_KEYS, "results")
    if (
        type(report.get("schema_version")) is not int
        or report.get("schema_version") != RESULT_SCHEMA_VERSION
    ):
        raise CatalogError("result schema_version must be 1")
    if report.get("catalog_id") != catalog.get("catalog_id"):
        raise CatalogError("results.catalog_id does not match the evaluated catalog")
    _validate_generated_at(report.get("generated_at"))
    if not _source_commit_matches_provenance(root, report.get("source_commit")):
        raise CatalogError("results.source_commit provenance is invalid")
    source_tree_sha256, source_file_count = _source_tree_digest(root)
    if not SHA256_PATTERN.fullmatch(str(report.get("source_tree_sha256", ""))):
        raise CatalogError("results.source_tree_sha256 must be a SHA-256 digest")
    if report.get("source_tree_sha256") != source_tree_sha256:
        raise CatalogError("results.source_tree_sha256 does not match the evaluated tree")
    if (
        not isinstance(report.get("source_file_count"), int)
        or isinstance(report.get("source_file_count"), bool)
        or report.get("source_file_count") != source_file_count
        or source_file_count < 1
    ):
        raise CatalogError("results.source_file_count does not match the evaluated tree")
    if report.get("apply_recommendation") != "DENY_APPLY":
        raise CatalogError("results.apply_recommendation must remain DENY_APPLY")
    hard_gates = report.get("hard_gates")
    if (
        not isinstance(hard_gates, dict)
        or set(hard_gates) != set(HARD_GATES)
        or any(type(value) is not int for value in hard_gates.values())
        or hard_gates != HARD_GATES
    ):
        raise CatalogError("results.hard_gates do not match the mandatory policy")

    requirements = catalog.get("requirements")
    gates = catalog.get("gates")
    if not isinstance(requirements, list) or not isinstance(gates, list):
        raise CatalogError("validated catalog is malformed")
    expected_ids = [str(item["requirement_id"]) for item in requirements]
    if set(trace_statuses) != set(expected_ids):
        raise CatalogError("result traceability input does not match the catalog")
    gates_by_id = {str(gate["gate_id"]): gate for gate in gates}
    evaluations = report.get("evaluations")
    if not isinstance(evaluations, list) or not evaluations:
        raise CatalogError("results.evaluations must be a non-empty list")
    if len(evaluations) != len(requirements):
        raise CatalogError("result requirement coverage does not match the catalog")
    for index, (evaluation, requirement) in enumerate(zip(evaluations, requirements, strict=True)):
        context = f"evaluations[{index}]"
        if not isinstance(evaluation, dict):
            raise CatalogError(f"{context} must be an object")
        _require_exact_keys(evaluation, EVAL_KEYS, context)
        requirement_id = _require_string(evaluation, "requirement_id", context)
        expected_id = str(requirement["requirement_id"])
        if requirement_id != expected_id:
            raise CatalogError(f"{context}.requirement_id is not catalog-bound")
        if evaluation["status"] not in RESULT_STATUSES:
            raise CatalogError(f"{context}.status is invalid")
        if evaluation["severity"] not in SEVERITIES:
            raise CatalogError(f"{context}.severity is invalid")
        if evaluation["evaluator"] not in EVALUATORS:
            raise CatalogError(f"{context}.evaluator is invalid")
        for key in EVAL_KEYS - {"required_fix"}:
            _require_string(evaluation, key, context)
        if not isinstance(evaluation["required_fix"], str):
            raise CatalogError(f"{context}.required_fix must be a string")
        static_bindings = {
            "eval_id": f"EVAL-{expected_id}",
            "target": requirement["target"],
            "severity": requirement["severity"],
            "expected": requirement["expected"],
        }
        for key, expected_value in static_bindings.items():
            if evaluation[key] != expected_value:
                raise CatalogError(f"{context}.{key} is not catalog-bound")
        selected_gates = [gates_by_id[gate_id] for gate_id in requirement["gate_ids"]]
        expected_evaluator = (
            "deterministic"
            if all(gate["type"] == "command" for gate in selected_gates)
            else "llm-judge"
        )
        if evaluation["evaluator"] != expected_evaluator:
            raise CatalogError(f"{context}.evaluator is not catalog-bound")
        if evaluation["reproducibility"] != _reproduction(selected_gates):
            raise CatalogError(f"{context}.reproducibility is not catalog-bound")
        trace_status = trace_statuses[expected_id]
        gate_statuses = _parse_evidence(
            evaluation["evidence"], selected_gates, trace_status, context
        )
        _validate_actual_trace_and_gates(
            evaluation["actual"], selected_gates, trace_status, context
        )
        derived_status = _evaluation_status(_status_for_claims(gate_statuses), trace_status)
        if evaluation["status"] != derived_status:
            raise CatalogError(f"{context}.status is not supported by its evidence")
        expected_fix = "" if derived_status == "PASS" else requirement["required_fix"]
        if evaluation["required_fix"] != expected_fix:
            raise CatalogError(f"{context}.required_fix is not catalog-bound")

    expected_status, expected_summary = _report_aggregates(evaluations)
    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise CatalogError("results.summary must be an object")
    _require_exact_keys(summary, SUMMARY_KEYS, "results.summary")
    integer_summary_keys = SUMMARY_KEYS - {"completed_requirements_pass_rate"}
    if (
        any(type(summary[key]) is not int for key in integer_summary_keys)
        or type(summary["completed_requirements_pass_rate"]) is not float
    ):
        raise CatalogError("results.summary contains invalid value types")
    if summary != expected_summary:
        raise CatalogError("results.summary does not match recomputed aggregates")
    if report.get("status") != expected_status:
        raise CatalogError("results.status does not match recomputed aggregates")


def _select_gates(catalog: Mapping[str, Any], selected: set[str] | None) -> list[dict[str, Any]]:
    gates = list(catalog["gates"])
    if selected is None:
        return gates
    known = {gate["gate_id"] for gate in gates}
    unknown = selected - known
    if unknown:
        raise CatalogError(f"unknown selected gates: {', '.join(sorted(unknown))}")
    return [gate for gate in gates if gate["gate_id"] in selected]


def _not_run(gate: Mapping[str, Any]) -> GateResult:
    command = tuple(str(part) for part in gate.get("command", []))
    message = "gate was not selected for this harness invocation"
    return GateResult(
        gate_id=str(gate["gate_id"]),
        status="NOT_RUN",
        exit_code=None,
        duration_seconds=0.0,
        output_sha256=hashlib.sha256(message.encode()).hexdigest(),
        output_excerpt=message,
        command=command,
    )


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--traceability", type=Path, default=DEFAULT_TRACEABILITY)
    parser.add_argument("--output", type=Path, help="write the JSON report to this path")
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="GATE_ID",
        help="run only this gate (repeatable); unselected gates become NOT_RUN",
    )
    parser.add_argument(
        "--check-results",
        type=Path,
        help="validate an existing result file and exit without executing gates",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        catalog = load_catalog(args.catalog)
        validate_catalog_coverage(catalog, args.traceability)
        trace_status_map = traceability_statuses(args.traceability)
        if args.check_results:
            report = json.loads(args.check_results.read_text(encoding="utf-8"))
            validate_report(report, catalog, trace_status_map)
            print(f"eval_results_validation=PASS requirements={len(trace_status_map)}")
            return 0

        selected = set(args.only) if args.only else None
        selected_gates = _select_gates(catalog, selected)
        selected_ids = {gate["gate_id"] for gate in selected_gates}
        gate_results: dict[str, GateResult] = {}
        for gate in catalog["gates"]:
            if gate["gate_id"] in selected_ids:
                result = run_gate(gate)
            else:
                result = _not_run(gate)
            gate_results[result.gate_id] = result
            print(
                f"gate={result.gate_id} status={result.status} "
                f"duration_seconds={result.duration_seconds:.3f}",
                file=sys.stderr,
            )
        evaluations = build_evaluations(catalog, gate_results, trace_status_map)
        report = build_report(catalog, evaluations)
        validate_report(report, catalog, trace_status_map)
    except (CatalogError, OSError, json.JSONDecodeError) as exc:
        print(f"eval_harness=FAIL error={_redact(str(exc))}", file=sys.stderr)
        return 2

    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if report["status"] in {"PASS", "BLOCKED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
