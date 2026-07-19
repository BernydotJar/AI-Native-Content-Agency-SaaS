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
- Alternatives: local worker; Cloud Tasks; Pub/Sub.
- Trade-off: Simpler and testable now; long-running providers will require leases, retries, cancellation, and dead-letter semantics before activation.
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
- Status: Accepted
- Context: `roles/run.admin` and project-wide image read exceed the permissions needed by the deployment workflow.
- Chosen option: Use one custom role containing exactly 19 required Cloud Run, location, operation and project-read permissions. Grant Artifact Registry Reader only on the intended repository.
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
- Chosen option: Resolve a unique exact display name, require the channel to be enabled, and require `VERIFIED` status for email before budgets or alerts depend on it.
- Trade-off: Environment setup is stricter, but misdelivery becomes a pre-apply error instead of an operational surprise.

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
