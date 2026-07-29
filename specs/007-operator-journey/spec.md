# INC-007 — Backend-first operator journey and degraded states

## Problem

The durable FastAPI runtime is exposed through one production panel, but the interface treats most failures as one red paragraph, enables actions without explaining role authority, and does not distinguish session restoration, empty audit, conflict, rate limit, dependency outage, read-only access or stale run recovery. Non-technical operators cannot reliably understand what is safe, what is blocked and what action to take next.

## Purpose

Make the backend-backed console the authoritative operator journey for authenticated work while keeping the cinematic simulator explicitly separate and side-effect free.

## Actors

- viewer: inspect identity, run evidence and audit; no mutations;
- operator: create governed runs; no Greenlight decision;
- approver: inspect and decide Greenlight; no run creation;
- admin: create, decide and revoke;
- auditor/supporting reviewer: diagnose with request IDs without receiving secrets.

## Journeys

1. Resume a valid HttpOnly session without exposing credentials.
2. Explain unauthenticated, restoring and authenticated states.
3. Create a run only when the server-derived role permits it.
4. Keep the same idempotency key across ambiguous retries.
5. Classify authorization, conflict, rate-limit, not-found, validation and dependency failures.
6. Recover a stale run by reloading it from the backend.
7. Expire local session state on authentication failure.
8. Refresh audit with explicit loading, empty, success and failure states.
9. Preserve all external-effect and publication boundaries.

## Functional requirements

- FR-001: initial session restoration has a named loading state and live announcement.
- FR-002: server-derived role determines create/decision/revoke controls.
- FR-003: insufficient authority is rendered as read-only guidance, not as a hidden control or leaked permission string.
- FR-004: `401` clears local session/run/audit state and requests reauthentication.
- FR-005: `403`, `404`, `409`, `422`, `429`, `503` and unknown failures map to distinct stable operator states.
- FR-006: every correlated failure exposes its request ID for support without exposing payload or credentials.
- FR-007: retryable dependency failures preserve the mutation idempotency key.
- FR-008: terminal conflict/not-found states offer backend run refresh when a run ID exists.
- FR-009: audit refresh exposes loading, empty, success and degraded states.
- FR-010: the current run can be refreshed through `GET /api/v1/runs/{run_id}`.
- FR-011: no credential is written to browser storage or retained after session exchange.
- FR-012: publication remains disabled and visually explicit in every run state.

## Non-functional requirements

- keyboard-operable controls and logical focus;
- visible `focus-visible` state inherited from the design system;
- `role=status` or `role=alert` chosen according to urgency;
- `aria-live` announcements without replacing focused controls;
- no state communicated only by color;
- no unbounded error content or internal permission names;
- responsive at 320 CSS px and zoom/reflow compatible;
- no new external dependency.

## States

`restoring_session`, `signed_out`, `authenticated`, `read_only`, `loading`, `empty`, `success`, `validation_error`, `authorization_denied`, `not_found`, `conflict`, `rate_limited`, `dependency_failure`, `session_expired`, `degraded`.

## Acceptance criteria

- focused component/API tests prove role-aware controls and all error classes;
- ambiguous retry reuses one command key;
- session expiry clears protected local state;
- run refresh resolves stale state;
- audit loading/empty/failure are distinguishable;
- existing end-to-end local package and backend contracts remain unchanged;
- no external effects, deployment, infrastructure or spend.

## Out of scope

- persistent cloud deployment;
- live provider/media/browser integrations;
- campaign publication;
- redesign of the cinematic simulator;
- manual screen-reader certification, which remains in INC-008.
