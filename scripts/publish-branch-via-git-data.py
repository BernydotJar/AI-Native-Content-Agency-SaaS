#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class TreeEntry:
    path: str
    mode: str
    object_type: str
    sha: str


def _run(
    command: Sequence[str],
    *,
    input_bytes: bytes | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        list(command),
        cwd=ROOT,
        input=input_bytes,
        capture_output=True,
        check=check,
        timeout=180,
    )


def parse_git_tree(raw: bytes) -> dict[str, TreeEntry]:
    result: dict[str, TreeEntry] = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, separator, path_bytes = record.partition(b"\t")
        if not separator:
            raise ValueError("git tree entry is malformed")
        mode, object_type, sha = metadata.decode("ascii").split(" ", 2)
        path = path_bytes.decode("utf-8", "surrogateescape")
        if path in result:
            raise ValueError("git tree contains duplicate paths")
        result[path] = TreeEntry(path, mode, object_type, sha)
    return result


def parse_remote_tree(document: Mapping[str, object]) -> dict[str, TreeEntry]:
    if document.get("truncated") is True:
        raise RuntimeError("remote tree response was truncated")
    raw_entries = document.get("tree")
    if not isinstance(raw_entries, list):
        raise RuntimeError("remote tree response is invalid")
    result: dict[str, TreeEntry] = {}
    for raw in raw_entries:
        if not isinstance(raw, Mapping):
            raise RuntimeError("remote tree entry is invalid")
        path = raw.get("path")
        mode = raw.get("mode")
        object_type = raw.get("type")
        sha = raw.get("sha")
        if not all(isinstance(value, str) and value for value in (path, mode, object_type, sha)):
            raise RuntimeError("remote tree entry is incomplete")
        if object_type == "tree":
            continue
        if path in result:
            raise RuntimeError("remote tree contains duplicate paths")
        result[path] = TreeEntry(path, mode, object_type, sha)
    return result


def changed_paths(
    local: Mapping[str, TreeEntry], remote: Mapping[str, TreeEntry]
) -> tuple[str, ...]:
    paths = []
    for path in sorted(set(local) | set(remote)):
        if local.get(path) != remote.get(path):
            paths.append(path)
    return tuple(paths)


def _json_api(
    repository: str,
    endpoint: str,
    *,
    method: str = "GET",
    payload: Mapping[str, object] | None = None,
    allow_not_found: bool = False,
) -> Mapping[str, object] | None:
    command = ["gh", "api"]
    if method != "GET":
        command.extend(["--method", method])
    command.append("repos/{}/{}".format(repository, endpoint.lstrip("/")))
    input_bytes = None
    if payload is not None:
        command.extend(["--input", "-"])
        input_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    completed = _run(command, input_bytes=input_bytes, check=False)
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", "replace")
        if allow_not_found and "HTTP 404" in stderr:
            return None
        raise RuntimeError("GitHub API request failed")
    decoded = json.loads(completed.stdout.decode("utf-8"))
    if not isinstance(decoded, Mapping):
        raise RuntimeError("GitHub API response is invalid")
    return decoded


def _resolve_parent(repository: str, branch: str, base_ref: str) -> tuple[str, bool]:
    existing = _json_api(
        repository,
        "git/ref/heads/{}".format(branch),
        allow_not_found=True,
    )
    if existing is not None:
        target = existing.get("object")
        if not isinstance(target, Mapping) or not isinstance(target.get("sha"), str):
            raise RuntimeError("remote branch response is invalid")
        return str(target["sha"]), True
    commit = _json_api(repository, "commits/{}".format(base_ref))
    assert commit is not None
    sha = commit.get("sha")
    if not isinstance(sha, str) or not sha:
        raise RuntimeError("base ref did not resolve to a commit")
    return sha, False


def _commit_tree(repository: str, commit_sha: str) -> str:
    commit = _json_api(repository, "git/commits/{}".format(commit_sha))
    assert commit is not None
    tree = commit.get("tree")
    if not isinstance(tree, Mapping) or not isinstance(tree.get("sha"), str):
        raise RuntimeError("remote commit tree is unavailable")
    return str(tree["sha"])


def _local_tree() -> dict[str, TreeEntry]:
    return parse_git_tree(_run(["git", "ls-tree", "-r", "-z", "HEAD"]).stdout)


def _remote_tree(repository: str, tree_sha: str) -> dict[str, TreeEntry]:
    document = _json_api(repository, "git/trees/{}?recursive=1".format(tree_sha))
    assert document is not None
    return parse_remote_tree(document)


def _upload_blob(repository: str, entry: TreeEntry) -> str:
    content = _run(["git", "cat-file", "blob", entry.sha]).stdout
    document = _json_api(
        repository,
        "git/blobs",
        method="POST",
        payload={
            "content": base64.b64encode(content).decode("ascii"),
            "encoding": "base64",
        },
    )
    assert document is not None
    sha = document.get("sha")
    if not isinstance(sha, str) or not sha:
        raise RuntimeError("GitHub did not return a blob SHA")
    if sha != entry.sha:
        raise RuntimeError("uploaded blob SHA does not match the local Git object")
    return sha


def publish(
    repository: str,
    branch: str,
    base_ref: str,
    message: str,
    *,
    dry_run: bool = False,
) -> Mapping[str, object]:
    status = _run(["git", "status", "--porcelain"]).stdout
    if status:
        raise RuntimeError("worktree must be clean before Git Data publication")
    parent_sha, branch_exists = _resolve_parent(repository, branch, base_ref)
    parent_tree_sha = _commit_tree(repository, parent_sha)
    local = _local_tree()
    remote = _remote_tree(repository, parent_tree_sha)
    paths = changed_paths(local, remote)
    if dry_run:
        return {
            "status": "dry_run",
            "branch": branch,
            "parent_sha": parent_sha,
            "changed_paths": len(paths),
        }
    if not paths:
        return {
            "status": "unchanged",
            "branch": branch,
            "commit_sha": parent_sha,
            "verified_paths": len(local),
        }

    tree_updates: list[dict[str, object]] = []
    for path in paths:
        entry = local.get(path)
        if entry is None:
            previous = remote[path]
            tree_updates.append(
                {
                    "path": path,
                    "mode": previous.mode,
                    "type": previous.object_type,
                    "sha": None,
                }
            )
        elif entry.object_type == "blob":
            tree_updates.append(
                {
                    "path": path,
                    "mode": entry.mode,
                    "type": "blob",
                    "sha": _upload_blob(repository, entry),
                }
            )
        else:
            tree_updates.append(
                {
                    "path": path,
                    "mode": entry.mode,
                    "type": entry.object_type,
                    "sha": entry.sha,
                }
            )

    tree_document = _json_api(
        repository,
        "git/trees",
        method="POST",
        payload={"base_tree": parent_tree_sha, "tree": tree_updates},
    )
    assert tree_document is not None
    new_tree_sha = tree_document.get("sha")
    if not isinstance(new_tree_sha, str) or not new_tree_sha:
        raise RuntimeError("GitHub did not return a tree SHA")
    commit_document = _json_api(
        repository,
        "git/commits",
        method="POST",
        payload={"message": message, "tree": new_tree_sha, "parents": [parent_sha]},
    )
    assert commit_document is not None
    commit_sha = commit_document.get("sha")
    if not isinstance(commit_sha, str) or not commit_sha:
        raise RuntimeError("GitHub did not return a commit SHA")
    if branch_exists:
        _json_api(
            repository,
            "git/refs/heads/{}".format(branch),
            method="PATCH",
            payload={"sha": commit_sha, "force": False},
        )
    else:
        _json_api(
            repository,
            "git/refs",
            method="POST",
            payload={"ref": "refs/heads/{}".format(branch), "sha": commit_sha},
        )

    published = _remote_tree(repository, new_tree_sha)
    mismatches = changed_paths(local, published)
    if mismatches:
        raise RuntimeError("remote tree verification failed")
    return {
        "status": "published",
        "branch": branch,
        "commit_sha": commit_sha,
        "parent_sha": parent_sha,
        "changed_paths": len(paths),
        "verified_paths": len(local),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish a clean local Git tree through GitHub Git Data API."
    )
    parser.add_argument("--repo", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--message")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    message = arguments.message
    if not message:
        message = _run(["git", "log", "-1", "--pretty=%s"]).stdout.decode().strip()
    try:
        result = publish(
            arguments.repo,
            arguments.branch,
            arguments.base_ref,
            message,
            dry_run=arguments.dry_run,
        )
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(
            json.dumps(
                {"status": "failed", "reason": type(error).__name__},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
