# Production Foundation Architecture

Updated: 2026-07-19
Status: Local repair and focused code critics complete; final eval/CI/release gates pending; cloud apply denied

## Runtime topology

```text
Integrated React UI (default)
  |  same-origin JSON/HTTP, v1 contracts, polling
  v
FastAPI control plane
  |-- centralized development identity / authorization
  |-- application services and idempotency policy
  |-- canonical Greenlight manifest policy
  |-- existing eight-agent deterministic workflow
  |-- structured errors, audit, correlation and security middleware
  v
SQLAlchemy repository
  |-- SQLite: isolated local/test use
  `-- PostgreSQL: Compose and cloud runtime

Explicit legacy demo mode
  `-- VITE_RUNTIME_MODE=demo -> browser-only timers and TypeScript fixtures
```

The integrated UI is authoritative only through API responses. It may retain one opaque run ID in browser storage to reconnect, but it reconstructs mission progress, artifacts, evidence, events, audit and approval from the backend. It never advances an integrated agent with a browser timer.

## Code boundaries

| Boundary | Location | Responsibility |
|---|---|---|
| API contracts | `backend/control_plane/contracts.py` and `backend/openapi.json` | Canonical versioned request/response/error models and enums. |
| HTTP routes | `backend/control_plane/api.py` | Validation, versioned identity response, idempotency header, health/readiness and response status. |
| Application policy | `backend/control_plane/service.py` | Command orchestration, Greenlight, audit and transaction boundaries. |
| Repository port | `backend/control_plane/ports.py` | Provider-neutral application-facing persistence protocol and records. |
| SQL adapter | `backend/control_plane/repository.py` | Tenant-scoped SQLAlchemy persistence and optimistic/unique constraints. |
| Relational schema | `backend/control_plane/storage.py`, `backend/migrations/` | Durable tables, foreign keys, checks and migrations. |
| Manifest integrity | `backend/control_plane/manifest.py` | Canonical deterministic JSON and SHA-256 binding. |
| Existing workflow | `backend/agency_runtime/` | Eight deterministic sandbox stations and provider ports. |
| Typed web client | `src/api/` | OpenAPI-generated response/request types, identity/correlation/idempotency headers, structured errors and drift checks. |
| Integrated view | `src/control-plane/IntegratedApp.tsx` | API-owned run rendering, refresh and exact-manifest decisions. |
| Legacy demo | `src/control-plane/DemoApp.tsx` | Explicitly isolated local showcase; never a production claim. |

## Data model in use

The control plane uses only behaviorally necessary tables:

- `tenants` and `principals` establish explicit identity scope;
- `missions` stores the submitted brief;
- `runs` stores status, manifest, policy and optimistic version;
- `run_steps`, `artifacts`, `tool_evidence`, and `run_events` reconstruct progress and outputs;
- `approvals` enforces one decision per run plus tenant/idempotency-key uniqueness and retains direct command provenance;
- `audit_events` records commands and correlation IDs;
- `idempotency_records` stores the canonical request hash and original response.

Memory observations remain in the legacy `SQLiteMemory` subsystem and are not represented as durable multi-tenant product memory in V1. No vector table, outbox, Pub/Sub topic, or Cloud Task is added because no current behavior consumes it.

## Command flows

### Create mission

1. Identity dependency validates non-production tenant/principal headers.
2. `Idempotency-Key` and strict payload are validated.
3. Before the first repository read, the command acquires a tenant/key transaction lock: PostgreSQL uses a transaction-scoped advisory lock and isolated SQLite local/test databases use `BEGIN IMMEDIATE`.
4. After acquiring the lock, compatible replay returns the original response and incompatible reuse is a conflict.
5. Repository ensures identity rows and inserts the mission/audit/idempotency response in the same transaction that holds the lock.

### Start run

1. The command acquires its tenant/key transaction lock and rechecks durable replay before loading the mission or invoking a provider.
2. The tenant-scoped mission is loaded.
3. A unique run ID is passed into the existing deterministic workflow.
4. CEO through Risk execute with sandbox tools; Publisher stops in `waiting_greenlight`.
5. Run, eight steps, artifacts, evidence, events, audit and idempotency response commit together, releasing the transaction lock.
6. The response is already `awaiting_greenlight`; polling reads persisted state.

If the process stops before this command commits, no partial workflow is claimed durable and the caller retries with the same idempotency key. This is command-boundary durability, not resumable mid-step execution.

Concurrent identical `run.start` calls contend on the cross-instance database lock before provider work. The winner executes and commits once; the waiter then reads and returns the winner's exact durable response. Deterministic tests require one run, one command/audit record, seven tool-evidence rows, and exactly seven sandbox telemetry records for two simultaneous callers. The lock is held until commit or rollback, so provider exceptions release it without claiming a response. PostgreSQL sets a transaction-local five-second `lock_timeout`; a stalled waiter rolls back and receives the redacted structured database-unavailable response instead of blocking indefinitely or leaking the timeout into a pooled connection. Effectful adapters remain outside this iteration and require a separate provider-specific safety review even though duplicate same-key execution is now prevented.

### Decide Greenlight

1. The command acquires its tenant/key transaction lock and rechecks durable replay.
2. The repository locks/versions the tenant-scoped run.
3. It verifies `awaiting_greenlight` and a passed Risk artifact.
4. It recomputes the current pre-Publisher artifact manifest.
5. Supplied hash and `greenlight.v1` must match stored/current values.
6. One optimistic transition and one unique approval are claimed.
7. Rejection blocks Publisher. Approval invokes only the sandbox packager and persists `publication_performed=false`.
8. Approval, its direct idempotency key, Publisher state/output, audit payload and generic replay response commit together.

Migration `0003_approval_idempotency` upgrades legacy decisions by linking each approval to exactly one durable `run.approval` command record. It fails closed instead of inventing a key when linkage is missing or ambiguous.

## Authentication and tenancy

Header-based identity exists only for development/test. Production settings reject it during validation. Cloud dev additionally requires Cloud Run IAM invocation; no `allUsers` binding is allowed. A future production identity provider must implement the centralized identity boundary and preserve repository tenant scoping.

## Deployment topology

The deployable dev image builds the Vite SPA and Python service, mounts the SPA through FastAPI, and starts as UID 10001. Compose supplies PostgreSQL and a migration one-shot service. A separate opt-in `postgres-integration` image stage adds hash-locked CI dependencies without becoming the default/final runtime target; direct image inspection proves `httpx2` is absent from runtime and present only in the test runner. Cloud Run additionally runs the checked migration before Uvicorn under an advisory lock, so a new revision cannot become ready against an old schema; the deployment migration job repeats that idempotent operation as evidence.

The GCP dev design separates bootstrap, foundation (`environments/dev`) and routine runtime (`environments/dev_runtime`) state. Bootstrap and dev project IDs must differ. Each project is Terraform-managed: `CREATE_NEW` creates it, while `ADOPT_EXISTING` requires versioned evidence, an exact acknowledgement and a declarative import. Required project labels cannot be overridden.

A separately authorized administrator owns services, runtime IAM, Artifact Registry, Cloud SQL, notification delivery and budget. Three exact-workflow/environment WIF identities split image build, resource-read-only runtime planning and runtime apply; the foundation authorization gate accepts only the fixed phase account names in the reviewed bootstrap project. Conditions bind immutable numeric GitHub owner/repository IDs as well as exact names, `main`, direct workflow and phase environment. Plan may read the two dev states and create/delete only a disposable runtime `.tflock`; apply may mutate only the runtime-state prefix and merely read foundation state. The state bucket uses versioning and seven-day soft deletion but deliberately has no retention policy that would trap lock objects.

The apply identity receives an exact 16-permission custom role for non-destructive Cloud Run service/job operations, repository-scoped Artifact Registry read, a separate custom role containing only `artifactregistry.tags.create`/`tags.update`, read-only verification roles and `actAs` on one runtime account. Service/job/artifact deletion, artifact upload and `run.services.setIamPolicy` are absent. The separately reviewed foundation grants project-level `roles/run.servicesInvoker`—not the broader job-capable `roles/run.invoker`—to the deploy identity in the dedicated dev project so it can verify a newly created private service without routine IAM mutation. Runtime state owns no service IAM member. Post-apply rejects public/unexpected bindings; requires the runtime account's exact four roles; matches application, migration and proxy images by container name; and verifies all WIF, impersonation, state-prefix, repository and custom-role authority. Runtime also binds foundation project, bootstrap project, region, immutable repository identity and project/channel provenance digests. It intentionally excludes a public invoker, long-lived keys/passwords, VPC connector/NAT/load balancer, queue, Kubernetes and model serving.

Monitoring email channels are Terraform resources, not manually created prerequisites. `CREATE_NEW` and `ADOPT_EXISTING` share versioned, sensitive provenance; adoption uses an exact import address. A narrowly targeted, independently approved first plan creates/imports the project, required APIs and channel, after which a human completes the provider email verification. The full foundation plan requires `VERIFIED` status plus reviewed evidence, and all runtime/cost-bearing resources depend on that gate. Artifact Registry retains the 20 most recent versions and deletes tagged or untagged versions older than seven days, except the immediate predecessor protected by the moving `rollback-current` KEEP tag. Deployment and rollback plans still use the digest, never that mutable tag.

The routine workflow binds an immutable foundation-repository image digest, the current deployed predecessor and a saved runtime plan to the full tracked Git tree, commit, workflow, actor, reviewer and GitHub run. A short-lived exact-schema `ALLOW_DEV_APPLY` attestation is verified before GCP authentication. After authentication and granular permission preflight—but before apply—the workflow rechecks the predecessor and moves the one retention tag. Apply is followed by authenticated/unauthenticated smoke evidence, resource/IAM/log/foundation-drift verification, and a second no-change plan. Main protection and all three phase environments are configured fail-closed, but the only collaborator cannot self-review, the workflow is not yet on `main`, and required Actions variables remain absent; no deploy dispatch is currently possible.

No authorized cloud target, saved plan or apply is claimed. Discovery now sees exact-name candidate `ai-native-content-agency-saas`, but it is billing-disabled, unlabeled, outside Terraform state and has unknown provenance/role. All six visible billing accounts remain closed, no region/parent is authorized, and the candidate is not treated as adopted. See `agent/reports/gcp-discovery-2026-07-18.md`.

## Live transport evidence

`e2e/control-plane.e2e.ts` drives the served SPA through approval and rejection without request interception. `e2e/restart-persistence.e2e.ts` creates a third run, restarts only the API container, waits for readiness and compares the exact PostgreSQL-backed response after reload. A fresh owned-volume execution passed all three scenarios and removed its volume. The separate real-PostgreSQL gate also proved same-key contention, cross-tenant denial and application recreation. This closes transport/restart behavior locally; it does not replace exact-tree CI or manual visual/accessibility QA.

## Architecture truth table

| Capability | Current target state |
|---|---|
| UI -> API transport | Real local SPA/FastAPI/PostgreSQL behavior with fresh 3/3 Playwright evidence; exact-tree CI pending. |
| Run/approval persistence | SQL-backed at command boundaries. |
| External providers | Deterministic sandbox only. |
| Publication/ad spend | Unavailable. |
| Mid-step durable execution | Not implemented or claimed. |
| Multi-tenant identity | Tenant isolation is implemented; production end-user auth is not. |
| GCP deployment | Bootstrap/foundation/runtime roots and phase identities are locally validated only; candidate adoption is undecided and no real plan/apply exists. |
| Staging/production | Definition and human gates only; never applied in this iteration. |
