# 003 — Security, Privacy and Uniform Denial Evidence

Status: review
Owner: Security/Privacy Reviewer

## Problem

The selected `agency_runtime` architecture enforces authentication, RBAC and tenant-scoped storage, but several API responses expose internal session state, role names, permission names, run identifiers or conflict details. Authenticated authorization and CSRF denials are rejected but not written to the durable tenant audit ledger. Validation responses may also echo submitted values. The active branch lacks an authoritative threat model, privacy model and data classification for this runtime.

## Purpose

Eliminate actionable metadata leakage from API failures, create stable machine-readable error codes, record authenticated security denials without credentials or campaign content, and document the selected architecture's threats, privacy boundaries, retention decisions and residual risk.

## Actors and journeys

- **Viewer/operator/approver/admin:** receives a useful request ID and stable public code without learning internal permissions, session state or another tenant's resource existence.
- **Tenant auditor:** observes authorization and CSRF denials for that tenant, including actor, request ID, bounded reason and timestamp, but no credentials or submitted content.
- **Incident responder:** correlates a public error, low-cardinality metric, sanitized HTTP log and durable audit event.
- **Privacy reviewer:** maps each stored/logged field to purpose, sensitivity, retention owner and deletion gate.
- **Attacker:** cannot distinguish missing, foreign or guessed resources; cannot use 401 responses to enumerate expired, revoked or deactivated sessions; cannot cause validation responses to reflect secrets.

## Functional requirements

1. Every application error response contains `code`, safe `detail` and `request_id`.
2. Authentication failures use one public code/detail for missing, invalid, expired, revoked and credential-deactivated sessions and bearer credentials.
3. Authorization responses never reveal role, permission or internal exception text.
4. Missing and cross-tenant run lookups use the same status, code, detail and shape and do not echo the requested run ID.
5. State conflicts use one public response and do not reveal current state or another request's decision.
6. Request-validation responses omit submitted `input`, secret values and Pydantic context; they may expose only bounded field locations and error types.
7. Authenticated RBAC and CSRF denials are appended transactionally to the tenant's audit ledger before returning the denial.
8. Security-denial audit payloads contain no API key, cookie, CSRF token, request body, campaign content or raw client IP.
9. Denial metrics use bounded labels and no tenant/identity/content labels.
10. API responses include no-store and baseline browser security headers without breaking the SPA.
11. SQLite and PostgreSQL implement the same standalone audit-write contract.
12. The frontend preserves public error code, safe detail and request correlation.
13. Threat model, privacy model and data-classification/retention record describe implemented, missing and human-gated controls.

## Non-functional requirements

- error generation requires no network or external service;
- response bodies are deterministic except for the request ID;
- public error details are short, non-sensitive and stable across storage backends;
- audit insertion failure never allows the protected action;
- metrics remain low-cardinality;
- all changes preserve existing RBAC, tenant isolation, sessions, Greenlight and recovery behavior;
- documentation distinguishes implementation evidence from deployment policy.

## Invariants

- tenant identity always derives from the authenticated server-side principal;
- public error bodies never contain `role`, `permission`, `key_id`, token/session state, requested foreign identifier or internal exception text;
- an authenticated authorization/CSRF denial either has a durable tenant audit event or the request fails closed as an internal service error;
- audit events never cross tenant boundaries;
- unauthenticated failures are not assigned to an unproven tenant; hashed rate-limit buckets and sanitized metrics/logs remain their evidence;
- request IDs accepted from clients are bounded and validated;
- no external effects are enabled.

## Error and degraded states

- `authentication_failed` → 401;
- `authentication_rate_limited` → 429 with bounded `Retry-After`;
- `request_verification_failed` → 403;
- `authorization_denied` → 403;
- `resource_not_found` → 404;
- `resource_state_conflict` → 409;
- `request_validation_failed` → 422 with sanitized field/type list;
- `authentication_unavailable` / `storage_unavailable` → 503;
- `internal_error` → 500, safe body and sanitized server log.

## Security boundaries

- API keys are accepted only for bearer authentication or one-time session exchange and are never returned or stored raw.
- Session and CSRF tokens are HttpOnly/in-memory boundaries and are stored only as hashes.
- Security events are tenant-scoped application audit data, not a substitute for immutable SIEM or edge/WAF telemetry.
- Raw source IP is represented only by a one-way rate-limit bucket and is not placed in audit/metrics.
- The current application database role and deployment remain operator-controlled; least-privilege non-owner production role and managed identity are required deployment controls.

## Privacy boundaries

- Campaign briefs, artifacts, Greenlight notes, memories, subject identifiers and audit events may contain personal, political or sensitive client data.
- The repository has no automatic retention/deletion engine; destructive execution remains human-gated until policy, jurisdiction and legal hold are defined.
- HTTP logs contain route templates, status, request ID, duration and authenticated tenant ID only; no query/body/token is logged.
- Metrics contain no tenant, identity or content labels.
- Backups contain the same classifications as the database and require external encryption, access, retention and deletion controls.

## Acceptance criteria

- security/privacy tests first fail on raw details and missing audit events;
- all 401 variants return the same safe contract;
- 403 authorization and CSRF contracts are distinct but non-enumerating;
- missing and cross-tenant 404 responses are byte-equivalent except request ID;
- duplicate and concurrent conflicts expose no run/state/decision text;
- validation responses never include submitted credential or brief content;
- SQLite denial events persist across restart and remain tenant-scoped;
- PostgreSQL denial events written by one instance are read by another;
- metrics report bounded denial reasons and no tenant/permission labels;
- frontend `RuntimeApiError` exposes code/detail/request ID;
- threat/privacy/data-classification documents pass program validation and critique;
- full frontend, locked wheel, PostgreSQL and recovery regressions pass.

## Out of scope

- managed IdP, SSO, MFA or account recovery;
- edge DDoS/WAF or global API request quotas;
- cryptographic audit-ledger signing/export;
- automated retention/deletion or legal-hold execution;
- production database role creation/rotation;
- external browser/video/publishing/media integrations;
- durable API idempotency keys, handled by INC-004;
- cloud/staging deployment, merge or production authorization.
