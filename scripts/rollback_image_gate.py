#!/usr/bin/env python3
"""Fail closed unless the desired image and one protected rollback image exist."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Sequence


IMAGE_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
ROLLBACK_TAG = "rollback-current"
SCHEMA_VERSION = "artifact-rollback-evidence.v1"


class RollbackGateError(RuntimeError):
    pass


Runner = Callable[..., subprocess.CompletedProcess[str]]


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RollbackGateError("invalid rollback evidence: {}".format(path.name)) from error


def _write(path: Path, report: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parse_application_image(reference: str, artifact_repository: str) -> str:
    expected_prefix = "{}/app@".format(artifact_repository.rstrip("/"))
    if not reference.startswith(expected_prefix):
        raise RollbackGateError("application image is outside the exact foundation repository")
    digest = reference[len(expected_prefix) :]
    if IMAGE_DIGEST.fullmatch(digest) is None:
        raise RollbackGateError("application image is not pinned by one sha256 digest")
    return digest


def _run_json(
    command: Sequence[str],
    *,
    runner: Runner,
    allow_not_found: bool = False,
) -> Optional[Any]:
    completed = runner(
        list(command),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        combined = "{}\n{}".format(completed.stdout, completed.stderr).lower()
        if allow_not_found and (
            "not_found" in combined or "not found" in combined or "cannot find" in combined
        ):
            return None
        raise RollbackGateError("cloud evidence command failed: {}".format(" ".join(command[:4])))
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RollbackGateError("cloud evidence command returned invalid JSON") from error


def _require_digest(evidence: Any, digest: str, label: str) -> None:
    observed = set(IMAGE_DIGEST.findall(json.dumps(evidence, sort_keys=True)))
    if digest not in observed:
        raise RollbackGateError("{} did not resolve to the expected digest".format(label))


def _service_application_image(service: Any) -> str:
    if not isinstance(service, dict):
        raise RollbackGateError("Cloud Run service evidence is malformed")
    containers: Any = service
    for key in ("spec", "template", "spec", "containers"):
        if not isinstance(containers, dict) or key not in containers:
            break
        containers = containers[key]
    if not isinstance(containers, list):
        containers = (
            service.get("template", {}).get("containers")
            if isinstance(service.get("template"), dict)
            else None
        )
    if not isinstance(containers, list):
        raise RollbackGateError("Cloud Run service containers are absent")
    images = [
        container.get("image")
        for container in containers
        if isinstance(container, dict) and container.get("name") == "application"
    ]
    if len(images) != 1 or not isinstance(images[0], str):
        raise RollbackGateError("Cloud Run application container is not unique")
    return images[0]


def _describe_image(reference: str, *, runner: Runner) -> Any:
    evidence = _run_json(
        [
            "gcloud",
            "artifacts",
            "docker",
            "images",
            "describe",
            reference,
            "--format=json",
        ],
        runner=runner,
    )
    if evidence is None:  # pragma: no cover - impossible without allow_not_found
        raise RollbackGateError("image evidence is absent")
    return evidence


def inspect(
    *,
    artifact_repository: str,
    desired_image: str,
    project_id: str,
    region: str,
    service_name: str,
    require_protected_rollback: bool,
    baseline: Optional[Any] = None,
    runner: Runner = subprocess.run,
) -> Dict[str, object]:
    desired_digest = _parse_application_image(desired_image, artifact_repository)
    _require_digest(
        _describe_image(desired_image, runner=runner),
        desired_digest,
        "desired application image",
    )

    service = _run_json(
        [
            "gcloud",
            "run",
            "services",
            "describe",
            service_name,
            "--project",
            project_id,
            "--region",
            region,
            "--format=json",
        ],
        runner=runner,
        allow_not_found=True,
    )
    rollback_image: Optional[str] = None
    rollback_digest: Optional[str] = None
    retention_verified = False
    if service is not None:
        rollback_image = _service_application_image(service)
        rollback_digest = _parse_application_image(rollback_image, artifact_repository)
        _require_digest(
            _describe_image(rollback_image, runner=runner),
            rollback_digest,
            "rollback application image",
        )
        if require_protected_rollback:
            protected_reference = "{}/app:{}".format(artifact_repository.rstrip("/"), ROLLBACK_TAG)
            _require_digest(
                _describe_image(protected_reference, runner=runner),
                rollback_digest,
                "protected rollback tag",
            )
            retention_verified = True

    report: Dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS",
        "artifact_repository": artifact_repository.rstrip("/"),
        "desired_image": desired_image,
        "rollback_image": rollback_image,
        "rollback_depth": 1,
        "retention_tag": ROLLBACK_TAG,
        "retention_verified": retention_verified,
        "first_deployment": rollback_image is None,
        "checks": [
            "desired_digest_exists",
            "immediate_predecessor_digest_exists",
            "single_moving_rollback_tag",
        ],
        "limitations": [
            "Rollback is intentionally bounded to the immediately preceding deployed application digest.",
        ],
    }
    if baseline is not None:
        if not isinstance(baseline, dict):
            raise RollbackGateError("baseline rollback evidence is malformed")
        comparable = (
            "schema_version",
            "status",
            "artifact_repository",
            "desired_image",
            "rollback_image",
            "rollback_depth",
            "retention_tag",
            "first_deployment",
        )
        if any(baseline.get(key) != report.get(key) for key in comparable):
            raise RollbackGateError("rollback candidate changed after the reviewed runtime plan")
    return report


def protect(
    baseline: Any,
    *,
    runner: Runner = subprocess.run,
) -> Dict[str, object]:
    if (
        not isinstance(baseline, dict)
        or baseline.get("schema_version") != SCHEMA_VERSION
        or baseline.get("status") != "PASS"
    ):
        raise RollbackGateError("baseline rollback evidence is malformed")
    repository = baseline.get("artifact_repository")
    rollback_image = baseline.get("rollback_image")
    if not isinstance(repository, str):
        raise RollbackGateError("baseline artifact repository is absent")
    if rollback_image is None:
        return {
            **baseline,
            "retention_verified": False,
            "protection_action": "FIRST_DEPLOYMENT_NO_PREDECESSOR",
        }
    if not isinstance(rollback_image, str):
        raise RollbackGateError("baseline rollback image is malformed")
    rollback_digest = _parse_application_image(rollback_image, repository)
    tag_reference = "{}/app:{}".format(repository, ROLLBACK_TAG)
    completed = runner(
        [
            "gcloud",
            "artifacts",
            "docker",
            "tags",
            "add",
            rollback_image,
            tag_reference,
            "--quiet",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RollbackGateError("failed to move the protected rollback tag")
    _require_digest(
        _describe_image(tag_reference, runner=runner),
        rollback_digest,
        "protected rollback tag",
    )
    return {
        **baseline,
        "retention_verified": True,
        "protection_action": "MOVED_SINGLE_ROLLBACK_TAG",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("--artifact-repository", required=True)
    inspect_parser.add_argument("--desired-image", required=True)
    inspect_parser.add_argument("--project-id", required=True)
    inspect_parser.add_argument("--region", required=True)
    inspect_parser.add_argument("--service-name", required=True)
    inspect_parser.add_argument("--require-protected-rollback", action="store_true")
    inspect_parser.add_argument("--baseline-report", type=Path)
    inspect_parser.add_argument("--output", type=Path, required=True)

    protect_parser = subparsers.add_parser("protect")
    protect_parser.add_argument("--baseline-report", type=Path, required=True)
    protect_parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        if arguments.command == "inspect":
            baseline = (
                _load(arguments.baseline_report) if arguments.baseline_report is not None else None
            )
            report = inspect(
                artifact_repository=arguments.artifact_repository,
                desired_image=arguments.desired_image,
                project_id=arguments.project_id,
                region=arguments.region,
                service_name=arguments.service_name,
                require_protected_rollback=arguments.require_protected_rollback,
                baseline=baseline,
            )
        else:
            report = protect(_load(arguments.baseline_report))
        _write(arguments.output, report)
        print(json.dumps(report, sort_keys=True))
        return 0
    except RollbackGateError as error:
        print("rollback image gate denied: {}".format(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
