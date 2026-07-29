#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path


KEY_ID = "local-social-v1"
ROOT = Path(__file__).resolve().parents[1]
ACTIVE_KEY_NAME = "AGENCY_SOCIAL_TOKEN_ACTIVE_KEY_ID"
KEYRING_NAME = "AGENCY_SOCIAL_TOKEN_ENCRYPTION_KEYS_JSON"


def generated_assignments() -> dict[str, str]:
    raw = secrets.token_bytes(32)
    encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return {
        ACTIVE_KEY_NAME: KEY_ID,
        KEYRING_NAME: "'{}'".format(
            json.dumps({KEY_ID: encoded}, separators=(",", ":"))
        ),
    }


def render(assignments: dict[str, str]) -> str:
    return "\n".join(
        [
            "# Add these lines to .env.local. Never commit that file.",
            "{}={}".format(ACTIVE_KEY_NAME, assignments[ACTIVE_KEY_NAME]),
            "{}={}".format(KEYRING_NAME, assignments[KEYRING_NAME]),
        ]
    ) + "\n"


def tracked_by_git(path: Path) -> bool:
    try:
        relative = path.resolve().relative_to(ROOT)
    except ValueError:
        return False
    completed = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--error-unmatch", str(relative)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.returncode == 0


def write_env_file(path: Path, assignments: dict[str, str]) -> None:
    if path.is_symlink():
        raise ValueError("refusing symlink environment file: {}".format(path))
    if tracked_by_git(path):
        raise ValueError("refusing tracked environment file: {}".format(path))

    original = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = original.splitlines()
    found: set[str] = set()
    updated: list[str] = []
    for line in lines:
        name, separator, current = line.partition("=")
        if name not in assignments or not separator:
            updated.append(line)
            continue
        if name in found:
            raise ValueError("duplicate environment assignment: {}".format(name))
        found.add(name)
        if current.strip():
            raise ValueError(
                "{} is already configured; rotate keys deliberately instead of overwriting it".format(
                    name
                )
            )
        updated.append("{}={}".format(name, assignments[name]))

    missing = [name for name in assignments if name not in found]
    if missing:
        if updated and updated[-1] != "":
            updated.append("")
        updated.append("# Generated locally. Never commit real values.")
        updated.extend("{}={}".format(name, assignments[name]) for name in missing)

    content = "\n".join(updated).rstrip("\n") + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    os.chmod(temporary, mode)
    os.replace(temporary, path)
    os.chmod(path, 0o600)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Safely fill empty social encryption assignments in an untracked env file.",
    )
    args = parser.parse_args()
    assignments = generated_assignments()
    if args.env_file is None:
        sys.stdout.write(render(assignments))
        return 0
    try:
        write_env_file(args.env_file, assignments)
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 65
    print("social_encryption_key_written={} (value hidden)".format(args.env_file))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
