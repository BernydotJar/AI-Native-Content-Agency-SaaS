# GCP Development Deployment Runbook

Status: `DENY_APPLY`. No accessible billing account reports `open=True`; no target parent/region or distinct project roles are authorized; no real saved plan exists.

## Hard preconditions

Do not plan or mutate the unrelated active `gcloud` project. Before any real bootstrap or dev plan, record and review:

- one explicit organization/folder choice or the documented no-organization exception;
- one accessible open billing account;
- globally unique bootstrap/dev project IDs and an explicit supported region;
- granular project, billing, API, IAM, WIF, Artifact Registry, Cloud Run, Cloud SQL, Storage, monitoring and budget permissions;
- organization policies, quotas, regional tier availability and an updated cost envelope;
- refreshed ADC/WIF without printing or storing tokens.

Read-only discovery now shows candidate project `ai-native-content-agency-saas`. Its matching name does not authorize use. Before a plan, explicitly reject it or assign it to exactly one of bootstrap/dev under the evidence-backed `ADOPT_EXISTING` path, then select a distinct second project. Never allow one project ID to satisfy both roles.

If any item is absent, remain in static/mock validation mode.

## Bootstrap

1. Create an ignored `infra/bootstrap/terraform.tfvars` from the example with explicit values. Select exactly one lifecycle:
   - `CREATE_NEW`: Terraform creates and manages the project; adoption metadata is absent.
   - `ADOPT_EXISTING`: provide `gcp-project-adoption.v1` metadata bound to reviewed discovery evidence and the exact acknowledgement. The import block brings the project under Terraform management. Inspect import, parent, billing, APIs, network and labels in the saved plan; a data-only reference is not adoption.
2. Initialize without inheriting `gcloud` defaults:

   ```bash
   terraform -chdir=infra/bootstrap init -backend=false
   terraform -chdir=infra/bootstrap validate
   terraform -chdir=infra/bootstrap plan -input=false -out=tfplan
   terraform -chdir=infra/bootstrap show -json tfplan > infra/bootstrap/tfplan.json
   python3 scripts/terraform_plan_gate.py infra/bootstrap/tfplan.json
   ```

3. Hash and archive the short-lived saved plan as controlled evidence. A static PASS is not apply authorization.
4. Require independent cloud critique, security review and production-readiness evaluation. Apply only if the evaluator returns `ALLOW_DEV_APPLY`, and only with `terraform apply -input=false tfplan`.
5. Verify the versioned state bucket and WIF condition, then migrate state using the reviewed Terraform output. Remove local state only after remote-state verification.

## Dev foundation and narrow runtime

1. Create ignored `infra/environments/dev/backend.hcl` and `terraform.tfvars` from their examples. Select project `CREATE_NEW` or evidence-backed `ADOPT_EXISTING`, pass the distinct reviewed `bootstrap_project_id`, immutable numeric GitHub owner/repository IDs and required region. The image, plan and apply email inputs must be the exact fixed `github-image-dev`, `github-plan-dev` and `github-deploy-dev` service accounts in that bootstrap project; the authorization gate rejects arbitrary external accounts.
2. Declare one to five sensitive `gcp-notification-channel.v1` records in `notification_channels`:
   - `CREATE_NEW` makes Terraform create and retain the email channel; do not provide an existing channel name.
   - `ADOPT_EXISTING` requires its exact `projects/PROJECT_ID/notificationChannels/ID` name, reviewed evidence and acknowledgement; the root import block brings it under Terraform management.

   Use the separately authorized foundation administrator to produce a targeted saved phase-A plan. Review that it contains only the selected dev project/import, required APIs and Terraform-managed channel dependencies; run the normal plan gate and independent review before applying the exact file:

   ```bash
   terraform -chdir=infra/environments/dev plan -input=false \
     -target=module.observability.google_monitoring_notification_channel.delivery \
     -out=channel.tfplan
   terraform -chdir=infra/environments/dev show -json channel.tfplan > infra/environments/dev/channel.tfplan.json
   python3 scripts/terraform_plan_gate.py infra/environments/dev/channel.tfplan.json
   # Only after an independent ALLOW_DEV_APPLY for this exact file:
   terraform -chdir=infra/environments/dev apply -input=false channel.tfplan
   ```

   Human response to the provider-sent verification email is the only non-automatable step; the channel itself must never be created manually. Record verification evidence outside Git, add its SHA-256 and HTTPS decision reference, and then create a new full saved foundation plan. The verification gate requires the Terraform-managed channel to be enabled and `VERIFIED`; alert, budget and all runtime/costly resources depend on that gate.
3. Do not grant a GitHub identity `projectIamAdmin`, `serviceAccountAdmin`, `serviceUsageAdmin`, `roles/run.admin`, Artifact Registry admin, Cloud SQL admin or Monitoring admin. The foundation grants only:
   - build: repository-level `roles/artifactregistry.writer`;
   - plan: project `roles/run.viewer`, reads only the foundation/runtime state content, and may create/delete only a disposable `.tflock` below `environments/dev-runtime`;
   - apply: project custom role `projects/PROJECT_ID/roles/agencyRuntimeDeployer`, project `roles/run.servicesInvoker`, repository-level `roles/artifactregistry.reader` plus `projects/PROJECT_ID/roles/agencyRollbackTagOperator`, read-only SQL/logging/monitoring/IAM review, foundation-state read, state mutation only below `environments/dev-runtime`, and `roles/iam.serviceAccountUser` on the one runtime identity.

   The custom runtime role contains exactly 16 permissions: `resourcemanager.projects.get`; `run.executions.get`; `run.locations.get/list`; `run.operations.get`; service `create/get/getIamPolicy/list/update`; and job `create/get/getIamPolicy/list/run/update`. It excludes service/job delete, `run.services.setIamPolicy`, `run.jobs.runWithOverrides`, job IAM mutation, project/foundation IAM mutation and every predefined Cloud Run administration role. Foundation grants the deploy identity project-level `roles/run.servicesInvoker` inside the dedicated dev project; unlike `roles/run.invoker`, it does not grant job execution. Runtime owns no service IAM member. Destruction or service-IAM mutation requires a separate human-authorized identity and plan.
4. Apply the independently evaluated full foundation plan only after its own `ALLOW_DEV_APPLY`. Verify the remote outputs before allowing routine deployment. The rollback role contains exactly `artifactregistry.tags.create` and `artifactregistry.tags.update`; it cannot upload/delete artifacts. Cleanup can delete versions older than seven days while keeping the 20 most recent and the one `rollback-current` version. Routine deployment always uses an immutable digest.
5. Configure `infra/environments/dev_runtime/backend.hcl` with the same bucket and distinct `environments/dev-runtime` prefix. That root consumes foundation outputs and owns only Cloud Run and its migration job; it owns no service IAM binding. It must exactly match bootstrap/dev separation, region, immutable GitHub IDs, project-provenance digest and notification-channel-provenance digest.
6. GitHub environments `dev-build`, `dev-plan`, and `dev` now exist and accept protected branches only. `dev` requires user `BernydotJar` and prevents self-review. This still fails closed: `BernydotJar` is the repository's only collaborator, so no distinct actor/reviewer pair can currently satisfy the approval boundary. Add a distinct eligible reviewer before any dispatch; never weaken prevent-self-review. Expose `DEV_APPLY_ATTESTATION_JSON` only in `dev` after that control exists.
7. Main protection now requires the exact four CI job names, strict updates, one approval, last-push approval, stale-review dismissal, conversation resolution, linear history and admin enforcement, with force-push and deletion disabled. The updated workflow is not on `main` until the draft PR is independently approved and merged outside this iteration, so the live gate remains incomplete.
8. Configure the twelve non-secret workflow variables named in `.github/workflows/deploy-dev.yml`: `GCP_BOOTSTRAP_PROJECT_ID`, `GCP_DEV_PROJECT_ID`, `GCP_REGION`, `GCP_TF_STATE_BUCKET`, `GCP_FOUNDATION_PROJECT_PROVENANCE_SHA256`, `GCP_FOUNDATION_NOTIFICATION_CHANNEL_PROVENANCE_SHA256`, the three WIF provider variables and the three phase service-account variables. The live repository currently has zero Actions variables. Populate them only from reviewed Terraform/GitHub outputs after foundation exists; do not use placeholders in a dispatch.
9. Dispatch the workflow from the pinned `main` revision only after those gates close. Each phase executes a granular `testIamPermissions` preflight. Build pushes one digest; plan creates `tfplan`, `tfplan.json` and `plan-metadata.json`; neither phase can apply.

The independent evaluator must review the plan JSON, cost envelope and metadata, then set the protected attestation secret to exactly this locked schema (with real values):

```json
{
  "schema_version": "dev-apply-attestation.v1",
  "decision": "ALLOW_DEV_APPLY",
  "plan_sha256": "64 lowercase hex",
  "source_tree_sha256": "64 lowercase hex",
  "source_commit": "exact GitHub SHA",
  "image_reference": "registry/repository/image@sha256:64 lowercase hex",
  "workflow_ref": "owner/repository/.github/workflows/deploy-dev.yml@refs/heads/main",
  "workflow_actor": "dispatcher",
  "reviewer": "different-independent-reviewer",
  "environment": "dev",
  "reviewed_at": "RFC3339 UTC within 24 hours",
  "evidence_url": "https://github.com/owner/repository/actions/runs/numeric-run-id"
}
```

The apply job recomputes every binding before it authenticates. Missing/extra/duplicate fields, a stale review, self-review or any mismatch denies apply. GitHub environment approval alone is not sufficient. The workflow never uses `-auto-approve`.

## Post-apply evidence

Require all of the following before calling dev usable:

- unauthenticated invocation is denied;
- the intended principal can invoke through IAM;
- app and migration identities have only reviewed roles;
- the deploy identity has exactly the 16-permission runtime project role, reviewed viewer/invoker roles, repository Reader, and the repository-scoped `agencyRollbackTagOperator` role with only `artifactregistry.tags.create`/`tags.update`; `roles/run.admin`, artifact upload and artifact deletion are absent;
- Cloud SQL direct/password access is absent and IAM connector access works;
- mission/start/get/decision/restart flow passes with external effects false;
- logs/alerts/budget exist and contain no secrets;
- service/job labels, named application/migration/proxy images, runtime identity and phase IAM roles match the reviewed sets;
- all three WIF providers/claims, phase impersonation policies, state-prefix bindings, complete repository policy and both custom-role permission sets match foundation evidence;
- the attested pre-apply rollback report proves the desired digest exists and the immediate predecessor equals the digest resolved by `app:rollback-current` (or explicitly records a first deployment);
- alert and budget outputs identify the enabled, verified email channels selected by foundation state; an out-of-band test email, recipient receipt and measured spend are separately recorded by the billing owner;
- a second `terraform plan -detailed-exitcode` returns zero/no changes;
- actual resource inventory and estimated monthly cost are recorded.

## Rollback

- Application: routine rollback is bounded to the immediate predecessor recorded in the reviewed pre-apply report. Confirm that predecessor and `app:rollback-current` resolve to the same SHA-256, use the digest—not the tag—as `container_image`, produce a new saved plan, repeat critique/evaluation, and apply that exact plan. Older images are outside the guaranteed rollback window.
- Migration: revision startup runs the checked migration under a PostgreSQL advisory lock before Uvicorn and `/readyz`; the job repeats it for evidence. A failure prevents new-revision readiness. Repair forward with a reviewed compatible revision; do not auto-downgrade.
- Terraform state: use bucket versioning/soft-delete recovery and validate lineage before any further plan.
- Destruction: export required evidence/data, obtain a separate destructive human gate, change deletion protection explicitly, and review a new plan. Never fold teardown into routine rollback.

No bootstrap, real-target plan, project import/adoption, apply, rollback or teardown is claimed as executed in the current environment. The current candidate project remains outside Terraform state and unassigned.
