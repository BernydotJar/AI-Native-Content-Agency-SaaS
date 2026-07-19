"""Deterministic platform/security evaluation with structured output."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _all_platform_text() -> str:
    paths = [
        ROOT / "Dockerfile",
        ROOT / "docker-compose.yml",
        ROOT / ".gitignore",
        *(ROOT / ".github").rglob("*.yml"),
        *(ROOT / "infra").rglob("*.tf"),
        *(ROOT / "infra").rglob("*.hcl"),
    ]
    return "\n".join(path.read_text(encoding="utf-8") for path in paths if path.is_file())


def _tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def main() -> None:
    text = _all_platform_text()
    wif = _read("infra/modules/github_wif/main.tf")
    cloud_sql = _read("infra/modules/cloud_sql/main.tf")
    cloud_run = _read("infra/modules/cloud_run/main.tf")
    compose = _read("docker-compose.yml")
    dockerfile = _read("Dockerfile")
    deploy = _read(".github/workflows/deploy-dev.yml")
    bootstrap = _read("infra/bootstrap/main.tf")
    dev_foundation = _read("infra/environments/dev/main.tf")
    dev_runtime = _read("infra/environments/dev_runtime/main.tf")
    observability = _read("infra/modules/observability/main.tf")
    start_container = _read("scripts/start_container.py")
    apply_gate = _read("scripts/dev_apply_gate.py")
    post_apply = _read("scripts/post_apply_verify.py")
    rollback_gate = _read("scripts/rollback_image_gate.py")
    runtime_variables = _read("infra/environments/dev_runtime/variables.tf")
    artifact_registry = _read("infra/modules/artifact_registry/main.tf")
    gitignore = _read(".gitignore")
    tracked = _tracked_files()

    checks = {
        "no_public_iam_binding": re.search(r'member\s*=\s*"all(?:Authenticated)?Users"', text)
        is None,
        "no_basic_owner_editor_roles": re.search(r"roles/(?:owner|editor)\b", text, re.IGNORECASE)
        is None,
        "no_forbidden_broad_deployment_roles": not any(
            role in dev_foundation
            for role in (
                "roles/artifactregistry.admin",
                "roles/cloudsql.admin",
                "roles/iam.serviceAccountAdmin",
                "roles/monitoring.admin",
                "roles/resourcemanager.projectIamAdmin",
                "roles/run.admin",
                "roles/serviceusage.serviceUsageAdmin",
            )
        ),
        "runtime_deployer_custom_role_is_exact": (
            'role_id     = "agencyRuntimeDeployer"' in dev_foundation
            and "permissions = local.runtime_deployer_permissions" in dev_foundation
            and '"run.services.delete"' not in dev_foundation
            and '"run.jobs.delete"' not in dev_foundation
            and "run.services.setIamPolicy" not in dev_foundation
            and "run.jobs.run" in dev_foundation
            and "run.jobs.runWithOverrides" not in dev_foundation
        ),
        "runtime_deployer_image_read_is_repository_scoped": (
            'resource "google_artifact_registry_repository_iam_member" "runtime_deployer_reader"'
            in dev_foundation
            and 'role       = "roles/artifactregistry.reader"' in dev_foundation
            and "artifact_registry_read" in _read("scripts/gcp_permission_preflight.py")
        ),
        "no_service_account_keys": "google_service_account_key" not in text,
        "no_terraform_secret_values": all(
            token not in text
            for token in (
                "google_secret_manager_secret_version",
                "random_password",
                "private_key =",
            )
        ),
        "no_personal_paths": ("/" + "Users" + "/") not in text,
        "no_unrelated_project_literal": "meridian-hr-crm" not in text,
        "wif_exact_owner": "assertion.repository_owner ==" in wif,
        "wif_exact_repository": "assertion.repository ==" in wif,
        "wif_immutable_owner_and_repository_ids": (
            '"attribute.repository_owner_id" = "assertion.repository_owner_id"' in wif
            and '"attribute.repository_id"       = "assertion.repository_id"' in wif
            and "assertion.repository_owner_id == '${var.github_repository_owner_id}'" in wif
            and "assertion.repository_id == '${var.github_repository_id}'" in wif
        ),
        "wif_exact_branch_ref": "assertion.ref ==" in wif
        and "assertion.ref_type == 'branch'" in wif,
        "wif_exact_environment": (
            '"attribute.environment"      = "assertion.environment"' in wif
            and "assertion.environment == '${each.value}'" in wif
        ),
        "wif_exact_workflow": (
            '"attribute.workflow_ref"     = "assertion.workflow_ref"' in wif
            and "assertion.workflow_ref == '${local.workflow_ref}'" in wif
        ),
        "wif_phase_identities_are_split": (
            "for_each = var.phase_service_account_ids" in wif
            and "for_each = var.phase_environments" in wif
            and "attribute.environment" in wif
        ),
        "plan_state_cannot_mutate_tfstate": (
            'resource "google_project_iam_custom_role" "terraform_state_locker"' in bootstrap
            and 'resource "google_storage_bucket_iam_member" "terraform_plan_lock"' in bootstrap
            and "resource.name.endsWith('.tflock')" in bootstrap
            and 'member = "serviceAccount:${module.github_wif.service_account_emails.plan}"'
            in bootstrap
            and 'resource "google_storage_bucket_iam_member" "terraform_apply_runtime"' in bootstrap
        ),
        "apply_state_is_runtime_prefix_only": (
            "apply-runtime-state-only" in bootstrap
            and "/objects/environments/dev-runtime/" in bootstrap
            and 'google_storage_bucket_iam_member" "terraform_state"' not in bootstrap
        ),
        "cloud_sql_connector_required": 'connector_enforcement       = "REQUIRED"' in cloud_sql,
        "cloud_sql_iam_auth": 'name  = "cloudsql.iam_authentication"' in cloud_sql,
        "cloud_sql_no_authorized_networks": "authorized_networks" not in cloud_sql,
        "cloud_sql_postgres_15_enterprise": (
            'database_version    = "POSTGRES_15"' in cloud_sql
            and 'edition                     = "ENTERPRISE"' in cloud_sql
        ),
        "cloud_run_invoker_check_enabled": "invoker_iam_disabled = false" in cloud_run,
        "cloud_run_service_iam_is_foundation_bounded": (
            "google_cloud_run_v2_service_iam_member" not in cloud_run
            and '"roles/run.servicesInvoker"' in dev_foundation
            and '"roles/run.invoker"' not in dev_foundation
            and "run.services.setIamPolicy" not in dev_foundation
        ),
        "foundation_phase_identities_are_exact": all(
            value in dev_foundation
            for value in (
                '"github-image-dev@${var.bootstrap_project_id}.iam.gserviceaccount.com"',
                '"github-plan-dev@${var.bootstrap_project_id}.iam.gserviceaccount.com"',
                '"github-deploy-dev@${var.bootstrap_project_id}.iam.gserviceaccount.com"',
            )
        ),
        "terraform_state_lock_release_is_not_retention_blocked": (
            "retention_policy" not in bootstrap
            and "versioning" in bootstrap
            and "soft_delete_policy" in bootstrap
            and "retention_duration_seconds = 604800" in bootstrap
        ),
        "artifact_cleanup_bounds_tagged_builds": (
            "immutable_tags = false" in _read("infra/modules/artifact_registry/main.tf")
            and 'tag_state  = "ANY"' in _read("infra/modules/artifact_registry/main.tf")
            and 'older_than = "604800s"' in _read("infra/modules/artifact_registry/main.tf")
            and "most_recent_versions" in _read("infra/modules/artifact_registry/main.tf")
            and "keep_count = 20" in _read("infra/modules/artifact_registry/main.tf")
        ),
        "runtime_project_roles_are_live_verified_exactly": all(
            role in post_apply
            for role in (
                "roles/cloudsql.client",
                "roles/cloudsql.instanceUser",
                "roles/logging.logWriter",
                "roles/monitoring.metricWriter",
            )
        )
        and "runtime_roles != RUNTIME_PROJECT_ROLES" in post_apply,
        "runtime_images_are_repository_and_digest_bound": (
            "outputs.artifact_repository}/app" in dev_runtime
            and "exact source-reviewed proxy release and digest" in runtime_variables
            and "evil.invalid" not in runtime_variables
        ),
        "rollback_is_single_digest_and_cleanup_protected": (
            'id     = "keep-current-rollback"' in artifact_registry
            and 'tag_prefixes = ["rollback-current"]' in artifact_registry
            and 'ROLLBACK_TAG = "rollback-current"' in rollback_gate
            and '"rollback_depth": 1' in rollback_gate
            and deploy.count("rollback_image_gate.py") == 3
            and deploy.count("rollback_image_gate.py protect") == 1
            and deploy.find("Require ALLOW_DEV_APPLY")
            < deploy.find("rollback_image_gate.py protect")
            < deploy.find("Apply only the attested saved plan")
            and 'role_id     = "agencyRollbackTagOperator"' in dev_foundation
            and '"artifactregistry.tags.create"' in dev_foundation
            and '"artifactregistry.tags.update"' in dev_foundation
            and "artifactregistry.versions.delete" not in dev_foundation
            and "artifactregistry.repositories.deleteArtifacts" not in dev_foundation
        ),
        "foundation_drift_is_live_verified": all(
            value in deploy
            for value in (
                "wif-provider-build.json",
                "build-service-account-iam.json",
                "state-bucket-iam.json",
                "runtime-custom-role.json",
                "rollback-custom-role.json",
                "--github-repository-owner-id",
            )
        )
        and all(
            value in post_apply
            for value in (
                "_verify_wif_and_impersonation",
                "_verify_state_bucket_iam",
                "_verify_custom_role",
                "ROLLBACK_TAG_OPERATOR_PERMISSIONS",
            )
        ),
        "cloud_run_passwordless_proxy": "--auto-iam-authn" in cloud_run,
        "cloud_run_proxy_localhost_only": "--address=127.0.0.1" in cloud_run,
        "cloud_migration_uses_connector": "run_cloud_migrations.py" in cloud_run,
        "cloud_service_migrates_before_startup": (
            'name  = "AGENCY_RUN_MIGRATIONS_ON_START"' in cloud_run
            and 'path = "/readyz"' in cloud_run
            and "run_cloud_migrations()" in start_container
        ),
        "foundation_and_runtime_states_are_split": (
            'module "cloud_run"' not in dev_foundation
            and 'module "cloud_run"' in dev_runtime
            and 'data "terraform_remote_state" "foundation"' in dev_runtime
        ),
        "foundation_region_identity_and_provenance_are_runtime_bound": all(
            value in dev_runtime
            for value in (
                "var.project_id != var.bootstrap_project_id",
                "outputs.bootstrap_project_id == var.bootstrap_project_id",
                "outputs.region == var.region",
                "outputs.project_provenance_sha256 == var.foundation_project_provenance_sha256",
                "outputs.notification_channel_provenance_sha256 == var.foundation_notification_channel_provenance_sha256",
                "outputs.github_repository_owner_id == var.github_repository_owner_id",
                "outputs.github_repository_id == var.github_repository_id",
            )
        ),
        "project_adoption_is_explicit_and_imported": (
            all(
                value in bootstrap
                for value in (
                    'var.project_provisioning_mode == "ADOPT_EXISTING"',
                    "import {",
                    "project_provenance",
                )
            )
            and all(
                value in _read("infra/bootstrap/variables.tf")
                for value in (
                    'contains(["CREATE_NEW", "ADOPT_EXISTING"], var.project_provisioning_mode)',
                    "gcp-project-adoption.v1",
                )
            )
            and all(
                value in dev_foundation
                for value in (
                    "var.project_id != var.bootstrap_project_id",
                    'var.project_provisioning_mode == "ADOPT_EXISTING"',
                    "import {",
                    "project_provenance",
                )
            )
            and all(
                value in _read("infra/environments/dev/variables.tf")
                for value in (
                    'contains(["CREATE_NEW", "ADOPT_EXISTING"], var.project_provisioning_mode)',
                    "gcp-project-adoption.v1",
                )
            )
        ),
        "required_labels_cannot_be_overridden": (
            "effective_labels = merge(var.additional_labels, local.required_labels)" in bootstrap
            and "effective_labels = merge(var.additional_labels, local.required_labels)"
            in dev_foundation
            and "effective_labels = merge(var.additional_labels, local.required_labels)"
            in dev_runtime
            and "additional_labels cannot override application, environment or managed_by."
            in _read("infra/environments/dev_runtime/variables.tf")
        ),
        "alert_and_budget_delivery_channels_required": (
            'type         = "email"' in observability
            and 'channel.verification_status == "VERIFIED"' in observability
            and "channel.enabled" in observability
            and "notification_channels = local.notification_channel_ids" in observability
            and "monitoring_notification_channels = local.notification_channel_ids" in observability
            and observability.count("depends_on = [terraform_data.notification_delivery_gate]") == 2
        ),
        "notification_channels_are_terraform_owned_and_attested": (
            'resource "google_monitoring_notification_channel" "delivery"' in observability
            and "prevent_destroy = true" in observability
            and "for_each = local.notification_channel_imports" in dev_foundation
            and "to = module.observability.google_monitoring_notification_channel.delivery[each.key]"
            in dev_foundation
            and "notification_channels" in observability
            and "gcp-notification-channel.v1" in _read("infra/modules/observability/variables.tf")
            and "notification_channel_provenance_sha256" in observability
            and "notification_channel_provenance_sha256" in dev_runtime
        ),
        "notification_verification_precedes_costly_foundation_resources": (
            "depends_on = [module.services, module.observability]" in dev_foundation
            and dev_foundation.count("depends_on = [module.services, module.observability]") >= 5
            and 'module "artifact_registry"' in dev_foundation
        ),
        "compose_waits_for_database": "condition: service_healthy" in compose,
        "compose_waits_for_migration": "condition: service_completed_successfully" in compose,
        "compose_loopback_publish_only": '"127.0.0.1:8080:8080"' in compose,
        "compose_edge_is_separated": (
            "agency-edge:" in compose
            and compose.count("- agency-edge") == 1
            and "agency-internal:\n    internal: true" in compose
        ),
        "container_non_root": "USER ${APP_UID}:${APP_GID}" in dockerfile,
        "container_locked_install": "--require-hashes" in dockerfile and "npm ci" in dockerfile,
        "deploy_dev_only": "environment: dev" in deploy and "refs/heads/main" in deploy,
        "deploy_saved_plan_only": "terraform apply" in deploy and "tfplan" in deploy,
        "deploy_no_auto_approve": "-auto-approve" not in deploy,
        "deploy_wif_only": "workload_identity_provider" in deploy
        and "credentials_json" not in deploy,
        "deploy_phase_identities_are_split": all(
            value in deploy
            for value in (
                "GCP_IMAGE_PUSHER_SERVICE_ACCOUNT",
                "GCP_RUNTIME_PLAN_SERVICE_ACCOUNT",
                "GCP_RUNTIME_DEPLOYER_SERVICE_ACCOUNT",
                "environment: dev-build",
                "environment: dev-plan",
                "environment: dev",
            )
        ),
        "deploy_runtime_binds_foundation_and_immutable_repository_identity": (
            all(
                len(
                    re.findall(
                        r"^\s+{}:".format(re.escape(value)),
                        deploy,
                        re.MULTILINE,
                    )
                )
                == 2
                for value in (
                    "TF_VAR_bootstrap_project_id",
                    "TF_VAR_foundation_notification_channel_provenance_sha256",
                    "TF_VAR_foundation_project_provenance_sha256",
                    "TF_VAR_github_repository_id",
                    "TF_VAR_github_repository_owner_id",
                )
            )
            and "${{ github.repository_id }}" in deploy
            and "${{ github.repository_owner_id }}" in deploy
        ),
        "deploy_exact_attestation_precedes_auth": (
            "Require ALLOW_DEV_APPLY" in deploy
            and deploy.index("Require ALLOW_DEV_APPLY")
            < deploy.index("Authenticate as the runtime-only deployment identity")
            and "scripts/dev_apply_gate.py verify" in deploy
        ),
        "deploy_hashes_full_tracked_tree": (
            "scripts/dev_apply_gate.py create-metadata" in deploy
            and '"ls-files", "--stage", "-z"' in apply_gate
            and '["rev-parse", "--verify", "HEAD"]' in apply_gate
            and "source_commit does not match the checked-out HEAD" in apply_gate
        ),
        "deploy_granular_permission_preflight": deploy.count("gcp_permission_preflight.py") == 3,
        "deploy_post_apply_core_evidence": all(
            value in deploy
            for value in (
                "unauthenticated_status",
                "--identity-token-env AGENCY_ID_TOKEN",
                "post_apply_verify.py",
                "artifact-iam.json",
                '--project-id "${TF_VAR_project_id}"',
                "second_plan=NO_CHANGES",
            )
        ),
        "no_unjustified_distributed_services": not any(
            resource in text
            for resource in (
                "google_pubsub_",
                "google_cloud_tasks_queue",
                "google_vpc_access_connector",
                "google_compute_router_nat",
                "google_compute_global_forwarding_rule",
                "google_container_cluster",
            )
        ),
        "terraform_sensitive_files_ignored": all(
            pattern in gitignore
            for pattern in (
                "**/.terraform/",
                "*.tfstate",
                "*.tfplan",
                "infra/**/backend.hcl",
            )
        ),
        "no_tracked_state_or_plan": not any(
            re.search(r"(?:^|/)(?:terraform\.tfstate|tfplan)(?:\.|$)", path) for path in tracked
        ),
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    report = {
        "evaluation_id": "PLATFORM-STATIC-001",
        "status": "PASS" if not failed else "FAIL",
        "apply_recommendation": "DENY_APPLY",
        "checks": [
            {"name": name, "status": "PASS" if passed else "FAIL"}
            for name, passed in checks.items()
        ],
        "failed_checks": failed,
        "limitations": [
            "No real GCP plan was produced because every visible billing account is closed.",
            "Mock providers do not prove IAM permissions, quotas, policy, regional availability, cost, API behavior, or drift.",
            "This static evaluator cannot issue ALLOW_DEV_APPLY; a saved real plan and independent approval are required.",
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
