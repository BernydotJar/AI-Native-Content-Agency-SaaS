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
- Reason: no versioned effect contract exists; service authentication, idempotency, receipts, revocation, and external authorization are all absent.

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
Status: accepted and verified at `1002d077564618623fe00f27ffae23c2b410aca8` in GitHub Actions run `29868899218`

Decision: production-like PostgreSQL verification must use a migration/bootstrap role for schema authority and a non-owner runtime role with exact grants. The runtime must fail closed when schema is absent/incompatible and must not CREATE, ALTER, DROP or TRUNCATE runtime objects.

Rationale: application SQL predicates are a primary tenant boundary; an overprivileged runtime credential turns an application compromise into schema/database control.

Consequence: INC-012 passed the negative ownership/DDL and full application/recovery gates. Production still requires authorized persistent-environment observation and the remaining global release findings to close.

## D-009 — Long-running PostgreSQL pods validate; they never migrate

Date: 2026-07-21
Status: accepted and exact-head verified at `1002d077564618623fe00f27ffae23c2b410aca8`; GitHub Actions run `29868899218` passed eight of eight jobs

Decision: `PostgresRuntimeDatabase` defaults to `validate`. Only the explicit `agency-runtime-schema initialize` operator command may run schema DDL. DDL, metadata insertion and validation share one advisory-locked transaction. Application connections fix `search_path=pg_catalog,public`. Helm and Terraform reject `initialize` for application pods and expose only the runtime-role URL to the Deployment.

Rationale: application startup is horizontally concurrent and continuously exposed. Giving every replica schema ownership or implicit migration authority expands compromise impact and makes rollout/rollback nondeterministic.

Consequence: a new or upgraded database must be initialized and granted before application rollout. Missing, incomplete or incompatible schema fails startup/readiness instead of being repaired implicitly. The code/delivery HIGH is closed; persistent environment observation remains a separate production gate.

## D-010 — Versioned SLO and alert contracts

Date: 2026-07-21
Status: accepted locally at `6a885827b7e89d06111c87c34293250eab196d47`; remote CI pending

Decision: SLOs, exact error budgets, alert metadata, Prometheus rules and deterministic exercises are versioned and validated together. `PrometheusRule` is opt-in and assumes an existing operator; the repository never equates rule rendering with telemetry or paging.

Consequence: rule/catalog/runbook drift fails CI. Persistent loading, alert delivery and human response remain staging/production evidence.

## D-011 — Backup freshness is emitted only after integrity validation

Date: 2026-07-21
Status: accepted locally at `6a885827b7e89d06111c87c34293250eab196d47`; external production controls pending

Decision: successful SQLite/PostgreSQL backup commands may atomically write a private Prometheus textfile only after manifest/artifact integrity validation. The signal contains backend, bytes and timestamp only.

Consequence: stale/missing signals are locally testable without leaking paths or credentials. Scheduler, KMS, encryption, immutable off-host retention and real alert delivery remain explicit external gates.

## D-012 — Frontend role capabilities are guidance, never authority

Date: 2026-07-21
Status: accepted locally at `4f101221d3ddfb426aded5e7f4caec9c87985b32`; remote CI pending

Decision: the production console derives visible create/decision controls from the server-issued session role, but every request remains subject to backend authorization. Viewers and approvers can load a tenant-scoped run by ID without acquiring create authority. Public failure states are selected from bounded HTTP/status contracts and never reflect raw exception detail or permission names.

Consequence: the interface is understandable and avoids predictable forbidden requests, while frontend state cannot elevate authority or replace tenant/RBAC enforcement. Manual accessibility evidence remains owned by `INC-008`.

## D-013 — Theme is visual state; premium is a server-owned product entitlement

Date: 2026-07-21
Status: accepted locally at `f63a58648eec0579d53a007c8ed83ff376b95727` and `8ecf77e7f58789d1e5b47826b595b172bac6fa89`; remote CI pending

Decision: expose four politically neutral free themes and one premium theme. Theme never changes role, permission, Greenlight, risk or recommendation. Premium activates only from the exact allowlisted `theme:premium` entitlement on the active server-managed identity. The SPA refreshes `/me`, falls back to blue when entitlement disappears, stores no theme/entitlement in browser persistence and treats CSS as inspectable rather than DRM.

Consequence: administrators can grant/revoke supported premium UI without billing infrastructure or database schema changes. Checkout, invoicing and subscription lifecycle remain separate unimplemented systems. Manual accessibility review remains a human release gate.

## D-014 — External integration review is data, not execution authority

Date: 2026-07-21
Status: accepted locally; exact-head CI pending

Decision: review `browser-use/video-use` at exact commit
`92c2b34e44c205cbc2acae7f6ca7c1c219d5dd66`, package its source hashes and
findings, and expose that evidence through authenticated GET endpoints only.
Define strict product-owned plan and future receipt shapes, but keep
`activation_allowed`, `execution_available`, `execution_permitted` and
`external_effects_enabled` false. Do not install, import or invoke upstream code.

Consequence: operators can inspect a reproducible architecture/license/security
review without gaining provider authority. Path traversal, media disclosure,
supply-chain reproducibility, isolated worker, outbound idempotency/receipt,
privacy and semantic-eval requirements remain mandatory before any activation.
