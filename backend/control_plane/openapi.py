from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional, Sequence

from .api import create_app
from .settings import Settings


def canonical_openapi() -> str:
    application = create_app(
        Settings(
            environment="test",
            auth_mode="development_headers",
            database_url="sqlite+pysqlite:///:memory:",
            auto_create_schema=True,
        )
    )
    return json.dumps(
        application.openapi(),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export or check the canonical OpenAPI document")
    parser.add_argument("--output", default="openapi.json")
    parser.add_argument("--check", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = build_parser().parse_args(argv)
    target = Path(arguments.output)
    generated = canonical_openapi()
    if arguments.check:
        if not target.exists() or target.read_text(encoding="utf-8") != generated:
            raise SystemExit("OpenAPI drift detected: regenerate {}".format(target))
        return 0
    target.write_text(generated, encoding="utf-8")
    return 0


def entrypoint() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    entrypoint()
