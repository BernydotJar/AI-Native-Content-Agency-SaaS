#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
CONTRACT = ROOT / "contracts/openapi-v1.json"

if os.environ.get("API_CONTRACT_USE_INSTALLED", "0") != "1":
    sys.path.insert(0, str(BACKEND))

from agency_runtime.api import create_app  # noqa: E402
from agency_runtime.version import VERSION  # noqa: E402

STANDARD_ERROR_CODES = ("400", "401", "403", "404", "409", "413", "422", "429", "500", "503")
PUBLIC_ERROR_REF = "#/components/schemas/PublicErrorResponse"
VALIDATION_ERROR_REF = "#/components/schemas/ValidationErrorResponse"
OPERATION_METHODS = frozenset({"get", "post", "put", "patch", "delete", "options", "head"})
UNVERSIONED_PATHS = frozenset({"/healthz", "/readyz"})
OPERATION_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def canonical(document: Any) -> str:
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def build_contract() -> dict[str, Any]:
    app = create_app(
        database_path=":memory:",
        static_dir=Path("/definitely/missing"),
        identity_credentials=[
            {
                "tenant_id": "contract-tenant",
                "subject_id": "contract-admin",
                "role": "admin",
                "key_id": "contract-admin-v1",
                "api_key": "contract-admin-key-material-2026",
                "active": True,
            }
        ],
        session_cookie_secure=False,
    )
    return app.openapi()


def response_ref(operation: dict[str, Any], code: str) -> str:
    try:
        return str(
            operation["responses"][code]["content"]["application/json"]["schema"]["$ref"]
        )
    except (KeyError, TypeError) as error:
        raise ValueError(f"operation response {code} does not reference a JSON schema") from error


def response_refs(operation: dict[str, Any], code: str) -> set[str]:
    try:
        schema = operation["responses"][code]["content"]["application/json"]["schema"]
    except (KeyError, TypeError) as error:
        raise ValueError(f"operation response {code} does not reference a JSON schema") from error
    if "$ref" in schema:
        return {str(schema["$ref"])}
    variants = schema.get("anyOf") or schema.get("oneOf")
    if not isinstance(variants, list) or not variants:
        raise ValueError(f"operation response {code} does not reference a JSON schema")
    refs = {str(item.get("$ref", "")) for item in variants if isinstance(item, dict)}
    if len(refs) != len(variants) or "" in refs:
        raise ValueError(f"operation response {code} contains an invalid union schema")
    return refs


def validate_contract(document: dict[str, Any]) -> dict[str, int]:
    errors: list[str] = []
    info = document.get("info", {})
    if document.get("openapi") != "3.1.0":
        errors.append("OpenAPI version must be 3.1.0")
    if info.get("title") != "AI Native Content Agency API":
        errors.append("API title drift")
    if info.get("version") != VERSION:
        errors.append(f"API version drift: expected {VERSION}, found {info.get('version')}")

    schemas = document.get("components", {}).get("schemas", {})
    for name in ("PublicErrorResponse", "ValidationErrorItem", "ValidationErrorResponse"):
        if name not in schemas:
            errors.append(f"missing component schema {name}")
    public = schemas.get("PublicErrorResponse", {})
    if set(public.get("required", [])) != {"code", "detail", "request_id"}:
        errors.append("PublicErrorResponse required fields drift")
    if public.get("additionalProperties") is not False:
        errors.append("PublicErrorResponse must reject additional properties")
    validation = schemas.get("ValidationErrorResponse", {})
    if set(validation.get("required", [])) != {"code", "detail", "request_id", "errors"}:
        errors.append("ValidationErrorResponse required fields drift")
    if validation.get("additionalProperties") is not False:
        errors.append("ValidationErrorResponse must reject additional properties")
    validation_errors = validation.get("properties", {}).get("errors", {})
    if validation_errors.get("items", {}).get("$ref") != "#/components/schemas/ValidationErrorItem":
        errors.append("ValidationErrorResponse errors must reference ValidationErrorItem")
    if validation_errors.get("maxItems") != 20:
        errors.append("ValidationErrorResponse errors must remain bounded to 20 items")

    paths = document.get("paths", {})
    observed_unversioned = {
        path
        for path in paths
        if path != "/api/v1" and not path.startswith("/api/v1/")
    }
    if observed_unversioned != UNVERSIONED_PATHS:
        errors.append(
            "unversioned path set drift: expected {}, found {}".format(
                sorted(UNVERSIONED_PATHS), sorted(observed_unversioned)
            )
        )

    operation_ids: list[str] = []
    operation_count = 0
    for path, path_item in sorted(paths.items()):
        if not isinstance(path_item, dict):
            errors.append(f"path item is not an object: {path}")
            continue
        for method, operation in sorted(path_item.items()):
            if method not in OPERATION_METHODS:
                continue
            operation_count += 1
            if not isinstance(operation, dict):
                errors.append(f"operation is not an object: {method.upper()} {path}")
                continue
            operation_id = str(operation.get("operationId", ""))
            if not OPERATION_ID.fullmatch(operation_id):
                errors.append(f"invalid operationId for {method.upper()} {path}: {operation_id!r}")
            operation_ids.append(operation_id)
            for code in STANDARD_ERROR_CODES:
                expected_refs = (
                    {VALIDATION_ERROR_REF, PUBLIC_ERROR_REF}
                    if code == "422"
                    else {PUBLIC_ERROR_REF}
                )
                try:
                    actual_refs = response_refs(operation, code)
                except ValueError as error:
                    errors.append(f"{method.upper()} {path}: {error}")
                    continue
                if actual_refs != expected_refs:
                    errors.append(
                        f"{method.upper()} {path}: response {code} references "
                        f"{sorted(actual_refs)}, expected {sorted(expected_refs)}"
                    )
    if len(operation_ids) != len(set(operation_ids)):
        errors.append("operationId values must be unique")

    serialized = canonical(document)
    for forbidden in (
        "contract-admin-key-material-2026",
        "local-openai-key-not-for-external-use",
        "local-x-secret-not-for-external-use",
        "local-instagram-secret-not-for-external-use",
    ):
        if forbidden in serialized:
            errors.append(f"contract contains secret fixture material: {forbidden}")

    if errors:
        raise ValueError("API contract validation failed:\n- " + "\n- ".join(errors))
    return {
        "paths": len(paths),
        "operations": operation_count,
        "schemas": len(schemas),
        "standard_error_responses": operation_count * len(STANDARD_ERROR_CODES),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the canonical versioned OpenAPI contract.")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Intentionally replace the committed contract after reviewed API changes.",
    )
    args = parser.parse_args()

    document = build_contract()
    summary = validate_contract(document)
    rendered = canonical(document)
    if args.write:
        CONTRACT.parent.mkdir(parents=True, exist_ok=True)
        CONTRACT.write_text(rendered, encoding="utf-8")
    elif not CONTRACT.is_file():
        raise FileNotFoundError(f"canonical API contract is missing: {CONTRACT}")
    elif CONTRACT.read_text(encoding="utf-8") != rendered:
        raise ValueError(
            "canonical API contract drift; review the change and run scripts/verify-api-contract.py --write"
        )

    print("api_contract=pass")
    print(f"api_version={VERSION}")
    for key, value in sorted(summary.items()):
        print(f"{key}={value}")
    print("external_effects=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"API contract verification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
