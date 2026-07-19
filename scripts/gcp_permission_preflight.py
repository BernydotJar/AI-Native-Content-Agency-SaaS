#!/usr/bin/env python3
"""Fail closed unless a WIF phase has every explicitly required GCP permission."""

from __future__ import annotations

import argparse
import json
import subprocess
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple


@dataclass(frozen=True)
class PermissionTarget:
    name: str
    method: str
    url: str
    permissions: Tuple[str, ...]


PROJECT_PERMISSIONS = {
    "build": (
        "resourcemanager.projects.get",
        "run.services.get",
    ),
    "plan": (
        "resourcemanager.projects.get",
        "run.jobs.get",
        "run.jobs.getIamPolicy",
        "run.jobs.list",
        "run.locations.get",
        "run.locations.list",
        "run.operations.get",
        "run.services.get",
        "run.services.getIamPolicy",
        "run.services.list",
    ),
    "apply": (
        "resourcemanager.projects.get",
        "run.executions.get",
        "run.jobs.create",
        "run.jobs.get",
        "run.jobs.getIamPolicy",
        "run.jobs.list",
        "run.jobs.run",
        "run.jobs.update",
        "run.locations.get",
        "run.locations.list",
        "run.operations.get",
        "run.services.create",
        "run.services.get",
        "run.services.getIamPolicy",
        "run.services.list",
        "run.services.update",
    ),
}
STATE_PERMISSIONS = ("storage.objects.list",)
ARTIFACT_PERMISSIONS = (
    "artifactregistry.repositories.downloadArtifacts",
    "artifactregistry.repositories.get",
    "artifactregistry.repositories.uploadArtifacts",
)
ARTIFACT_READ_PERMISSIONS = (
    "artifactregistry.repositories.downloadArtifacts",
    "artifactregistry.repositories.get",
)
ARTIFACT_APPLY_PERMISSIONS = ARTIFACT_READ_PERMISSIONS + (
    "artifactregistry.tags.create",
    "artifactregistry.tags.update",
)


class PermissionError(RuntimeError):
    pass


def permission_targets(
    phase: str,
    project_id: str,
    region: str,
    state_bucket: Optional[str],
    runtime_service_account_email: Optional[str],
) -> List[PermissionTarget]:
    if phase == "build":
        resource = "projects/{}/locations/{}/repositories/agency-images".format(
            project_id, region
        )
        return [
            PermissionTarget(
                "project_runtime_read",
                "POST",
                "https://cloudresourcemanager.googleapis.com/v1/projects/{}:testIamPermissions".format(
                    project_id
                ),
                PROJECT_PERMISSIONS[phase],
            ),
            PermissionTarget(
                "artifact_registry",
                "POST",
                "https://artifactregistry.googleapis.com/v1/{}:testIamPermissions".format(
                    resource
                ),
                ARTIFACT_PERMISSIONS,
            ),
        ]
    if phase not in PROJECT_PERMISSIONS or not state_bucket:
        raise PermissionError("plan/apply preflight requires an explicit state bucket")
    targets = [
        PermissionTarget(
            "project_runtime",
            "POST",
            "https://cloudresourcemanager.googleapis.com/v1/projects/{}:testIamPermissions".format(
                project_id
            ),
            PROJECT_PERMISSIONS[phase],
        ),
        PermissionTarget(
            "terraform_state",
            "GET",
            "https://storage.googleapis.com/storage/v1/b/{}/iam/testPermissions".format(
                urllib.parse.quote(state_bucket, safe="")
            ),
            STATE_PERMISSIONS,
        ),
    ]
    if phase == "plan":
        repository = "projects/{}/locations/{}/repositories/agency-images".format(
            project_id, region
        )
        targets.append(
            PermissionTarget(
                "artifact_registry_read",
                "POST",
                "https://artifactregistry.googleapis.com/v1/{}:testIamPermissions".format(
                    repository
                ),
                ARTIFACT_READ_PERMISSIONS,
            )
        )
    if phase == "apply":
        if not runtime_service_account_email:
            raise PermissionError(
                "apply preflight requires the runtime service-account email"
            )
        resource = "projects/{}/serviceAccounts/{}".format(
            project_id,
            urllib.parse.quote(runtime_service_account_email, safe=""),
        )
        repository = "projects/{}/locations/{}/repositories/agency-images".format(
            project_id, region
        )
        targets.extend(
            [
                PermissionTarget(
                    "artifact_registry_read_and_rollback_tag",
                    "POST",
                    "https://artifactregistry.googleapis.com/v1/{}:testIamPermissions".format(
                        repository
                    ),
                    ARTIFACT_APPLY_PERMISSIONS,
                ),
                PermissionTarget(
                    "runtime_service_account",
                    "POST",
                    "https://iam.googleapis.com/v1/{}:testIamPermissions".format(
                        resource
                    ),
                    ("iam.serviceAccounts.actAs",),
                ),
            ]
        )
    return targets


def _access_token() -> str:
    result = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        check=False,
        capture_output=True,
        text=True,
    )
    token = result.stdout.strip()
    if result.returncode != 0 or not token:
        raise PermissionError("gcloud did not provide a short-lived access token")
    return token


def _transport(request: urllib.request.Request) -> bytes:
    with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 - locked Google endpoints
        return response.read()


def _request(target: PermissionTarget, token: str) -> Mapping[str, object]:
    headers = {"Authorization": "Bearer {}".format(token), "Accept": "application/json"}
    data = None
    url = target.url
    if target.method == "POST":
        headers["Content-Type"] = "application/json"
        data = json.dumps({"permissions": list(target.permissions)}).encode("utf-8")
    else:
        url += "?" + urllib.parse.urlencode(
            [("permissions", permission) for permission in target.permissions]
        )
    request = urllib.request.Request(
        url, data=data, headers=headers, method=target.method
    )
    try:
        payload = json.loads(_transport(request))
    except Exception as error:
        raise PermissionError(
            "permission test failed for {}".format(target.name)
        ) from error
    if not isinstance(payload, dict):
        raise PermissionError(
            "permission response was invalid for {}".format(target.name)
        )
    return payload


def probe_state_access(
    state_bucket: str,
    token: str,
    nonce: Optional[str] = None,
    transport: Callable[[urllib.request.Request], bytes] = _transport,
) -> Dict[str, object]:
    """Prove foundation reads and a disposable runtime lock without touching state."""

    encoded_bucket = urllib.parse.quote(state_bucket, safe="")
    foundation_name = "environments/dev/default.tfstate"
    lock_name = "environments/dev-runtime/permission-preflight-{}.tflock".format(
        nonce or uuid.uuid4().hex
    )
    headers = {"Authorization": "Bearer {}".format(token), "Accept": "application/json"}
    metadata_url = (
        "https://storage.googleapis.com/storage/v1/b/{}/o/{}?fields=name".format(
            encoded_bucket,
            urllib.parse.quote(foundation_name, safe=""),
        )
    )
    upload_url = "https://storage.googleapis.com/upload/storage/v1/b/{}/o?{}".format(
        encoded_bucket,
        urllib.parse.urlencode(
            {"uploadType": "media", "name": lock_name, "ifGenerationMatch": "0"}
        ),
    )

    created = False
    created_generation: Optional[str] = None
    cleanup_error: Optional[Exception] = None
    try:
        metadata_request = urllib.request.Request(
            metadata_url, headers=headers, method="GET"
        )
        metadata = json.loads(transport(metadata_request))
        if not isinstance(metadata, dict) or metadata.get("name") != foundation_name:
            raise PermissionError(
                "foundation state read probe returned invalid metadata"
            )

        upload_headers = dict(headers)
        upload_headers["Content-Type"] = "application/octet-stream"
        upload_request = urllib.request.Request(
            upload_url,
            data=b"terraform-lock-permission-probe",
            headers=upload_headers,
            method="POST",
        )
        uploaded_bytes = transport(upload_request)
        created = True
        uploaded = json.loads(uploaded_bytes)
        raw_generation = (
            uploaded.get("generation") if isinstance(uploaded, dict) else None
        )
        if (
            not isinstance(uploaded, dict)
            or uploaded.get("name") != lock_name
            or not isinstance(raw_generation, (str, int))
            or not str(raw_generation).isdigit()
        ):
            raise PermissionError("runtime lock create probe returned invalid metadata")
        created_generation = str(raw_generation)
    except PermissionError:
        raise
    except Exception as error:
        raise PermissionError("state read/lock capability probe failed") from error
    finally:
        if created:
            delete_url = (
                "https://storage.googleapis.com/storage/v1/b/{}/o/{}?{}".format(
                    encoded_bucket,
                    urllib.parse.quote(lock_name, safe=""),
                    urllib.parse.urlencode(
                        {"ifGenerationMatch": created_generation or "invalid"}
                    ),
                )
            )
            delete_request = urllib.request.Request(
                delete_url, headers=headers, method="DELETE"
            )
            try:
                transport(delete_request)
            except Exception as error:  # cleanup failure must fail closed
                cleanup_error = error
        if cleanup_error is not None:
            raise PermissionError("state lock probe cleanup failed") from cleanup_error

    return {
        "status": "PASS",
        "foundation_state_metadata_read": True,
        "runtime_lock_create_delete": True,
    }


def evaluate(
    targets: Sequence[PermissionTarget],
    requester: Callable[[PermissionTarget], Mapping[str, object]],
) -> Dict[str, object]:
    results = []
    for target in targets:
        payload = requester(target)
        granted_raw = payload.get("permissions", [])
        if not isinstance(granted_raw, list) or not all(
            isinstance(item, str) for item in granted_raw
        ):
            raise PermissionError(
                "permission response was invalid for {}".format(target.name)
            )
        granted = set(granted_raw)
        missing = sorted(set(target.permissions) - granted)
        if missing:
            raise PermissionError(
                "{} is missing required permissions: {}".format(
                    target.name, ",".join(missing)
                )
            )
        results.append(
            {
                "target": target.name,
                "required_permission_count": len(target.permissions),
            }
        )
    return {"status": "PASS", "targets": results}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("build", "plan", "apply"), required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--state-bucket")
    parser.add_argument("--runtime-service-account-email")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        targets = permission_targets(
            arguments.phase,
            arguments.project_id,
            arguments.region,
            arguments.state_bucket,
            arguments.runtime_service_account_email,
        )
        token = _access_token()
        report = evaluate(targets, lambda target: _request(target, token))
        if arguments.state_bucket:
            report["state_access_probe"] = probe_state_access(
                arguments.state_bucket,
                token,
            )
        report["phase"] = arguments.phase
        print(json.dumps(report, sort_keys=True))
        return 0
    except PermissionError as error:
        print("GCP permission preflight denied: {}".format(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
