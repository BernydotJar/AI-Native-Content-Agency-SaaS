# Decision Log

## D-001 — Select `agency_runtime` as the active runtime on PR #3

- Date: 2026-07-21
- Status: accepted for this branch
- Decision: Preserve the current FastAPI/RBAC/PostgreSQL implementation as the source of truth. Treat PR #2 as a donor branch rather than merging its alternate `control_plane` wholesale.
- Reason: The branches diverged and contain incompatible persistence, API, authentication, packaging, CI, and infrastructure designs. Blind integration would create two authorities and invalidate existing evidence.
- Reversal condition: a reviewed replacement plan with API/data migration, rollback, compatibility tests, and explicit ownership.

## D-002 — GCP deployment is not proven

- Date: 2026-07-21
- Status: accepted
- Decision: Record the current cloud state as `not deployed / not observed`.
- Evidence: the active branch has no GCP resources; issue #1 and PR #2 record `DENY_APPLY`, closed billing accounts, no authorized target, and no apply evidence.
- Resume condition: an explicitly authorized target, open billing, granular permission preflight, reviewed saved plan, apply record, endpoint smoke, and no-drift plan.

## D-003 — Keep all external effects disabled

- Date: 2026-07-21
- Status: accepted
- Decision: Do not activate `video-use`, browser automation, publisher APIs, media generation, advertising, or spend during this program slice.
- Reason: no versioned effect contract, credentials, idempotency/receipt/revocation controls, or external authorization exists.

## D-004 — Normalize product version at 0.7.0

- Date: 2026-07-21
- Status: accepted
- Decision: Align frontend package, Python runtime, FastAPI metadata, metrics, Helm chart, and OCI metadata at `0.7.0`; enforce consistency with a repository gate.
- Reason: frontend `0.0.0` contradicted runtime/chart `0.7.0` and made release artifacts ambiguous.

## D-005 — Backup tools must fail closed

- Date: 2026-07-21
- Status: accepted
- Decision: Backup manifests include backend, size, SHA-256, timestamp, tool version, and validation result. Restore verifies integrity and refuses an existing target unless an explicit replacement flag is supplied. Production restore remains a human destructive-data gate.

## D-006 — Public errors are stable and non-enumerating

Date: 2026-07-21
Status: accepted for INC-003

Decision: application failures expose only a stable snake-case code, bounded safe detail and request ID. Authentication state variants share one 401; role/permission, foreign IDs, current state, submitted input and internal exception messages are not public contracts.

Rationale: raw framework/application exception text created authentication, authorization, metadata and privacy oracles and made clients depend on internals.

Consequence: server diagnosis uses correlated sanitized logs/audit. Frontend behavior branches on status/code rather than exception prose.

## D-007 — Audit only authenticated denials in the tenant ledger

Date: 2026-07-21
Status: accepted for INC-003

Decision: authenticated RBAC and CSRF denials are written to the server-derived tenant audit ledger before returning 403. Anonymous authentication failures are not assigned to a tenant and remain in one-way rate buckets, bounded metrics and sanitized route logs.

Rationale: assigning failed/guessed credentials to a tenant would create false evidence and a cross-tenant injection surface.

Consequence: tenant audit is complete for proven-principal denials but is not a global edge/WAF security log.

## D-008 — PostgreSQL migration and runtime authority must be separated

Date: 2026-07-21
Status: accepted; implementation present, exact-worktree verification pending in INC-012

Decision: production-like PostgreSQL verification must use a migration/bootstrap role for schema authority and a non-owner runtime role with exact grants. The runtime must fail closed when schema is absent/incompatible and must not CREATE, ALTER, DROP or TRUNCATE runtime objects.

Rationale: application SQL predicates are a primary tenant boundary; an overprivileged runtime credential turns an application compromise into schema/database control.

Consequence: no production-ready claim until INC-012 passes negative ownership/DDL tests and full application/recovery regression.

## D-009 — Long-running PostgreSQL pods validate; they never migrate

Date: 2026-07-21
Status: accepted for INC-012; foundation `df7fc7f878d8beb34fc956746a6bdfe34794f9f0`, effective local head `23bfee60f8536d2fcd7e3c5ca20636103f9401c8`, behavioral verification pending

Decision: `PostgresRuntimeDatabase` defaults to `validate`. Only the explicit `agency-runtime-schema initialize` operator command may run schema DDL. DDL, metadata insertion and validation share one advisory-locked transaction. Application connections fix `search_path=pg_catalog,public`. Helm and Terraform reject `initialize` for application pods and expose only the runtime-role URL to the Deployment.

Rationale: application startup is horizontally concurrent and continuously exposed. Giving every replica schema ownership or implicit migration authority expands compromise impact and makes rollout/rollback nondeterministic.

Consequence: a new or upgraded database must be initialized and granted before application rollout. Missing, incomplete or incompatible schema fails startup/readiness instead of being repaired implicitly. Exact-commit execution evidence is still required before the HIGH finding closes.
