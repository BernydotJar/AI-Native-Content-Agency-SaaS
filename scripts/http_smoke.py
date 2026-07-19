#!/usr/bin/env python3
"""Exercise the built same-origin SPA/API without third-party dependencies."""

from __future__ import annotations

import argparse
import json
import os
import re
import uuid
from typing import Dict, Optional
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


def request_json(
    base_url: str,
    path: str,
    tenant_id: str,
    principal_id: str,
    payload: Optional[Dict[str, object]] = None,
    idempotency_key: Optional[str] = None,
    identity_token: Optional[str] = None,
) -> Dict[str, object]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "X-Tenant-ID": tenant_id,
        "X-Principal-ID": principal_id,
        "X-Correlation-ID": "http-smoke",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    if identity_token is not None:
        headers["Authorization"] = "Bearer {}".format(identity_token)
    request = Request(
        base_url.rstrip("/") + path,
        data=body,
        headers=headers,
        method="POST" if body is not None else "GET",
    )
    try:
        with urlopen(request, timeout=10) as response:  # noqa: S310 - explicit operator URL
            result = json.load(response)
    except HTTPError as error:
        failure = error.read(2048).decode("utf-8", errors="replace")
        raise RuntimeError("HTTP smoke request failed with status {}: {}".format(
            error.code, failure
        )) from error
    if not isinstance(result, dict):
        raise RuntimeError("HTTP smoke response was not a JSON object")
    return result


def verify_run(run: Dict[str, object]) -> None:
    if run.get("status") != "completed":
        raise RuntimeError("smoke run did not complete")
    if run.get("external_side_effects") is not False:
        raise RuntimeError("smoke run reported an external side effect")
    artifacts = run.get("artifacts")
    if not isinstance(artifacts, list):
        raise RuntimeError("smoke run omitted artifacts")
    packages = [
        artifact
        for artifact in artifacts
        if isinstance(artifact, dict) and artifact.get("kind") == "campaign_package"
    ]
    if len(packages) != 1 or packages[0].get("payload", {}).get("publication_performed") is not False:
        raise RuntimeError("smoke run did not produce exactly one sandbox-only package")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--tenant-id", default="tenant-http-smoke")
    parser.add_argument("--principal-id", default="operator-http-smoke")
    parser.add_argument("--existing-run-id")
    parser.add_argument(
        "--identity-token-env",
        help="Name of an environment variable containing a short-lived Cloud Run identity token.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    identity_token = None
    if args.identity_token_env:
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", args.identity_token_env):
            raise RuntimeError("identity-token environment variable name is invalid")
        identity_token = os.environ.get(args.identity_token_env)
        if not identity_token:
            raise RuntimeError("identity-token environment variable is unset or empty")
    if args.existing_run_id:
        run = request_json(
            args.base_url,
            "/api/v1/runs/{}".format(quote(args.existing_run_id, safe="")),
            args.tenant_id,
            args.principal_id,
            identity_token=identity_token,
        )
        verify_run(run)
        print(json.dumps({"result": "PASS", "mode": "restore", "run_id": run["run_id"]}))
        return 0

    command_scope = uuid.uuid4().hex
    mission = request_json(
        args.base_url,
        "/api/v1/missions",
        args.tenant_id,
        args.principal_id,
        {
            "schema_version": "v1",
            "title": "HTTP persistence smoke",
            "objective": "Verify the built image against its durable database",
            "audience": "Production operators",
            "platforms": ["x", "instagram"],
            "budget_cents": 0,
            "source_asset": "sandbox://http-smoke/source",
            "campaign_goal": "reliability",
        },
        "http-smoke-mission-{}".format(command_scope),
        identity_token,
    )
    run = request_json(
        args.base_url,
        "/api/v1/missions/{}/runs".format(quote(str(mission["mission_id"]), safe="")),
        args.tenant_id,
        args.principal_id,
        {"schema_version": "v1"},
        "http-smoke-run-{}".format(command_scope),
        identity_token,
    )
    completed = request_json(
        args.base_url,
        "/api/v1/runs/{}/approvals".format(quote(str(run["run_id"]), safe="")),
        args.tenant_id,
        args.principal_id,
        {
            "schema_version": "v1",
            "decision": "approved",
            "reviewer": args.principal_id,
            "note": "Local sandbox packaging only",
            "artifact_manifest_hash": run["artifact_manifest_hash"],
            "policy_version": "greenlight.v1",
        },
        "http-smoke-approval-{}".format(command_scope),
        identity_token,
    )
    verify_run(completed)
    print(
        json.dumps(
            {
                "result": "PASS",
                "mode": "create",
                "mission_id": mission["mission_id"],
                "run_id": completed["run_id"],
                "status": completed["status"],
                "artifact_count": len(completed["artifacts"]),
                "evidence_count": len(completed["evidence"]),
                "external_side_effects": completed["external_side_effects"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
