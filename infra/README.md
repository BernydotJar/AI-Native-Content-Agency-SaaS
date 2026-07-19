# GCP delivery foundation

Terraform is the source of truth for the managed bootstrap project and the isolated `dev` environment. The configuration is deliberately explicit: no provider inherits the active `gcloud` project, no service-account keys exist, Cloud Run keeps its IAM invoker check enabled, and no public principal is accepted.

## Current execution status

`BLOCKED_BY_EXTERNAL_DEPENDENCY`: discovery found six visible billing accounts and all six were closed, no visible organization, and no selected region. One product-named project candidate now exists, but it has no billing association, required labels, Terraform adoption provenance, or declared bootstrap/dev purpose. Static initialization, validation, and mock-provider tests are allowed. A real plan, project creation/adoption, billing association, state migration, or apply is not allowed until one open billing account and explicit non-personal bootstrap/dev targets and region pass the permission preflight.

The active `gcloud` project is unrelated and is never used implicitly. Both root providers require `project_id`.

## Roots

- `bootstrap/`: always manages one isolated bootstrap project. `CREATE_NEW` creates it; `ADOPT_EXISTING` uses a versioned Terraform import block and requires acknowledgement bound to discovery evidence. It creates the versioned uniform-access state bucket and three keyless build/plan/apply identities. Separate WIF providers bind immutable GitHub owner/repository IDs as well as the exact names, `main` ref, direct workflow and `dev-build`/`dev-plan`/`dev` environments. Conditional state IAM lets plan read the two dev states and create/delete only a runtime `.tflock`; apply can mutate only the runtime-state prefix and merely read foundation state.
- `environments/dev/`: the separately reviewed foundation state. It likewise creates or explicitly imports and manages the distinct dev project, services, runtime identity and IAM, Artifact Registry, PostgreSQL 15 Cloud SQL, Terraform-owned alert delivery and budget. Its apply identity uses an exact 16-permission custom Cloud Run service/job role, repository-scoped image reader and a separate two-permission rollback-tag role—not `roles/run.admin`; it has no service/job delete, artifact deletion/upload or service IAM mutation permission. Foundation grants project-level `roles/run.servicesInvoker` to that identity inside the dedicated dev project. The three supplied phase identities must be the fixed build/plan/apply accounts in the exact bootstrap project. It is not planned or applied by the routine deployment workflow.
- `environments/dev_runtime/`: the narrow routine state. It consumes foundation outputs and manages only the IAM-private Cloud Run service and migration job. The application image must be the exact foundation `agency-images/app@sha256` path and the Cloud SQL Auth Proxy must equal one source-reviewed release/digest; runtime owns no service IAM member. It fails unless bootstrap project, dev project, region, project-provenance digest, notification-channel-provenance digest and deployment identity match the reviewed foundation.
- `environments/staging/` and `environments/prod/`: definitions and human-gate records only. They contain no executable Terraform resources.

Reusable modules live under `modules/`. Root lock files are committed after `terraform providers lock`; state, variable values, backend configuration, saved plans, and plan JSON are ignored.

## Safe bootstrap sequence

1. Repeat GCP-0 discovery. Confirm exactly one explicit parent choice, an open billing account, distinct non-personal globally unique bootstrap/dev project IDs, an allowed region, applicable policies, service quotas, and granular permissions. A product-like name alone is not adoption.
2. Record the immutable numeric GitHub repository and owner IDs from an authenticated GitHub API response. Copy `bootstrap/terraform.tfvars.example` outside Git or create ignored `terraform.tfvars`; bind both names and IDs. Do not use the unrelated active project.
3. For each project choose exactly one lifecycle:
   - `CREATE_NEW`: leave adoption metadata absent and let the managed `google_project` resource create the selected ID.
   - `ADOPT_EXISTING`: preserve the reviewed discovery artifact outside Git, calculate its SHA-256, provide the exact `gcp-project-adoption.v1` acknowledgement and decision reference, and let the versioned import block import the project into state. The saved plan must show the expected import and must not show replacement, deletion, parent drift, billing drift, network creation, or label removal.
   Never use `create_project=false` or a data-only project reference as silent adoption.
4. Run `terraform -chdir=infra/bootstrap init -backend=false`, `validate`, and a saved plan. Inspect plan JSON through `scripts/terraform_plan_gate.py`.
5. Run cloud critique, security review, and an independent readiness evaluation. Only an external `ALLOW_DEV_APPLY` permits the exact saved bootstrap plan.
6. After the state bucket exists, migrate local bootstrap state with the output command. Verify the remote state and remove local state files.
7. Configure the foundation backend from `environments/dev/backend.hcl.example`. Declare each email recipient as sensitive `gcp-notification-channel.v1` input in `notification_channels`, choosing `CREATE_NEW` or evidence-backed `ADOPT_EXISTING`. First produce and independently approve a targeted saved plan for the dev project, required APIs and `module.observability.google_monitoring_notification_channel.delivery`; apply only that exact plan so Terraform creates or imports the channel. Human address verification is the only non-automatable step—never create the channel manually. After verification, record evidence outside Git, add its SHA-256 and HTTPS decision reference, and produce a new full saved plan. Alert, budget and every costly/runtime foundation resource remain blocked until the Terraform-managed channel resolves inside the exact project as enabled and `VERIFIED` with reviewed evidence.
8. Configure `environments/dev_runtime` with the same bucket and the distinct `environments/dev-runtime` prefix. Pass the bootstrap project ID, immutable GitHub owner/repository IDs and the two provenance digests exported by foundation. The runtime plan is permitted only after every foundation binding is verified.
9. Configure three protected GitHub environments. `dev-build` receives only the image provider/account, `dev-plan` receives only the read-only plan provider/account, and `dev` receives the exact runtime deploy provider/account plus required reviewers and the short-lived exact attestation secret. Confirm its project roles contain `projects/PROJECT_ID/roles/agencyRuntimeDeployer`, `roles/run.servicesInvoker` and only the reviewed viewer roles. On `agency-images`, confirm Reader plus `projects/PROJECT_ID/roles/agencyRollbackTagOperator`; the latter must contain exactly `artifactregistry.tags.create` and `artifactregistry.tags.update`.
10. Dispatch the pinned `main` workflow. It tests granular permissions, safely probes a disposable runtime lock, builds and binds an immutable image digest, captures the current deployed digest as the single rollback candidate, plans the narrow runtime state, hashes every tracked path/mode/blob, and uploads one-day plan evidence. Cleanup deletes old tagged or untagged versions after seven days while keeping the 20 most recent and any digest carrying `rollback-current`; tags are never the deployment integrity boundary.
11. An independent reviewer creates `ALLOW_DEV_APPLY` metadata bound to the exact plan, tree, commit, image, workflow, actor, run URL and review time. The apply job verifies it before GCP authentication, authenticates, passes the exact permission preflight, rechecks the candidate, and only then moves `rollback-current` to that immediate predecessor. It applies only the attested plan, runs migrations/smoke/evidence checks, verifies WIF/impersonation/state/repository/custom-role drift and requires a no-change second plan.

The routine runtime role has no `run.services.setIamPolicy`. Foundation-managed project-level `roles/run.servicesInvoker` grants only Cloud Run service invocation—not job execution—and lets the deploy identity smoke-test the newly created private service without changing its IAM policy. Post-apply rejects public or unexpected service bindings, requires the runtime account's exact four project roles, verifies exact named container images, and compares all foundation authority evidence. Service/job and artifact deletion remain absent; any destructive lifecycle or IAM mutation requires a separate human-authorized identity and plan.

No step uses `-auto-approve`. Staging, production, public access, billing changes, deletion, publication, and spend changes retain human gates.

## Passwordless database path

Cloud SQL is PostgreSQL 15 with explicit Enterprise edition, a small shared-core dev tier, ZONAL availability, bounded disk growth, backups, IAM database authentication, connector enforcement `REQUIRED`, and no authorized networks. The application uses a pinned Cloud SQL Auth Proxy sidecar with `--auto-iam-authn` over shared localhost. Before Uvicorn starts, each new revision runs the checked Alembic upgrade through the Cloud SQL Python Connector under a PostgreSQL advisory transaction lock; startup fails closed if migration fails. The separately managed job repeats the same idempotent migration as deployment evidence. Terraform creates no database password or secret value.

The proxy uses Cloud SQL's public connector path because no VPC connector, NAT, or load balancer is justified. Connector enforcement, IAM, ephemeral certificates, and the absence of authorized networks remain mandatory. Actual tier availability, quota, policy, and price must be checked in the selected target region before any real plan.

## Local integrated runtime

Compose uses PostgreSQL 15, matching cloud major-version behavior. It builds one non-root image containing the Vite SPA and FastAPI control plane, waits for PostgreSQL health, executes Alembic in a one-shot migration service, and starts the application only after migration success.

```bash
POSTGRES_PASSWORD='<URL-safe local-only value>' docker compose up --build --wait
curl --fail http://127.0.0.1:8080/healthz
curl --fail http://127.0.0.1:8080/readyz
POSTGRES_PASSWORD='<same value>' docker compose down
```

The password is local Compose data only; it must not be committed. Cloud uses IAM authentication instead.

## Validation

```bash
scripts/validate_platform.sh
python3 scripts/platform_eval.py
terraform -chdir=infra/bootstrap test
terraform -chdir=infra/environments/dev test
terraform -chdir=infra/environments/dev_runtime test
terraform -chdir=infra/modules/artifact_registry test
terraform -chdir=infra/modules/observability test
```

`terraform test` uses mock providers and cannot prove permissions, quotas, regional availability, cost, a real plan, apply safety, runtime health, or drift. Those gates remain blocked until the external billing condition is satisfied.

## Rollback and teardown

- Application rollback: only the immediate predecessor named in the attested pre-apply report is in the routine rollback window. Prove both that digest and `app:rollback-current` resolve to the same SHA-256, then produce a new saved plan and repeat critique/evaluation before redeploying it. The tag is a retention pointer, never the deployment reference. Older versions are outside the guaranteed window even if they happen to remain among the 20 newest. Database migrations must be backward compatible before traffic moves.
- Failed migration: the migration job stops before readiness verification. Do not automatically downgrade; repair forward using a new reviewed revision.
- Infrastructure teardown: first export required evidence/artifacts, confirm no retained data is needed, and obtain the destructive human gate. The routine deploy identity cannot delete Cloud Run services or jobs. Deletion protection is enabled on Cloud Run, its migration job, Cloud SQL, and projects. Disabling it and using a separate destructive identity require a reviewed source change and a new saved plan.
- State recovery: bucket versioning and seven-day soft delete allow recovery. There is deliberately no bucket retention policy because it would also retain `.tflock` objects and prevent normal lock release. Do not delete the state bucket while managed resources exist.

No teardown has been executed or validated against real GCP resources.
