# Decision Log

## DEC-001 — FastAPI is the control plane

- Date: 2026-07-18
- Status: Accepted
- Context: The browser and Python runtimes have incompatible process-local state.
- Alternatives: browser-only state; framework-specific agent server; FastAPI.
- Chosen option: FastAPI with versioned OpenAPI contracts and application-service boundaries.
- Trade-off: Adds a service/dependency boundary but removes duplicate authority.
- Review trigger: A second protocol or non-HTTP consumer demonstrates a need.

## DEC-002 — PostgreSQL is runtime source of truth

- Date: 2026-07-18
- Status: Accepted
- Context: Runs and approvals must survive process restart and support transactional idempotency.
- Alternatives: in-memory state; SQLite everywhere; PostgreSQL runtime with SQLite isolated tests.
- Chosen option: Repository ports with SQLAlchemy; PostgreSQL for container/cloud runtime and SQLite for isolated local/test use.
- Trade-off: Requires migrations and database operations, but provides enforceable constraints and portability.
- Review trigger: Proven scale or compliance requirements exceed a single relational primary.

## DEC-003 — Provider-neutral ports and sandbox defaults

- Date: 2026-07-18
- Status: Accepted
- Chosen option: The domain and application services depend on repository/tool/identity interfaces; current external tools remain explicit deterministic sandbox adapters.
- Trade-off: More boundary code now, lower provider lock-in and safer activation later.

## DEC-004 — Polling instead of SSE in V1

- Date: 2026-07-18
- Status: Accepted
- Context: The deterministic inline workflow finishes before the command response.
- Chosen option: Conditional polling and refresh from persisted state.
- Alternatives: SSE; WebSocket.
- Trade-off: Polling adds small request overhead but avoids a misleading streaming layer with no asynchronous producer.
- Review trigger: Runs become asynchronous or progress latency must be below the polling interval.

## DEC-005 — Inline execution before a queue

- Date: 2026-07-18
- Status: Accepted
- Chosen option: Execute the bounded sandbox workflow inline and commit durable state at command boundaries. Do not claim resumable mid-step execution.
- Alternatives: local worker; Cloud Tasks; Pub/Sub; durable pre-provider idempotency ownership.
- Trade-off: Simpler and testable now; simultaneous identical starts may repeat effect-free sandbox work and emit one rolled-back run ID. Any effectful or long-running provider requires cross-instance key ownership/leases, retries, cancellation, receipts and dead-letter semantics before activation.
- Review trigger: A run can exceed the request timeout or has a real retryable external operation.

## DEC-006 — Canonical approval binding

- Date: 2026-07-18
- Status: Accepted
- Chosen option: SHA-256 over deterministic JSON of all pre-Publisher artifacts plus policy `greenlight.v1`.
- Trade-off: Any legitimate artifact change requires a new Risk pass and decision, intentionally favoring integrity over convenience.

## DEC-007 — Tenant model and development identity

- Date: 2026-07-18
- Status: Accepted for V1
- Chosen option: Every resource carries a tenant; centralized auth supplies tenant/principal. Explicit header-based development identity is permitted only in non-production configuration, which fails closed in production.
- Trade-off: Cloud dev additionally relies on private Cloud Run IAM. A production identity provider remains a later adapter.
- Review trigger: First external tenant or production authentication design.

## DEC-008 — GCP managed services through Terraform

- Date: 2026-07-18
- Status: Accepted
- Chosen option: Separate bootstrap and dev configurations; remote state, WIF, Artifact Registry, private Cloud Run, Cloud SQL, secrets containers and monitoring only when used. Staging/prod are definition-only.
- Trade-off: Managed services add monthly cost but reduce initial operational burden.
- Review trigger: Measured workload, regulatory isolation, or cost justifies a different service.

## DEC-009 — No Kubernetes, vLLM, queue, or vector database yet

- Date: 2026-07-18
- Status: Accepted
- Chosen option: Defer GKE/OpenShift, service mesh, GPUs/vLLM/llm-d, Pub/Sub/Cloud Tasks, Redis, and pgvector until a demonstrated behavior requires them.
- Trade-off: Avoids premature distributed-systems cost; future scale work remains explicit.

## DEC-010 — Split foundation and runtime Terraform state

- Date: 2026-07-18
- Status: Accepted
- Context: Routine planning and deployment must not gain authority to mutate bootstrap identity, registry or durable state infrastructure.
- Chosen option: Keep foundation and runtime state in separate prefixes and split plan/apply identities. Plan reads durable state and may create/delete only disposable runtime lock objects; apply mutates only the runtime prefix.
- Trade-off: Adds bootstrap sequencing and explicit output handoff, but makes routine privileges materially smaller and auditable.

## DEC-011 — Exact runtime deploy role and repository-scoped image read

- Date: 2026-07-18
- Status: Superseded by DEC-019
- Context: `roles/run.admin` and project-wide image read exceed the permissions needed by the deployment workflow.
- Chosen option at the time: Use one custom role containing the then-reviewed Cloud Run, location, operation and project-read permissions. Grant Artifact Registry Reader only on the intended repository.
- Trade-off: Permission changes require deliberate role revision and preflight updates; accidental authority expansion is rejected.

## DEC-012 — Database-enforced tenant ownership chains

- Date: 2026-07-18
- Status: Accepted
- Context: Single-column foreign keys proved record existence but could not prove parent and child belonged to the same tenant.
- Chosen option: Add composite tenant/resource uniqueness and foreign keys in migration 0002 while retaining service-layer authorization checks.
- Trade-off: Inserts and migrations carry more keys, but cross-tenant corruption fails at the database boundary.

## DEC-013 — Resolve observable delivery channels by governed identity

- Date: 2026-07-18
- Status: Accepted
- Context: Arbitrary notification channel IDs could silently target disabled or unverified destinations.
- Chosen option: Terraform owns every channel through `CREATE_NEW` or exact-name `ADOPT_EXISTING` import. A narrowly targeted saved plan creates/imports the project, APIs and channel; after human email verification, a full saved plan requires enabled/`VERIFIED` status plus reviewed evidence before alert, budget or any costly/runtime foundation resource can proceed.
- Trade-off: Setup requires two independently reviewed saved plans and a human verification response, but no resource is created manually and misdelivery fails closed before spend-bearing infrastructure.

## DEC-014 — Explicit database lifecycle and sequential polling

- Date: 2026-07-18
- Status: Accepted
- Context: Engine cleanup depended on successful test completion, and interval polling could overlap a terminal response.
- Chosen option: Dispose engines at application, OpenAPI and fixture lifecycles. Poll with one recursively scheduled timeout that stops on cancellation or a terminal response.
- Trade-off: Slightly more lifecycle code prevents leaked resources and overlapping requests.

## DEC-015 — Python 3.10 minimum with current test-client and pytest lines

- Date: 2026-07-18
- Status: Accepted
- Context: Supporting Python 3.9 required a deprecated compatibility path, while pytest 8.4.2 was affected by PYSEC-2026-1845.
- Chosen option: Set `requires-python >=3.10`, use `httpx2>=2.7,<3`, require pytest `>=9.0.3,<10`, and resolve the exact CI lock to pytest 9.1.1.
- Trade-off: Python 3.9 is no longer supported; runtime, CI and strict warning behavior are simpler and auditable.

## DEC-016 — Approvals directly retain their command identity

- Date: 2026-07-19
- Status: Accepted
- Context: The approval command key was durable only in the generic idempotency table, so an approval row and its audit event did not directly identify the command that produced the decision.
- Alternatives: infer the key by joining response payloads; add an optional audit-only field; persist the key on the approval and audit payload.
- Chosen option: Migration `0003_approval_idempotency` backfills a directly required `approvals.idempotency_key`, adds tenant/key uniqueness, returns it in the versioned approval contract, and records it in the approval audit payload. An existing approval without one safe durable match fails migration closed.
- Trade-off: The migration performs a provenance check and can stop on ambiguous legacy data; this is preferred to inventing command identity.
- Consequences: Approval evidence is self-contained and incompatible replay remains governed by the generic canonical request record.
- Review trigger: A future command ledger replaces the current idempotency table.
- Owner: Backend Reliability Producer

## DEC-017 — Live transport is a release gate

- Date: 2026-07-19
- Status: Accepted
- Context: Component tests that stub `fetch` and HTTP scripts that bypass the UI cannot prove the required browser-to-control-plane transport or persisted UI reconstruction.
- Alternatives: accept unit mocks; use an API-only smoke; run browser automation against the real Compose stack.
- Chosen option: Require Playwright against the served SPA, FastAPI and PostgreSQL without route interception. The gate covers create/start, persisted artifacts/evidence, exact-manifest approve/reject, reload and explicit refresh.
- Trade-off: CI installs Chromium and the gate takes longer, but it closes the central architectural boundary with observable behavior.
- Consequences: Unit mocks remain useful for faults and rendering but cannot satisfy APP-009, APP-010 or DLV-001 alone.
- Review trigger: The frontend or transport topology changes.
- Owner: Live Transport and CI Producer

## DEC-018 — Cloud identity and existing-project adoption require immutable provenance

- Date: 2026-07-19
- Status: Accepted
- Context: GitHub owner/repository names are mutable, and treating `create_project=false` as adoption left a target project outside Terraform management with no provenance.
- Alternatives: trust mutable names and data sources; require only a human note; bind immutable IDs and declarative imports to versioned evidence.
- Chosen option: WIF checks numeric `repository_owner_id` and `repository_id` in addition to exact names/ref/workflow/environment. Every bootstrap/dev project is a managed `google_project`; `ADOPT_EXISTING` requires `gcp-project-adoption.v1` evidence, acknowledgement and a Terraform import block.
- Trade-off: Bootstrap inputs and review are stricter and renamed/transferred repositories require an intentional identity update.
- Consequences: The discovered `ai-native-content-agency-saas` project remains unadopted until its provenance and intended role are explicitly authorized.
- Review trigger: GitHub changes OIDC claim semantics or GCP introduces a stronger workload identity binding.
- Owner: Terraform Safety Fixer

## DEC-019 — Routine runtime IAM excludes destructive lifecycle operations

- Date: 2026-07-19
- Status: Accepted
- Context: A routine deploy role containing `run.services.delete` and `run.jobs.delete` could turn a source rename or compromised workflow into destructive runtime loss.
- Alternatives: retain all 19 permissions; move all IAM mutation to the foundation; split destructive lifecycle from routine apply.
- Chosen option: Use an exact 16-permission routine role without service/job deletion or `run.services.setIamPolicy`. The separately reviewed foundation grants project-level `roles/run.servicesInvoker` to the deploy identity within the dedicated dev project; runtime state owns no service IAM member. Destruction requires a separate human-authorized identity and plan.
- Trade-off: A routine plan that needs deletion or service-IAM mutation fails instead of reconciling automatically. Project-level service invocation is broader than one service but does not grant job execution, is isolated to dev and lets a newly created private service be smoke-tested without routine IAM mutation; post-apply rejects unexpected service bindings.
- Consequences: Preflight, mock tests, platform checks and post-apply expectations use the same 16-permission set and exact project-role set.
- Review trigger: Terraform can move the service IAM binding to a non-circular foundation lifecycle or Cloud Run changes required permissions.
- Owner: Terraform Safety Fixer

## DEC-020 — Foundation identity is cryptographically bound into runtime planning

- Date: 2026-07-19
- Status: Accepted
- Context: A runtime plan could otherwise consume state from the right project but the wrong region, repository identity, project-adoption decision or notification recipient set.
- Alternatives: document matching inputs; compare only project ID; require exact foundation outputs and provenance digests.
- Chosen option: The runtime root checks bootstrap/dev separation, region, immutable GitHub IDs, project-provenance SHA-256 and notification-channel-provenance SHA-256 against foundation outputs. The foundation also rejects phase service-account emails that are not the fixed build/plan/apply accounts in the exact bootstrap project.
- Trade-off: Legitimate foundation changes invalidate runtime inputs and require a new reviewed plan.
- Consequences: Workflow variables carry explicit non-secret digests and IDs; mismatches fail before apply.
- Review trigger: Foundation/runtime state boundaries are redesigned.
- Owner: Terraform Safety Fixer

## DEC-021 — Recoverable state and bounded digest-based image retention

- Date: 2026-07-19
- Status: Accepted
- Context: A bucket retention policy also retains `.tflock` objects and can prevent normal lock release. Immutable unique image tags prevent cleanup from deleting old tagged builds, causing unbounded registry storage.
- Alternatives: retain all state objects for a fixed day; retain every uniquely tagged image; use recoverable versioning/soft deletion and make tags disposable while deploying only by digest.
- Chosen option: Keep state versioning and seven-day soft deletion but no bucket retention policy. Artifact Registry deletes any tagged or untagged version older than seven days after a KEEP rule preserves the 20 most recent; runtime accepts only digest-qualified images.
- Trade-off: State recovery depends on versioning/soft-delete rather than retention lock, and tags may move or disappear. Neither tag identity nor tag mutability is trusted for deployment integrity.
- Consequences: `.tflock` can be released normally, old builds are bounded, and the immutable deployment boundary remains the content digest.
- Review trigger: Regulatory retention requirements or a promotion system requires a separate immutable provenance store.
- Owner: Terraform Safety Fixer

## DEC-022 — Idempotency ownership precedes provider execution

- Date: 2026-07-19
- Status: Accepted locally; role-separated races and fresh PostgreSQL gate passed
- Context: Database uniqueness preserved one durable run for concurrent identical starts, but both callers could execute all seven sandbox tools before one transaction lost, producing duplicate telemetry and an orphan run identity. Approval had a related window in which a compatible loser returned a false conflict before the winner's response became visible.
- Alternatives: accept sandbox-only duplication; use an in-process mutex; insert and commit a pending command lease; acquire a database transaction lock before the first replay check and provider call.
- Chosen option: Every mutable command acquires deterministic tenant/key ownership inside its database transaction. PostgreSQL uses `pg_advisory_xact_lock` with a signed SHA-256-derived key and a transaction-local five-second `lock_timeout`; SQLite local/tests use `BEGIN IMMEDIATE`. The lock remains held through replay/work and commit or rollback. A waiter rechecks durable replay after acquisition; timeout rolls back and uses the redacted structured database error.
- Trade-off: SQLite serializes all mutable commands and a slow provider holds a database transaction; PostgreSQL serializes only matching tenant/key commands and a waiter must retry after a five-second unavailable response if the holder is still active. This is suitable for bounded V1 inline execution but must be revisited before long-running or effectful providers.
- Consequences: Simultaneous compatible starts and decisions execute once and return the same durable response; different payloads and different approval keys retain conflict semantics. Effectful external providers remain prohibited in this iteration.
- Review trigger: Provider latency exceeds the bounded command budget, a queue/outbox is introduced, another database dialect is supported, or an effectful adapter is proposed.
- Owner: Pre-provider Idempotency Ownership Fixer

## DEC-023 — One protected predecessor with post-attestation tag mutation

- Date: 2026-07-19
- Status: Accepted locally; live GCP evidence externally blocked
- Context: Bounded registry cleanup could delete the only useful rollback digest, while moving a retention tag during the build would mutate operational state before the exact-plan attestation.
- Alternatives: keep every image; trust the 20-newest window; move the tag during build; protect exactly the current deployed digest only after the protected apply gate.
- Chosen option: Planning proves the desired digest and binds the current application digest as the sole rollback candidate. After `ALLOW_DEV_APPLY` verification, GCP authentication and granular permission preflight, apply revalidates that candidate and moves `app:rollback-current` with a separate custom role containing only `artifactregistry.tags.create` and `artifactregistry.tags.update`. A KEEP cleanup policy protects the tagged version; Terraform always deploys a digest, never the tag.
- Trade-off: Routine rollback is guaranteed only one deployment deep. The apply identity gains narrowly scoped tag mutation, and a foundation change is required to install that role.
- Consequences: Build and plan remain unable to change rollback state; failed/unapproved plans cannot move the protection pointer. Post-apply compares named image provenance, complete repository IAM, both custom roles, WIF/impersonation and state boundaries. Artifact upload/deletion and repository-policy mutation remain unavailable to routine apply.
- Review trigger: Promotion requires more than one rollback version, Artifact Registry tag permissions change, or a separate deployment controller owns release metadata.
- Owner: Terraform Critic Fixer and Role-separated Reviewer
