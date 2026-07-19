"""Syntax and structural checks for Compose and GitHub workflow YAML."""

from __future__ import annotations

import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
ACTION_PIN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")


def _walk_steps(node: object) -> list[dict]:
    if not isinstance(node, dict):
        return []
    jobs = node.get("jobs", {})
    if not isinstance(jobs, dict):
        return []
    steps: list[dict] = []
    for job in jobs.values():
        if isinstance(job, dict) and isinstance(job.get("steps"), list):
            steps.extend(step for step in job["steps"] if isinstance(step, dict))
    return steps


def main() -> None:
    targets = [
        ROOT / "docker-compose.yml",
        *sorted((ROOT / ".github/workflows").glob("*.yml")),
    ]
    if len(targets) < 3:
        raise SystemExit("Expected Compose plus CI and deploy workflow YAML")
    for target in targets:
        payload = yaml.safe_load(target.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise SystemExit(f"{target.relative_to(ROOT)} must contain a YAML mapping")
        if target.parent.name == "workflows":
            if "jobs" not in payload:
                raise SystemExit(f"{target.relative_to(ROOT)} has no jobs")
            for step in _walk_steps(payload):
                action = step.get("uses")
                if (
                    action
                    and not str(action).startswith("docker://")
                    and not ACTION_PIN.fullmatch(str(action))
                ):
                    raise SystemExit(
                        f"Unpinned action in {target.relative_to(ROOT)}: {action}"
                    )
    print(f"yaml_validation=PASS files={len(targets)}")


if __name__ == "__main__":
    main()
