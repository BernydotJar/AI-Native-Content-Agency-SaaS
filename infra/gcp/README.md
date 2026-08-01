# GCP pilot foundation

This module is the keyless, fail-closed path from the local CampaignOS pilot to a stable
Cloud Run origin backed by Cloud SQL for PostgreSQL. It does not create a Google Cloud
project, attach billing, create resources, publish an image, add secret values, create
database roles, or deploy anything unless explicit feature flags and evidence receipts
are supplied.

## Default behavior

With only `project_id` supplied:

- `enable_bootstrap=false`;
- `enable_cloud_sql=false`;
- `enable_cloud_run=false`;
- Terraform plans zero resources;
- publication, political effects, paid media and model effects remain false;
- no service-account key is created;
- no secret value is stored in Terraform state.

## Current budget gate

`pilot-cost-review.json` records the operator's 4,000 COP monthly hard cap. The reviewed
minimum Cloud SQL compute lower bound is 24,609 COP/month before storage and ancillary
services, so the current decision is `DENY_APPLY`. This repository may validate plans,
but the current evidence does not authorize Cloud SQL, image publication, secret
versions or Cloud Run.

Google Cloud budgets send alerts; they are not hard spending shutdowns. Terraform also
requires a reviewed estimate, an authorized cap, and a SHA-256 cost receipt before
`enable_cloud_sql=true`, but those inputs still require human review of the exact saved
plan.

## Authentication

```bash
gcloud auth login --no-launch-browser --update-adc
gcloud auth list
gcloud projects list --format='table(projectId,name,lifecycleState)'
```

Do not paste access tokens, authorization codes, passwords or secret payloads into chat,
Git, shell history or Terraform variables.

## Validation without cloud access

```bash
python3 scripts/verify-gcp-pilot-readiness.py
terraform -chdir=infra/gcp fmt -check -recursive
terraform -chdir=infra/gcp init -backend=false
terraform -chdir=infra/gcp validate
terraform -chdir=infra/gcp test
```

## Plan-ready phases

1. Keep the zero-resource defaults and review current cost evidence.
2. After a sufficient cap, enable the project budget, APIs, Artifact Registry, Secret
   Manager containers, two service accounts and GitHub Workload Identity Federation.
3. Plan one zonal PostgreSQL 15 Cloud SQL instance with backups, PITR, bounded storage
   and deletion protection.
4. Apply the database only through a separately approved saved plan.
5. Initialize migration/runtime roles and schema v9 out of band, validate with the
   runtime role, and bind the receipt hash.
6. Build and publish an immutable `linux/amd64` image pinned by digest.
7. Add only the four required effects-off secret versions.
8. Plan Cloud Run with the managed `/cloudsql` socket, min 0, max 2 and all effects off.
9. Apply privately; enable public invocation only through its own approval.
10. Perform the staging observation and workload-only rollback drill.

The complete authority boundaries and verification procedure are in
`docs/runbooks/gcp-pilot-deployment.md`.
