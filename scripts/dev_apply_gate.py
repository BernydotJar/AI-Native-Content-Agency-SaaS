#!/usr/bin/env python3
"""Create review metadata and verify the exact dev-apply attestation.

The verifier intentionally uses only the Python standard library so it can run
before the apply job authenticates to Google Cloud. The attestation is supplied
through a protected GitHub environment secret and is never written to disk.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


METADATA_SCHEMA = "dev-plan-metadata.v1"
ATTESTATION_SCHEMA = "dev-apply-attestation.v1"
ALLOW_DECISION = "ALLOW_DEV_APPLY"
MAX_ATTESTATION_BYTES = 16_384
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
COMMIT_PATTERN = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
IMAGE_PATTERN = re.compile(r"^[A-Za-z0-9._:/-]+@sha256:[0-9a-f]{64}$")
IDENTITY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
RUN_ID_PATTERN = re.compile(r"^[0-9]{1,32}$")
WORKFLOW_REF_PATTERN = re.compile(
    r"^[^\s@]+/\.github/workflows/[^\s@]+\.ya?ml@refs/heads/[^\s@]+$"
)
ATTESTATION_KEYS = frozenset(
    {
        "schema_version",
        "decision",
        "plan_sha256",
        "source_tree_sha256",
        "source_commit",
        "image_reference",
        "workflow_ref",
        "workflow_actor",
        "reviewer",
        "environment",
        "reviewed_at",
        "evidence_url",
    }
)


class GateError(ValueError):
    """A fail-closed attestation or source-tree validation error."""


def _run_git(repository: Path, arguments: Sequence[str]) -> bytes:
    result = subprocess.run(
        ["git", *arguments],
        cwd=str(repository),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise GateError("git source-tree inspection failed")
    return result.stdout


def _require_clean_tracked_tree(repository: Path) -> None:
    for arguments in (
        ["diff", "--quiet", "--ignore-submodules=none", "--"],
        ["diff", "--cached", "--quiet", "--ignore-submodules=none", "--"],
    ):
        result = subprocess.run(
            ["git", *arguments],
            cwd=str(repository),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode == 1:
            raise GateError("tracked source tree contains uncommitted changes")
        if result.returncode != 0:
            raise GateError("git source-tree cleanliness check failed")


def _tracked_entries(repository: Path) -> List[Tuple[bytes, bytes, bytes]]:
    raw = _run_git(repository, ["ls-files", "--stage", "-z"])
    entries: List[Tuple[bytes, bytes, bytes]] = []
    seen_paths = set()
    for record in raw.split(b"\0"):
        if not record:
            continue
        try:
            metadata, path = record.split(b"\t", 1)
            mode, object_id, stage = metadata.split(b" ", 2)
        except ValueError as error:
            raise GateError("git returned malformed tracked-file metadata") from error
        if stage != b"0":
            raise GateError("source index contains an unresolved merge stage")
        if not path or path in seen_paths:
            raise GateError("source index contains an invalid tracked path")
        seen_paths.add(path)
        entries.append((path, mode, object_id))
    if not entries:
        raise GateError("source tree has no tracked files")
    return sorted(entries, key=lambda entry: entry[0])


def _hash_field(hasher: Any, name: bytes, value: bytes) -> None:
    hasher.update(name)
    hasher.update(b"\0")
    hasher.update(len(value).to_bytes(8, byteorder="big", signed=False))
    hasher.update(value)


def source_tree_sha256(repository: Path) -> str:
    """Hash every tracked path, Git mode and indexed content deterministically."""

    resolved = repository.resolve()
    if not (resolved / ".git").exists():
        raise GateError("source repository is not a Git worktree")
    _require_clean_tracked_tree(resolved)
    hasher = hashlib.sha256()
    hasher.update(b"tracked-source-tree-sha256.v1\0")
    for path, mode, object_id in _tracked_entries(resolved):
        if mode == b"160000":
            content = b"submodule:" + object_id
        else:
            content = _run_git(resolved, ["cat-file", "blob", object_id.decode("ascii")])
        _hash_field(hasher, b"path", path)
        _hash_field(hasher, b"mode", mode)
        _hash_field(hasher, b"content", content)
    _require_clean_tracked_tree(resolved)
    return hasher.hexdigest()


def file_sha256(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise GateError("saved plan must be a regular file")
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _require_pattern(name: str, value: str, pattern: re.Pattern[str]) -> None:
    if not pattern.fullmatch(value):
        raise GateError("{} has an invalid format".format(name))


def _validate_binding_values(
    source_commit: str,
    image_reference: str,
    workflow_ref: str,
) -> None:
    _require_pattern("source_commit", source_commit, COMMIT_PATTERN)
    _require_pattern("image_reference", image_reference, IMAGE_PATTERN)
    _require_pattern("workflow_ref", workflow_ref, WORKFLOW_REF_PATTERN)


def build_metadata(
    plan: Path,
    repository: Path,
    source_commit: str,
    image_reference: str,
    workflow_ref: str,
) -> Dict[str, str]:
    _validate_binding_values(source_commit, image_reference, workflow_ref)
    actual_commit = _run_git(
        repository.resolve(),
        ["rev-parse", "--verify", "HEAD"],
    ).decode("ascii", errors="strict").strip()
    if actual_commit != source_commit:
        raise GateError("source_commit does not match the checked-out HEAD")
    return {
        "schema_version": METADATA_SCHEMA,
        "plan_sha256": file_sha256(plan),
        "source_tree_sha256": source_tree_sha256(repository),
        "source_commit": source_commit,
        "image_reference": image_reference,
        "workflow_ref": workflow_ref,
    }


def _reject_duplicate_keys(pairs: Iterable[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GateError("attestation contains a duplicate key")
        result[key] = value
    return result


def parse_attestation(raw: str) -> Dict[str, str]:
    if not raw or len(raw.encode("utf-8")) > MAX_ATTESTATION_BYTES:
        raise GateError("attestation is missing or exceeds the size limit")
    try:
        parsed = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as error:
        raise GateError("attestation is not valid JSON") from error
    if not isinstance(parsed, dict):
        raise GateError("attestation must be a JSON object")
    keys = frozenset(parsed)
    if keys != ATTESTATION_KEYS:
        raise GateError("attestation fields do not match the locked schema")
    if any(type(value) is not str for value in parsed.values()):
        raise GateError("every attestation field must be a string")
    result = {str(key): str(value) for key, value in parsed.items()}
    if result["schema_version"] != ATTESTATION_SCHEMA:
        raise GateError("attestation schema version is not accepted")
    if result["decision"] != ALLOW_DECISION:
        raise GateError("attestation decision is not ALLOW_DEV_APPLY")
    _require_pattern("plan_sha256", result["plan_sha256"], SHA256_PATTERN)
    _require_pattern("source_tree_sha256", result["source_tree_sha256"], SHA256_PATTERN)
    _validate_binding_values(
        result["source_commit"],
        result["image_reference"],
        result["workflow_ref"],
    )
    _require_pattern("workflow_actor", result["workflow_actor"], IDENTITY_PATTERN)
    _require_pattern("reviewer", result["reviewer"], IDENTITY_PATTERN)
    if result["environment"] != "dev":
        raise GateError("attestation environment is not dev")
    try:
        reviewed_at = datetime.fromisoformat(result["reviewed_at"].replace("Z", "+00:00"))
    except ValueError as error:
        raise GateError("reviewed_at is not an RFC3339 timestamp") from error
    if reviewed_at.tzinfo is None:
        raise GateError("reviewed_at must include a timezone")
    result["reviewed_at"] = reviewed_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if result["workflow_actor"].casefold() == result["reviewer"].casefold():
        raise GateError("attestation reviewer must differ from the workflow actor")
    return result


def _canonical_json(payload: Mapping[str, str]) -> str:
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def verify_attestation(
    raw_attestation: str,
    plan: Path,
    repository: Path,
    source_commit: str,
    image_reference: str,
    workflow_ref: str,
    workflow_actor: str,
    run_id: str,
    environment: str = "dev",
    now: Optional[datetime] = None,
) -> Dict[str, str]:
    _require_pattern("workflow_actor", workflow_actor, IDENTITY_PATTERN)
    _require_pattern("run_id", run_id, RUN_ID_PATTERN)
    if environment != "dev":
        raise GateError("runtime environment is not dev")
    metadata = build_metadata(
        plan,
        repository,
        source_commit,
        image_reference,
        workflow_ref,
    )
    attestation = parse_attestation(raw_attestation)
    repository_name = workflow_ref.split("/.github/workflows/", 1)[0]
    evidence_url = "https://github.com/{}/actions/runs/{}".format(repository_name, run_id)
    expected = {
        "plan_sha256": metadata["plan_sha256"],
        "source_tree_sha256": metadata["source_tree_sha256"],
        "source_commit": source_commit,
        "image_reference": image_reference,
        "workflow_ref": workflow_ref,
        "workflow_actor": workflow_actor,
        "environment": environment,
        "evidence_url": evidence_url,
    }
    for field, value in expected.items():
        if attestation[field] != value:
            raise GateError("attestation does not match {}".format(field))
    current_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    reviewed_at = datetime.fromisoformat(attestation["reviewed_at"].replace("Z", "+00:00"))
    if reviewed_at > current_time + timedelta(minutes=5):
        raise GateError("attestation review timestamp is in the future")
    if reviewed_at < current_time - timedelta(hours=24):
        raise GateError("attestation review timestamp is older than the plan retention window")
    canonical = _canonical_json(attestation).encode("utf-8")
    return {
        "result": "VERIFIED",
        "decision": ALLOW_DECISION,
        "attestation_sha256": hashlib.sha256(canonical).hexdigest(),
        "reviewer": attestation["reviewer"],
    }


def _write_metadata(
    metadata: Mapping[str, str],
    output: Path,
    github_output: Optional[Path],
) -> None:
    output.write_text(
        json.dumps(metadata, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if github_output is not None:
        with github_output.open("a", encoding="utf-8") as stream:
            for name in (
                "plan_sha256",
                "source_tree_sha256",
                "source_commit",
                "image_reference",
                "workflow_ref",
            ):
                stream.write("{}={}\n".format(name, metadata[name]))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    metadata = commands.add_parser("create-metadata")
    metadata.add_argument("--plan", type=Path, required=True)
    metadata.add_argument("--repository", type=Path, default=Path("."))
    metadata.add_argument("--source-commit", required=True)
    metadata.add_argument("--image-reference", required=True)
    metadata.add_argument("--workflow-ref", required=True)
    metadata.add_argument("--output", type=Path, required=True)
    metadata.add_argument("--github-output", type=Path)

    verify = commands.add_parser("verify")
    verify.add_argument("--plan", type=Path, required=True)
    verify.add_argument("--repository", type=Path, default=Path("."))
    verify.add_argument("--source-commit", required=True)
    verify.add_argument("--image-reference", required=True)
    verify.add_argument("--workflow-ref", required=True)
    verify.add_argument("--workflow-actor", required=True)
    verify.add_argument("--run-id", required=True)
    verify.add_argument("--environment", default="dev")
    verify.add_argument("--attestation-env", default="DEV_APPLY_ATTESTATION_JSON")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        if arguments.command == "create-metadata":
            metadata = build_metadata(
                arguments.plan,
                arguments.repository,
                arguments.source_commit,
                arguments.image_reference,
                arguments.workflow_ref,
            )
            _write_metadata(metadata, arguments.output, arguments.github_output)
            print(json.dumps(metadata, sort_keys=True))
            return 0
        raw_attestation = os.environ.get(arguments.attestation_env, "")
        result = verify_attestation(
            raw_attestation,
            arguments.plan,
            arguments.repository,
            arguments.source_commit,
            arguments.image_reference,
            arguments.workflow_ref,
            arguments.workflow_actor,
            arguments.run_id,
            arguments.environment,
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except GateError as error:
        print("dev apply gate denied: {}".format(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
