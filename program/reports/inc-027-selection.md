# INC-027 Selection Record

Date: 2026-07-30

## Selection

Graph Engineer selected `F-013` as the highest-priority useful, safe and unlocked gap after `INC-026` became human-gated.

## Why this node

- It is an active security/data-integrity weakness at the authenticated boundary.
- A valid principal can currently create unlimited denial-audit rows.
- The implementation is local, deterministic and independently verifiable.
- It does not depend on staging, credentials, legal policy, provider access, deployment or branch-protection authority.

## Scope control

The node adds a bounded durable counter, not a new authentication system, API gateway or distributed cache. It reuses existing principal resolution, shared stores, metrics, Helm/Terraform contracts and Graph Harness gates.
