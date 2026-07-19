"""Reject clearly unsafe Terraform plan JSON before independent human evaluation."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


FORBIDDEN_RESOURCE_TYPES = {
    "google_service_account_key",
    "google_secret_manager_secret_version",
    "random_password",
}


def _load(source: str) -> dict[str, Any]:
    if source == "-":
        return json.load(sys.stdin)
    return json.loads(Path(source).read_text(encoding="utf-8"))


def _walk(value: Any) -> list[Any]:
    values = [value]
    if isinstance(value, dict):
        for nested in value.values():
            values.extend(_walk(nested))
    elif isinstance(value, list):
        for nested in value:
            values.extend(_walk(nested))
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan_json")
    arguments = parser.parse_args()
    plan = _load(arguments.plan_json)
    findings: list[dict[str, str]] = []
    summary = {"create": 0, "update": 0, "replace": 0, "destroy": 0}

    for change in plan.get("resource_changes", []):
        address = str(change.get("address", "unknown"))
        resource_type = str(change.get("type", ""))
        actions = list(change.get("change", {}).get("actions", []))
        if actions == ["create"]:
            summary["create"] += 1
        elif actions == ["update"]:
            summary["update"] += 1
        elif "delete" in actions and "create" in actions:
            summary["replace"] += 1
            findings.append({"severity": "HIGH", "target": address, "description": "replacement requires explicit review"})
        elif "delete" in actions:
            summary["destroy"] += 1
            findings.append({"severity": "HIGH", "target": address, "description": "destruction is not authorized"})
        if resource_type in FORBIDDEN_RESOURCE_TYPES:
            findings.append({"severity": "CRITICAL", "target": address, "description": "forbidden secret/key-generating resource"})

    serialized = json.dumps(plan, sort_keys=True)
    for pattern, description in (
        (r'"allUsers"|"allAuthenticatedUsers"', "public IAM principal"),
        (r'roles/(?:owner|editor)\b', "basic Owner/Editor role"),
        (
            r'roles/(?:artifactregistry\.admin|cloudsql\.admin|iam\.serviceAccountAdmin|monitoring\.admin|resourcemanager\.projectIamAdmin|run\.admin|serviceusage\.serviceUsageAdmin)\b',
            "forbidden broad deployment role",
        ),
        (r'"invoker_iam_disabled"\s*:\s*true', "Cloud Run invoker IAM check disabled"),
        (r'"authorized_networks"\s*:\s*\[(?!\s*\])', "Cloud SQL authorized network"),
    ):
        if re.search(pattern, serialized, re.IGNORECASE):
            findings.append({"severity": "CRITICAL", "target": "plan", "description": description})

    result = {
        "task_id": "CLOUD-STATIC-PRECHECK",
        "status": "FAIL" if findings else "PASS",
        "apply_recommendation": "DENY_APPLY" if findings else "REQUIRES_INDEPENDENT_REVIEW",
        "plan_summary": summary,
        "findings": findings,
        "limitations": [
            "A passing static precheck is not ALLOW_DEV_APPLY.",
            "Independent cloud critique, security review, cost review, and readiness evaluation remain mandatory.",
        ],
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(1 if findings else 0)


if __name__ == "__main__":
    main()
