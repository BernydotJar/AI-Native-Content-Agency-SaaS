# Production Foundation Architecture

Updated: 2026-07-18
Status: Implementation in progress; cloud apply blocked by billing

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
| HTTP routes | `backend/control_plane/api.py` | Validation, identity, idempotency header, health/readiness and response status. |
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
- `approvals` enforces one decision per run;
- `audit_events` records commands and correlation IDs;
- `idempotency_records` stores the canonical request hash and original response.

Memory observations remain in the legacy `SQLiteMemory` subsystem and are not represented as durable multi-tenant product memory in V1. No vector table, outbox, Pub/Sub topic, or Cloud Task is added because no current behavior consumes it.

## Command flows

### Create mission

1. Identity dependency validates non-production tenant/principal headers.
2. `Idempotency-Key` and strict payload are validated.
3. Repository ensures identity rows and inserts the mission/audit/idempotency response in one transaction.
4. Compatible replay returns the original response; incompatible reuse is a conflict.

### Start run

1. The tenant-scoped mission is loaded.
2. A unique run ID is passed into the existing deterministic workflow.
3. CEO through Risk execute with sandbox tools; Publisher stops in `waiting_greenlight`.
4. Run, eight steps, artifacts, evidence, events, audit and idempotency response commit together.
5. The response is already `awaiting_greenlight`; polling reads persisted state.

If the process stops before this command commits, no partial workflow is claimed durable and the caller retries with the same idempotency key. This is command-boundary durability, not resumable mid-step execution.

### Decide Greenlight

1. The repository locks/versions the tenant-scoped run.
2. It verifies `awaiting_greenlight` and a passed Risk artifact.
3. It recomputes the current pre-Publisher artifact manifest.
4. Supplied hash and `greenlight.v1` must match stored/current values.
5. One optimistic transition and one unique approval are claimed.
6. Rejection blocks Publisher. Approval invokes only the sandbox packager and persists `publication_performed=false`.
7. Approval, Publisher state/output, audit and idempotency response commit together.

## Authentication and tenancy

Header-based identity exists only for development/test. Production settings reject it during validation. Cloud dev additionally requires Cloud Run IAM invocation; no `allUsers` binding is allowed. A future production identity provider must implement the centralized identity boundary and preserve repository tenant scoping.

## Deployment topology

The dev image builds the Vite SPA and Python service, mounts the SPA through FastAPI, and starts as a non-root user. Compose supplies PostgreSQL and a migration one-shot service. Cloud Run additionally runs the checked migration before Uvicorn under an advisory lock, so a new revision cannot become ready against an old schema; the deployment migration job repeats that idempotent operation as evidence.

The GCP dev design separates a foundation state (`environments/dev`) from routine runtime state (`environments/dev_runtime`). A separately authorized administrator owns services, runtime IAM, Artifact Registry, Cloud SQL, notification delivery and budget. Three exact-workflow/environment WIF identities split image build, resource-read-only runtime planning and runtime apply. Plan may read the two dev states and create/delete only a disposable runtime `.tflock`; apply may mutate only the runtime-state prefix and merely read foundation state. The apply identity receives an exact custom role for the required Cloud Run service/job operations, repository-scoped Artifact Registry read, read-only verification roles and `actAs` on one runtime account; it never receives `roles/run.admin` and cannot administer project IAM, APIs, SQL, registry policy, alerts, or budget. Runtime state owns only the IAM-private service, migration job and invoker binding. It intentionally excludes a public invoker, long-lived keys/passwords, VPC connector/NAT/load balancer, queue, Kubernetes and model serving.

The routine workflow binds an immutable image and saved runtime plan to the full tracked Git tree, commit, workflow, actor, reviewer and GitHub run. A short-lived exact-schema `ALLOW_DEV_APPLY` attestation is verified before GCP authentication. Apply is followed by authenticated/unauthenticated smoke evidence, resource/IAM/log verification, and a second no-change plan.

No real cloud project, saved plan or apply is claimed: discovery found no related project and zero open visible billing accounts. See `agent/reports/gcp-discovery-2026-07-18.md`.

## Architecture truth table

| Capability | Current target state |
|---|---|
| UI -> API transport | Real local HTTP once application/container gates pass. |
| Run/approval persistence | SQL-backed at command boundaries. |
| External providers | Deterministic sandbox only. |
| Publication/ad spend | Unavailable. |
| Mid-step durable execution | Not implemented or claimed. |
| Multi-tenant identity | Tenant isolation is implemented; production end-user auth is not. |
| GCP deployment | Foundation/runtime roots and phase identities are defined and locally validated only; no real plan/apply until billing and exact attestation gates pass. |
| Staging/production | Definition and human gates only; never applied in this iteration. |
