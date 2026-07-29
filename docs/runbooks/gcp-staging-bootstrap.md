# GCP staging bootstrap runbook

## Current authorization boundary

This increment may install local tooling, validate Terraform and inspect projects after
interactive login. It must not create a project, attach billing, enable APIs, push an
image, add secrets or apply Terraform without a separate operator confirmation of the
exact plan.

## Login from the persistent Cloud Sandbox container

```bash
cd /workspace
gcloud auth login --no-launch-browser --update-adc
```

Open the displayed Google URL in your browser, complete sign-in and paste only the
one-time authorization code back into the container prompt. Keep the code out of chat.

Then inspect the authenticated account and available projects:

```bash
gcloud auth list
gcloud projects list --format='table(projectId,name,lifecycleState)'
gcloud config list
```

After selecting an existing project or creating a new project in the Google Cloud
console, configure it locally:

```bash
export PROJECT_ID='replace-with-project-id'
gcloud config set project "$PROJECT_ID"
gcloud config set run/region us-central1
gcloud auth application-default set-quota-project "$PROJECT_ID"
```

Record the numeric project and open billing account IDs for the reviewed Terraform plan:

```bash
gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)'
gcloud beta billing projects describe "$PROJECT_ID" --format='value(billingAccountName)'
```

## Plan-only validation

```bash
cp infra/gcp/terraform.tfvars.example infra/gcp/terraform.tfvars
# Edit only project_id first; keep both enable flags false.
terraform -chdir=infra/gcp init -backend=false
terraform -chdir=infra/gcp plan -out=/tmp/campaignos-gcp-zero.tfplan
terraform -chdir=infra/gcp show /tmp/campaignos-gcp-zero.tfplan
```

The initial plan must contain zero resources. Any non-zero resource count is a stop
condition.

The bootstrap plan must include one project-scoped monthly budget in the billing-account
currency with thresholds at 5%, 25% and 100%. For the current COP account, the reviewed
amount is `64000`, producing alerts at COP 3,200, COP 16,000 and COP 64,000. A budget is
not a hard spending cap.

## Cost boundary

Cloud Run can remain inside its free usage allowance at low traffic with zero minimum
instances, but billing must still be enabled for deployment. Artifact Registry storage,
outbound traffic and any managed PostgreSQL service may incur charges. This runbook does
not claim that a persistent production database is free.
