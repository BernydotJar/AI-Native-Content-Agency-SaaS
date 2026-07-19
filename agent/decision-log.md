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

