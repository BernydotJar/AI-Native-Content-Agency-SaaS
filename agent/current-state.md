# Current State

Updated: 2026-07-19T20:08:49Z

## Repository and release truth

- Branch: `feat/production-foundation-v1`; base branch: `main`.
- Latest committed implementation repair: `06a13b21989a44e75db31b41e1c460ae24e01d7f`; this state update belongs to the following governance source commit.
- Tracking issue: `#1`; draft PR: `#2`. The PR is open, draft, mergeable and unmerged.
- GitHub Actions run `29672994585` passed all four jobs on `34c3489`. It predates the current uncommitted repair increment and is historical evidence, not proof of the present tree.
- The repaired tree now has focused local source commits but has not been pushed or exercised by exact-tree GitHub Actions, and the repaired deploy workflow is not on `main`.
- `main` branch protection is now configured with strict required checks, administrator enforcement, one approving review, last-push approval, conversation resolution, linear history, and force-push/deletion disabled. The exact required checks are `Backend, migrations, OpenAPI, and PostgreSQL`; `Dependency, secret, and repository integrity gates`; `Frontend build, lint, and tests`; and `Terraform, Compose, container, and platform evals`.
- Environments `dev-build` and `dev-plan` allow only protected branches. `dev` also names `BernydotJar` as reviewer and enables `prevent_self_review`. This does not satisfy independence because no distinct reviewer/dispatch actor is available. Actions variables remain unconfigured, so no deploy dispatch is eligible.
- Release recommendation: `DENY_RELEASE`. Cloud recommendation: `DENY_APPLY`. No merge, release or deployment is authorized.

## Implemented local foundation

- FastAPI `/api/v1` is the authority for missions, runs, steps, artifacts, evidence, events, audit records, decisions and idempotency. `GET /api/v1/identity` now exposes versioned tenant/principal identity contracts for the active non-production identity boundary.
- SQLAlchemy and Alembic persist command-boundary state. SQLite is restricted to isolated local/tests; PostgreSQL is the Compose and intended cloud runtime. Migration `0003_approval_idempotency` directly binds each approval row to its command key and fails closed when a legacy approval cannot be linked safely.
- Greenlight is tenant scoped and bound to the exact pre-Publisher artifact SHA-256 plus `greenlight.v1`. Approval/rejection, its idempotency key and the audit payload are persisted. Approval creates only a sandbox package with `publication_performed=false`.
- The default React UI consumes the API. Demo timers remain behind explicit `VITE_RUNTIME_MODE=demo` isolation. Three Playwright scenarios exercise approval, rejection and app-only restart through the real SPA, FastAPI and PostgreSQL stack, including refresh/reconnect and exact restored artifacts/evidence on a fresh owned volume.
- The combined image is non-root and Compose orders PostgreSQL, Alembic and app readiness. The HTTP smoke asserts exactly eight artifacts and eight evidence records for an approved run; PostgreSQL integration now includes cross-tenant read/approval denial.
- Terraform contains separate bootstrap, dev-foundation and dev-runtime states. Project creation or adoption is explicit and Terraform-managed; adoption requires versioned evidence and a declarative import. Bootstrap/dev IDs must differ, required labels cannot be overridden, region/provenance outputs are runtime-bound, and WIF checks immutable numeric repository/owner IDs in addition to names/ref/workflow/environment.
- Foundation accepts only the three fixed bootstrap phase accounts: `github-image-dev`, `github-plan-dev`, and `github-deploy-dev` in the exact bootstrap project. Arbitrary service-account emails fail the authorization gate.
- Routine deploy IAM is a 16-permission Cloud Run custom role with no service/job delete or service IAM mutation. The separately reviewed foundation grants project-level `roles/run.servicesInvoker`—never `roles/run.invoker`—inside the dedicated dev project; runtime state owns no service IAM member. Apply also has repository Reader plus a separate two-permission rollback-tag role with no upload/delete. Post-apply rejects public/unexpected bindings, requires the runtime account's exact four roles, matches named app/migration/proxy images and verifies WIF, impersonation, state, repository and both custom-role authority.
- The state bucket uses versioning and seven-day soft delete but deliberately has no retention policy, so Terraform `.tflock` objects can be released normally.
- Artifact Registry tags are removable: cleanup deletes versions in tag state `ANY` older than seven days while keeping the 20 most recent versions and the immediate predecessor bearing `rollback-current`. Plan binds the predecessor; apply may move that tag only after exact attestation/auth/preflight. Deployment and rollback plans use the digest, not the tag.
- Monitoring email channels are Terraform-owned `notification_channels` using `gcp-notification-channel.v1`. `CREATE_NEW` creates the channel; `ADOPT_EXISTING` imports it with reviewed provenance. Email values are sensitive and channels use `prevent_destroy`. A targeted phase-A saved plan creates/imports only project/APIs/channels; after human verification, phase B supplies evidence and evaluates the full plan. Costly/runtime resources remain gated on verified channel provenance.

## Current local evidence

- Current backend validation: 58 pytest cases plus seven legacy unittest cases, Ruff check/format, mypy over 15 modules, OpenAPI drift, Alembic upgrade/downgrade/backfill/fail-closed coverage and PostgreSQL integration passed. The new cases cover cross-instance pre-provider key ownership and immediate rollback when lock acquisition fails.
- Frontend producer validation: 47 unit/component tests, lint, typecheck, OpenAPI mapping and build passed.
- Live transport: a fresh disposable Compose project passed approval, rejection and restart persistence 3/3 against real networking and PostgreSQL in five seconds; no fetch interception or mocked transport is used, and exact volume cleanup passed. The first restart attempt exposed and recorded a Compose process-control defect before the corrected rerun.
- Real PostgreSQL: the isolated non-deployed test stage applied migrations 0001-0003 and passed concurrent same-key single-execution, cross-tenant denial and application recreation on a fresh volume. Direct image inspection shows both targets run as UID 10001, with `httpx2` absent from runtime and present only in the integration stage.
- Platform validation now passes 24 Terraform tests—bootstrap 4, dev 7, runtime 9, observability 3 and Artifact Registry 1—plus 65 platform script tests, 61/61 static controls, repository integrity, YAML, Compose and diff checks. The umbrella command is green with eval-result validation intentionally skipped; normal validation remains red until final-tree eval results are regenerated. Every cloud result remains explicit `DENY_APPLY`.
- The first strict source-commit harness run passed Docker browser, real PostgreSQL, backend functional, image, platform, integrity and dependency gates, then correctly failed because its canonical backend Ruff configuration found three explicit-zip violations and 20 scripts needing canonical formatting. `TASK-HARNESS-RUFF-FIXER-016` repaired that parity gap without weakening policy; exact Ruff, 19 evaluator/governance tests and the complete source-only platform gate now pass, while the full harness rerun remains pending.
- These are local results. The backend evaluator's 24/24 repeated races and timeout review are now corroborated by fresh real PostgreSQL. Governance passes 14 checks on 39 typed tasks, a 24-edge critical path, 42 findings, 71 evidence items and 31 risks. A role-separated Terraform review closes all four code findings locally; it is not live-cloud proof. The checked-in eval result intentionally remains stale until the final source commit, and a new final evaluator has not issued a release recommendation.
- Interactive visual inspection through the required in-app browser remains unavailable because that runtime exposed zero browser instances. Playwright proves behavior and transport, not manual visual/accessibility quality.

## Independent veto history and active gates

- `TASK-REQ-AUDIT-002` found missing live transport, unenforced CI, non-compliant eval evidence, missing protected reviewer gates and stale GCP truth; it returned a release veto and `DENY_APPLY`.
- `EVAL-INC-002` independently reran the prior tree and returned `FAIL`/`DENY_APPLY` because the documented frozen Python environment lacked PyYAML for `scripts/validate_platform.sh`. PyYAML/interpreter repairs exist locally but await current-tree CI and final evaluation.
- `CLOUD-CRITIQUE-002` returned `FAIL`/`DENY_APPLY` for absent eligibility/plan/cost evidence plus mutable WIF identity, implicit project adoption, missing isolation/region bindings and destructive routine IAM. Subsequent static repairs close those code-level findings, state-lock retention, tag-cleanup, fixed phase-identity and Terraform-owned channel gaps locally. `CLOUD-CRITIQUE-005` then found runtime-IAM, image-provenance, rollback-availability and foundation-drift verification gaps; all four code findings pass focused tests and role-separated review, while its external HIGH eligibility veto remains authoritative.
- The backend critic reproduced a false-conflict identical approval race and duplicate provider execution during identical starts. `TASK-BACKEND-FIXER-006` and `TASK-START-IDEMPOTENCY-FIXER-007` added exact replay plus cross-instance pre-provider ownership: PostgreSQL uses a deterministic transaction advisory lock and isolated SQLite uses `BEGIN IMMEDIATE`.
- A fresh evaluator closed both race findings locally after 24/24 repetitions. It then identified an unbounded PostgreSQL wait; `TASK-BACKEND-LOCK-TIMEOUT-FIXER-011` added a transaction-local five-second bound, and six independent focused cases proved immediate rollback and redacted 503 behavior. The hermetic real-PostgreSQL gate now passes; effectful adapters remain prohibited.
- Previous vetoes remain authoritative until their repairs pass focused critics and a new independent evaluator. No governance file may convert a producer result into final approval.

## GCP discovery and hard blocker

- ADC refresh succeeds with token output discarded. The configured `gcloud` project remains the unrelated and prohibited `meridian-hr-crm`; no region is configured and no organization is visible.
- Six billing accounts are visible and all report closed. No eligible billing target exists.
- Seventeen projects are now visible. One exact-name candidate exists: project ID `ai-native-content-agency-saas`, display name `AI-Native-Content-Agency-SaaS`, state `ACTIVE`, created `2026-07-19T04:27:27.280Z`.
- The candidate has billing disabled, no attached billing account, no visible parent, no required labels, no service accounts, no WIF pools and no buckets. Its creation provenance and authorized bootstrap/dev role are unknown. Default Google APIs are enabled, while Artifact Registry, Cloud Run and Cloud SQL APIs are not enabled.
- The candidate is not treated as authorized or Terraform-adopted. A product-like name is not adoption evidence, and one project cannot silently serve both the required bootstrap and dev isolation roles.
- No real GCP plan, plan JSON, cost estimate, apply, state migration or resource mutation occurred.

Resume cloud planning only after an accessible billing account reports `open=True`; the intended parent, distinct bootstrap/dev project IDs, candidate create/adopt decision and region are explicitly authorized; granular permission/policy/quota/cost checks pass; and the exact saved plan receives cloud critique, security review and an independent `ALLOW_DEV_APPLY`.

## Safety boundaries

- External providers remain deterministic sandbox adapters.
- Publication, Meta Ads activation, advertising spend and public ingress are unavailable or prohibited.
- No service-account key, destructive migration, project deletion, staging/production apply, force push or merge is authorized.
- The draft PR remains the collaboration surface; it is not evidence of release readiness.
