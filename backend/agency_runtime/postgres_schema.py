"""Operator command for explicit PostgreSQL schema initialization or validation."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Iterable

from .postgres import POSTGRES_SCHEMA_VERSION, PostgresRuntimeDatabase, PostgresSchemaError
from .version import VERSION

ENVIRONMENT_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")


class SchemaCommandError(RuntimeError):
    """A safe operator-facing schema command error."""


def database_url_from_environment(name: str) -> str:
    if not ENVIRONMENT_NAME.fullmatch(name):
        raise SchemaCommandError("database URL environment variable name is invalid")
    value = os.environ.get(name)
    if not value:
        raise SchemaCommandError("database URL environment variable is not configured")
    return value


def operate_schema(mode: str, database_url_environment: str) -> dict[str, str]:
    database_url = database_url_from_environment(database_url_environment)
    database = PostgresRuntimeDatabase(
        database_url,
        min_size=1,
        max_size=1,
        schema_mode=mode,
    )
    try:
        return {
            "status": "pass",
            "mode": mode,
            "schema_version": POSTGRES_SCHEMA_VERSION,
            "runtime_version": VERSION,
        }
    finally:
        database.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("initialize", "validate"))
    parser.add_argument(
        "--database-url-env",
        default="AGENCY_DATABASE_URL",
        help="name of the environment variable containing the PostgreSQL URL",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        result = operate_schema(arguments.mode, arguments.database_url_env)
    except (SchemaCommandError, PostgresSchemaError) as error:
        print("schema_status=fail", file=sys.stderr)
        print(f"error={error}", file=sys.stderr)
        return 1
    except Exception as error:  # Fail closed without serializing driver/URL detail.
        print("schema_status=fail", file=sys.stderr)
        print(f"error_type={type(error).__name__}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
