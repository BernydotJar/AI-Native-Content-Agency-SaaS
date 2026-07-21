from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any, Mapping, Sequence


def to_primitive(value: Any) -> Any:
    """Convert runtime values into stable JSON-compatible primitives."""
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return to_primitive(asdict(value))
    if isinstance(value, Mapping):
        def key_text(key: Any) -> str:
            return str(key.value) if isinstance(key, Enum) else str(key)

        return {
            key_text(key): to_primitive(item)
            for key, item in sorted(value.items(), key=lambda pair: key_text(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [to_primitive(item) for item in value]
    if isinstance(value, set):
        return sorted(to_primitive(item) for item in value)
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        to_primitive(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def stable_id(prefix: str, *values: Any, length: int = 16) -> str:
    digest = hashlib.sha256(canonical_json(values).encode("utf-8")).hexdigest()
    return "{}-{}".format(prefix, digest[:length])


def require_non_empty(value: str, field_name: str) -> None:
    if not value or not value.strip():
        raise ValueError("{} must not be empty".format(field_name))


def require_confidence(value: float) -> None:
    if value < 0.0 or value > 1.0:
        raise ValueError("confidence must be between 0.0 and 1.0")
