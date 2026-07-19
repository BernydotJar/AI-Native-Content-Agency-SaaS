#!/usr/bin/env python3
"""Fail closed on high-confidence secrets, personal paths, and unsafe artifacts."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Iterable, Optional


ROOT = Path(__file__).resolve().parents[1]
MAX_SCANNED_BYTES = 5 * 1024 * 1024

CONTENT_RULES = {
    "aws_access_key": re.compile(rb"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "github_token": re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{36,255}\b"),
    "google_api_key": re.compile(rb"\bAIza[0-9A-Za-z_-]{35}\b"),
    "private_key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "slack_token": re.compile(rb"\bxox[baprs]-[0-9A-Za-z-]{20,}\b"),
}
PERSONAL_PATH_RULES = {
    "macos_personal_path": b"/" + b"Users" + b"/",
    "windows_personal_path": b"C:" + b"\\" + b"Users" + b"\\",
}
SERVICE_ACCOUNT_TYPE = b'"type"' + b":"
SERVICE_ACCOUNT_VALUE = b'"service_' + b'account"'
PRIVATE_KEY_FIELD = b'"private_' + b'key"'


def candidate_paths() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return sorted(
        (ROOT / raw.decode("utf-8", errors="surrogateescape"))
        for raw in result.stdout.split(b"\0")
        if raw
    )


def _unsafe_filename(relative: str) -> Optional[str]:
    name = Path(relative).name
    lower = name.lower()
    if name == ".env":
        return "environment_secret_file"
    if lower.startswith("gha-creds-") and lower.endswith(".json"):
        return "github_credential_artifact"
    if lower == "terraform.tfstate" or ".tfstate." in lower:
        return "terraform_state_artifact"
    if lower == "tfplan" or lower.startswith("tfplan.") or lower.endswith(".tfplan"):
        return "terraform_plan_artifact"
    if lower.endswith((".p12", ".pfx", ".pem")):
        return "credential_file_extension"
    return None


def _content_findings(content: bytes, label: str) -> list[dict[str, str]]:
    findings = [
        {"path": label, "rule": rule}
        for rule, pattern in CONTENT_RULES.items()
        if pattern.search(content)
    ]
    findings.extend(
        {"path": label, "rule": rule}
        for rule, marker in PERSONAL_PATH_RULES.items()
        if marker in content
    )
    if (
        SERVICE_ACCOUNT_TYPE in content
        and SERVICE_ACCOUNT_VALUE in content
        and PRIVATE_KEY_FIELD in content
    ):
        findings.append({"path": label, "rule": "google_service_account_key_json"})
    return findings


def scan(paths: Iterable[Path]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []

    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        relative = path.relative_to(ROOT).as_posix()
        filename_rule = _unsafe_filename(relative)
        if filename_rule:
            findings.append({"path": relative, "rule": filename_rule})
        if path.stat().st_size > MAX_SCANNED_BYTES:
            continue
        content = path.read_bytes()
        if b"\0" in content:
            continue
        findings.extend(_content_findings(content, relative))
    return sorted(findings, key=lambda item: (item["path"], item["rule"]))


def scan_history() -> tuple[int, list[dict[str, str]]]:
    commit_count = int(subprocess.run(
        ["git", "rev-list", "--all", "--count"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip() or "0")
    names = subprocess.run(
        ["git", "log", "--all", "--name-only", "--format=", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    findings = []
    for raw in names.split(b"\0"):
        relative = raw.decode("utf-8", errors="replace").strip()
        if not relative:
            continue
        filename_rule = _unsafe_filename(relative)
        if filename_rule:
            findings.append({"path": "git-history:{}".format(relative), "rule": filename_rule})
    patches = subprocess.run(
        ["git", "log", "--all", "-p", "--no-ext-diff", "--no-renames", "--format="],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    findings.extend(_content_findings(patches, "git-history"))
    return commit_count, sorted(findings, key=lambda item: (item["path"], item["rule"]))


def main() -> None:
    paths = candidate_paths()
    history_commit_count, history_findings = scan_history()
    findings = scan(paths) + history_findings
    report = {
        "evaluation_id": "REPOSITORY-INTEGRITY-001",
        "status": "FAIL" if findings else "PASS",
        "scanned_file_count": len(paths),
        "scanned_history_commit_count": history_commit_count,
        "findings": findings,
        "limitations": [
            "This deterministic high-confidence scan complements dependency audits and GitHub secret scanning.",
            "Potential secret values are never emitted in the report.",
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(1 if findings else 0)


if __name__ == "__main__":
    main()
