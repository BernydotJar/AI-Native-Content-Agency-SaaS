#!/usr/bin/env python3
"""Validate the fail-closed GCP pilot deployment-readiness contract."""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping

CONTRACT_FILES = (
    "infra/gcp/pilot-cost-review.json",
    "infra/gcp/cloud_sql.tf",
    "infra/gcp/cloud_run.tf",
    "infra/gcp/iam.tf",
    "infra/gcp/locals.tf",
    "infra/gcp/variables.tf",
    "infra/gcp/tests/fail_closed.tftest.hcl",
    "infra/gcp/terraform.tfvars.example",
    "docs/runbooks/gcp-pilot-deployment.md",
)
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class GCPPilotReadinessError(ValueError):
    """A GCP pilot planning invariant is missing, weakened or inconsistent."""


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise GCPPilotReadinessError(f"{path}: invalid JSON: {error}") from error


def require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise GCPPilotReadinessError(f"{label}: object required")
    return value


def require_tokens(text: str, tokens: tuple[str, ...], label: str) -> None:
    missing = [token for token in tokens if token not in text]
    if missing:
        raise GCPPilotReadinessError(f"{label}: missing invariants {missing}")


def forbid_tokens(text: str, tokens: tuple[str, ...], label: str) -> None:
    found = [token for token in tokens if token in text]
    if found:
        raise GCPPilotReadinessError(f"{label}: forbidden invariants present {found}")


def validate_cost_review(root: Path) -> Mapping[str, Any]:
    data = require_mapping(
        read_json(root / "infra/gcp/pilot-cost-review.json"), "cost review"
    )
    expected_keys = {
        "schema_version",
        "reviewed_at",
        "region",
        "billing_currency",
        "authorized_monthly_cap_units",
        "minimum_compute_assumption",
        "excluded_from_lower_bound",
        "all_in_monthly_estimate_units",
        "decision",
        "reason",
        "sources",
    }
    if set(data) != expected_keys:
        raise GCPPilotReadinessError("cost review field set drifted")
    if data.get("schema_version") != "agency-gcp-pilot-cost-review.v1":
        raise GCPPilotReadinessError("cost review schema version is unsupported")
    if data.get("region") != "us-central1" or data.get("billing_currency") != "COP":
        raise GCPPilotReadinessError("cost review must bind us-central1 and COP")
    cap = data.get("authorized_monthly_cap_units")
    if cap != 4000:
        raise GCPPilotReadinessError("authorized monthly cap must remain exactly 4,000 COP")
    assumption = require_mapping(
        data.get("minimum_compute_assumption"), "minimum compute assumption"
    )
    hourly = assumption.get("hourly_price_usd")
    hours = assumption.get("hours_per_month")
    exchange = assumption.get("exchange_rate_cop_per_usd")
    if not all(isinstance(value, (int, float)) and value > 0 for value in (hourly, hours, exchange)):
        raise GCPPilotReadinessError("cost assumptions must be positive numbers")
    monthly_usd = float(hourly) * float(hours)
    monthly_cop = monthly_usd * float(exchange)
    if not math.isclose(monthly_usd, float(assumption.get("computed_monthly_usd", -1)), abs_tol=0.000001):
        raise GCPPilotReadinessError("monthly USD computation drifted")
    if not math.isclose(monthly_cop, float(assumption.get("computed_monthly_cop", -1)), abs_tol=0.0001):
        raise GCPPilotReadinessError("monthly COP computation drifted")
    if math.ceil(monthly_cop) != assumption.get("rounded_monthly_cop"):
        raise GCPPilotReadinessError("rounded monthly COP lower bound drifted")
    if monthly_cop <= cap:
        raise GCPPilotReadinessError("minimum compute lower bound must exceed current cap")
    if data.get("all_in_monthly_estimate_units") is not None:
        raise GCPPilotReadinessError("an all-in estimate must not be claimed without live pricing review")
    if data.get("decision") != "DENY_APPLY":
        raise GCPPilotReadinessError("current cost evidence must deny apply")
    exclusions = data.get("excluded_from_lower_bound")
    if not isinstance(exclusions, list) or len(exclusions) < 6:
        raise GCPPilotReadinessError("lower-bound exclusions are incomplete")
    sources = data.get("sources")
    if not isinstance(sources, list) or len(sources) < 3:
        raise GCPPilotReadinessError("cost review sources are incomplete")
    return data


def extract_variable_block(text: str, name: str) -> str:
    marker = f'variable "{name}" {{'
    start = text.find(marker)
    if start < 0:
        raise GCPPilotReadinessError(f"variables.tf: missing {name}")
    next_start = text.find('\nvariable "', start + len(marker))
    return text[start:] if next_start < 0 else text[start:next_start]


def validate_terraform_contract(root: Path) -> None:
    variables = (root / "infra/gcp/variables.tf").read_text(encoding="utf-8")
    sql = (root / "infra/gcp/cloud_sql.tf").read_text(encoding="utf-8")
    run = (root / "infra/gcp/cloud_run.tf").read_text(encoding="utf-8")
    iam = (root / "infra/gcp/iam.tf").read_text(encoding="utf-8")
    locals_text = (root / "infra/gcp/locals.tf").read_text(encoding="utf-8")
    tests = (root / "infra/gcp/tests/fail_closed.tftest.hcl").read_text(
        encoding="utf-8"
    )

    for name in ("enable_bootstrap", "enable_cloud_sql", "enable_cloud_run"):
        block = extract_variable_block(variables, name)
        require_tokens(block, ("default     = false",), f"variable {name}")

    require_tokens(
        extract_variable_block(variables, "enable_cloud_sql"),
        (
            'can(regex("^[0-9a-f]{64}$", var.cost_review_receipt_sha256))',
            "var.reviewed_monthly_cost_estimate_units <= var.authorized_monthly_cost_cap_units",
            "var.monthly_budget_units <= var.authorized_monthly_cost_cap_units",
        ),
        "Cloud SQL cost gate",
    )
    require_tokens(
        extract_variable_block(variables, "schema_initialization_receipt_sha256"),
        ('can(regex("^[0-9a-f]{64}$", var.schema_initialization_receipt_sha256))',),
        "schema receipt gate",
    )
    require_tokens(
        extract_variable_block(variables, "min_instance_count"),
        ("condition     = var.min_instance_count == 0",),
        "Cloud Run minimum scale",
    )
    require_tokens(
        extract_variable_block(variables, "max_instance_count"),
        ("var.max_instance_count <= 2",),
        "Cloud Run maximum scale",
    )

    secret_block = extract_variable_block(variables, "secret_environment")
    require_tokens(
        secret_block,
        (
            '"AGENCY_DATABASE_URL"',
            '"AGENCY_IDENTITY_CREDENTIALS_JSON"',
            '"AGENCY_AUDIT_CHECKPOINT_SIGNING_KEYS_JSON"',
            '"AGENCY_AUDIT_CHECKPOINT_ACTIVE_KEY_ID"',
            'can(regex("^[1-9][0-9]*$", item.version))',
            "contains(var.managed_secret_ids, item.secret)",
        ),
        "minimal secret contract",
    )
    forbid_tokens(
        secret_block,
        (
            '"AGENCY_X_CONSUMER_KEY"',
            '"AGENCY_X_CONSUMER_SECRET"',
            '"AGENCY_INSTAGRAM_APP_ID"',
            '"AGENCY_INSTAGRAM_APP_SECRET"',
        ),
        "minimal secret contract",
    )

    require_tokens(
        sql,
        (
            'database_version    = "POSTGRES_15"',
            'connector_enforcement = "REQUIRED"',
            'disk_autoresize_limit = var.cloud_sql_disk_autoresize_limit_gb',
            "deletion_protection = var.cloud_sql_deletion_protection",
            "enabled                        = true",
            "point_in_time_recovery_enabled = true",
            'ssl_mode                                      = "ENCRYPTED_ONLY"',
        ),
        "Cloud SQL resource",
    )
    if not re.search(r"availability_type\s*=\s*\"ZONAL\"", sql):
        raise GCPPilotReadinessError("Cloud SQL resource: availability_type must be ZONAL")
    forbid_tokens(sql, ("authorized_networks {", "google_sql_user"), "Cloud SQL resource")
    require_tokens(locals_text, ('"sqladmin.googleapis.com"',), "required APIs")

    require_tokens(
        run,
        (
            'mount_path = "/cloudsql"',
            "instances = [google_sql_database_instance.app[0].connection_name]",
            '"agency.dev/cost-review-receipt"',
            '"agency.dev/schema-initialization-receipt"',
            "google_project_iam_member.runtime_cloud_sql_client",
        ),
        "Cloud Run resource",
    )
    require_tokens(
        iam,
        (
            'role    = "roles/cloudsql.client"',
            'role    = "roles/cloudsql.admin"',
            "for item in values(var.secret_environment) : item.secret",
        ),
        "GCP IAM contract",
    )
    runtime_client = iam[iam.index('resource "google_project_iam_member" "runtime_cloud_sql_client"') :]
    runtime_client = runtime_client[: runtime_client.find('\nresource "', 10)]
    forbid_tokens(runtime_client, ('roles/cloudsql.admin',), "runtime Cloud SQL IAM")

    effect_block = extract_variable_block(variables, "runtime_environment")
    require_tokens(
        effect_block,
        (
            'AGENCY_SOCIAL_PUBLICATION_ENABLED     = "false"',
            'AGENCY_POLITICAL_CONTENT_ENABLED      = "false"',
            'AGENCY_POLITICAL_PUBLICATION_ENABLED  = "false"',
            'AGENCY_POLITICAL_PAID_MEDIA_ENABLED   = "false"',
            'AGENCY_MODEL_EXECUTION_ENABLED        = "false"',
            'AGENCY_MODEL_EFFECT_AUTHORITY_ENABLED = "false"',
            'AGENCY_POSTGRES_SCHEMA_MODE           = "validate"',
        ),
        "effects-off runtime environment",
    )
    require_tokens(
        tests,
        (
            'run "defaults_plan_zero_resources"',
            'run "cloud_sql_rejects_estimate_above_hard_cap"',
            'run "cloud_sql_plan_is_bounded"',
            'run "cloud_run_requires_schema_receipt_and_minimal_secrets"',
            'run "effects_off_cloud_run_uses_minimal_pinned_secrets"',
        ),
        "Terraform tests",
    )


def validate_documentation(root: Path) -> None:
    runbook = (root / "docs/runbooks/gcp-pilot-deployment.md").read_text(
        encoding="utf-8"
    )
    require_tokens(
        runbook,
        (
            "DENY_APPLY",
            "4,000 COP",
            "24,609 COP",
            "AGENCY_POSTGRES_SCHEMA_MODE=validate",
            "schema_initialization_receipt_sha256",
            "cost_review_receipt_sha256",
            "must not create Cloud SQL",
        ),
        "GCP pilot runbook",
    )


def validate_repository(root: Path) -> dict[str, Any]:
    for relative in CONTRACT_FILES:
        if not (root / relative).is_file():
            raise GCPPilotReadinessError(f"contract file missing: {relative}")
    cost = validate_cost_review(root)
    validate_terraform_contract(root)
    validate_documentation(root)
    return {
        "status": "pass",
        "decision": cost["decision"],
        "authorized_monthly_cap_cop": cost["authorized_monthly_cap_units"],
        "minimum_compute_monthly_cop": cost["minimum_compute_assumption"]["rounded_monthly_cop"],
        "external_effects": 0,
    }


def copy_contract(source: Path, destination: Path) -> None:
    for relative in CONTRACT_FILES:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, target)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        result = validate_repository(args.root.resolve())
    except GCPPilotReadinessError as error:
        print(f"gcp pilot readiness: FAIL: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
