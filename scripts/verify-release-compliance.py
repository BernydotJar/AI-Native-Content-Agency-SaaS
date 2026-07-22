#!/usr/bin/env python3
"""Validate third-party, privacy, public-claim and release decisions fail closed."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

CONTRACT_FILES = (
    "compliance/third-party-inventory.json",
    "compliance/privacy-decision-register.json",
    "compliance/public-claims-policy.json",
    "compliance/release-decision.json",
)
SUPPORT_FILES = (
    "LICENSE",
    "package.json",
    "package-lock.json",
    "backend/setup.cfg",
    "backend/requirements.lock",
    "artifacts/supply-chain/license-policy.json",
    "artifacts/supply-chain/base-images.json",
    ".github/workflows/production-readiness.yml",
    "backend/agency_runtime/integration_reviews/video_use.json",
    "docs/privacy/data-classification-retention.md",
    "program/current-state.md",
    "program/release-plan.md",
    "program/critique-findings.json",
)
DIRECT_PYTHON = ("fastapi", "pg8000", "uvicorn")
REQUIRED_BLOCKERS = {"F-004", "F-007", "F-008", "F-010", "F-011"}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
UTC_TIMESTAMP = re.compile(
    r"^20[0-9]{2}-[01][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-5][0-9]Z$"
)


class ComplianceValidationError(ValueError):
    """A release-compliance invariant is invalid or incomplete."""


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ComplianceValidationError(f"{path}: invalid JSON: {error}") from error


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ComplianceValidationError(f"{label}: object required")
    return value


def sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ComplianceValidationError(f"{label}: array required")
    return value


def text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ComplianceValidationError(f"{label}: non-empty string required")
    return value.strip()


def exact_keys(item: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(item)
    if actual != expected:
        raise ComplianceValidationError(
            f"{label}: field mismatch missing={sorted(expected-actual)} "
            f"extra={sorted(actual-expected)}"
        )


def unique(items: Sequence[Mapping[str, Any]], field: str, label: str) -> set[str]:
    found: set[str] = set()
    for index, item in enumerate(items):
        value = text(item.get(field), f"{label}[{index}].{field}")
        if value in found:
            raise ComplianceValidationError(f"{label}: duplicate {field} {value!r}")
        found.add(value)
    return found


def sha256(path: Path) -> str:
    if not path.is_file():
        raise ComplianceValidationError(f"evidence file missing: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_python_lock(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+)==([^ ;\\]+)", line)
        if match:
            result[match.group(1).lower().replace("_", "-")] = match.group(2)
    return result


def expected_npm(root: Path) -> list[dict[str, str]]:
    package = mapping(read_json(root / "package.json"), "package manifest")
    lock = mapping(read_json(root / "package-lock.json"), "package lock")
    packages = mapping(lock.get("packages"), "package lock packages")
    root_package = mapping(packages.get(""), "package lock root")
    for source in ("dependencies", "devDependencies"):
        if mapping(package.get(source, {}), f"package.json {source}") != mapping(
            root_package.get(source, {}), f"package-lock {source}"
        ):
            raise ComplianceValidationError(
                f"package.json {source} differs from package-lock.json"
            )
    result: list[dict[str, str]] = []
    for source, scope in (
        ("dependencies", "runtime"),
        ("devDependencies", "development"),
    ):
        declared = mapping(root_package.get(source, {}), source)
        for name in sorted(declared):
            node = mapping(packages.get(f"node_modules/{name}"), f"node_modules/{name}")
            result.append(
                {
                    "name": name,
                    "version": text(node.get("version"), name),
                    "scope": scope,
                    "license": text(node.get("license"), f"{name} license"),
                }
            )
    return result


def setup_runtime_dependencies(path: Path) -> set[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    collecting = False
    result: set[str] = set()
    for line in lines:
        if line.strip() == "install_requires =":
            collecting = True
            continue
        if collecting:
            if not line.startswith((" ", "\t")) or not line.strip():
                break
            match = re.match(r"\s*([A-Za-z0-9_.-]+)", line)
            if match:
                result.add(match.group(1).lower().replace("_", "-"))
    return result


def expected_actions(root: Path) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for workflow in sorted((root / ".github/workflows").glob("*.yml")):
        relative = str(workflow.relative_to(root))
        for line in workflow.read_text(encoding="utf-8").splitlines():
            if "uses:" not in line:
                continue
            match = re.search(r"uses:\s*([^\s]+)@([^\s#]+)", line)
            if not match:
                raise ComplianceValidationError(
                    f"workflow action reference is invalid: {relative}"
                )
            if not HEX40.fullmatch(match.group(2)):
                raise ComplianceValidationError(
                    f"workflow action is not SHA pinned: {match.group(1)}"
                )
            item = {
                "action": match.group(1),
                "commit": match.group(2),
                "workflow": relative,
            }
            if item not in result:
                result.append(item)
    return sorted(result, key=lambda item: (item["action"], item["workflow"]))


def validate_inventory(root: Path, data: Mapping[str, Any]) -> int:
    expected = {
        "schema_version",
        "reviewed_at",
        "repository_license",
        "evidence_files",
        "npm_direct_dependencies",
        "python_direct_dependencies",
        "base_images",
        "github_actions",
        "external_candidates",
        "active_external_providers",
        "transitive_inventory_evidence",
        "approved_component_licenses",
    }
    exact_keys(data, expected, "third-party inventory")
    if data.get("schema_version") != "agency-third-party-inventory.v1":
        raise ComplianceValidationError("third-party inventory schema is unsupported")
    if not UTC_TIMESTAMP.fullmatch(text(data.get("reviewed_at"), "reviewed_at")):
        raise ComplianceValidationError("reviewed_at is invalid")

    license_record = mapping(data.get("repository_license"), "repository_license")
    exact_keys(license_record, {"spdx", "path", "sha256"}, "repository_license")
    if license_record.get("spdx") != "MIT" or license_record.get("path") != "LICENSE":
        raise ComplianceValidationError("repository license must be exact MIT")
    if sha256(root / "LICENSE") != license_record.get("sha256"):
        raise ComplianceValidationError("repository license hash mismatch")
    if not (root / "LICENSE").read_text(encoding="utf-8").startswith("MIT License"):
        raise ComplianceValidationError("repository LICENSE content is not MIT")

    raw_evidence = sequence(data.get("evidence_files"), "evidence_files")
    evidence = [
        mapping(item, f"evidence_files[{index}]")
        for index, item in enumerate(raw_evidence)
    ]
    unique(evidence, "path", "evidence_files")
    for index, item in enumerate(evidence):
        exact_keys(item, {"path", "sha256"}, f"evidence_files[{index}]")
        path = text(item.get("path"), f"evidence_files[{index}].path")
        digest = text(item.get("sha256"), f"evidence_files[{index}].sha256")
        if not HEX64.fullmatch(digest) or sha256(root / path) != digest:
            raise ComplianceValidationError(f"evidence hash mismatch: {path}")

    npm = list(sequence(data.get("npm_direct_dependencies"), "npm_direct_dependencies"))
    if npm != expected_npm(root):
        raise ComplianceValidationError(
            "npm direct inventory differs from package-lock.json"
        )
    locked = parse_python_lock(root / "backend/requirements.lock")
    if setup_runtime_dependencies(root / "backend/setup.cfg") != set(DIRECT_PYTHON):
        raise ComplianceValidationError(
            "backend/setup.cfg runtime dependencies differ from reviewed direct set"
        )
    python_licenses = {
        "fastapi": "MIT",
        "pg8000": "BSD-3-Clause",
        "uvicorn": "BSD-3-Clause",
    }
    expected_python = [
        {
            "name": name,
            "version": locked[name],
            "scope": "runtime",
            "license": python_licenses[name],
        }
        for name in DIRECT_PYTHON
    ]
    python = list(
        sequence(data.get("python_direct_dependencies"), "python_direct_dependencies")
    )
    if python != expected_python:
        raise ComplianceValidationError(
            "Python direct inventory differs from requirements.lock"
        )
    approved_licenses = set(
        sequence(data.get("approved_component_licenses"), "approved_component_licenses")
    )
    if approved_licenses != {"Apache-2.0", "BSD-3-Clause", "ISC", "MIT", "OFL-1.1"}:
        raise ComplianceValidationError("approved component license set is invalid")
    direct_licenses = {str(item.get("license", "")) for item in npm + python}
    if not direct_licenses or not direct_licenses.issubset(approved_licenses):
        raise ComplianceValidationError("direct component license is missing or unapproved")

    base_source = mapping(
        read_json(root / "artifacts/supply-chain/base-images.json"),
        "base image source",
    )
    images = mapping(base_source.get("images"), "base images")
    expected_base = [
        {"image": name, "digest": digest} for name, digest in sorted(images.items())
    ]
    base = list(sequence(data.get("base_images"), "base_images"))
    if base != expected_base or any(
        not HEX64.fullmatch(str(item.get("digest", "")).removeprefix("sha256:"))
        for item in base
    ):
        raise ComplianceValidationError(
            "base image inventory differs from digest source"
        )

    actions = list(sequence(data.get("github_actions"), "github_actions"))
    if actions != expected_actions(root):
        raise ComplianceValidationError(
            "GitHub Actions inventory differs from workflows"
        )

    candidates_raw = sequence(data.get("external_candidates"), "external_candidates")
    candidates = [
        mapping(item, f"external_candidates[{index}]")
        for index, item in enumerate(candidates_raw)
    ]
    unique(candidates, "id", "external_candidates")
    if len(candidates) != 1 or candidates[0].get("id") != "video-use":
        raise ComplianceValidationError("video-use candidate inventory is required")
    candidate = candidates[0]
    exact_keys(
        candidate,
        {"id", "enabled", "status", "repository", "commit", "license", "manifest_path"},
        "external_candidates[0]",
    )
    manifest = mapping(
        read_json(
            root
            / text(candidate.get("manifest_path"), "video-use manifest_path")
        ),
        "video-use manifest",
    )
    if (
        candidate.get("enabled") is not False
        or candidate.get("status") != "reviewed_disabled"
        or candidate.get("commit") != manifest.get("upstream_commit")
        or candidate.get("repository") != manifest.get("upstream_repository")
        or candidate.get("license") != manifest.get("license")
        or manifest.get("activation_allowed") is not False
        or manifest.get("execution_available") is not False
        or manifest.get("external_effects_enabled") is not False
    ):
        raise ComplianceValidationError(
            "video-use inventory differs from reviewed-disabled manifest"
        )
    active = sequence(
        data.get("active_external_providers"), "active_external_providers"
    )
    if active:
        raise ComplianceValidationError("active external providers are not authorized")
    transitive = mapping(
        data.get("transitive_inventory_evidence"),
        "transitive_inventory_evidence",
    )
    if set(transitive) != {"npm", "python", "operating_system"} or any(
        not text(value, "transitive evidence") for value in transitive.values()
    ):
        raise ComplianceValidationError("transitive inventory evidence is incomplete")
    return len(npm) + len(python) + len(base) + len(actions) + len(candidates)


def validate_privacy(root: Path, data: Mapping[str, Any]) -> int:
    expected = {
        "schema_version",
        "source_document",
        "operating_entity",
        "jurisdiction",
        "controller_processor_role",
        "risk_classification",
        "legal_advice",
        "release_recommendation",
        "destructive_automation_enabled",
        "policy_decisions",
        "external_provider_decisions",
        "required_human_reviewers",
        "resume_conditions",
    }
    exact_keys(data, expected, "privacy decision register")
    if data.get("schema_version") != "agency-privacy-decision-register.v1":
        raise ComplianceValidationError("privacy decision schema is unsupported")
    for field in ("operating_entity", "jurisdiction", "controller_processor_role"):
        if data.get(field) != "UNKNOWN":
            raise ComplianceValidationError(
                f"{field} must remain UNKNOWN without accountable approval"
            )
    if (
        data.get("risk_classification") != "YELLOW_UNKNOWN"
        or data.get("legal_advice") is not False
    ):
        raise ComplianceValidationError("privacy risk/legal-advice boundary is invalid")
    if data.get("release_recommendation") != "DENY_RELEASE":
        raise ComplianceValidationError("privacy register cannot approve release")
    if data.get("destructive_automation_enabled") is not False:
        raise ComplianceValidationError(
            "destructive privacy automation is not approved"
        )

    policies_raw = sequence(data.get("policy_decisions"), "policy_decisions")
    policies = [
        mapping(item, f"policy_decisions[{index}]")
        for index, item in enumerate(policies_raw)
    ]
    unique(policies, "id", "policy_decisions")
    if len(policies) < 7:
        raise ComplianceValidationError("privacy policy decisions are incomplete")
    for index, item in enumerate(policies):
        exact_keys(
            item,
            {
                "id",
                "data_class",
                "status",
                "retention_days",
                "deletion_implemented",
                "legal_hold_implemented",
            },
            f"policy_decisions[{index}]",
        )
        if item.get("status") != "unapproved":
            raise ComplianceValidationError(
                "privacy policy approval lacks accountable source"
            )
        if item.get("retention_days") is not None:
            raise ComplianceValidationError(
                "retention duration cannot be invented while unapproved"
            )
        if (
            item.get("deletion_implemented") is not False
            or item.get("legal_hold_implemented") is not False
        ):
            raise ComplianceValidationError(
                "deletion/legal hold cannot be implemented before approval"
            )

    providers_raw = sequence(
        data.get("external_provider_decisions"), "external_provider_decisions"
    )
    providers = [
        mapping(item, f"external_provider_decisions[{index}]")
        for index, item in enumerate(providers_raw)
    ]
    unique(providers, "id", "external_provider_decisions")
    for index, provider in enumerate(providers):
        exact_keys(
            provider,
            {
                "id", "integration_id", "enabled", "status", "data_categories",
                "contract_status", "region_status", "retention_status",
                "deletion_status", "training_use_status",
            },
            f"external_provider_decisions[{index}]",
        )
        if provider.get("integration_id") != "video-use" or list(
            sequence(provider.get("data_categories"), "provider data_categories")
        ) != ["media_audio"]:
            raise ComplianceValidationError("provider data boundary is invalid")
        if (
            provider.get("enabled") is not False
            or provider.get("status") != "reviewed_disabled"
        ):
            raise ComplianceValidationError("provider activation is not approved")
        for field in (
            "contract_status",
            "region_status",
            "retention_status",
            "deletion_status",
            "training_use_status",
        ):
            if provider.get(field) != "UNKNOWN":
                raise ComplianceValidationError(f"provider {field} must remain UNKNOWN")
    reviewers = set(
        sequence(data.get("required_human_reviewers"), "required_human_reviewers")
    )
    if reviewers != {
        "privacy_legal_reviewer",
        "security_reviewer",
        "business_data_owner",
    }:
        raise ComplianceValidationError("required privacy reviewers are incomplete")
    conditions = sequence(data.get("resume_conditions"), "resume_conditions")
    if len(conditions) < 5 or len(set(conditions)) != len(conditions):
        raise ComplianceValidationError("privacy resume conditions are incomplete")
    source = root / text(data.get("source_document"), "source_document")
    source_text = source.read_text(encoding="utf-8")
    if (
        "Jurisdiction: `UNKNOWN`" not in source_text
        or "no retention/deletion policy is approved" not in source_text
    ):
        raise ComplianceValidationError(
            "privacy source document contradicts decision register"
        )
    return len(policies) + len(providers)


def validate_claims(root: Path, data: Mapping[str, Any]) -> int:
    exact_keys(
        data,
        {
            "schema_version",
            "allowed_release_label",
            "surfaces",
            "prohibited_patterns",
            "required_disclosures",
        },
        "public claims policy",
    )
    if (
        data.get("schema_version") != "agency-public-claims-policy.v1"
        or data.get("allowed_release_label") != "sandbox_candidate"
    ):
        raise ComplianceValidationError(
            "public claims policy schema/release label is invalid"
        )
    surfaces = list(sequence(data.get("surfaces"), "claim surfaces"))
    if not surfaces or len(set(surfaces)) != len(surfaces):
        raise ComplianceValidationError("claim surfaces are empty or duplicated")
    content: dict[str, str] = {}
    for relative in surfaces:
        path = root / text(relative, "claim surface")
        if not path.is_file():
            raise ComplianceValidationError(f"claim surface missing: {relative}")
        content[str(relative)] = path.read_text(encoding="utf-8")
    patterns_raw = sequence(data.get("prohibited_patterns"), "prohibited_patterns")
    patterns = [
        mapping(item, f"prohibited_patterns[{index}]")
        for index, item in enumerate(patterns_raw)
    ]
    unique(patterns, "id", "prohibited_patterns")
    for index, item in enumerate(patterns):
        exact_keys(item, {"id", "pattern"}, f"prohibited_patterns[{index}]")
        try:
            pattern = re.compile(
                text(item.get("pattern"), "claim pattern"), re.IGNORECASE
            )
        except re.error as error:
            raise ComplianceValidationError(
                f"claim pattern is invalid: {error}"
            ) from error
        for relative, source in content.items():
            if pattern.search(source):
                raise ComplianceValidationError(
                    f"prohibited public claim {item['id']} in {relative}"
                )
    disclosures_raw = sequence(
        data.get("required_disclosures"), "required_disclosures"
    )
    disclosures = [
        mapping(item, f"required_disclosures[{index}]")
        for index, item in enumerate(disclosures_raw)
    ]
    for index, item in enumerate(disclosures):
        exact_keys(item, {"path", "text"}, f"required_disclosures[{index}]")
        relative = text(item.get("path"), "disclosure path")
        required = text(item.get("text"), "disclosure text")
        if relative not in content or required not in content[relative]:
            raise ComplianceValidationError(
                f"required disclosure missing from {relative}"
            )
    return len(surfaces)


def validate_release(root: Path, data: Mapping[str, Any]) -> None:
    expected = {
        "schema_version",
        "decision",
        "allow_release",
        "allow_cloud_apply",
        "allow_external_effects",
        "allow_destructive_data_action",
        "legal_privacy_approval",
        "independent_human_approval",
        "blocked_findings",
        "reason_codes",
        "source_documents",
    }
    exact_keys(data, expected, "release decision")
    if data.get("schema_version") != "agency-release-decision.v1":
        raise ComplianceValidationError("release decision schema is unsupported")
    if data.get("decision") != "DENY_RELEASE" or data.get("allow_release") is not False:
        raise ComplianceValidationError("release cannot be allowed with open blockers")
    for field in (
        "allow_cloud_apply",
        "allow_external_effects",
        "allow_destructive_data_action",
        "legal_privacy_approval",
        "independent_human_approval",
    ):
        if data.get(field) is not False:
            raise ComplianceValidationError(
                f"release authority {field} is not approved"
            )
    blockers = set(sequence(data.get("blocked_findings"), "blocked_findings"))
    if not REQUIRED_BLOCKERS.issubset(blockers):
        raise ComplianceValidationError("release blocker inventory is incomplete")
    findings = mapping(
        read_json(root / "program/critique-findings.json"), "critique findings"
    )
    status = {
        item.get("id"): item.get("status")
        for item in sequence(findings.get("findings"), "findings")
        if isinstance(item, Mapping)
    }
    if any(
        status.get(identifier) not in {"OPEN", "BLOCKED_EXTERNAL"}
        for identifier in REQUIRED_BLOCKERS
    ):
        raise ComplianceValidationError(
            "release decision differs from unresolved HIGH findings"
        )
    reasons = sequence(data.get("reason_codes"), "reason_codes")
    if len(reasons) < 6 or len(set(reasons)) != len(reasons):
        raise ComplianceValidationError("release reason codes are incomplete")
    source_documents = list(sequence(data.get("source_documents"), "source_documents"))
    if not source_documents or len(set(source_documents)) != len(source_documents):
        raise ComplianceValidationError("release source documents are empty or duplicated")
    for relative in source_documents:
        if not (root / text(relative, "source document")).is_file():
            raise ComplianceValidationError(
                f"release source document missing: {relative}"
            )
    current = (root / "program/current-state.md").read_text(encoding="utf-8")
    if (
        "Release recommendation: `DENY_RELEASE`" not in current
        or "Cloud recommendation: `DENY_APPLY`" not in current
    ):
        raise ComplianceValidationError(
            "operational state contradicts release decision"
        )


def validate_repository(root: Path) -> dict[str, Any]:
    root = root.resolve()
    inventory = mapping(read_json(root / CONTRACT_FILES[0]), "third-party inventory")
    privacy = mapping(
        read_json(root / CONTRACT_FILES[1]), "privacy decision register"
    )
    claims = mapping(read_json(root / CONTRACT_FILES[2]), "public claims policy")
    release = mapping(read_json(root / CONTRACT_FILES[3]), "release decision")
    components = validate_inventory(root, inventory)
    human = validate_privacy(root, privacy)
    surfaces = validate_claims(root, claims)
    validate_release(root, release)
    return {
        "status": "pass",
        "release_decision": release["decision"],
        "active_external_providers": len(inventory["active_external_providers"]),
        "third_party_components": components,
        "open_human_decisions": human,
        "claim_surfaces": surfaces,
    }


def copy_contract(source: Path, target: Path) -> None:
    claims = mapping(
        read_json(source / "compliance/public-claims-policy.json"), "claims"
    )
    release = mapping(
        read_json(source / "compliance/release-decision.json"), "release decision"
    )
    paths = (
        set(CONTRACT_FILES)
        | set(SUPPORT_FILES)
        | set(sequence(claims.get("surfaces"), "surfaces"))
        | set(sequence(release.get("source_documents"), "source_documents"))
    )
    for relative in paths:
        src = source / str(relative)
        dst = target / str(relative)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    args = parser.parse_args()
    try:
        result = validate_repository(args.root)
    except ComplianceValidationError as error:
        print(f"compliance_state=fail\nerror={error}", file=sys.stderr)
        return 1
    print("compliance_state=pass")
    for key in (
        "release_decision",
        "third_party_components",
        "active_external_providers",
        "open_human_decisions",
        "claim_surfaces",
    ):
        print(f"{key}={result[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
