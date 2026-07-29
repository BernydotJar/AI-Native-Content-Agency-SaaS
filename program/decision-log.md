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

## D-015 — The durable run document is the only topology authority

Date: 2026-07-23
Status: accepted locally at `3cc304d10b64b8cb32bffeee52f36e583c46f844`; remote publication blocked

Decision: the product SPA requests `Prefer: respond-async`, receives a persisted queued run
and polls the tenant-scoped run resource only while status is queued/running. A worker
persists an expiring lease and new fencing token before each checkpoint. The browser may
animate transitions, but it may not synthesize a station state, percentage or completion.

Rationale: terminal synchronous responses made the topology static, while client timers
would create false operational evidence. Durable checkpoints provide restart recovery,
cross-replica serialization and auditable progress without granting external-effect
authority.

Consequence: deterministic sandbox stations may be recomputed only when a claim crashed
before checkpoint persistence. Model inference and social publication remain governed by
separate pending intent/receipt authorities; this decision does not authorize spend or
publication.

## D-016 — External social publication is an exact durable effect, not an OAuth capability

Date: 2026-07-24
Status: accepted locally at `8eb0cf7dee9b3400351a8b7d603a94666253f1e7`; remote CI and real sandbox authorization pending

Decision: Account connection never grants publication authority. A social effect may execute
only after the server reconstructs the exact approved copy/media/account/Greenlight binding,
persists a unique intent and fencing token, and confirms the server-side publication flag.
Compatible retries and different command keys reuse one receipt. Ambiguous outcomes become
`unknown` and require idempotent human reconciliation. Audit success is deterministic and
repairable on replay without a second provider call.

Rationale: OAuth proves delegated account access but does not solve duplicate effects,
stale approval, media substitution, persistence failure, audit gaps or operator intent.
Treating a post as a durable economic effect closes those failure modes and keeps browser
state non-authoritative.

Consequence: X/Instagram adapters may exist while remaining disabled by default.
MockTransport, a socket guard and installed-image tests are verification only; real account
use, current terms/privacy review, sandbox authorization, deployment and spend remain human
gates.

## D-017 — Model inference is a durable economic effect

Date: 2026-07-24
Status: accepted locally at `6eb7fa070bcbe71c840ca316fc86d369d9d1691b`; exact-head CI and real provider authorization pending

Decision: a model operation may execute only after the server resolves the provider/model,
constructs the governed request, persists an exact tenant/run/station/source/request/cost
binding and assigns a fencing token. Compatible retries reuse one stored output and receipt.
Ambiguous outcomes become `unknown`; no automatic retry or Greenlight approval is allowed
until idempotent administrator reconciliation attaches the result and repairs audit evidence.

Rationale: provider protocol readiness does not prevent duplicate token spend after an
ambiguous response or local persistence failure. Browser-selected provider/model/prompt state
also cannot be trusted as economic authority.

Consequence: the five-provider gateway can be invoked explicitly through a governed admin
command while both model flags remain false by default. Automatic per-station inference,
real credentials, prompt transfer, egress, budget and production activation remain separate
human and release gates.

## D-018 — Political campaign content requires server-bound evidence and legal authority

Date: 2026-07-25
Status: accepted locally at `6ebbd634bd32408db0a7678289b0f906cda014c0`; exact-head CI and accountable human review pending

Decision: a political campaign brief may be drafted without external effects, but it may not become publication-eligible unless every used claim is source/locator bound, marked verified by an authenticated subject with `greenlight:decide`, and the legal-review status is approved by the same server-authoritative identity boundary. Client-supplied reviewer names are never authority. Critique must expose `revise` truthfully when any gate fails.

A second, independent runtime flag `AGENCY_POLITICAL_PUBLICATION_ENABLED` remains false by default. Enabling general social publication does not enable political publication.

Rationale: a source string, a connected social account or a Greenlight decision alone cannot prove factual, legal or campaign authority. Separating drafting, evidence review, legal review, Greenlight and effect enablement prevents accidental or self-attested political publication.

Consequence: campaign intelligence can produce reviewable Spanish copy and an accessible non-rendered media plan. Real media, post verification, jurisdiction-specific review, candidate/campaign authorization and any external post remain separate gates under INC-022 and the release decision.

## D-019 — INC-021 is complete at increment scope, not release scope

Date: 2026-07-25
Status: accepted at exact remote head `25f2ef0c19d89f008a87aa1daa79b1ca9a1df9a1`

Decision: mark INC-021 `done` after local deterministic gates and GitHub Actions run `30149528848` passed all eight exact-head jobs. Keep PR #13 draft, keep `DENY_RELEASE` and `DENY_APPLY`, and keep all political/social external effects disabled.

Consequence: the next safe executable task is INC-022 for governed media and read-after-write publication verification. Increment completion does not constitute legal approval, candidate authorization, deployment or permission to publish.

## D-020 — Provider IDs are not sufficient evidence of publication

Date: 2026-07-25
Status: accepted locally; exact-head CI pending

Decision: Instagram publication is successful only after the media container reaches `FINISHED`, `media_publish` returns an ID, and an independent media read matches the intended account, caption hash, media type, permalink and timestamp. Any ambiguity after an external mutation is durable `unknown`, not retryable success or failure.

Media supplied to the provider must come from the product-owned Media Vault: decoded JPEG bytes, server SHA-256, rights/alt metadata, tenant/run binding, opaque capability, expiry and revocation. External mutable image URLs are not accepted as Greenlight evidence.

Consequence: the system can truthfully show a durable verified permalink after reload. Real publication, provider deletion, signing-key rotation and production object storage remain separate human/release gates.

## 2026-07-25 — Close stacked campaign/media increments before political compliance

Decision: merge PR #13 and PR #14 normally into their stacked base branches after exact-head CI passed, preserving ancestry with merge commits rather than squash/rebase. PR #13 merged as `cce712e86b356cf9c4a2dca087f8af078101915e`; PR #14 merged as `7522164240b8090fe70ec51525a6a247e4a558c8` after run `30164438593` passed all eight jobs.

Consequence: Campaign Intelligence, Publication Media and Verified Publication are closed as increments. The cumulative stack is still not on protected `main`; a later cumulative PR remains subject to current checks and independent approval.

## 2026-07-25 — Separate political planning, approval and final effect authority

Decision: INC-023 uses independent default-off switches for political content, general publication, political publication and paid planning. Political Greenlight requires a legal/electoral reviewer distinct from the Greenlight approver and includes a hashed compliance record. Organic publication requires the exact typed phrase `PUBLICAR POLITICA <run_id> <channel_id>` before intent reservation; only its SHA-256 is durable. Paid mode cannot use the organic endpoint.

Consequence: local deterministic gates can prove authority separation and zero-provider fail-closed behavior, but cannot supply jurisdiction-specific legal approval or authorize a real post. Release and cloud apply remain denied.

## D-021 — Graph Harness SDLC is the delivery execution runtime

Date: 2026-07-29
Status: accepted for INC-038; close and merge pending

Decision: pin `BernydotJar/Graph-harness-sdlc` at `1bebce3db35303072049233786464bb01163c98b` as a gitlink. Preserve the SaaS task ledger and dependency graph as domain sources, generate the framework project contract deterministically, and persist execution as a hash-chained append-only event ledger. Do not copy framework runtime modules into the application.

Rationale: the repository already had rich domain artifacts but lacked one executable typed runtime for dependency readiness, evidence freshness, production gates and localized repair. A pinned adapter preserves product-specific truth while avoiding a competing framework implementation.

Consequence: CI fails on framework revision drift, projection drift, state drift, event-chain corruption, stale evidence or illegal graph state. INC-038 remains `review`; exact-head CI, closure and merge are separate gates. Product behavior and all external-effect authority remain unchanged.

## D-023 — Decouple semantic-eval implementation from manual accessibility approval

Date: 2026-07-29
Status: accepted for INC-010

Decision: replace the `INC-010 -> INC-008` technical dependency with `INC-010 -> INC-021`, while retaining `INC-008` as an independent blocked release node. `INC-010` still depends on security (`INC-003`) and durable idempotency (`INC-004`).

Rationale: the semantic/adversarial evaluator consumes campaign artifacts, evidence provenance and authority boundaries. It does not consume a human screen-reader, rendered-contrast or visual-review approval. Keeping that unrelated dependency prevented safe implementation and conflated engineering readiness with release readiness.

Consequence: the eval harness can be implemented and exact-head verified without claiming that manual accessibility, legal review, staging observation, deployment or release are complete. The global release decision remains `DENY_RELEASE` until all blocked nodes close.
