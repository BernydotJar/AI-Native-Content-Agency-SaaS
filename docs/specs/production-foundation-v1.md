# Production Foundation V1

Status: In progress
Version: 1.0
Date: 2026-07-18
Owner: Orchestrator
Compatibility policy: additive changes may extend the `v1` API; removals, renamed fields, enum narrowing, or semantic changes require a new API/schema version.

## Purpose

This iteration replaces the disconnected browser and Python run state with one persisted control plane. It also creates a reproducible, least-privilege path to a private GCP development environment. The product remains a sandbox: approval may create a local campaign package, but it never publishes content, creates an advertising campaign, or spends money.

## Baseline

At the start of this iteration the React application ran a timer-based state machine in the browser. `AgencyOrchestrator` ran a second synchronous state machine in Python and stored runs only in an in-process dictionary. SQLite persisted memory observations, not missions, runs, steps, artifacts, approvals, or audit events. There was no HTTP API, authentication boundary, PostgreSQL adapter, migration system, container, CI workflow, or Terraform.

The baseline gates passed before production-foundation changes: 28 frontend tests, 16 Python tests, frontend lint, frontend build, and the approved sandbox CLI demo.

## Included architecture

```text
React/Vite UI
  -> versioned HTTP API (polling for V1)
FastAPI control plane
  -> application services
  -> existing eight-station sandbox workflow
  -> repository and identity ports
SQL repository adapter
  -> SQLite for isolated local/test execution
  -> PostgreSQL for container and cloud runtime
```

Execution is inline and bounded in V1 because the deterministic workflow completes before the start-run response. Durable state is committed at command boundaries. This iteration does not claim resumable mid-step execution. A queue is deferred until real workloads demonstrate a need for leases, retries, cancellation, and dead-letter handling.

## Contract rules

- All API resources use schema identifier `v1` and UTC RFC 3339 timestamps.
- IDs are opaque, stable strings scoped by resource type.
- Every mutable command requires `Idempotency-Key`.
- A repeated tenant, operation, key, and identical canonical payload returns the original response.
- Reusing that tuple with a different payload returns `409 idempotency_conflict`.
- Errors use one structured envelope with a machine code, message, correlation ID, and optional field details.
- The OpenAPI document is checked in and frontend types are generated or drift-checked from it.
- Polling is the V1 progress transport. Clients may refresh and reconstruct the run exclusively from persisted backend state.

## Tenant and identity boundary

Authorization is centralized and deny-by-default. Every application resource is tenant scoped. Development mode may accept explicit development tenant and principal headers only when the environment is not production. Production configuration must fail during startup if development authentication is selected. Cloud dev remains private at the Cloud Run IAM boundary; development headers are identifiers, not credentials.

## Greenlight policy

Policy version: `greenlight.v1`.

Before any approval, the backend computes a SHA-256 manifest over deterministic JSON containing every pre-Publisher artifact identifier, kind, creator, and payload plus the policy version. The approval command includes tenant, run, reviewer, decision, optional note, the exact manifest hash, policy version, and idempotency key. It is valid only when:

1. the run belongs to the requesting tenant;
2. Risk completed with `passed=true`;
3. the run is awaiting Greenlight;
4. the reviewer is non-empty;
5. the supplied policy version is current;
6. the supplied hash equals the freshly computed manifest;
7. no incompatible approval or replay exists.

Approval produces only a sandbox package with `publication_performed=false`. Rejection blocks Publisher. A changed artifact invalidates the old manifest. Database uniqueness/version constraints serialize concurrent decisions.

## Functional requirements

| ID | Requirement | Acceptance evidence |
|---|---|---|
| APP-001 | Create a tenant-scoped mission through `POST /api/v1/missions`. | OpenAPI plus positive, malformed, missing-identity, and idempotency tests. |
| APP-002 | Persist identity, mission, run, steps, artifacts, evidence, approvals, idempotency, and audit state through repository ports. | SQLite and PostgreSQL-capable adapter, migrations, repository tests, restart test. |
| APP-003 | Start the existing eight-station workflow through the API. | Persisted run reaches `awaiting_greenlight`; seven pre-gate steps and Publisher wait state are queryable. |
| APP-004 | Query run, step, artifact, tool-evidence, audit/progress state. | Same data remains available from a new application instance; wrong-tenant reads fail. |
| APP-005 | Hold Publisher behind Risk and Greenlight. | Negative transition tests and tool evidence prove zero external side effects. |
| APP-006 | Persist approval and rejection decisions in the backend. | Decision, reviewer, note, timestamp, tenant, audit event, and transition tests. |
| APP-007 | Bind approval to `greenlight.v1` and the canonical manifest hash. | Stale hash, wrong policy, changed artifact, and Risk-not-passed tests. |
| APP-008 | Make commands durably idempotent and reject incompatible replay. | Database constraint plus compatible replay, conflict, and concurrent-decision tests. |
| APP-009 | Expose persisted progress using polling. | Refresh/reconnect test reconstructs all step states without browser timers. |
| APP-010 | Use a typed frontend API client for the integrated mode. | UI integration tests cover create, start, refresh, artifacts/evidence, approve/reject, and errors. |
| APP-011 | Isolate the legacy browser simulation. | Integrated mode is default outside tests; demo mode is explicitly labeled and has separate state/IDs. |
| APP-012 | Version tenant, principal, mission, run, step, agent, artifact, evidence, approval, audit, progress, and error contracts. | OpenAPI/schema drift gate and checked frontend contract. |
| APP-013 | Keep V1 execution proportional and truthful. | ADR documents inline boundaries, timeout/failure behavior, and no mid-step durability claim. |
| APP-014 | Emit structured telemetry with correlation, tenant, run, step/tool, latency, result, retry, decision, and side-effect flags when applicable. | Log capture tests; secret and log-injection tests. |
| APP-015 | Keep domain/provider dependencies neutral and sandbox adapters explicit. | Boundary/configuration tests and `external_side_effect=false` evidence. |

## Security and privacy requirements

| ID | Requirement | Acceptance evidence |
|---|---|---|
| SEC-001 | Explicit tenant/principal and centralized deny-by-default authorization. | Missing, invalid, and cross-tenant tests for reads and commands. |
| SEC-002 | Development identity cannot activate in production. | Production startup/configuration test fails closed. |
| SEC-003 | Constrained CORS, request-size limit, validation, security headers, and safe names/paths. | Oversized, malformed, traversal-like, and origin tests. |
| SEC-004 | Typed configuration and redacted structured logs. | Configuration and log-capture tests; no secrets or full sensitive prompts logged. |
| SEC-005 | Mandatory dependency, secret, personal-path, and repository-integrity scans. | Local eval and CI outputs. |
| SEC-006 | Versioned threat model and adversarial evals. | Cross-tenant, replay, injection-as-data, log injection, malformed input, and dev-auth tests. |
| SEC-007 | External effects disabled by default. | Sandbox adapter and API response evidence; publication and spend are absent. |

## Delivery requirements

| ID | Requirement | Acceptance evidence |
|---|---|---|
| DLV-001 | One documented integrated local startup and smoke flow. | Executed commands start web/API/database, migrate, smoke, and shut down cleanly. |
| DLV-002 | Unit, repository, API, contract, integration, security, reliability, and restart tests. | Required test pass rate is 100%. |
| DLV-003 | Reproducible non-root containers and Compose. | Deterministic installs, health checks, migration ordering, build and smoke pass. |
| DLV-004 | Mandatory CI for application, migration, schema, container, security, Terraform, and whitespace gates. | GitHub Actions definitions and local equivalent gates pass. |
| DLV-005 | Validatable Terraform for bootstrap and isolated environments. | `fmt`, `init`, `validate`, provider locks, variables/outputs, and no embedded credentials. |
| DLV-006 | Executable eval harness with structured results. | Deterministic, functional, security, reliability, and drift results are recorded. |
| DLV-007 | Operational documentation matches executed reality. | Setup, API, migration, deployment, rollback, incident, sandbox, and limitations docs. |
| DLV-008 | Deploy workflow uses distinct build/read-only-plan/apply GitHub OIDC/WIF identities and environment gates, never service-account keys. | Workflow inspection and Terraform bindings scoped to exact owner/repository/ref/direct workflow/phase environment. |

## GCP requirements

| ID | Requirement | Acceptance evidence |
|---|---|---|
| GCP-000 | Terraform is the source of truth; only bootstrap and dev may be applied. | Execution-mode record; staging/prod definitions cannot be selected accidentally. |
| GCP-001 | Complete non-mutating account, ADC, hierarchy, billing, project, policy, quota, region, and existing-resource discovery. | Masked discovery report with ambiguities. |
| GCP-002 | Verify granular project, billing, API, IAM, WIF, registry, Run, SQL, secrets, state, storage, and budget permissions. | Permission preflight evidence; broad role names alone are insufficient. |
| GCP-003 | Isolate bootstrap/dev projects and define, but do not apply, staging/prod. | Variable non-personal project IDs and environment guards. |
| GCP-004 | Bootstrap versioned uniform-access remote state and GitHub WIF without keys. | Saved plan/apply, state migration, backend proof, no state in Git. |
| GCP-005 | Provision only dev resources mapped to an implemented behavior and cost. | Requirement-to-resource map, saved plan, and cost envelope. |
| GCP-006 | Produce and inspect saved plan plus JSON after fmt/init/validate. | No unauthorized destroy/replace, public access, broad IAM, keys, secrets, wrong region, or stage/prod resources. |
| GCP-007 | Cloud critique, security review, and independent evaluator all allow the exact plan. | Zero open CRITICAL/HIGH and `ALLOW_DEV_APPLY`. |
| GCP-008 | Apply only the evaluated saved dev plan. | Plan hash/source hash and apply record. |
| GCP-009 | Verify health, database/migrations, authorized/denied access, logs, labels, budget, smoke, and integration behavior. | Post-apply evidence report. |
| GCP-010 | A second plan has no unexpected changes. | Saved no-change plan or repaired/re-evaluated drift. |
| GCP-011 | Record non-sensitive resource and cost evidence. | Masked billing, project IDs, region, results, ongoing cost, rollback; no secrets. |
| GCP-012 | Preserve human gates for staging, production, public access, spend, billing, destruction, publication, and ads. | Environment/workflow/Terraform guards. |
| GCP-013 | If external authorization blocks a phase, finish independent work and record one exact resume condition. | Blocker evidence and no unsupported completion claim. |

## Governance requirements

| ID | Requirement | Acceptance evidence |
|---|---|---|
| GOV-001 | This specification and its traceability remain versioned. | File and matrix review. |
| GOV-002 | Persist state, ledger, graph, decisions, evidence, evals, critiques, risks, issues, and reports. | `agent/` artifacts validate and match the worktree. |
| GOV-003 | Subagents use explicit ownership contracts and writer locks. | Task ledger and agent reports. |
| GOV-004 | Enforce Producer -> Tests -> Critique -> Fixer -> Independent Evaluator -> Apply Gate -> Post-Apply verification. | Gate evidence per increment. |
| GOV-005 | Independent critique/evaluator may veto. | No apply or release with missing evidence or open CRITICAL/HIGH. |
| GOV-006 | Record the nine required architecture decisions. | ADR index and files. |
| GOV-007 | Use focused commits, tracking issue, draft PR, and never merge in this iteration. | Git and GitHub evidence. |
| GOV-008 | Claims remain truthful about sandbox, durability, tenancy, cloud, and deployment. | Documentation and UI audit. |

## Non-functional requirements

- API requests have a bounded body size and correlation ID.
- Database mutations use explicit transactions, foreign keys, and uniqueness/version constraints.
- The service starts only after configuration validation and reports dependency readiness separately from liveness.
- Containers run as a non-root user and install locked dependencies.
- Secrets, state files, saved plans, credentials, tokens, and database passwords are excluded from Git.
- Logs exclude credentials, authorization headers, full prompts, binary content, and unnecessary PII.
- Cloud Run dev ingress is private unless a later human gate explicitly changes it.
- Cloud SQL uses the smallest justified development footprint and no destructive production migration is in scope.

## Deferred with reason

- SSE/WebSocket: polling is enough for synchronous V1 runs.
- Cloud Tasks/Pub/Sub/outbox: no asynchronous behavior currently consumes them.
- pgvector: no retrieval behavior needs vectors.
- Separate web service, load balancer, NAT, GKE, Kubernetes, service mesh, GPUs, vLLM, or llm-d: no demonstrated load or behavior justifies them.
- Staging/production apply, real provider activation, publication, and advertising spend: remain human-gated and out of scope.

## Definition of Done

The iteration is complete only when every included requirement has direct, reproducible PASS evidence; the UI/API/database flow survives a process restart; all required local, container, migration, contract, security, reliability, and Terraform gates pass; the exact dev plan has independent `ALLOW_DEV_APPLY`; post-apply smoke and no-drift checks pass; issue, draft PR, decisions, evidence, and documentation are current; and no CRITICAL or HIGH finding remains open. If a non-automatable GCP choice or credential blocks apply, completion is not claimed and the blocker records the exact resume condition.
