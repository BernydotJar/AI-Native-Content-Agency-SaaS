# Threat Model — Production Foundation V1

Status: Active design and verification document
Updated: 2026-07-18

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
  -> exact owner/repository/main/workflow/environment WIF conditions
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
| TM-002 | Client claims another reviewer/tenant | Auth principal is persisted separately; tenant never comes from payload; reviewer is attributable text, not authority. | Approval audit and wrong-tenant tests. |
| TM-003 | Stale or modified artifacts are approved | Recompute canonical SHA-256 manifest and policy in the locked approval transaction. | Stale hash, artifact mutation, wrong policy tests. |
| TM-004 | Duplicate/concurrent command creates two resources/decisions | Tenant/key uniqueness, canonical request hash, replay response, optimistic run version, one approval per run. | Compatible replay, incompatible replay, concurrency tests. |
| TM-005 | Approval is mistaken for publication | Publisher adapter remains sandbox; response/evidence states `external_side_effects=false`; no live credentials exist. | Gate and package assertions. |
| TM-006 | Oversized or malformed input consumes resources | Strict Pydantic contracts, bounded content length/body, source asset scheme restriction. | Oversized, malformed JSON, extra-field tests. |
| TM-007 | Path traversal or malicious filename | V1 accepts no binary upload/path; source assets must be `sandbox://`; existing skill writer confines and validates paths. | Contract and existing skill traversal tests. |
| TM-008 | Prompt/log injection changes policy or corrupts logs | Objective is stored as data; logs exclude bodies and use JSON serialization; correlation IDs are constrained. | Injection-as-data and log capture tests. |
| TM-009 | Development auth reaches production | Typed settings reject development auth and schema auto-create in production; CI exercises startup failure. | Production configuration test. |
| TM-010 | Broad CORS or browser framing/content sniffing | Explicit origins, no credentials, limited methods/headers, security response headers. | CORS and header tests. |
| TM-011 | Database outage leaks internals or creates partial state | Structured generic error, explicit rollback/transaction, readiness failure. | Unavailable DB and partial-transaction tests. |
| TM-012 | Secret or credential enters source/log/plan | No secret values in Terraform, no service-account keys, scans and ignore rules, redacted evidence. | Secret/personal-path/state-plan scans. |
| TM-013 | GitHub OIDC token from another repo/ref/workflow/phase deploys | Three WIF providers require exact owner, repository, `main` ref, direct `workflow_ref`, and phase environment; each impersonates only its phase account. | Terraform condition assertions and workflow inspection. |
| TM-014 | Cloud Run or bucket becomes public | Invoker IAM check remains enabled, no `allUsers`, uniform bucket access, saved-plan veto. | Plan JSON critique and unauthenticated invocation denial after apply. |
| TM-015 | Cloud SQL is directly reachable or uses a long-lived password | Connector enforcement/authorized-network absence and automatic IAM database authentication. | Terraform critique and runtime connectivity/denial checks. |
| TM-016 | Terraform targets the unrelated configured project | Project, billing, parent, and region are mandatory explicit variables; no gcloud default is consumed. | Variable validation and plan target review. |
| TM-017 | Destructive, stale, or substituted plan is applied | Saved runtime plan/JSON, no destroy/replace, full tracked-tree/plan/image/commit binding, independently signed short-lived attestation, and verification before cloud authentication. | Apply-gate unit tests, workflow ordering, cloud critique, and evaluator report. |
| TM-018 | Routine deploy identity can change foundation IAM, SQL, services, registry policy, alerts, budget, or foundation state | Foundation and runtime use separate state roots. Plan can read required state and mutate only a disposable runtime `.tflock`; apply can mutate only the runtime-state prefix. GitHub apply receives an exact custom Cloud Run service/job role, repository-scoped image read, read-only verification roles, and `actAs` on one runtime account. `roles/run.admin` and other forbidden admin roles are rejected. | Exact custom-role test, safe permission probes, plan gate, and project/repository post-apply IAM verification. |
| TM-019 | New application revision serves against an old schema | Startup runs the checked Alembic upgrade through the IAM connector under a PostgreSQL advisory transaction lock; migration failure prevents readiness. | Entry-point ordering tests, Terraform startup probe, and deployment migration evidence. |

## Abuse cases intentionally unavailable

There is no API for external publication, ad campaign creation, budget spend, arbitrary URL fetch, arbitrary repository access, provider credentials, raw upload, shell execution, or dynamic skill creation. Adding any of these requires a new threat-model review and adapter-specific auth, scopes, timeout, rate limit, retry, receipt, revocation, and failure tests.

## Residual risks

- V1 development header identity is not a production end-user authentication system; private Cloud Run IAM is mandatory around cloud dev.
- Inline execution cannot resume a partially completed agent step. An interrupted uncommitted command is retried through its idempotency key.
- SQLite concurrency is a test/local approximation; PostgreSQL is required for runtime concurrency claims.
- A real Terraform plan, notification-recipient delivery proof, measured cost, unauthenticated cloud denial test, and database IAM connectivity test remain blocked until an open billing account and explicit target project/region are authorized.
- The attestation proves reviewer intent and artifact identity, but GitHub environment reviewer configuration must still be inspected in the live repository before the first apply.
