# INC-037 — GCP staging bootstrap

Updated: 2026-07-29

## Objective

Replace the expired Quick Tunnel dependency with a stable Google Cloud foundation while
keeping runtime deployment, database creation, secret values and external publication
behind separate gates.

## Authenticated target

```text
account=eduardo.sacahui@gmail.com
project=ai-native-content-agency-saas
project_number=970393454298
region=us-central1
billing_enabled=true
gcloud=578.0.0
terraform=1.15.8
google_provider=7.41.0
```

The operator explicitly authorized linking billing and applying the reviewed bootstrap.

## Applied foundation

Terraform now manages:

```text
Google APIs                                      10
Artifact Registry repositories                    1
Billing budgets                                   1
Runtime service accounts                          1
Deployer service accounts                         1
Workload Identity Pools                           1
Workload Identity Providers                       1
Project IAM memberships                           3
Service-account IAM memberships                   2
Secret Manager containers                         8
Per-secret runtime accessor memberships           8
Terraform state entries, including data           38
```

The GitHub OIDC condition is exact:

```text
assertion.repository == 'BernydotJar/AI-Native-Content-Agency-SaaS' &&
assertion.ref == 'refs/heads/main'
```

No service-account key exists.

## Budget guardrail

The selected billing account uses COP. Terraform reads the account currency instead of
assuming USD. At bootstrap time, USD 20 converted to COP 64,257.20; the reviewed amount
was rounded down to a conservative monthly budget of COP 64,000.

```text
budget=CampaignOS staging monthly guardrail
currency=COP
monthly_amount=64000
threshold_1=5%   / COP 3200
threshold_2=25%  / COP 16000
threshold_3=100% / COP 64000
scope=projects/970393454298
```

Budget notifications use the billing-account IAM recipients. A GCP budget is an alerting
guardrail, not an automatic service shutdown.

## Artifact Registry guardrail

Repository:

```text
us-central1-docker.pkg.dev/ai-native-content-agency-saas/campaignos
```

Active cleanup policies:

```text
delete-older-than-30d: DELETE tag_state=ANY older_than=2592000s
keep-five-most-recent: KEEP keep_count=5
cleanup_policy_dry_run=false
```

No image has been pushed.

## Secret boundary

Eight secret containers exist, but all are empty. Verification found:

```text
secret_containers=8
secret_versions=0
user_managed_service_account_keys=0
```

Terraform never stores the secret values. Cloud Run requires numeric secret versions and
therefore remains impossible to plan successfully until the values are added through a
separately reviewed migration.

## Runtime boundary

Verified live after apply:

```text
cloud_run_services=0
cloud_sql_instances=0
compute_instances=0
gke_clusters=0
artifact_images=0
social_publication_effects=0
```

All application publication, political publication, paid-media and model-effect switches
remain false.

## Apply recovery evidence

The initial immutable plan contained 35 create actions and no changes or destroys. Google
completed 34 control-plane resources, then rejected only the budget because the local ADC
quota project was not honored for the Billing Budgets API. The state was reconciled before
continuing.

Recovery steps were bounded and audited:

1. verified 34 resources present and in Terraform state;
2. set `billing_project` and `user_project_override` explicitly in the provider;
3. enabled and imported Cloud Resource Manager and Cloud Billing APIs;
4. read the real billing-account currency through `google_billing_account`;
5. generated a plan with one actionable create: the COP budget;
6. applied that saved plan successfully;
7. generated a second plan with one in-place update: Artifact Registry cleanup policies;
8. applied with zero additions or destructions.

No rollback or destructive action was needed.

## State recovery

Latest persistent state backup:

```text
path=.local/gcp-state-backups/terraform-20260729T010938Z.tfstate
sha256=8b7c04994ace29c3ab25eae94d81f76f63755e0ba4d34baba15c888b5a84f891
entries=38
```

The file remains local and ignored by Git. A production remote-state backend is still a
future decision because it introduces another storage resource and cost surface.

## Image publication design

The Cloud Sandbox host and nested Docker daemon are ARM64. Verified Buildx and QEMU
attempts could not register the cross-platform layers because the nested storage driver
returned `operation not supported`. No local image was produced.

`.github/workflows/publish-gcp-image.yml` therefore delegates the image build to the
GitHub-hosted AMD64 runner. The workflow:

- runs only by manual dispatch;
- requires `confirm_publish=true`;
- refuses non-`main` refs;
- obtains short-lived Google credentials through WIF;
- uses no service-account JSON key;
- builds `linux/amd64`;
- pushes only a commit-SHA tag;
- records the immutable digest;
- emits SBOM and provenance;
- performs no Cloud Run deploy, Terraform apply or secret access.

The workflow actions are full-SHA pinned and a repository verifier fails if deployment or
secret-read authority is added.

## Validation

```text
terraform_fmt=pass
terraform_validate=pass
terraform_tests=3_pass_0_fail
actionlint=pass
gcp_image_workflow_authority=pass
runtime_deploy_authority=false
cloud_run_services=0
cloud_sql_instances=0
secret_versions=0
service_account_keys=0
```

Release recommendation: `DENY_RELEASE`

Cloud recommendation: `DENY_APPLY`

The explicitly authorized bootstrap is complete. `DENY_APPLY` remains the global gate for
all additional mutations, especially image publication, database creation, secret values
and Cloud Run deployment.
