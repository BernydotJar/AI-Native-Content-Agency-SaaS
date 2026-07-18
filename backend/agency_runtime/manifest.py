from __future__ import annotations

import json
from importlib import resources
from typing import Mapping


def load_flow_manifest() -> Mapping[str, object]:
    """Load a fresh machine-readable description of the sandbox flow."""
    package = resources.files("agency_runtime")
    content = package.joinpath("flow_manifest.json").read_text(encoding="utf-8")
    return json.loads(content)
