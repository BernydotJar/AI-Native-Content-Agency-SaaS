# GCP staging bootstrap

This module is the keyless, fail-closed path from the local CampaignOS pilot to a stable
Cloud Run origin. It does not create a Google Cloud project, attach billing, create a
database, add secret values, publish an image or deploy anything unless its explicit
feature flags are enabled.

## Default behavior

With only `project_id` supplied:

- `enable_bootstrap=false`;
- `enable_cloud_run=false`;
- Terraform plans zero resources;
- publication, political effects, paid media and model effects remain false;
- no service-account key is created;
- no secret value is stored in Terraform state.

When bootstrap is enabled, a project-scoped monthly budget is mandatory. Its amount is
expressed in whole units of the billing account currency, with notifications at 5%, 25%
and 100%. The current COP account uses `64000`, approximately USD 20 at bootstrap time.
Budget notifications use billing-account IAM recipients and do not stop services.

## Authentication

```bash
gcloud auth login --no-launch-browser --update-adc
gcloud auth list
gcloud projects list --format='table(projectId,name,lifecycleState)'
```

Do not paste access tokens or authorization codes into chat, Git, shell history files or
Terraform variables.

## Validation without cloud access

```bash
terraform -chdir=infra/gcp fmt -check -recursive
terraform -chdir=infra/gcp init -backend=false
terraform -chdir=infra/gcp validate
terraform -chdir=infra/gcp test
```

## Phases

1. Zero-resource plan with all feature flags false.
2. Bootstrap the project budget, APIs, Artifact Registry, Secret Manager containers,
   two least-privilege service accounts and GitHub Workload Identity Federation.
3. Build and push an immutable `linux/amd64` image. The repository deletes versions
   older than 30 days while retaining at least the five most recent versions.
4. Add secret values out-of-band with `gcloud secrets versions add`.
5. Deploy Cloud Run privately and verify health.
6. Open public invocation only after the security review.
7. Configure stable Cloud Run or custom-domain OAuth callbacks.

A persistent PostgreSQL database is a separate gate. Cloud Run must not be enabled with
an ephemeral SQLite database.
