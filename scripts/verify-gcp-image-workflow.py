#!/usr/bin/env python3
"""Fail closed if the manual GCP image publisher gains deployment authority."""

from __future__ import annotations

import re
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/publish-gcp-image.yml"

REQUIRED = (
    "workflow_dispatch:",
    "contents: read",
    "id-token: write",
    "github.ref == 'refs/heads/main'",
    "inputs.confirm_publish == true",
    "persist-credentials: false",
    "google-github-actions/auth@7c6bc770dae815cd3e89ee6cdf493a5fab2cc093",
    "google-github-actions/setup-gcloud@aa5489c8933f4cc7a4f7d45035b3b1440c9c10db",
    "projects/970393454298/locations/global/workloadIdentityPools/github-actions/providers/github",
    "campaignos-deployer@ai-native-content-agency-saas.iam.gserviceaccount.com",
    "platforms: linux/amd64",
    "push: true",
    "tags: ${{ env.IMAGE_URI }}:${{ github.sha }}",
    "Cloud Run deployment: not performed",
)

FORBIDDEN = (
    "credentials_json:",
    "gcloud run deploy",
    "gcloud run services replace",
    "terraform apply",
    "terraform destroy",
    "google-github-actions/deploy-cloudrun",
    "gcloud secrets versions access",
    "allow-unauthenticated",
    ":latest",
)


def main() -> int:
    source = WORKFLOW.read_text(encoding="utf-8")
    missing = [item for item in REQUIRED if item not in source]
    forbidden = [item for item in FORBIDDEN if item.lower() in source.lower()]
    if missing:
        raise SystemExit("gcp_image_workflow=fail\nmissing=" + ",".join(missing))
    if forbidden:
        raise SystemExit("gcp_image_workflow=fail\nforbidden=" + ",".join(forbidden))

    actions = re.findall(r"uses:\s*([^\s]+)@([^\s#]+)", source)
    if not actions or any(not re.fullmatch(r"[0-9a-f]{40}", commit) for _, commit in actions):
        raise SystemExit("gcp_image_workflow=fail\nactions_must_be_sha_pinned=true")

    if re.search(r"(?m)^\s*(push|pull_request|schedule):\s*$", source):
        raise SystemExit("gcp_image_workflow=fail\nmanual_dispatch_only=true")

    print("gcp_image_workflow=pass")
    print(f"sha_pinned_actions={len(actions)}")
    print("runtime_deploy_authority=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
