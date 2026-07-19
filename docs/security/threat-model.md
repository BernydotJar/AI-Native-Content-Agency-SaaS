# Threat Model — Production Foundation V1

Status: Active design and verification document
Updated: 2026-07-19

## Scope and assets

The protected assets are tenant-scoped missions, run state, artifacts, tool evidence, audit events, approval intent, idempotency records, database state, Terraform state, cloud identities, and configuration. External publishing credentials, ad accounts, uploaded binaries, and production customer data are not in scope because this iteration does not accept or activate them.

## Trust boundaries

```text
Browser
  -> Cloud Run IAM or local developer boundary
  -> FastAPI identity/request boundary
  -> application authorization and Greenlight policy
  -> SQL transaction boundary
  -> sandbox tool adapters

GitHub Actions OIDC
  -> immutable numeric owner/repository IDs plus exact names/main/workflow/environment WIF conditions
  -> distinct build, resource-read-only plan, and apply service accounts
  -> immutable image + narrow runtime Terraform state

Separately reviewed foundation administrator
  -> dev project APIs/IAM/registry/SQL/alerts/budget
  -> foundation Terraform state (not routine workflow-owned)
```

Development tenant/principal headers are identifiers, not credentials. They are permitted only in non-production settings. The cloud development endpoint must require Cloud Run IAM, so an unauthenticated Internet caller cannot reach that development identity mode.

## Threats and required controls

| ID | Threat | Control | Verification |
|---|---|---|---|
| TM-001 | Cross-tenant read or command | Tenant comes from centralized identity, every repository query scopes tenant, missing identity denied. | Wrong/missing tenant API tests. |
| TM-002 | Client claims another reviewer/tenant or loses decision provenance | Auth principal is persisted separately; tenant never comes from payload; reviewer is attributable text, not authority; approval row/response/audit directly retain the command key. | Approval audit/idempotency and wrong-tenant tests. |
| TM-003 | Stale or modified artifacts are approved | Recompute canonical SHA-256 manifest and policy in the locked approval transaction. | Stale hash, artifact mutation, wrong policy tests. |
| TM-004 | Duplicate/concurrent command creates two resources/decisions or executes a provider twice | A tenant/key PostgreSQL transaction advisory lock (or isolated SQLite `BEGIN IMMEDIATE`) is acquired before replay and provider work and held through commit/rollback; canonical request hash, replay response, uniqueness, optimistic run version and one approval per run remain defense in depth. | Compatible/incompatible replay, duplicate delivery/event count, simultaneous identical start with exactly seven tool calls, and same-/different-key approval concurrency tests. |
| TM-005 | Approval is mistaken for publication | Publisher adapter remains sandbox; response/evidence states `external_side_effects=false`; no live credentials exist. | Gate and package assertions. |
| TM-006 | Oversized or malformed input consumes resources | Strict Pydantic contracts, bounded content length/body, source asset scheme restriction. | Oversized, malformed JSON, extra-field tests. |
| TM-007 | Path traversal or malicious filename | V1 accepts no binary upload/path; source assets must be `sandbox://`; existing skill writer confines and validates paths. | Contract and existing skill traversal tests. |
| TM-008 | Prompt/log injection changes policy or corrupts logs | Objective is stored as data; logs exclude bodies and use JSON serialization; correlation IDs are constrained. | Injection-as-data and log capture tests. |
| TM-009 | Development auth reaches production | Typed settings reject development auth and schema auto-create in production; CI exercises startup failure. | Production configuration test. |
| TM-010 | Broad CORS or browser framing/content sniffing | Explicit origins, no credentials, limited methods/headers, security response headers. | CORS and header tests. |
| TM-011 | Database outage leaks internals or creates partial state | Structured generic error, explicit rollback/transaction, readiness failure. | Unavailable DB and partial-transaction tests. |
| TM-012 | Secret or credential enters source/log/plan | No secret values in Terraform, no service-account keys, scans and ignore rules, redacted evidence. | Secret/personal-path/state-plan scans. |
| TM-013 | GitHub OIDC token from another or renamed/transferred repo/ref/workflow/phase deploys | Three WIF providers require immutable numeric owner/repository IDs plus exact names, `main`, direct `workflow_ref`, and phase environment; each impersonates only its phase account. | Positive and negative Terraform condition assertions plus workflow inspection. |
| TM-014 | Cloud Run or bucket becomes public | Invoker IAM check remains enabled, no `allUsers`, uniform bucket access, saved-plan veto. | Plan JSON critique and unauthenticated invocation denial after apply. |
| TM-015 | Cloud SQL is directly reachable or uses a long-lived password | Connector enforcement/authorized-network absence and automatic IAM database authentication. | Terraform critique and runtime connectivity/denial checks. |
| TM-016 | Terraform targets the unrelated configured project | Project, billing, parent, and region are mandatory explicit variables; no gcloud default is consumed. | Variable validation and plan target review. |
| TM-017 | Destructive, stale, or substituted plan is applied | Saved runtime plan/JSON, no destroy/replace, full tracked-tree/plan/image/commit binding, independently signed short-lived attestation, and verification before cloud authentication. | Apply-gate unit tests, workflow ordering, cloud critique, and evaluator report. |
| TM-018 | Routine deploy identity can delete runtime or change service/foundation IAM, SQL, registry policy, alerts, budget, or foundation state | Foundation and runtime use separate state roots. Plan can read required state and mutate only a disposable runtime `.tflock`; apply can mutate only runtime state. GitHub apply receives an exact 16-permission Cloud Run role without delete/setIamPolicy, repository read, a separate two-permission tag mover, read-only verification and `actAs` on one runtime account. It cannot upload/delete artifacts or change cleanup/IAM. Foundation owns project-level `roles/run.servicesInvoker`; runtime owns no service IAM member. | Exact role and negative permission tests, safe probes, plan gate, public/unexpected service-binding denial and exact runtime/repository/custom-role post-apply verification. |
| TM-019 | New application revision serves against an old schema | Startup runs the checked Alembic upgrade through the IAM connector under a PostgreSQL advisory transaction lock; migration failure prevents readiness. | Entry-point ordering tests, Terraform startup probe, and deployment migration evidence. |
| TM-020 | A coincidentally named existing project or notification recipient is silently trusted | Projects and notification channels are always Terraform-managed. Each adoption requires versioned evidence, acknowledgement and declarative import. Channel creation is also Terraform-owned; alert, budget and costly resources wait for an exact enabled/VERIFIED match plus reviewed evidence. Runtime binds both provenance digests. | Create/adopt negative mocks, unverified/evidence gate tests, import inspection and foundation/runtime digest preconditions. |
| TM-021 | Workflow or attestation is treated as mandatory without live enforcement or independent identity | Main must require current checks and non-self review; protected `dev` must bind a distinct authenticated reviewer and prevent self-review before the attestation secret is available. | Read back branch protection/rulesets, environments, reviewers, restrictions and variables before first dispatch. |
| TM-022 | Concurrent identical run starts execute an effectful provider more than once before the durable response exists | A cross-instance tenant/key transaction lock now precedes replay and provider work and has a transaction-local five-second PostgreSQL wait bound. Current adapters remain deterministic sandboxes with `external_side_effects=false`; activation still requires adapter-specific timeout, retry, receipt and revocation semantics. | 12/12 role-separated races, lock-timeout negatives and fresh real PostgreSQL contention with exactly seven tool records. |
| TM-023 | Cleanup deletes the only safe rollback image, or a mutable tag substitutes the deployed image | Runtime plans/deploys only exact foundation `app@sha256` references. Plan binds the current digest; after attestation/auth/preflight, apply rechecks it and a two-permission role moves one `rollback-current` retention tag. KEEP takes precedence over the old-version delete rule; the tag is never passed to Terraform as an image. | Digest/tag existence and mismatch negatives, cleanup-policy mocks, workflow-order scan and post-apply report verification. |

## Abuse cases intentionally unavailable

There is no API for external publication, ad campaign creation, budget spend, arbitrary URL fetch, arbitrary repository access, provider credentials, raw upload, shell execution, or dynamic skill creation. Adding any of these requires a new threat-model review and adapter-specific auth, scopes, timeout, rate limit, retry, receipt, revocation, and failure tests.

## Residual risks

- V1 development header identity is not a production end-user authentication system; private Cloud Run IAM is mandatory around cloud dev.
- Inline execution cannot resume a partially completed agent step. An interrupted uncommitted command is retried through its idempotency key.
- Matching-key commands hold a database transaction while bounded inline provider work runs. This is accepted for V1 sandboxes but must move to a lease/outbox/queue design before long-running or effectful adapters are enabled.
- SQLite concurrency is a test/local approximation; PostgreSQL is required for runtime concurrency claims.
- Candidate project `ai-native-content-agency-saas` has unknown provenance and is not adopted; distinct bootstrap/dev roles, an open billing account, parent and region remain unselected.
- A real Terraform plan, notification-recipient delivery proof, measured cost, unauthenticated cloud denial test and database IAM connectivity test remain blocked until that eligibility is resolved.
- Routine application rollback is guaranteed only for the immediate predecessor protected by `rollback-current`; older digests are not promised even if registry cleanup has not yet removed them.
- Main protection and all three protected-branch deployment environments now exist. `dev` prevents self-review, but its configured reviewer is also the only collaborator; no distinct actor/reviewer pair can currently satisfy the gate. The updated workflow is not on `main`, required Actions variables are absent, and the attestation schema alone does not prove an authenticated independent reviewer.
- The current repaired tree has producer evidence but no exact-tree GitHub Actions result or final independent evaluator decision.
