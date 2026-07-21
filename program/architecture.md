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
  -> durable audit, sessions, rate-limit state, runs and Greenlight
```

The multi-stage OCI image serves the SPA and FastAPI as UID/GID 10001. Helm and Terraform currently describe a Kubernetes deployment. PostgreSQL can provide shared application state but is not provisioned by the selected Terraform module.

## Authority and data boundaries

- Tenant, subject, role, key ID, and permissions derive from server configuration or a validated server session.
- Browser sessions use HttpOnly/SameSite cookies and an in-memory CSRF token.
- Machine clients use bearer credentials.
- Runs, sessions, audit events, authentication-rate buckets, and memories are stored in SQLite or PostgreSQL.
- Greenlight stores exact artifact IDs and hashes but currently lacks a client idempotency-key contract and post-approval revocation.
- Tools are deterministic sandbox adapters. They perform no external publication, media generation, navigation, repository mutation, or ad spend.

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

- no durable idempotency-key ledger for mutable API commands;
- no post-approval Greenlight revocation protocol;
- no asynchronous lease/outbox/worker model for future effectful tools;
- no object store for media or large artifacts;
- no managed IdP, SSO, MFA, recovery, or lifecycle provisioning;
- no implemented retention/deletion engine;
- no executed backup/restore or deployment rollback evidence at baseline;
- no live alert routing, traces, soak/load evidence, or staging runtime observation;
- no selected and authorized cloud target;
- two frontend experiences remain in parallel: deterministic cinematic simulation and backend-backed production console.
