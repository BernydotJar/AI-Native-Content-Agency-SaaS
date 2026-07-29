# INC-017 — Usable campaign output and deterministic run reuse

## Problem

A repeated mission currently returns a generic `409` even though the exact tenant-scoped
run already exists. The workspace also devotes primary screen area to provider and
integration diagnostics while the publishable post output is hidden inside generic
artifacts.

## Actors and jobs

- Operator: define a mission, obtain channel-ready drafts and reopen the same result.
- Approver: inspect the exact post output, evidence and Greenlight state.
- Tenant admin: inspect model providers and integration configuration outside the main job.

## Functional requirements

1. Repeating the exact brief with a new idempotency key returns the existing run as a
   safe resource replay and records a new command receipt.
2. Reusing an idempotency key for a changed brief remains a uniform `409`.
3. The API marks resource replay explicitly and does not increment run-created metrics.
4. The primary workspace displays post drafts by channel from the versioned `copy_deck`.
5. Each draft exposes hook, body, CTA, combined copy, claim-review state and publication
   readiness.
6. Context/evidence is available through compact progressive disclosure.
7. Provider and integration diagnostics live in Settings/Admin, not the main journey.
8. No button claims external publication while external effects remain disabled.

## Non-functional requirements

- Tenant isolation and server-side authorization remain unchanged.
- Raw idempotency keys, provider secrets and social credentials never enter responses.
- Keyboard, focus, reflow and reduced-motion contracts remain intact.
- No fake progress animation may be introduced.

## Empty/degraded states

- No run: explain that output appears after a mission is created or opened.
- No copy deck: show a bounded “writer output unavailable” state.
- Greenlight pending/rejected/revoked: show exact publication blocker.
- Clipboard unavailable: copy action reports failure without losing the draft.

## Acceptance evidence

- Backend idempotency/resource-reuse tests.
- Frontend output and progressive-disclosure tests.
- Full frontend build and Chromium regression.
- Locked Python and PostgreSQL regression.
- Production package and supply-chain gates before promotion.
