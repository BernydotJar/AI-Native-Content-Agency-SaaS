# GCP delivery foundation

Terraform is the source of truth for the optional bootstrap project and the isolated `dev` environment. The configuration is deliberately explicit: no provider inherits the active `gcloud` project, no service-account keys exist, Cloud Run keeps its IAM invoker check enabled, and no public principal is accepted.

## Current execution status

`BLOCKED_BY_EXTERNAL_DEPENDENCY`: discovery found six visible billing accounts and all six were closed, no related project, no visible organization, and no selected region. Static initialization, validation, and mock-provider tests are allowed. A real plan, project creation/adoption, billing association, state migration, or apply is not allowed until one open billing account and an explicit non-personal target project/region pass the permission preflight.

The active `gcloud` project is unrelated and is never used implicitly. Both root providers require `project_id`.

## Roots

- `bootstrap/`: optionally creates an isolated bootstrap project, the versioned uniform-access state bucket, and three keyless build/plan/apply identities. Separate WIF providers bind them to the exact owner, repository, `main` ref, direct workflow and `dev-build`/`dev-plan`/`dev` environments. Conditional state IAM lets plan read the two dev states and create/delete only a runtime `.tflock`; apply can mutate only the runtime-state prefix and merely read foundation state.
- `environments/dev/`: the separately reviewed foundation state. It creates/adopts the dev project, services, runtime identity and IAM, Artifact Registry, PostgreSQL 15 Cloud SQL, alert delivery and budget. It is not planned or applied by the routine deployment workflow.
- `environments/dev_runtime/`: the narrow routine state. It consumes foundation outputs and manages only the IAM-private Cloud Run service, migration job and invoker binding for an immutable image.
- `environments/staging/` and `environments/prod/`: definitions and human-gate records only. They contain no executable Terraform resources.

Reusable modules live under `modules/`. Root lock files are committed after `terraform providers lock`; state, variable values, backend configuration, saved plans, and plan JSON are ignored.

## Safe bootstrap sequence

1. Repeat GCP-0 discovery. Confirm exactly one explicit parent choice, an open billing account, a non-personal globally unique bootstrap/dev project ID, an allowed region, applicable policies, service quotas, and granular permissions.
2. Copy `bootstrap/terraform.tfvars.example` outside Git or create ignored `terraform.tfvars`. Do not use the unrelated active project.
3. Run `terraform -chdir=infra/bootstrap init -backend=false`, `validate`, and a saved plan. Inspect plan JSON through `scripts/terraform_plan_gate.py`.
4. Run cloud critique, security review, and an independent readiness evaluation. Only an external `ALLOW_DEV_APPLY` permits the exact saved bootstrap plan.
5. After the state bucket exists, migrate local bootstrap state with the output command. Verify the remote state and remove local state files.
6. Configure the foundation backend from `environments/dev/backend.hcl.example`. Select pre-existing Monitoring channels by exact display name; each must resolve uniquely as an enabled, verified email channel. Use a separately authorized foundation administrator—not a GitHub runtime identity—to plan/apply APIs, IAM, registry, SQL, alert delivery and budget after exact-plan review.
7. Configure `environments/dev_runtime` with the same bucket and the distinct `environments/dev-runtime` prefix. The runtime plan is permitted only after the foundation state and identities are verified.
8. Configure three protected GitHub environments. `dev-build` receives only the image provider/account, `dev-plan` receives only the read-only plan provider/account, and `dev` receives the Cloud Run deploy provider/account plus required reviewers and the short-lived exact attestation secret.
9. Dispatch the pinned `main` workflow. It tests granular permissions, safely probes a disposable runtime lock, builds an immutable image, plans the narrow runtime state, hashes every tracked path/mode/blob, and uploads one-day plan evidence.
10. An independent reviewer creates `ALLOW_DEV_APPLY` metadata bound to the exact plan, tree, commit, image, workflow, actor, run URL and review time. The apply job verifies it before GCP authentication, applies only that plan, runs migrations/smoke/evidence checks and requires a no-change second plan.

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
```

`terraform test` uses mock providers and cannot prove permissions, quotas, regional availability, cost, a real plan, apply safety, runtime health, or drift. Those gates remain blocked until the external billing condition is satisfied.

## Rollback and teardown

- Application rollback: redeploy a previously verified immutable digest and run the same saved-plan/evaluator sequence. Database migrations must be backward compatible before traffic moves.
- Failed migration: the migration job stops before readiness verification. Do not automatically downgrade; repair forward using a new reviewed revision.
- Infrastructure teardown: first export required evidence/artifacts, confirm no retained data is needed, and obtain the destructive human gate. Deletion protection is enabled on Cloud Run, its migration job, Cloud SQL, and projects. Disabling it requires a reviewed source change and a new saved plan.
- State recovery: bucket versioning, a one-day unlocked retention policy, and seven-day soft delete allow recovery. Do not delete the state bucket while managed resources exist.

No teardown has been executed or validated against real GCP resources.
