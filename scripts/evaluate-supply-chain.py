#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

FindingKey = tuple[str, str, str, str, str]


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object in {path}")
    return value


def package_type(component: dict[str, Any]) -> str | None:
    for item in component.get("properties", []):
        if item.get("name") == "syft:package:type":
            return item.get("value")
    return None


def component_licenses(component: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for item in component.get("licenses", []):
        if not isinstance(item, dict):
            continue
        license_value = item.get("license")
        if isinstance(license_value, dict):
            value = license_value.get("id") or license_value.get("name")
            if value:
                values.append(str(value))
        expression = item.get("expression")
        if expression:
            values.append(str(expression))
    return sorted(set(values))


def finding_key(item: dict[str, Any]) -> FindingKey:
    artifact = item["artifact"]
    vulnerability = item["vulnerability"]
    return (
        str(artifact.get("type", "")),
        str(artifact.get("name", "")),
        str(artifact.get("version", "")),
        str(vulnerability.get("id", "")),
        str(vulnerability.get("severity", "")),
    )


def baseline_key(item: dict[str, Any]) -> FindingKey:
    return (
        str(item["package_type"]),
        str(item["package"]),
        str(item["version"]),
        str(item["vulnerability"]),
        str(item["severity"]),
    )


def format_key(key: FindingKey) -> str:
    package_type_value, package, version, vulnerability, severity = key
    return f"{severity} {vulnerability} {package_type_value}:{package}@{version}"


def fix_versions(item: dict[str, Any]) -> tuple[str, ...]:
    fix = item.get("vulnerability", {}).get("fix", {})
    versions = fix.get("versions", []) if isinstance(fix, dict) else []
    return tuple(sorted(str(version) for version in versions if version))


def evaluate_vulnerabilities(
    report: dict[str, Any], baseline: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    expiry = date.fromisoformat(str(baseline["expires_on"]))
    if date.today() > expiry:
        errors.append(f"vulnerability baseline expired on {expiry.isoformat()}")

    all_findings = report.get("matches", [])
    counts = Counter(
        str(item.get("vulnerability", {}).get("severity", "Unknown"))
        for item in all_findings
    )
    current_items = {
        finding_key(item): item
        for item in all_findings
        if item.get("vulnerability", {}).get("severity") in {"Critical", "High"}
    }
    accepted_items = {
        baseline_key(item): item for item in baseline.get("accepted", [])
    }
    accepted = set(accepted_items)

    invalid_baseline = sorted(item for item in accepted if item[4] != "High")
    errors.extend(
        f"baseline may only accept High findings: {format_key(item)}"
        for item in invalid_baseline
    )

    critical = sorted(item for item in current_items if item[4] == "Critical")
    errors.extend(
        f"unaccepted Critical finding: {format_key(item)}" for item in critical
    )

    current_high = {item for item in current_items if item[4] == "High"}
    errors.extend(
        f"new High finding: {format_key(item)}"
        for item in sorted(current_high - accepted)
    )
    errors.extend(
        f"stale baseline entry: {format_key(item)}"
        for item in sorted(accepted - current_high)
    )

    fixable_counts: Counter[str] = Counter()
    fix_exception_hits: list[str] = []
    for key, finding in current_items.items():
        versions = fix_versions(finding)
        if not versions:
            continue
        fixable_counts[key[4]] += 1
        if key[4] == "Critical":
            continue
        accepted_entry = accepted_items.get(key)
        exception = (
            str(accepted_entry.get("fix_exception", "")).strip()
            if accepted_entry is not None
            else ""
        )
        if not exception:
            errors.append(
                "fixable High finding lacks an explicit compatibility exception: "
                f"{format_key(key)} fixes={','.join(versions)}"
            )
        else:
            fix_exception_hits.append(format_key(key))

    for key, accepted_entry in accepted_items.items():
        if not str(accepted_entry.get("reason", "")).strip():
            errors.append(f"baseline entry lacks a review reason: {format_key(key)}")
        if accepted_entry.get("fix_exception") and key not in current_items:
            errors.append(f"stale fix exception: {format_key(key)}")

    return {
        "counts": dict(sorted(counts.items())),
        "fixable_counts": dict(sorted(fixable_counts.items())),
        "accepted_high_findings": len(current_high & accepted),
        "accepted_fix_exceptions": sorted(fix_exception_hits),
    }, errors


def evaluate_licenses(
    sbom: dict[str, Any], policy: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    package_types = set(policy.get("package_types", []))
    allowed = set(policy.get("allowed_licenses", []))
    denied_tokens = tuple(str(item).upper() for item in policy.get("denied_tokens", []))
    exceptions = {
        (str(item["package"]), str(item["version"]))
        for item in policy.get("missing_license_exceptions", [])
    }
    reviewed_acceptances: dict[tuple[str, str, str], str] = {}
    for item in policy.get("reviewed_license_acceptances", []):
        package = str(item.get("package", "")).strip()
        version = str(item.get("version", "")).strip()
        reported = str(item.get("reported_license", "")).strip()
        reason = str(item.get("reason", "")).strip()
        key = (package, version, reported)
        if not all(key) or not reason:
            errors.append(
                "reviewed license acceptance requires package, version, "
                "reported_license, and reason"
            )
            continue
        if key in reviewed_acceptances:
            errors.append(
                "duplicate reviewed license acceptance: "
                f"{reported}: {package}@{version}"
            )
            continue
        reviewed_acceptances[key] = reason

    reviewed_mappings: dict[tuple[str, str, str], tuple[str, ...]] = {}
    for item in policy.get("reviewed_license_mappings", []):
        package = str(item.get("package", "")).strip()
        version = str(item.get("version", "")).strip()
        reported = str(item.get("reported_license", "")).strip()
        normalized = tuple(
            str(value).strip()
            for value in item.get("normalized_licenses", [])
            if str(value).strip()
        )
        reason = str(item.get("reason", "")).strip()
        key = (package, version, reported)
        if not all(key) or not normalized or not reason:
            errors.append(
                "reviewed license mapping requires package, version, "
                "reported_license, normalized_licenses, and reason"
            )
            continue
        if key in reviewed_mappings:
            errors.append(
                "duplicate reviewed license mapping: "
                f"{reported}: {package}@{version}"
            )
            continue
        reviewed_mappings[key] = normalized

    packages: list[tuple[str, str, list[str]]] = []
    exception_hits: list[str] = []
    acceptance_hits: list[str] = []
    mapping_hits: list[str] = []
    license_counts: Counter[str] = Counter()
    for component in sbom.get("components", []):
        component_type = package_type(component)
        if component_type not in package_types:
            continue
        name = str(component.get("name", ""))
        version = str(component.get("version", ""))
        licenses = component_licenses(component)
        packages.append((name, version, licenses))
        if not licenses:
            if (name, version) in exceptions:
                exception_hits.append(f"{name}@{version}")
            else:
                errors.append(f"missing license metadata: {name}@{version}")
            continue
        for license_name in licenses:
            license_counts[license_name] += 1
            upper = license_name.upper()
            if any(token in upper for token in denied_tokens):
                errors.append(f"denied license {license_name}: {name}@{version}")
                continue
            if license_name in allowed:
                continue
            exact_key = (name, version, license_name)
            if exact_key in reviewed_acceptances:
                acceptance_hits.append(f"{name}@{version}: {license_name}")
                continue
            mapping_key = exact_key
            normalized_licenses = reviewed_mappings.get(mapping_key)
            if normalized_licenses is None:
                errors.append(f"unapproved license {license_name}: {name}@{version}")
                continue
            mapping_valid = True
            for normalized_license in normalized_licenses:
                normalized_upper = normalized_license.upper()
                if any(token in normalized_upper for token in denied_tokens):
                    errors.append(
                        "reviewed license mapping resolves to denied license "
                        f"{normalized_license}: {name}@{version}"
                    )
                    mapping_valid = False
                elif normalized_license not in allowed:
                    errors.append(
                        "reviewed license mapping resolves to unapproved license "
                        f"{normalized_license}: {name}@{version}"
                    )
                    mapping_valid = False
            if mapping_valid:
                mapping_hits.append(f"{name}@{version}: {license_name}")

    expected_exceptions = {f"{name}@{version}" for name, version in exceptions}
    errors.extend(
        f"stale missing-license exception: {item}"
        for item in sorted(expected_exceptions - set(exception_hits))
    )
    expected_acceptances = {
        f"{name}@{version}: {reported}"
        for name, version, reported in reviewed_acceptances
    }
    errors.extend(
        f"stale reviewed license acceptance: {item}"
        for item in sorted(expected_acceptances - set(acceptance_hits))
    )
    expected_mappings = {
        f"{name}@{version}: {reported}"
        for name, version, reported in reviewed_mappings
    }
    errors.extend(
        f"stale reviewed license mapping: {item}"
        for item in sorted(expected_mappings - set(mapping_hits))
    )

    return {
        "packages_evaluated": len(packages),
        "licenses": dict(sorted(license_counts.items())),
        "missing_license_exceptions_used": sorted(exception_hits),
        "reviewed_license_acceptances_used": sorted(acceptance_hits),
        "reviewed_license_mappings_used": sorted(mapping_hits),
    }, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sbom", type=Path, required=True)
    parser.add_argument("--vulnerabilities", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--license-policy", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    vulnerability_summary, vulnerability_errors = evaluate_vulnerabilities(
        load_json(args.vulnerabilities), load_json(args.baseline)
    )
    license_summary, license_errors = evaluate_licenses(
        load_json(args.sbom), load_json(args.license_policy)
    )
    errors = vulnerability_errors + license_errors

    baseline = load_json(args.baseline)
    summary = {
        "status": "pass" if not errors else "fail",
        "vulnerabilities": vulnerability_summary,
        "baseline_expires_on": baseline["expires_on"],
        "license_policy": license_summary,
        "errors": errors,
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
