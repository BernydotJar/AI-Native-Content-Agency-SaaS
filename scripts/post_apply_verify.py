#!/usr/bin/env python3
"""Validate non-sensitive GCP dev evidence after an exact runtime apply."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Set


DEPLOY_STANDARD_PROJECT_ROLES = {
    "roles/cloudsql.viewer",
    "roles/iam.securityReviewer",
    "roles/logging.viewer",
    "roles/monitoring.viewer",
}
PLAN_PROJECT_ROLES = {"roles/run.viewer"}
FORBIDDEN_DEPLOY_ROLES = {
    "roles/artifactregistry.admin",
    "roles/cloudsql.admin",
    "roles/editor",
    "roles/iam.serviceAccountAdmin",
    "roles/owner",
    "roles/resourcemanager.projectIamAdmin",
    "roles/run.admin",
    "roles/serviceusage.serviceUsageAdmin",
}


class EvidenceError(RuntimeError):
    pass


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EvidenceError("invalid evidence file: {}".format(path.name)) from error


def _values_for_key(value: Any, expected_key: str) -> Iterable[Any]:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key == expected_key:
                yield nested
            yield from _values_for_key(nested, expected_key)
    elif isinstance(value, list):
        for nested in value:
            yield from _values_for_key(nested, expected_key)


def _has_labels(value: Any, expected: Mapping[str, str]) -> bool:
    return any(
        isinstance(labels, dict)
        and all(labels.get(key) == label for key, label in expected.items())
        for labels in _values_for_key(value, "labels")
    )


def _iam_roles(policy: Any, member: str) -> Set[str]:
    if not isinstance(policy, dict) or not isinstance(policy.get("bindings"), list):
        raise EvidenceError("IAM policy evidence is malformed")
    roles: Set[str] = set()
    for binding in policy["bindings"]:
        if not isinstance(binding, dict):
            continue
        members = binding.get("members", [])
        if isinstance(members, list) and member in members:
            role = binding.get("role")
            if isinstance(role, str):
                roles.add(role)
        if isinstance(members, list) and ({"allUsers", "allAuthenticatedUsers"} & set(members)):
            raise EvidenceError("public IAM principal detected")
    return roles


def verify(
    service: Any,
    service_iam: Any,
    job: Any,
    sql: Any,
    logs: Any,
    project_iam: Any,
    artifact_iam: Any,
    outputs: Any,
    expected_image: str,
    expected_runtime_service_account: str,
    plan_service_account: str,
    deploy_service_account: str,
    project_id: str,
) -> Dict[str, object]:
    expected_labels = {
        "application": "ai-native-content-agency",
        "environment": "dev",
        "managed_by": "terraform",
    }
    for name, resource in (("service", service), ("migration_job", job)):
        if expected_image not in set(_values_for_key(resource, "image")):
            raise EvidenceError("{} does not use the evaluated image".format(name))
        service_accounts = set(_values_for_key(resource, "serviceAccountName")) | set(
            _values_for_key(resource, "serviceAccount")
        )
        if expected_runtime_service_account not in service_accounts:
            raise EvidenceError("{} does not use the reviewed runtime identity".format(name))
        if not _has_labels(resource, expected_labels):
            raise EvidenceError("{} is missing required labels".format(name))

    deploy_member = "serviceAccount:{}".format(deploy_service_account)
    if "roles/run.invoker" not in _iam_roles(service_iam, deploy_member):
        raise EvidenceError("deployment identity is not the explicit private invoker")

    connector_values = {str(value).upper() for value in _values_for_key(sql, "connectorEnforcement")}
    if "REQUIRED" not in connector_values:
        raise EvidenceError("Cloud SQL connector enforcement is not REQUIRED")
    authorized_networks = list(_values_for_key(sql, "authorizedNetworks"))
    if any(value not in (None, []) for value in authorized_networks):
        raise EvidenceError("Cloud SQL exposes an authorized network")

    plan_member = "serviceAccount:{}".format(plan_service_account)
    plan_roles = _iam_roles(project_iam, plan_member)
    deploy_roles = _iam_roles(project_iam, deploy_member)
    artifact_roles = _iam_roles(artifact_iam, deploy_member)
    expected_deploy_roles = DEPLOY_STANDARD_PROJECT_ROLES | {
        "projects/{}/roles/agencyRuntimeDeployer".format(project_id)
    }
    if plan_roles != PLAN_PROJECT_ROLES:
        raise EvidenceError("plan identity project roles differ from the reviewed set")
    if deploy_roles & FORBIDDEN_DEPLOY_ROLES:
        raise EvidenceError("deploy identity received a forbidden administration role")
    if deploy_roles != expected_deploy_roles:
        raise EvidenceError("deploy identity project roles differ from the reviewed set")
    if artifact_roles != {"roles/artifactregistry.reader"}:
        raise EvidenceError("deploy identity repository roles differ from the reviewed set")

    if not isinstance(outputs, dict):
        raise EvidenceError("Terraform output evidence is malformed")
    budget = outputs.get("foundation_budget_enabled", {}).get("value")
    channels = outputs.get("foundation_notification_channel_ids", {}).get("value")
    if budget is not True or not isinstance(channels, list) or not channels:
        raise EvidenceError("budget or alert-delivery evidence is absent")

    if not isinstance(logs, list) or not logs:
        raise EvidenceError("no post-smoke Cloud Run logs were observed")
    serialized_logs = json.dumps(logs, sort_keys=True).lower()
    if "http_request" not in serialized_logs:
        raise EvidenceError("post-smoke request telemetry was not observed")
    for prohibited in ("authorization", "bearer ", "password", "private-token"):
        if prohibited in serialized_logs:
            raise EvidenceError("potential secret material appeared in logs")

    return {
        "status": "PASS",
        "checks": [
            "immutable_image_and_runtime_identity",
            "private_invoker",
            "cloud_sql_connector_only",
            "phase_role_boundaries",
            "repository_scoped_image_reader",
            "required_labels",
            "budget_and_notification_channels",
            "post_smoke_logs_redacted",
        ],
        "limitations": [
            "Budget configuration is proven from reviewed foundation state; recipient delivery and measured cost require separate billing-owner evidence.",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    for name in (
        "service",
        "service-iam",
        "job",
        "sql",
        "logs",
        "project-iam",
        "artifact-iam",
        "outputs",
    ):
        parser.add_argument("--{}".format(name), type=Path, required=True)
    parser.add_argument("--expected-image", required=True)
    parser.add_argument("--runtime-service-account", required=True)
    parser.add_argument("--plan-service-account", required=True)
    parser.add_argument("--deploy-service-account", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        report = verify(
            _load(arguments.service),
            _load(arguments.service_iam),
            _load(arguments.job),
            _load(arguments.sql),
            _load(arguments.logs),
            _load(arguments.project_iam),
            _load(arguments.artifact_iam),
            _load(arguments.outputs),
            arguments.expected_image,
            arguments.runtime_service_account,
            arguments.plan_service_account,
            arguments.deploy_service_account,
            arguments.project_id,
        )
        arguments.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, sort_keys=True))
        return 0
    except EvidenceError as error:
        print("post-apply verification denied: {}".format(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
