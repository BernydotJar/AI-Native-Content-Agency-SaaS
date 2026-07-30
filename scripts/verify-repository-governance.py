#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
HEX40 = re.compile(r"^[0-9a-f]{40}$")
JOB = re.compile(r"^  ([a-z0-9][a-z0-9-]*):\s*$")
EXPECTED_CHECKS = {
    "container", "helm", "postgresql-shared-state", "python-locks",
    "supply-chain", "terraform", "verify", "workflow-lint",
}
EXPECTED_PR_MAP = {
    2: "INC-001", 3: "INC-003", 4: "INC-004", 5: "INC-005",
    6: "INC-007", 7: "INC-008", 8: "INC-009", 9: "INC-011",
    10: "INC-016", 11: "INC-019",
}

class GovernanceValidationError(ValueError):
    pass

def load(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise GovernanceValidationError(f"{path}: invalid JSON: {error}") from error
    if not isinstance(value, Mapping):
        raise GovernanceValidationError(f"{path}: root must be an object")
    return value

def exact_keys(value: Mapping[str, Any], expected: set[str], name: str) -> None:
    if set(value) != expected:
        raise GovernanceValidationError(f"{name}: field mismatch")

def workflow_jobs(path: Path) -> set[str]:
    jobs: set[str] = set()
    in_jobs = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line == "jobs:":
            in_jobs = True
            continue
        if in_jobs and line and not line.startswith(" "):
            break
        if in_jobs:
            if line.startswith("    name:"):
                raise GovernanceValidationError(
                    "workflow jobs must use job IDs as check contexts"
                )
            match = JOB.fullmatch(line)
            if match:
                jobs.add(match.group(1))
    if not jobs:
        raise GovernanceValidationError("production-readiness workflow has no jobs")
    return jobs

def validate(root: Path, *, require_closed: bool = False) -> dict[str, Any]:
    policy = load(root / "program/repository-governance.json")
    exact_keys(policy, {
        "schema_version", "repository", "repository_mode", "protected_branch",
        "pull_request_required", "strict_status_checks", "required_status_checks",
        "required_approving_review_count", "require_last_push_approval",
        "require_code_owner_reviews", "dismiss_stale_reviews", "enforce_admins",
        "required_linear_history", "required_conversation_resolution",
        "allow_force_pushes", "allow_deletions",
    }, "repository governance")
    if policy.get("schema_version") != "repository-governance.v1":
        raise GovernanceValidationError("repository governance schema is unsupported")
    if policy.get("repository") != "BernydotJar/AI-Native-Content-Agency-SaaS":
        raise GovernanceValidationError("repository governance targets the wrong repository")
    if policy.get("repository_mode") != "single_owner" or policy.get("protected_branch") != "main":
        raise GovernanceValidationError("repository mode or protected branch is invalid")
    for field in (
        "pull_request_required", "strict_status_checks", "dismiss_stale_reviews",
        "enforce_admins", "required_linear_history", "required_conversation_resolution",
    ):
        if policy.get(field) is not True:
            raise GovernanceValidationError("required single-owner protection is disabled")
    for field in (
        "require_last_push_approval", "require_code_owner_reviews",
        "allow_force_pushes", "allow_deletions",
    ):
        if policy.get(field) is not False:
            raise GovernanceValidationError("forbidden or impossible protection is enabled")
    if policy.get("required_approving_review_count") != 0:
        raise GovernanceValidationError("single-owner repository must not require a second-person approval")
    checks = policy.get("required_status_checks")
    if not isinstance(checks, list) or checks != sorted(EXPECTED_CHECKS):
        raise GovernanceValidationError("required status checks are not canonical")
    jobs = workflow_jobs(root / ".github/workflows/production-readiness.yml")
    if jobs != EXPECTED_CHECKS or set(checks) != jobs:
        raise GovernanceValidationError("branch-protection checks differ from workflow jobs")

    state = load(root / "program/graph-harness.state.json")
    nodes = state.get("nodes")
    if not isinstance(nodes, Mapping):
        raise GovernanceValidationError("Graph Harness node state is invalid")
    superseded = load(root / "program/superseded-work.json")
    exact_keys(superseded, {
        "schema_version", "audit_base_commit", "updated_at", "issue", "pull_requests"
    }, "superseded work")
    if superseded.get("schema_version") != "superseded-work.v1" or not HEX40.fullmatch(str(superseded.get("audit_base_commit", ""))):
        raise GovernanceValidationError("superseded-work metadata is invalid")
    issue = superseded.get("issue")
    if not isinstance(issue, Mapping) or set(issue) != {"number", "mapped_node", "remote_state", "disposition", "reason"}:
        raise GovernanceValidationError("superseded issue contract is invalid")
    if issue.get("number") != 1 or issue.get("mapped_node") != "INC-001" or issue.get("disposition") != "superseded":
        raise GovernanceValidationError("founding issue mapping is invalid")
    if issue.get("remote_state") not in {"open", "closed"}:
        raise GovernanceValidationError("founding issue remote state is invalid")
    if require_closed and issue.get("remote_state") != "closed":
        raise GovernanceValidationError("founding issue is not remotely closed")

    prs = superseded.get("pull_requests")
    if not isinstance(prs, list) or len(prs) != len(EXPECTED_PR_MAP):
        raise GovernanceValidationError("superseded PR inventory is incomplete")
    observed: dict[int, str] = {}
    for item in prs:
        if not isinstance(item, Mapping) or set(item) != {"number", "head_sha", "mapped_node", "remote_state", "merged", "disposition", "reason"}:
            raise GovernanceValidationError("superseded PR contract is invalid")
        number = item.get("number")
        if not isinstance(number, int) or number in observed:
            raise GovernanceValidationError("superseded PR number is invalid or duplicated")
        node_id = str(item.get("mapped_node"))
        observed[number] = node_id
        if item.get("disposition") != "superseded" or item.get("merged") is not False:
            raise GovernanceValidationError("superseded PR cannot be marked merged")
        if item.get("remote_state") not in {"open", "closed"}:
            raise GovernanceValidationError("superseded PR remote state is invalid")
        if require_closed and item.get("remote_state") != "closed":
            raise GovernanceValidationError(f"PR #{number} is not remotely closed")
        if not HEX40.fullmatch(str(item.get("head_sha", ""))):
            raise GovernanceValidationError("superseded PR head is invalid")
        node = nodes.get(node_id)
        if not isinstance(node, Mapping) or node.get("status") not in {"done", "blocked"}:
            raise GovernanceValidationError(f"mapped node {node_id} is not terminal or externally blocked")
    if observed != EXPECTED_PR_MAP:
        raise GovernanceValidationError("superseded PR-to-node mapping is invalid")
    return {
        "status": "pass", "repository_mode": policy["repository_mode"],
        "required_checks": len(checks), "superseded_pull_requests": len(prs),
        "remote_closure_required": require_closed,
    }

def validate_live_protection(policy: Mapping[str, Any], protection: Mapping[str, Any]) -> None:
    def enabled(name: str) -> bool:
        value = protection.get(name)
        return isinstance(value, Mapping) and value.get("enabled") is True

    if enabled("enforce_admins") != policy["enforce_admins"]:
        raise GovernanceValidationError("live admin enforcement differs from policy")
    if enabled("required_linear_history") != policy["required_linear_history"]:
        raise GovernanceValidationError("live linear-history protection differs from policy")
    if enabled("required_conversation_resolution") != policy["required_conversation_resolution"]:
        raise GovernanceValidationError("live conversation protection differs from policy")
    if enabled("allow_force_pushes") != policy["allow_force_pushes"]:
        raise GovernanceValidationError("live force-push protection differs from policy")
    if enabled("allow_deletions") != policy["allow_deletions"]:
        raise GovernanceValidationError("live deletion protection differs from policy")
    reviews = protection.get("required_pull_request_reviews")
    if not isinstance(reviews, Mapping):
        raise GovernanceValidationError("live pull-request review protection is absent")
    expected_reviews = {
        "dismiss_stale_reviews": policy["dismiss_stale_reviews"],
        "require_code_owner_reviews": policy["require_code_owner_reviews"],
        "require_last_push_approval": policy["require_last_push_approval"],
        "required_approving_review_count": policy["required_approving_review_count"],
    }
    observed_reviews = {key: reviews.get(key) for key in expected_reviews}
    if observed_reviews != expected_reviews:
        raise GovernanceValidationError("live review protection differs from policy")
    status = protection.get("required_status_checks")
    if not isinstance(status, Mapping) or status.get("strict") is not policy["strict_status_checks"]:
        raise GovernanceValidationError("live strict status-check protection differs from policy")
    checks = status.get("checks")
    if not isinstance(checks, list):
        raise GovernanceValidationError("live status checks are invalid")
    contexts = sorted(
        str(item.get("context"))
        for item in checks
        if isinstance(item, Mapping) and isinstance(item.get("context"), str)
    )
    if contexts != policy["required_status_checks"]:
        raise GovernanceValidationError("live required status checks differ from policy")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--require-closed", action="store_true")
    parser.add_argument("--protection-json", type=Path)
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        result = validate(root, require_closed=args.require_closed)
        if args.protection_json is not None:
            validate_live_protection(
                load(root / "program/repository-governance.json"),
                load(args.protection_json.resolve()),
            )
            result["live_protection_verified"] = True
    except GovernanceValidationError as error:
        print(f"repository_governance=fail reason={error}", file=sys.stderr)
        return 1
    print("repository_governance=pass")
    for key, value in result.items():
        if key != "status":
            print(f"{key}={str(value).lower() if isinstance(value, bool) else value}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
