# Program Constitution

Status: authoritative for the production-readiness program
Updated: 2026-07-21

## Product mission

Native / War Room must let a small content-agency team turn a client brief into a reviewable, tenant-isolated campaign package without pretending that sandbox evidence is live research, generated media, publication, advertising spend, or legal approval.

## Non-negotiable principles

1. **Truth before velocity.** Every capability is labeled as specified, implemented, tested, observed, deployed, or externally blocked. A manifest, test, PR, or green CI job is never promoted to runtime evidence outside its scope.
2. **Server-side authority.** Authentication, authorization, tenant binding, Greenlight decisions, artifact integrity, and durable state are enforced by the backend. Client-selected tenant or role data is never authoritative.
3. **Safe-by-default effects.** Publishing, ad spend, external infrastructure creation, credentials, and real provider calls remain disabled until a versioned adapter contract, independent review, and explicit human authorization exist.
4. **Exact reviewer intent.** Greenlight applies only to the exact reviewed artifact set and never means publication. A later effectful adapter must additionally provide idempotency, receipts, revocation, retry bounds, and replay protection.
5. **Operational evidence.** Backup, restore, rollback, alerts, readiness, incident response, and capacity are release gates that require executed evidence rather than configuration alone.
6. **Tenant and privacy boundaries.** Every durable business record is tenant scoped; logs and metrics minimize identity and content; data retention and deletion require explicit policy and human-approved destructive execution.
7. **Accessible operations.** Critical journeys must work with keyboard, visible focus, semantic structure, zoom/reflow, reduced motion, and non-color-only status communication.
8. **Reproducible delivery.** Locked dependencies, deterministic gates, non-root packaging, supply-chain evidence, and version consistency are mandatory.
9. **Human gates remain human.** Merge, production, spending, destructive migration, external publication, external infrastructure, and sensitive legal decisions are never inferred from technical success.
10. **Independent veto.** Producer evidence is reviewed separately. CRITICAL or HIGH findings prevent release unless closed or demonstrated as an external blocker with an exact resume condition.

## Architecture policy

The active implementation on `agent/production-readiness` uses `backend/agency_runtime` as its runtime source of truth. The open `feat/production-foundation-v1` branch is a donor of independently useful controls, not an automatically compatible successor. Controls may be ported only through bounded specs and regression gates; introducing a second production backend is prohibited without an explicit replacement migration plan.

## Required evidence states

Allowed completion-audit classifications are:

- `proven`
- `contradicted`
- `incomplete`
- `weak_evidence`
- `missing`
- `not_applicable_with_justification`

Program task states are:

- `pending`
- `spec_ready`
- `approved`
- `in_progress`
- `review`
- `done`
- `blocked`
- `superseded`

`done` applies to one increment only. It never implies that the global program is complete.
