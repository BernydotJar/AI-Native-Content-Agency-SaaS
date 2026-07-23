# INC-018 — Durable asynchronous run execution

## Problem

The orchestrator currently completes all eight stations inside `POST /api/v1/runs`.
The UI receives only the terminal state, so the topology cannot display truthful live
progress and a process crash has no station-level recovery point.

## Objective

Persist a run before work starts, execute stations through a durable worker contract and
expose monotonic station progress through polling or server events without browser timers
that invent state.

## Invariants

1. `POST /runs` persists and returns an accepted run before station execution.
2. A lease/fence allows only one active worker per run.
3. Every station transition is durable and tenant-scoped.
4. Completed stations are idempotent and never execute twice after replay.
5. A crashed lease can be recovered only after expiry and a new fence.
6. Greenlight remains impossible until required stations are terminal.
7. Cancellation/revocation prevents new station work.
8. API/UI never infer progress not stored by the backend.

## States

`queued → running → awaiting_greenlight → completed|rejected|revoked|failed`

Station states: `idle → queued → processing → ready|failed|cancelled`.

## Acceptance

- SQLite and PostgreSQL worker/lease/fence tests.
- Cross-replica single-executor test.
- Crash recovery and idempotent station completion tests.
- UI polling/event test showing multiple real states.
- No external provider, publication or media side effect during verification.
