# Current Product Architecture

Updated: 2026-07-21
Status: active architecture record; runtime claims require executable evidence

## Selected runtime

```text
React 19 / TypeScript / Vite SPA
  -> same-origin FastAPI API
  -> TenantAuthenticator and RBAC
  -> RuntimeService
       -> SQLiteRunStore + SQLiteMemory for local/single replica
       -> PostgresRunStore + PostgresMemory for shared replicas
       -> deterministic eight-agent AgencyOrchestrator
       -> sandbox-only tool adapters
       -> immutable integration-review registry (GET-only; no executor)
  -> durable audit, sessions, rate-limit state, runs and Greenlight
```

The multi-stage OCI image serves the SPA and FastAPI as UID/GID 10001. Helm and Terraform currently describe a Kubernetes deployment. PostgreSQL can provide shared application state but is not provisioned by the selected Terraform module.

## Authority and data boundaries

- Tenant, subject, role, key ID, and permissions derive from server configuration or a validated server session.
- Browser sessions use HttpOnly/SameSite cookies and an in-memory CSRF token.
- Machine clients use bearer credentials.
- Runs, sessions, audit events, authentication-rate buckets, and memories are stored in SQLite or PostgreSQL.
- Inbound run/Greenlight commands use durable idempotency, exact artifact binding, revocation and fencing. Social publication and explicit model operations each use separate default-disabled durable intents, unique effect bindings, fenced execution, bounded provider receipts, unknown-state reconciliation and audit repair.
- Station tools remain deterministic sandbox adapters. Social publication adapters exist behind an explicit disabled-by-default authority; no real publication, media generation, navigation, repository mutation or ad spend was performed.
- Reviewed external candidates are immutable package data exposed through authenticated GET endpoints; `video-use` remains `reviewed_disabled` with no executable adapter.

## Deployment evidence boundary

The active branch contains no GCP module, configured target, saved GCP plan, apply record, endpoint, or runtime observation. The parallel PR `#2` contains a separate static GCP/Cloud Run foundation and a separate `control_plane` backend. It is unmerged and not proof that the selected runtime is deployed.

Current executable infrastructure evidence is limited to:

- OCI image build/runtime smoke;
- Helm lint/template and negative guards;
- Terraform validation and an agentless K3s API/admission drill;
- PostgreSQL local runtime and migration verification.

Agentless K3s does not prove pod scheduling. OCI smoke does not prove Kubernetes workload readiness. Neither proves GCP deployment.

## Parallel-branch reconciliation

`feat/production-foundation-v1` and `agent/production-readiness` diverged from `main` and implement overlapping control planes. The program will:

1. retain `agency_runtime` as the selected runtime for this branch;
2. inventory reusable controls from the parallel branch;
3. port them as isolated increments with tests;
4. avoid wholesale merge/cherry-pick of the alternate backend;
5. require a human architecture decision before deleting or superseding either open PR.

## Known architectural gaps

- durable asynchronous station leases/checkpoints and social publication intent/receipt authority exist; model inference still requires its separate durable effect integration;
- no enabled browser/video provider adapter; the exact `video-use` review remains disabled on HIGH findings;
- no object store for media or large artifacts;
- no managed IdP, SSO, MFA, recovery, or lifecycle provisioning;
- no implemented retention/deletion engine;
- no executed backup/restore or deployment rollback evidence at baseline;
- no live alert routing, traces, soak/load evidence, or staging runtime observation;
- no selected and authorized cloud target;
- one backend-backed cinematic workspace remains; browser state is presentation, never execution authority.

## Campaign intelligence and political authority boundary — 2026-07-25

```text
Authenticated operator/approver
  -> structured Campaign Brief
  -> Research claim ledger
       -> source + locator
       -> verification_status
       -> server-bound reviewed_by
  -> Strategy / Growth / Writer / Media
  -> Critique Agent
       -> evidence coverage
       -> source/disclosure visibility
       -> office relevance
       -> legal review status
       -> unsupported-promotion check
  -> Human Greenlight
  -> Social publication authority
       -> general flag
       -> independent political flag
       -> exact artifact/media/account binding
```

Evidence verification and legal approval are not trusted from arbitrary client text. A request that marks either approved must be authenticated with `greenlight:decide`; the server replaces client-supplied reviewer identities with the authenticated subject. Political publication remains blocked unless both general social authority and the separate political authority are enabled.

INC-021 deliberately stops at `media_plan`. INC-022 owns the object/media boundary and post-publication read-after-write verification. No current architecture claim treats a provider-returned ID alone as proof of a publicly visible post.
