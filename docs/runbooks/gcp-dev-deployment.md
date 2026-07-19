# GCP Development Deployment Runbook

Status: `DENY_APPLY` while no accessible billing account reports `open=True`.

## Hard preconditions

Do not plan or mutate the unrelated active `gcloud` project. Before any real bootstrap or dev plan, record and review:

- one explicit organization/folder choice or the documented no-organization exception;
- one accessible open billing account;
- globally unique bootstrap/dev project IDs and an explicit supported region;
- granular project, billing, API, IAM, WIF, Artifact Registry, Cloud Run, Cloud SQL, Storage, monitoring and budget permissions;
- organization policies, quotas, regional tier availability and an updated cost envelope;
- refreshed ADC/WIF without printing or storing tokens.

If any item is absent, remain in static/mock validation mode.

## Bootstrap

1. Create an ignored `infra/bootstrap/terraform.tfvars` from the example with explicit values.
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

1. Create ignored `infra/environments/dev/backend.hcl` and `terraform.tfvars` from their examples. Supply one to five exact Monitoring channel display names. Terraform must resolve each to exactly one enabled, `VERIFIED` email channel before it can plan the foundation under `environments/dev`. With a separately authorized human/bootstrap administrator, review project/services, runtime IAM, phase-specific IAM, repository, SQL tier/disk/backups/deletion protection, notification delivery, budget and zero public principals.
2. Do not grant a GitHub identity `projectIamAdmin`, `serviceAccountAdmin`, `serviceUsageAdmin`, Artifact Registry admin, Cloud SQL admin or Monitoring admin. The foundation grants only:
   - build: repository-level `roles/artifactregistry.writer`;
   - plan: project `roles/run.viewer`, reads only the foundation/runtime state content, and may create/delete only a disposable `.tflock` below `environments/dev-runtime`;
   - apply: `roles/run.admin` plus read-only SQL/logging/monitoring/IAM review, foundation-state read, state mutation only below `environments/dev-runtime`, and `iam.serviceAccountUser` on the one runtime identity.
3. Apply the independently evaluated foundation plan only after its own `ALLOW_DEV_APPLY`. Verify the remote outputs before allowing routine deployment.
4. Configure `infra/environments/dev_runtime/backend.hcl` with the same bucket and distinct `environments/dev-runtime` prefix. That root consumes foundation outputs and owns only Cloud Run, its migration job and the private invoker binding.
5. Create protected GitHub environments `dev-build`, `dev-plan`, and `dev`. Bind each to its phase-specific WIF provider/account. Protect `dev` with required reviewers, prevent self-review, restrict it to `main`, and expose `DEV_APPLY_ATTESTATION_JSON` only there.
6. Configure workflow variables `GCP_DEV_PROJECT_ID`, `GCP_REGION`, `GCP_TF_STATE_BUCKET`, the three provider variables, and the three phase service-account variables named in `.github/workflows/deploy-dev.yml`.
7. Dispatch the workflow from the pinned `main` revision. Each phase executes a granular `testIamPermissions` preflight. Build pushes one digest; plan creates `tfplan`, `tfplan.json` and `plan-metadata.json`; neither phase can apply.

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
- Cloud SQL direct/password access is absent and IAM connector access works;
- mission/start/get/decision/restart flow passes with external effects false;
- logs/alerts/budget exist and contain no secrets;
- service/job labels, immutable image, runtime identity and phase IAM roles match the reviewed sets;
- alert and budget outputs identify the enabled, verified email channels selected by foundation state; an out-of-band test email, recipient receipt and measured spend are separately recorded by the billing owner;
- a second `terraform plan -detailed-exitcode` returns zero/no changes;
- actual resource inventory and estimated monthly cost are recorded.

## Rollback

- Application: select a previously verified immutable digest, produce a new saved plan, repeat critique/evaluation, and apply that exact plan.
- Migration: revision startup runs the checked migration under a PostgreSQL advisory lock before Uvicorn and `/readyz`; the job repeats it for evidence. A failure prevents new-revision readiness. Repair forward with a reviewed compatible revision; do not auto-downgrade.
- Terraform state: use bucket versioning/soft-delete recovery and validate lineage before any further plan.
- Destruction: export required evidence/data, obtain a separate destructive human gate, change deletion protection explicitly, and review a new plan. Never fold teardown into routine rollback.

No bootstrap, plan against a real target, apply, rollback or teardown is claimed as executed in the current environment.
