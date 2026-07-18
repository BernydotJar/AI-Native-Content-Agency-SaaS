"""Compatibility facade for the repository's local eight-agent sandbox runtime.

This module intentionally exposes the stdlib `agency_runtime` implementation. It
does not import or imply installation of an external `agency_swarm` framework.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Mapping, Optional, Sequence, Union


REPOSITORY_ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from agency_runtime import (  # noqa: E402
    AGENT_SEQUENCE,
    AgencyOrchestrator,
    DynamicSkillCreator,
    MissionBrief,
    Platform,
    SQLiteMemory,
    build_sandbox_toolset,
    load_flow_manifest,
)
from agency_runtime.cli import main as sandbox_cli_main  # noqa: E402


Clock = Callable[[], str]
EXTERNAL_FRAMEWORK_REQUIRED = False
RUNTIME_MODE = "deterministic_sandbox"


def build_orchestrator(
    memory_path: Union[str, Path] = ":memory:",
    clock: Optional[Clock] = None,
) -> AgencyOrchestrator:
    """Build the local eight-agent orchestrator with sandbox-only adapters.

    The returned orchestrator owns its `memory` connection. Call
    `orchestrator.memory.close()` when the runtime is no longer needed.
    """
    if clock is None:
        memory = SQLiteMemory(memory_path)
        return AgencyOrchestrator(build_sandbox_toolset(), memory)
    memory = SQLiteMemory(memory_path, clock=clock)
    return AgencyOrchestrator(build_sandbox_toolset(), memory, clock=clock)


def flow_manifest() -> Mapping[str, object]:
    return load_flow_manifest()


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        arguments = ["demo"]
    return sandbox_cli_main(arguments)


__all__ = [
    "AGENT_SEQUENCE",
    "AgencyOrchestrator",
    "DynamicSkillCreator",
    "EXTERNAL_FRAMEWORK_REQUIRED",
    "MissionBrief",
    "Platform",
    "RUNTIME_MODE",
    "SQLiteMemory",
    "build_orchestrator",
    "flow_manifest",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
