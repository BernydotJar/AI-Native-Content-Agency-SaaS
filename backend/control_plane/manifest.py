from __future__ import annotations

import hashlib
import json
from typing import Iterable, Mapping, Sequence, SupportsInt, cast

from .contracts import POLICY_VERSION, SCHEMA_VERSION


def canonical_artifact_manifest(
    run_id: str,
    artifacts: Sequence[Mapping[str, object]],
) -> Mapping[str, object]:
    pre_publisher = [
        {
            "artifact_id": str(item["artifact_id"]),
            "kind": str(item["kind"]),
            "title": str(item["title"]),
            "created_by": str(item["created_by"]),
            "payload": item["payload"],
            "evidence_ids": list(cast(Iterable[object], item["evidence_ids"])),
            "ordinal": int(cast(SupportsInt, item["ordinal"])),
        }
        for item in artifacts
        if str(item["created_by"]) != "publisher"
    ]
    pre_publisher.sort(
        key=lambda item: (
            int(cast(SupportsInt, item["ordinal"])),
            str(item["artifact_id"]),
        )
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "run_id": run_id,
        "artifacts": pre_publisher,
    }


def artifact_manifest_hash(
    run_id: str,
    artifacts: Sequence[Mapping[str, object]],
) -> str:
    payload = canonical_artifact_manifest(run_id, artifacts)
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def request_payload_hash(operation: str, payload: Mapping[str, object]) -> str:
    encoded = json.dumps(
        {"operation": operation, "payload": payload},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
