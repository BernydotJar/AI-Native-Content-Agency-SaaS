#!/usr/bin/env python3
"""Validate SLOs, alert rules, runbooks and deterministic alert exercises."""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


CONTRACT_PATHS = (
    "ops/slo-catalog.json",
    "ops/alert-catalog.json",
    "ops/alert-exercises.json",
    "infra/monitoring/prometheus-rules.yaml",
    "infra/helm/ai-native-content-agency/files/prometheus-rules.json",
    "docs/runbooks/incident-response.md",
    "docs/runbooks/runtime-backup-restore.md",
    "backend/agency_runtime/observability.py",
    "scripts/manage-runtime-backup.py",
)
ALLOWED_OPERATORS = {">", ">=", "<", "<=", "=="}
PLATFORM_METRICS = {"probe_success", "time", "up"}
METRIC_REFERENCES = {
    "agency_http_requests_total": "backend/agency_runtime/observability.py",
    "agency_http_request_duration_seconds_bucket": (
        "backend/agency_runtime/observability.py"
    ),
    "agency_security_denials_total": "backend/agency_runtime/observability.py",
    "agency_social_publications_total": "backend/agency_runtime/observability.py",
    "agency_backup_last_success_timestamp_seconds": (
        "scripts/manage-runtime-backup.py"
    ),
}


class OperabilityValidationError(ValueError):
    """A versioned operability invariant is invalid or incomplete."""


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise OperabilityValidationError(f"{path}: invalid JSON: {error}") from error


def require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise OperabilityValidationError(f"{label}: object required")
    return value


def require_sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise OperabilityValidationError(f"{label}: array required")
    return value


def require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OperabilityValidationError(f"{label}: non-empty string required")
    return value.strip()


def unique(items: Sequence[Mapping[str, Any]], field: str, label: str) -> set[str]:
    observed: set[str] = set()
    for index, item in enumerate(items):
        value = require_text(item.get(field), f"{label}[{index}].{field}")
        if value in observed:
            raise OperabilityValidationError(f"{label}: duplicate {field} {value!r}")
        observed.add(value)
    return observed


def heading_slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9 -]", "", value.lower())
    return re.sub(r"[ -]+", "-", normalized).strip("-")


def markdown_anchors(path: Path) -> set[str]:
    anchors: set[str] = set()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise OperabilityValidationError(f"runbook missing: {path}") from error
    for line in lines:
        match = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if match:
            anchors.add(heading_slug(match.group(1)))
    return anchors


def validate_runbook(root: Path, reference: str) -> None:
    path_text, separator, anchor = reference.partition("#")
    if not separator or not path_text or not anchor:
        raise OperabilityValidationError(
            f"runbook reference must include a path and anchor: {reference!r}"
        )
    path = root / path_text
    if not path.is_file():
        raise OperabilityValidationError(f"runbook missing: {path_text}")
    if anchor not in markdown_anchors(path):
        raise OperabilityValidationError(
            f"runbook anchor missing: {reference}"
        )


def validate_slos(data: Mapping[str, Any]) -> tuple[set[str], int]:
    if data.get("schema_version") != "agency-slo-catalog.v1":
        raise OperabilityValidationError("SLO catalog schema version is unsupported")
    window_days = data.get("window_days")
    if not isinstance(window_days, int) or window_days <= 0:
        raise OperabilityValidationError("SLO window_days must be positive")
    raw_slos = require_sequence(data.get("slos"), "slos")
    slos = [require_mapping(item, f"slos[{index}]") for index, item in enumerate(raw_slos)]
    identifiers = unique(slos, "id", "slos")
    if len(slos) < 4:
        raise OperabilityValidationError("at least four SLOs are required")
    for index, slo in enumerate(slos):
        kind = require_text(slo.get("kind"), f"slos[{index}].kind")
        require_text(slo.get("indicator"), f"slos[{index}].indicator")
        require_text(slo.get("owner"), f"slos[{index}].owner")
        if kind == "availability":
            target = slo.get("target")
            budget = slo.get("error_budget_minutes")
            if not isinstance(target, (int, float)) or not 0 < float(target) < 1:
                raise OperabilityValidationError(
                    f"slos[{index}].target must be between zero and one"
                )
            expected = round(window_days * 24 * 60 * (1 - float(target)), 3)
            if not isinstance(budget, (int, float)) or not math.isclose(
                float(budget), expected, abs_tol=0.001
            ):
                raise OperabilityValidationError(
                    f"slos[{index}] error budget drift: expected {expected} minutes"
                )
        elif kind == "latency":
            fraction = slo.get("target_fraction")
            threshold = slo.get("threshold_seconds")
            if (
                not isinstance(fraction, (int, float))
                or not 0 < float(fraction) <= 1
                or not isinstance(threshold, (int, float))
                or float(threshold) <= 0
            ):
                raise OperabilityValidationError(
                    f"slos[{index}] latency target is invalid"
                )
        elif kind == "freshness":
            maximum_age = slo.get("maximum_age_seconds")
            rpo = slo.get("rpo_seconds")
            if (
                not isinstance(maximum_age, int)
                or maximum_age <= 0
                or not isinstance(rpo, int)
                or rpo <= 0
                or maximum_age < rpo
            ):
                raise OperabilityValidationError(
                    f"slos[{index}] freshness target is invalid"
                )
        else:
            raise OperabilityValidationError(f"slos[{index}].kind is unsupported")
    return identifiers, len(slos)


def flatten_rules(document: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    groups = require_sequence(document.get("groups"), "prometheus groups")
    result: list[Mapping[str, Any]] = []
    for group_index, raw_group in enumerate(groups):
        group = require_mapping(raw_group, f"groups[{group_index}]")
        require_text(group.get("name"), f"groups[{group_index}].name")
        rules = require_sequence(group.get("rules"), f"groups[{group_index}].rules")
        for rule_index, raw_rule in enumerate(rules):
            result.append(
                require_mapping(
                    raw_rule, f"groups[{group_index}].rules[{rule_index}]"
                )
            )
    return result


def referenced_metrics(expression: str) -> set[str]:
    candidates = set(re.findall(r"\b[a-zA-Z_:][a-zA-Z0-9_:]*\b", expression))
    return {
        item
        for item in candidates
        if item.startswith("agency_") or item in PLATFORM_METRICS
    }


def validate_metric_references(root: Path, expression: str, alert_name: str) -> None:
    for metric in referenced_metrics(expression):
        if metric in PLATFORM_METRICS:
            continue
        source = METRIC_REFERENCES.get(metric)
        if source is None:
            raise OperabilityValidationError(
                f"{alert_name}: metric {metric} has no reviewed source"
            )
        source_text = (root / source).read_text(encoding="utf-8")
        if metric not in source_text:
            raise OperabilityValidationError(
                f"{alert_name}: emitted metric {metric} is missing from {source}"
            )


def validate_alerts(
    root: Path,
    catalog: Mapping[str, Any],
    rules_document: Mapping[str, Any],
    slo_ids: set[str],
) -> tuple[list[Mapping[str, Any]], int]:
    if catalog.get("schema_version") != "agency-alert-catalog.v1":
        raise OperabilityValidationError("alert catalog schema version is unsupported")
    raw_alerts = require_sequence(catalog.get("alerts"), "alerts")
    alerts = [
        require_mapping(item, f"alerts[{index}]")
        for index, item in enumerate(raw_alerts)
    ]
    names = unique(alerts, "name", "alerts")
    rules = flatten_rules(rules_document)
    rule_names = unique(rules, "alert", "prometheus rules")
    if names != rule_names:
        raise OperabilityValidationError(
            f"alert/rule parity mismatch missing={sorted(names-rule_names)} "
            f"extra={sorted(rule_names-names)}"
        )
    rule_by_name = {str(rule["alert"]): rule for rule in rules}
    for index, alert in enumerate(alerts):
        name = str(alert["name"])
        expression = require_text(alert.get("expression"), f"alerts[{index}].expression")
        duration = require_text(alert.get("for"), f"alerts[{index}].for")
        severity = require_text(
            alert.get("severity"), f"alerts[{index}].severity"
        )
        owner = require_text(alert.get("owner"), f"alerts[{index}].owner")
        slo = require_text(alert.get("slo"), f"alerts[{index}].slo")
        summary = require_text(alert.get("summary"), f"alerts[{index}].summary")
        runbook = require_text(alert.get("runbook"), f"alerts[{index}].runbook")
        condition = require_mapping(
            alert.get("exercise_condition"),
            f"alerts[{index}].exercise_condition",
        )
        require_text(condition.get("metric"), f"alerts[{index}].condition.metric")
        operator = require_text(
            condition.get("operator"), f"alerts[{index}].condition.operator"
        )
        threshold = condition.get("threshold")
        if operator not in ALLOWED_OPERATORS or not isinstance(
            threshold, (int, float)
        ):
            raise OperabilityValidationError(
                f"alerts[{index}] exercise condition is invalid"
            )
        if slo not in slo_ids and not slo.startswith("SEC-"):
            raise OperabilityValidationError(
                f"alerts[{index}].slo references unknown objective {slo}"
            )
        if severity not in {"warning", "critical"}:
            raise OperabilityValidationError(
                f"alerts[{index}].severity is unsupported"
            )
        validate_runbook(root, runbook)
        validate_metric_references(root, expression, name)
        rule = rule_by_name[name]
        expected = {
            "alert": name,
            "expr": expression,
            "for": duration,
            "labels": {"owner": owner, "severity": severity, "slo": slo},
            "annotations": {"runbook_url": runbook, "summary": summary},
        }
        if dict(rule) != expected:
            raise OperabilityValidationError(
                f"{name}: Prometheus rule differs from alert catalog"
            )
    return alerts, len(alerts)


def compare(value: float, operator: str, threshold: float) -> bool:
    return {
        ">": value > threshold,
        ">=": value >= threshold,
        "<": value < threshold,
        "<=": value <= threshold,
        "==": value == threshold,
    }[operator]


def evaluate_alerts(
    alerts: Sequence[Mapping[str, Any]], metrics: Mapping[str, Any]
) -> list[str]:
    firing: list[str] = []
    for alert in alerts:
        condition = require_mapping(alert["exercise_condition"], "condition")
        metric = str(condition["metric"])
        if metric not in metrics or not isinstance(metrics[metric], (int, float)):
            raise OperabilityValidationError(
                f"exercise metric missing or invalid: {metric}"
            )
        if compare(
            float(metrics[metric]),
            str(condition["operator"]),
            float(condition["threshold"]),
        ):
            firing.append(str(alert["name"]))
    return sorted(firing)


def validate_exercises(
    data: Mapping[str, Any], alerts: Sequence[Mapping[str, Any]]
) -> int:
    if data.get("schema_version") != "agency-alert-exercises.v1":
        raise OperabilityValidationError("alert exercise schema version is unsupported")
    raw_scenarios = require_sequence(data.get("scenarios"), "scenarios")
    scenarios = [
        require_mapping(item, f"scenarios[{index}]")
        for index, item in enumerate(raw_scenarios)
    ]
    unique(scenarios, "id", "scenarios")
    covered: set[str] = set()
    healthy_seen = False
    for index, scenario in enumerate(scenarios):
        identifier = str(scenario["id"])
        metrics = require_mapping(
            scenario.get("metrics"), f"scenarios[{index}].metrics"
        )
        expected_raw = require_sequence(
            scenario.get("expected_alerts"), f"scenarios[{index}].expected_alerts"
        )
        expected = sorted(
            require_text(item, f"scenarios[{index}].expected_alerts")
            for item in expected_raw
        )
        observed = evaluate_alerts(alerts, metrics)
        if observed != expected:
            raise OperabilityValidationError(
                f"exercise {identifier} mismatch expected={expected} observed={observed}"
            )
        if identifier == "healthy":
            healthy_seen = True
            if expected:
                raise OperabilityValidationError("healthy exercise must fire no alerts")
        covered.update(expected)
    alert_names = {str(item["name"]) for item in alerts}
    if not healthy_seen or covered != alert_names:
        raise OperabilityValidationError(
            f"exercise coverage mismatch missing={sorted(alert_names-covered)}"
        )
    return len(scenarios)


def validate_repository(root: Path) -> dict[str, Any]:
    slo_catalog = require_mapping(
        read_json(root / "ops/slo-catalog.json"), "SLO catalog"
    )
    alert_catalog = require_mapping(
        read_json(root / "ops/alert-catalog.json"), "alert catalog"
    )
    exercises = require_mapping(
        read_json(root / "ops/alert-exercises.json"), "alert exercises"
    )
    rules_path = root / "infra/monitoring/prometheus-rules.yaml"
    rules_document = require_mapping(read_json(rules_path), "Prometheus rules")
    chart_rules = require_mapping(
        read_json(
            root
            / "infra/helm/ai-native-content-agency/files/prometheus-rules.json"
        ),
        "chart Prometheus rules",
    )
    if rules_document != chart_rules:
        raise OperabilityValidationError(
            "monitoring and Helm Prometheus rule sources differ"
        )
    slo_ids, slo_count = validate_slos(slo_catalog)
    alerts, alert_count = validate_alerts(
        root, alert_catalog, rules_document, slo_ids
    )
    exercise_count = validate_exercises(exercises, alerts)
    return {
        "status": "pass",
        "slos": slo_count,
        "alerts": alert_count,
        "exercises": exercise_count,
    }


def copy_contract(source_root: Path, target_root: Path) -> None:
    for relative in CONTRACT_PATHS:
        source = source_root / relative
        target = target_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        result = validate_repository(arguments.root.resolve())
    except (OperabilityValidationError, OSError) as error:
        if arguments.json:
            print(json.dumps({"status": "fail", "error": str(error)}, sort_keys=True))
        else:
            print(f"operability=fail\nerror={error}", file=sys.stderr)
        return 1
    if arguments.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print("operability=pass")
        print(f"slos={result['slos']}")
        print(f"alerts={result['alerts']}")
        print(f"exercises={result['exercises']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
