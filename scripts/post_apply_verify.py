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
    "roles/run.servicesInvoker",
}
PLAN_PROJECT_ROLES = {"roles/run.viewer"}
IMAGE_PUSHER_PROJECT_ROLES = {"roles/run.viewer"}
RUNTIME_PROJECT_ROLES = {
    "roles/cloudsql.client",
    "roles/cloudsql.instanceUser",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
}
RUNTIME_DEPLOYER_PERMISSIONS = {
    "resourcemanager.projects.get",
    "run.executions.get",
    "run.jobs.create",
    "run.jobs.get",
    "run.jobs.getIamPolicy",
    "run.jobs.list",
    "run.jobs.run",
    "run.jobs.update",
    "run.locations.get",
    "run.locations.list",
    "run.operations.get",
    "run.services.create",
    "run.services.get",
    "run.services.getIamPolicy",
    "run.services.list",
    "run.services.update",
}
ROLLBACK_TAG_OPERATOR_PERMISSIONS = {
    "artifactregistry.tags.create",
    "artifactregistry.tags.update",
}
EXPECTED_CLOUD_SQL_PROXY_IMAGE = (
    "gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.18.2@sha256:"
    "fc224915ef435afeb5b2a9421260a0d31986d5c8b7c7f5783c7f5d5885700cd2"
)
WIF_PHASES = {
    "build": ("github-build", "dev-build"),
    "plan": ("github-plan", "dev-plan"),
    "apply": ("github-apply", "dev"),
}
WIF_ATTRIBUTE_MAPPING = {
    "google.subject": "assertion.sub",
    "attribute.repository": "assertion.repository",
    "attribute.repository_owner": "assertion.repository_owner",
    "attribute.ref": "assertion.ref",
    "attribute.ref_type": "assertion.ref_type",
    "attribute.environment": "assertion.environment",
    "attribute.workflow_ref": "assertion.workflow_ref",
    "attribute.repository_id": "assertion.repository_id",
    "attribute.repository_owner_id": "assertion.repository_owner_id",
}
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


def _named_container_images(value: Any) -> Dict[str, str]:
    observed: Dict[str, str] = {}
    for containers in _values_for_key(value, "containers"):
        if not isinstance(containers, list):
            continue
        for container in containers:
            if not isinstance(container, dict):
                raise EvidenceError("container evidence is malformed")
            name = container.get("name")
            image = container.get("image")
            if not isinstance(name, str) or not isinstance(image, str):
                raise EvidenceError("container name or image evidence is absent")
            if name in observed and observed[name] != image:
                raise EvidenceError("container name resolves to multiple images")
            observed[name] = image
    return observed


def _iam_roles(policy: Any, member: str) -> Set[str]:
    if not isinstance(policy, dict) or not isinstance(policy.get("bindings", []), list):
        raise EvidenceError("IAM policy evidence is malformed")
    roles: Set[str] = set()
    for binding in policy.get("bindings", []):
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


def _member_bindings(policy: Any, member: str) -> Set[tuple[str, str, str]]:
    if not isinstance(policy, dict) or not isinstance(policy.get("bindings", []), list):
        raise EvidenceError("IAM policy evidence is malformed")
    records: Set[tuple[str, str, str]] = set()
    for binding in policy.get("bindings", []):
        if not isinstance(binding, dict):
            continue
        members = binding.get("members", [])
        if not isinstance(members, list):
            continue
        if {"allUsers", "allAuthenticatedUsers"} & set(members):
            raise EvidenceError("public IAM principal detected")
        if member not in members:
            continue
        role = binding.get("role")
        condition = binding.get("condition") or {}
        if not isinstance(role, str) or not isinstance(condition, dict):
            raise EvidenceError("IAM binding evidence is malformed")
        title = condition.get("title", "")
        expression = condition.get("expression", "")
        if not isinstance(title, str) or not isinstance(expression, str):
            raise EvidenceError("IAM binding condition is malformed")
        records.add((role, title, expression))
    return records


def _all_binding_records(policy: Any) -> Set[tuple[str, str, str, str]]:
    if not isinstance(policy, dict) or not isinstance(policy.get("bindings", []), list):
        raise EvidenceError("IAM policy evidence is malformed")
    records: Set[tuple[str, str, str, str]] = set()
    for binding in policy.get("bindings", []):
        if not isinstance(binding, dict):
            raise EvidenceError("IAM binding evidence is malformed")
        role = binding.get("role")
        members = binding.get("members")
        condition = binding.get("condition") or {}
        if (
            not isinstance(role, str)
            or not isinstance(members, list)
            or not members
            or not isinstance(condition, dict)
        ):
            raise EvidenceError("IAM binding evidence is malformed")
        title = condition.get("title", "")
        expression = condition.get("expression", "")
        if not isinstance(title, str) or not isinstance(expression, str):
            raise EvidenceError("IAM binding condition is malformed")
        for member in members:
            if not isinstance(member, str):
                raise EvidenceError("IAM binding member is malformed")
            if member in ("allUsers", "allAuthenticatedUsers"):
                raise EvidenceError("public IAM principal detected")
            records.add((role, member, title, expression))
    return records


def _wif_condition(
    *,
    github_repository: str,
    github_repository_owner_id: str,
    github_repository_id: str,
    environment: str,
) -> str:
    owner = github_repository.split("/", maxsplit=1)[0]
    workflow_ref = "{}/.github/workflows/deploy-dev.yml@refs/heads/main".format(github_repository)
    return " && ".join(
        (
            "assertion.repository_owner == '{}'".format(owner),
            "assertion.repository_owner_id == '{}'".format(github_repository_owner_id),
            "assertion.repository == '{}'".format(github_repository),
            "assertion.repository_id == '{}'".format(github_repository_id),
            "assertion.ref == 'refs/heads/main'",
            "assertion.ref_type == 'branch'",
            "assertion.environment == '{}'".format(environment),
            "assertion.workflow_ref == '{}'".format(workflow_ref),
        )
    )


def _verify_wif_and_impersonation(
    wif_providers: Any,
    phase_service_account_iam: Any,
    *,
    github_repository: str,
    github_repository_owner_id: str,
    github_repository_id: str,
) -> None:
    if not isinstance(wif_providers, dict) or set(wif_providers) != set(WIF_PHASES):
        raise EvidenceError("phase WIF provider evidence is incomplete")
    if not isinstance(phase_service_account_iam, dict) or set(phase_service_account_iam) != set(
        WIF_PHASES
    ):
        raise EvidenceError("phase impersonation evidence is incomplete")
    pool_name: Optional[str] = None
    for phase, (provider_id, environment) in WIF_PHASES.items():
        provider = wif_providers[phase]
        if not isinstance(provider, dict):
            raise EvidenceError("{} WIF provider evidence is malformed".format(phase))
        name = provider.get("name")
        if not isinstance(name, str) or not name.endswith(
            "/workloadIdentityPools/github-actions/providers/{}".format(provider_id)
        ):
            raise EvidenceError("{} WIF provider name differs".format(phase))
        current_pool_name = name.rsplit("/providers/", maxsplit=1)[0]
        if pool_name is None:
            pool_name = current_pool_name
        elif pool_name != current_pool_name:
            raise EvidenceError("phase WIF providers do not share the reviewed pool")
        if provider.get("attributeMapping") != WIF_ATTRIBUTE_MAPPING:
            raise EvidenceError("{} WIF attribute mapping differs".format(phase))
        expected_condition = _wif_condition(
            github_repository=github_repository,
            github_repository_owner_id=github_repository_owner_id,
            github_repository_id=github_repository_id,
            environment=environment,
        )
        actual_condition = provider.get("attributeCondition")
        if not isinstance(actual_condition, str) or " ".join(actual_condition.split()) != " ".join(
            expected_condition.split()
        ):
            raise EvidenceError("{} WIF attribute condition differs".format(phase))
        oidc = provider.get("oidc")
        if not isinstance(oidc, dict) or oidc.get("issuerUri") != (
            "https://token.actions.githubusercontent.com"
        ):
            raise EvidenceError("{} WIF issuer differs".format(phase))
        if provider.get("state") not in (None, "ACTIVE"):
            raise EvidenceError("{} WIF provider is not active".format(phase))

        principal = "principalSet://iam.googleapis.com/{}/attribute.environment/{}".format(
            current_pool_name, environment
        )
        expected_bindings = {("roles/iam.workloadIdentityUser", "", "")}
        actual_bindings = _member_bindings(phase_service_account_iam[phase], principal)
        if actual_bindings != expected_bindings:
            raise EvidenceError("{} phase impersonation binding differs".format(phase))
        all_impersonation_members = {
            member
            for binding in phase_service_account_iam[phase].get("bindings", [])
            if isinstance(binding, dict)
            and binding.get("role")
            in (
                "roles/iam.workloadIdentityUser",
                "roles/iam.serviceAccountTokenCreator",
            )
            for member in binding.get("members", [])
            if isinstance(member, str)
        }
        if all_impersonation_members != {principal}:
            raise EvidenceError("{} phase has extra impersonation principals".format(phase))
        if _all_binding_records(phase_service_account_iam[phase]) != {
            ("roles/iam.workloadIdentityUser", principal, "", "")
        }:
            raise EvidenceError("{} phase IAM policy has unreviewed drift".format(phase))


def _verify_state_bucket_iam(
    state_bucket_iam: Any,
    *,
    bootstrap_project_id: str,
    state_bucket_name: str,
    plan_service_account: str,
    deploy_service_account: str,
) -> None:
    object_prefix = "projects/_/buckets/{}/objects".format(state_bucket_name)
    plan_member = "serviceAccount:{}".format(plan_service_account)
    deploy_member = "serviceAccount:{}".format(deploy_service_account)
    expected_plan = {
        (
            "projects/{}/roles/terraformStateLister".format(bootstrap_project_id),
            "",
            "",
        ),
        (
            "projects/{}/roles/terraformStateReader".format(bootstrap_project_id),
            "plan-state-read",
            "resource.type == 'storage.googleapis.com/Object' && "
            "(resource.name.startsWith('{}/environments/dev/') || "
            "resource.name.startsWith('{}/environments/dev-runtime/'))".format(
                object_prefix, object_prefix
            ),
        ),
        (
            "projects/{}/roles/terraformStateLocker".format(bootstrap_project_id),
            "plan-runtime-lock-only",
            "resource.type == 'storage.googleapis.com/Object' && "
            "resource.name.startsWith('{}/environments/dev-runtime/') && "
            "resource.name.endsWith('.tflock')".format(object_prefix),
        ),
    }
    expected_deploy = {
        (
            "projects/{}/roles/terraformStateLister".format(bootstrap_project_id),
            "",
            "",
        ),
        (
            "projects/{}/roles/terraformStateReader".format(bootstrap_project_id),
            "apply-state-read",
            "resource.type == 'storage.googleapis.com/Object' && "
            "(resource.name.startsWith('{}/environments/dev/'))".format(object_prefix),
        ),
        (
            "roles/storage.objectAdmin",
            "apply-runtime-state-only",
            "resource.type == 'storage.googleapis.com/Object' && "
            "resource.name.startsWith('{}/environments/dev-runtime/')".format(object_prefix),
        ),
    }
    if _member_bindings(state_bucket_iam, plan_member) != expected_plan:
        raise EvidenceError("plan identity state-bucket boundary differs")
    if _member_bindings(state_bucket_iam, deploy_member) != expected_deploy:
        raise EvidenceError("deploy identity state-bucket boundary differs")


def _verify_custom_role(
    custom_role: Any,
    project_id: str,
    *,
    role_id: str,
    expected_permissions: Set[str],
    label: str,
) -> None:
    if not isinstance(custom_role, dict):
        raise EvidenceError("{} custom-role evidence is malformed".format(label))
    if custom_role.get("name") != "projects/{}/roles/{}".format(project_id, role_id):
        raise EvidenceError("{} custom-role name differs".format(label))
    included = custom_role.get("includedPermissions")
    if not isinstance(included, list) or set(included) != expected_permissions:
        raise EvidenceError("{} custom-role permissions differ".format(label))
    if custom_role.get("deleted") is True:
        raise EvidenceError("{} custom role is deleted".format(label))


def _verify_rollback_report(
    rollback: Any, *, expected_image: str, artifact_repository: str
) -> None:
    if not isinstance(rollback, dict):
        raise EvidenceError("rollback evidence is malformed")
    if (
        rollback.get("schema_version") != "artifact-rollback-evidence.v1"
        or rollback.get("status") != "PASS"
        or rollback.get("artifact_repository") != artifact_repository
        or rollback.get("desired_image") != expected_image
        or rollback.get("rollback_depth") != 1
        or rollback.get("retention_tag") != "rollback-current"
    ):
        raise EvidenceError("rollback evidence differs from the reviewed convention")
    rollback_image = rollback.get("rollback_image")
    if rollback_image is None:
        if rollback.get("first_deployment") is not True:
            raise EvidenceError("first-deployment rollback evidence is inconsistent")
    elif not isinstance(rollback_image, str) or rollback.get("retention_verified") is not True:
        raise EvidenceError("prior rollback digest is not protected")


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
    foundation_evidence: Any,
    foundation_expectations: Any,
) -> Dict[str, object]:
    if not isinstance(foundation_expectations, dict):
        raise EvidenceError("foundation drift expectations are malformed")
    expected_labels = {
        "application": "ai-native-content-agency",
        "environment": "dev",
        "managed_by": "terraform",
    }
    expected_container_images = {
        "service": {
            "application": expected_image,
            "cloud-sql-proxy": EXPECTED_CLOUD_SQL_PROXY_IMAGE,
        },
        "migration_job": {"migration": expected_image},
    }
    for name, resource in (("service", service), ("migration_job", job)):
        if _named_container_images(resource) != expected_container_images[name]:
            raise EvidenceError("{} container image provenance differs".format(name))
        service_accounts = set(_values_for_key(resource, "serviceAccountName")) | set(
            _values_for_key(resource, "serviceAccount")
        )
        if expected_runtime_service_account not in service_accounts:
            raise EvidenceError("{} does not use the reviewed runtime identity".format(name))
        if not _has_labels(resource, expected_labels):
            raise EvidenceError("{} is missing required labels".format(name))

    deploy_member = "serviceAccount:{}".format(deploy_service_account)
    service_deploy_roles = _iam_roles(service_iam, deploy_member)
    if service_deploy_roles:
        raise EvidenceError("deployment identity has an unexpected service IAM binding")
    if _all_binding_records(service_iam):
        raise EvidenceError("Cloud Run service IAM policy has unreviewed drift")

    connector_values = {
        str(value).upper() for value in _values_for_key(sql, "connectorEnforcement")
    }
    if "REQUIRED" not in connector_values:
        raise EvidenceError("Cloud SQL connector enforcement is not REQUIRED")
    authorized_networks = list(_values_for_key(sql, "authorizedNetworks"))
    if any(value not in (None, []) for value in authorized_networks):
        raise EvidenceError("Cloud SQL exposes an authorized network")

    plan_member = "serviceAccount:{}".format(plan_service_account)
    image_pusher_service_account = foundation_expectations.get("image_pusher_service_account")
    if not isinstance(image_pusher_service_account, str):
        raise EvidenceError("image-pusher expectation is absent")
    image_pusher_member = "serviceAccount:{}".format(image_pusher_service_account)
    runtime_member = "serviceAccount:{}".format(expected_runtime_service_account)
    plan_roles = _iam_roles(project_iam, plan_member)
    image_pusher_roles = _iam_roles(project_iam, image_pusher_member)
    deploy_roles = _iam_roles(project_iam, deploy_member)
    runtime_roles = _iam_roles(project_iam, runtime_member)
    artifact_image_pusher_roles = _iam_roles(artifact_iam, image_pusher_member)
    artifact_plan_roles = _iam_roles(artifact_iam, plan_member)
    artifact_roles = _iam_roles(artifact_iam, deploy_member)
    expected_deploy_roles = DEPLOY_STANDARD_PROJECT_ROLES | {
        "projects/{}/roles/agencyRuntimeDeployer".format(project_id)
    }
    if plan_roles != PLAN_PROJECT_ROLES:
        raise EvidenceError("plan identity project roles differ from the reviewed set")
    if image_pusher_roles != IMAGE_PUSHER_PROJECT_ROLES:
        raise EvidenceError("image-pusher project roles differ from the reviewed set")
    if deploy_roles & FORBIDDEN_DEPLOY_ROLES:
        raise EvidenceError("deploy identity received a forbidden administration role")
    if deploy_roles != expected_deploy_roles:
        raise EvidenceError("deploy identity project roles differ from the reviewed set")
    if runtime_roles != RUNTIME_PROJECT_ROLES:
        raise EvidenceError("runtime identity project roles differ from the reviewed set")
    if artifact_image_pusher_roles != {"roles/artifactregistry.writer"}:
        raise EvidenceError("image-pusher repository roles differ from the reviewed set")
    if artifact_plan_roles != {"roles/artifactregistry.reader"}:
        raise EvidenceError("plan identity repository roles differ from the reviewed set")
    rollback_role_name = "projects/{}/roles/agencyRollbackTagOperator".format(project_id)
    if artifact_roles != {"roles/artifactregistry.reader", rollback_role_name}:
        raise EvidenceError("deploy identity repository roles differ from the reviewed set")
    expected_artifact_records = {
        ("roles/artifactregistry.writer", image_pusher_member, "", ""),
        ("roles/artifactregistry.reader", plan_member, "", ""),
        ("roles/artifactregistry.reader", deploy_member, "", ""),
        (rollback_role_name, deploy_member, "", ""),
    }
    if _all_binding_records(artifact_iam) != expected_artifact_records:
        raise EvidenceError("repository IAM policy has unreviewed drift")

    if not isinstance(outputs, dict):
        raise EvidenceError("Terraform output evidence is malformed")
    budget = outputs.get("foundation_budget_enabled", {}).get("value")
    channels = outputs.get("foundation_notification_channel_ids", {}).get("value")
    if budget is not True or not isinstance(channels, list) or not channels:
        raise EvidenceError("budget or alert-delivery evidence is absent")

    if not isinstance(foundation_evidence, dict):
        raise EvidenceError("foundation drift evidence is malformed")
    expected_fields = (
        "bootstrap_project_id",
        "state_bucket_name",
        "artifact_repository",
        "github_repository",
        "github_repository_owner_id",
        "github_repository_id",
    )
    if any(not isinstance(foundation_expectations.get(field), str) for field in expected_fields):
        raise EvidenceError("foundation drift expectations are incomplete")
    artifact_repository = foundation_expectations["artifact_repository"]
    expected_prefix = "{}/app@sha256:".format(artifact_repository.rstrip("/"))
    if (
        not expected_image.startswith(expected_prefix)
        or len(expected_image) != len(expected_prefix) + 64
        or not set(expected_image[-64:]) <= set("0123456789abcdef")
    ):
        raise EvidenceError("application image is outside the foundation repository")
    _verify_wif_and_impersonation(
        foundation_evidence.get("wif_providers"),
        foundation_evidence.get("phase_service_account_iam"),
        github_repository=foundation_expectations["github_repository"],
        github_repository_owner_id=foundation_expectations["github_repository_owner_id"],
        github_repository_id=foundation_expectations["github_repository_id"],
    )
    _verify_state_bucket_iam(
        foundation_evidence.get("state_bucket_iam"),
        bootstrap_project_id=foundation_expectations["bootstrap_project_id"],
        state_bucket_name=foundation_expectations["state_bucket_name"],
        plan_service_account=plan_service_account,
        deploy_service_account=deploy_service_account,
    )
    _verify_custom_role(
        foundation_evidence.get("runtime_custom_role"),
        project_id,
        role_id="agencyRuntimeDeployer",
        expected_permissions=RUNTIME_DEPLOYER_PERMISSIONS,
        label="runtime deployer",
    )
    _verify_custom_role(
        foundation_evidence.get("rollback_custom_role"),
        project_id,
        role_id="agencyRollbackTagOperator",
        expected_permissions=ROLLBACK_TAG_OPERATOR_PERMISSIONS,
        label="rollback tag operator",
    )
    _verify_rollback_report(
        foundation_evidence.get("rollback"),
        expected_image=expected_image,
        artifact_repository=artifact_repository,
    )

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
            "exact_named_image_provenance_and_runtime_identity",
            "private_invoker",
            "cloud_sql_connector_only",
            "phase_role_boundaries",
            "repository_scoped_image_reader",
            "runtime_identity_exact_roles",
            "foundation_wif_and_impersonation_drift",
            "state_bucket_prefix_boundaries",
            "runtime_deployer_custom_role_drift",
            "rollback_tag_operator_custom_role_drift",
            "single_protected_rollback_digest",
            "required_labels",
            "budget_and_notification_channels",
            "post_smoke_logs_redacted",
        ],
        "limitations": [
            "Budget configuration is proven from reviewed foundation state; recipient delivery and measured cost require separate billing-owner evidence.",
            "Rollback is bounded to the immediately preceding digest protected by one moving repository tag.",
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
        "wif-provider-build",
        "wif-provider-plan",
        "wif-provider-apply",
        "build-service-account-iam",
        "plan-service-account-iam",
        "apply-service-account-iam",
        "state-bucket-iam",
        "runtime-custom-role",
        "rollback-custom-role",
        "rollback-report",
    ):
        parser.add_argument("--{}".format(name), type=Path, required=True)
    parser.add_argument("--expected-image", required=True)
    parser.add_argument("--runtime-service-account", required=True)
    parser.add_argument("--plan-service-account", required=True)
    parser.add_argument("--deploy-service-account", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--bootstrap-project-id", required=True)
    parser.add_argument("--state-bucket-name", required=True)
    parser.add_argument("--artifact-repository", required=True)
    parser.add_argument("--image-pusher-service-account", required=True)
    parser.add_argument("--github-repository", required=True)
    parser.add_argument("--github-repository-owner-id", required=True)
    parser.add_argument("--github-repository-id", required=True)
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
            {
                "wif_providers": {
                    "build": _load(arguments.wif_provider_build),
                    "plan": _load(arguments.wif_provider_plan),
                    "apply": _load(arguments.wif_provider_apply),
                },
                "phase_service_account_iam": {
                    "build": _load(arguments.build_service_account_iam),
                    "plan": _load(arguments.plan_service_account_iam),
                    "apply": _load(arguments.apply_service_account_iam),
                },
                "state_bucket_iam": _load(arguments.state_bucket_iam),
                "runtime_custom_role": _load(arguments.runtime_custom_role),
                "rollback_custom_role": _load(arguments.rollback_custom_role),
                "rollback": _load(arguments.rollback_report),
            },
            {
                "bootstrap_project_id": arguments.bootstrap_project_id,
                "state_bucket_name": arguments.state_bucket_name,
                "artifact_repository": arguments.artifact_repository,
                "image_pusher_service_account": (arguments.image_pusher_service_account),
                "github_repository": arguments.github_repository,
                "github_repository_owner_id": (arguments.github_repository_owner_id),
                "github_repository_id": arguments.github_repository_id,
            },
        )
        arguments.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps(report, sort_keys=True))
        return 0
    except EvidenceError as error:
        print("post-apply verification denied: {}".format(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
