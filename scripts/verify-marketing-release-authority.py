#!/usr/bin/env python3
"""Require explicit repository release authority before publishing the public demo."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECISION = ROOT / "compliance/release-decision.json"


def main() -> int:
    try:
        data = json.loads(DECISION.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"marketing_release_authority=FAIL invalid_release_decision error={error}", file=sys.stderr)
        return 1

    allowed = (
        data.get("decision") == "ALLOW_RELEASE"
        and data.get("allow_release") is True
        and data.get("legal_privacy_approval") is True
        and data.get("independent_human_approval") is True
    )
    if not allowed:
        reasons = data.get("reason_codes") if isinstance(data.get("reason_codes"), list) else []
        print(
            "marketing_release_authority=BLOCKED "
            f"decision={data.get('decision')} allow_release={data.get('allow_release')} "
            f"legal_privacy_approval={data.get('legal_privacy_approval')} "
            f"independent_human_approval={data.get('independent_human_approval')} "
            f"reason_codes={','.join(str(item) for item in reasons)}",
            file=sys.stderr,
        )
        return 1

    print("marketing_release_authority=pass decision=ALLOW_RELEASE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
