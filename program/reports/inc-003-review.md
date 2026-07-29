# INC-003 Security and Privacy Review Record

Date: 2026-07-21
Branch: `agent/production-readiness`
Parent commit: `e2d3e3c9d5a255fb55289d5b5bfd0786ec609df4`
Scope: selected `agency_runtime` trust/privacy model, public error boundary, authenticated denial evidence, request-size enforcement and security response headers
Release effect: none
External effect: none
Increment decision: `REVIEW` — bounded implementation passes; newly identified production HIGH findings have ready follow-up work and remain release blockers

## Producer result

```yaml
task_id: INC-003
status: PARTIAL
summary: >
  Implemented uniform public errors, validation/internal-error redaction,
  tenant-scoped durable authorization/CSRF denial evidence, bounded denial
  metrics, browser security/no-store headers and a pre-dispatch body limit for
  declared and streamed requests. Added authoritative threat/privacy/data
  classification models. The review also identified non-owner PostgreSQL
  runtime authority, retention and production backup controls as unresolved
  HIGH gates outside this bounded code slice.
files_inspected:
  - backend/agency_runtime/api.py
  - backend/agency_runtime/auth.py
  - backend/agency_runtime/persistence.py
  - backend/agency_runtime/postgres.py
  - backend/agency_runtime/observability.py
  - backend/agency_runtime/memory.py
  - backend/tests/*
  - src/lib/runtimeApi.ts
  - infra/helm/ai-native-content-agency/*
  - docs/OPERATIONS.md
files_modified:
  - backend/agency_runtime/api.py
  - backend/agency_runtime/persistence.py
  - backend/agency_runtime/postgres.py
  - backend/agency_runtime/observability.py
  - backend/tests/test_security_privacy.py
  - backend/tests/test_identity_access.py
  - backend/tests/test_sessions.py
  - backend/tests/test_observability.py
  - backend/tests/test_postgres_runtime.py
  - src/lib/runtimeApi.ts
  - src/lib/runtimeApi.test.ts
  - infra/helm/ai-native-content-agency/values.yaml
  - infra/helm/ai-native-content-agency/values.schema.json
  - infra/helm/ai-native-content-agency/templates/deployment.yaml
  - docs/security/threat-model.md
  - docs/privacy/privacy-model.md
  - docs/privacy/data-classification-retention.md
  - docs/OPERATIONS.md
  - README.md
  - program/**
  - specs/003-security-privacy/**
human_gates:
  - merge and release
  - production deployment
  - retention/deletion/legal-hold policy
  - persistent data deletion or replacement
  - external provider/browser/publisher activation
```

## Implemented contract

### Safe public errors

- Every application failure returns `code`, safe `detail` and `request_id`.
- Missing, invalid, expired, revoked and credential-deactivated authentication states share one 401 response.
- Authorization responses reveal no role or permission.
- Missing and foreign runs share one 404 body and do not echo the requested ID.
- state conflicts reveal no current state, decision or run ID.
- validation exposes only at most 20 bounded `{location,type}` records and never submitted input/context.
- internal exceptions expose only `internal_error`; diagnostic output records request ID and exception type, not message/content.
- TypeScript preserves code/detail/request correlation.

### Denial evidence

- Authenticated RBAC denial writes `authorization.denied` before returning 403.
- Authenticated CSRF denial writes `request.verification_denied` before returning 403.
- Events use the authenticated server-derived tenant/actor and contain bounded reason/auth method/role only.
- Credentials, session/CSRF tokens, request body, campaign content and raw client address are absent.
- SQLite evidence survives restart; PostgreSQL evidence written by one instance is visible to another.
- Anonymous failures are not attributed to an unproven tenant; durable hash buckets, safe metrics and route logs remain their evidence.

### Resource limits and headers

- ASGI buffers at most 1 MiB by default before dispatch; configuration is constrained from 1 KiB to 10 MiB.
- Declared and multi-message chunked overflows return safe 413 before authentication/mutation.
- duplicate/ambiguous framing is rejected with safe 400.
- Helm exposes the same value as `runtime.maxRequestBodyBytes`.
- API/operations responses use no-store/no-cache, no-sniff, frame denial, no-referrer, restrictive permissions and same-origin resource policy.
- TLS/HSTS/CSP and proxy/platform logging remain deployment evidence, not application claims.

## Spec-compliance review

Result: PASS for the implemented public-error, denial-evidence, input-limit, metrics, frontend and documentation scope.

Unresolved items discovered by the spec remain in the global release queue:

- runtime/migration PostgreSQL authority is not separated and a non-owner production runtime role is not demonstrated;
- approved retention/deletion/legal-hold rules and technical enforcement do not exist;
- backups are not scheduled/encrypted/immutable/off-host in an authorized environment;
- audit is transactional but not cryptographically tamper-evident or immutably exported;
- valid principals can amplify tenant audit rows because no general authenticated request quota exists;
- durable command idempotency and Greenlight revocation/fencing remain INC-004;
- semantic prompt-injection/groundedness/legal-overclaim evals remain INC-010;
- staging proxy/database/platform telemetry and capacity/failover remain unobserved.

## Critic findings and repairs

| Finding | Severity | Repair / disposition |
|---|---|---|
| 401/403/404/409 responses revealed session state, role, permission, resource ID or conflict detail. | HIGH | Replaced with stable `public-error.v1` and regression tests across auth/session/RBAC/tenant/conflict. |
| FastAPI validation could reflect submitted API key or political brief content. | HIGH | Custom validation handler emits only bounded location/type; secret/content reflection tests pass. |
| Internal exception message could reach a client/log. | HIGH | Catch-all safe 500; log request ID + exception type only; injected-secret test passes. |
| RBAC and CSRF denials had no durable tenant evidence. | HIGH | Added standalone transactional audit write to both stores and cross-restart/replica tests. |
| Metrics could gain high-cardinality tenant/permission labels. | HIGH | Counter accepts only `authorization` or `csrf`; invalid-label test passes. |
| Oversized/chunked bodies reached JSON/Pydantic parsing without a global cap. | HIGH | Added bounded ASGI prebuffer and declared/chunked/ambiguous-framing tests. |
| Client-controlled error code/detail could become unsafe in future use. | MEDIUM | `PublicApiError` enforces 4xx/5xx, snake-case code, length and control-character restrictions. |
| Security headers could be inferred from deployment rather than application. | MEDIUM | Added/tested baseline headers and explicitly left TLS/HSTS/CSP as deployment gates. |
| Authenticated denial audit can be storage-amplified. | MEDIUM | Documented; general authenticated quota/capacity/retention remains operations work. |
| PostgreSQL runtime role may own/create schema. | HIGH | Open ready task `INC-012`; release remains denied. |
| Retention/deletion and encrypted off-host backup policy are absent. | HIGH | Human/legal/deployment blockers and follow-up tasks; no destructive automation introduced. |

Open CRITICAL findings created by the slice: zero.
Open HIGH findings in the implemented error/denial/body-limit code after repair: zero.
Open HIGH architecture/deployment/privacy findings discovered by the slice: recorded in program state and not waived.

## Independent verification

| Gate | Command | Observed |
|---|---|---|
| Program schema/traceability | `npm run validate:program` | PASS; version 0.7.0, 79 requirements, 12 tasks and 27 required files |
| Locked backend/wheel | `./scripts/verify-python-locks.sh` | PASS; `agency-runtime 0.7.0`, `pip check`, 78 tests with eight expected PostgreSQL-only skips |
| Shared PostgreSQL and recovery | `./scripts/verify-postgresql-runtime.sh` | PASS; 78/78 including cross-instance denial, migration/replay, SQLite/PostgreSQL restore and cleanup |
| Frontend lint | `npm run lint` | PASS; zero findings |
| Frontend tests | `npm test -- --reporter=dot` | PASS; 33/33 |
| Frontend bundle | `npm run build` | PASS |
| Helm | `./scripts/verify-helm.sh` | PASS; schema/lint/render/guards including request-body environment |
| Patch hygiene | `git diff --check` | PASS |

## Evidence limitations

- The implementation was committed and pushed at `a9f063fc7db531a86822b58f603473a71247a903`; workflow `29856839172` completed all eight repository jobs successfully at that exact head.
- Those results do not cover the newer uncommitted `INC-012` PostgreSQL authority changes.
- No external reverse proxy, TLS/HSTS/CSP, managed identity, non-owner database role, RLS, SIEM, KMS, encrypted backup, staging workload or production environment was observed.
- The privacy/legal documents identify decisions and uncertainty; they are not legal approval.
- One execution system performed producer/critic/verifier roles procedurally; accountable final release review remains human and independent.

## Increment gate

`INC-003`: `REVIEW`.

The bounded security implementation is suitable for a feature-branch commit. The increment must remain `review`, not global `done`, until `INC-012` closes the executable PostgreSQL runtime-authority HIGH or demonstrates an exact external blocker. Global release remains `DENY_RELEASE`; cloud remains `DENY_APPLY`.
