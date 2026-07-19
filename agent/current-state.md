# Current State

Updated: 2026-07-19T03:59:19Z

## Repository

- Branch: `feat/production-foundation-v1`
- Base: `dcb1d1c567ad688b7fd78a219411b42d5806034c`
- Verified implementation commit: `2513be1019a675426a6b3c27c0309137bea5c433`
- Remote: `origin` (`BernydotJar/AI-Native-Content-Agency-SaaS`)
- Tracking issue: `#1` — Production Foundation V1: unified control plane and GCP dev path
- Draft PR: `#2` — Production Foundation V1: durable control plane and gated GCP dev path
- GitHub Actions run `29672546616`: all four required CI jobs passed on the verified implementation commit.
- Merge status: draft and unmerged; human review remains required.

## Implemented local foundation

- FastAPI `/api/v1` is the authoritative control plane for missions, runs, steps, artifacts, evidence, events, audit, approvals and idempotency.
- SQLAlchemy/Alembic persist command-boundary state. SQLite is restricted to local/test use; Compose and the cloud design use PostgreSQL 15.
- Tenant ownership is enforced in application behavior and by composite database foreign keys across dependent records.
- Greenlight is tenant-scoped and bound to the exact pre-Publisher artifact SHA-256 plus `greenlight.v1`. Approval produces only a sandbox package with `publication_performed=false`.
- The default React UI uses the API, stable retry keys, stale-response guards and sequential non-overlapping polling. The timer-based prototype is isolated behind `VITE_RUNTIME_MODE=demo`.
- A pinned non-root combined SPA/API image, PostgreSQL/Alembic Compose topology, CI, dependency gates and Terraform bootstrap/dev definitions exist.
- Foundation and runtime Terraform state are separated. Plan and apply identities are split; runtime deployment uses an exact custom Cloud Run role plus repository-scoped Artifact Registry read access.
- Notification channels are selected by exact display name and must be enabled; email delivery requires a verified channel.
- Terraform defines only bootstrap/dev executable roots. Staging and production remain definition-only.

## Verified exact-tree gates

- Backend: 44/44 strict pytest cases pass on Python 3.13.5; Ruff, mypy, canonical OpenAPI, Alembic and PostgreSQL integration pass.
- Frontend: 47/47 tests pass; the prior polling-race test passed eight consecutive focused runs; lint, typecheck, OpenAPI contract and production build pass.
- Dependency gates: npm audit and both exact hash-locked Python audits report zero known vulnerabilities. The CI lock resolves pytest 9.1.1, above the affected pytest 8.x range.
- Platform: nine Terraform roots initialize read-only and validate; three mock-provider tests, 25 script tests, YAML/Compose checks and 46/46 static controls pass.
- Container: `ai-native-content-agency:validation-final5` runs as UID/GID `10001:10001`; migrations and readiness pass; a full HTTP mission/run/approval flow emitted eight artifacts and eight evidence records with zero external effects.
- Persistence: run `run-1e4a654937524e008520932253dfde80` remained readable and complete after restarting the application container against the preserved PostgreSQL volume.
- CI: backend/PostgreSQL, frontend, security/integrity and Terraform/Compose/container jobs all pass in GitHub Actions run `29672546616`.
- Interactive visual QA remains unproven because the required in-app browser runtime exposed no browser instances.

## Review model and limitations

- Producer, critic and evaluator passes were performed sequentially with explicit role separation and deterministic evidence.
- Additional independent subagents could not be allocated because the workspace's collaboration credits were exhausted. No artifact claims independent verification.
- The draft PR therefore remains the boundary for human review; this state is `READY_FOR_REVIEW`, not merged or released.

## Safety boundaries

- Local application recommendation: `READY_FOR_REVIEW`.
- Cloud apply recommendation: `DENY_APPLY`.
- Bootstrap and dev may be applied only from a genuinely independent approval of one exact saved Terraform plan.
- Cloud Run dev remains IAM-private; no `allUsers` or `allAuthenticatedUsers` binding is permitted.
- No provider publication, Meta Ads activation, advertising spend, service-account key, destructive migration, staging/production apply or merge is authorized.

## External GCP blocker

Read-only discovery found six visible billing accounts and zero open accounts, no related target project, no visible organization, and no selected region. The active gcloud project `meridian-hr-crm` is unrelated and prohibited as a target. ADC refresh succeeded with token output discarded.

A real plan/apply requires an accessible account reporting `open=True`, explicit hierarchy/project/region selection, granular permissions/policy/quota/cost preflight, an immutable image in the target registry, a saved plan and independent `ALLOW_DEV_APPLY` for that exact plan. No GCP mutation, plan or apply occurred.
