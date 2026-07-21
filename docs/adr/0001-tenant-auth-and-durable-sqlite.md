# ADR 0001: Tenant authentication and durable SQLite runtime state

- Status: accepted
- Date: 2026-07-21

## Context

The first network-addressable runtime kept executions in process memory and exposed run and Greenlight endpoints without authentication. That was sufficient for a deterministic local vertical slice but unsafe for a multiuser pilot. A durable shared database service is not yet provisioned, and enabling an external identity provider would require credentials and deployment decisions outside this repository.

## Decision

1. Require bearer credentials for every `/api/v1/*` endpoint.
2. Derive tenant identity exclusively from a server-side mapping supplied through `AGENCY_TENANT_API_KEYS_JSON`; do not trust a tenant header or request-body field.
3. Store only SHA-256 credential fingerprints in the authenticator's in-process lookup structure and compare candidates with `hmac.compare_digest`.
4. Persist complete run and Greenlight documents in SQLite under the composite key `(tenant_id, run_id)`.
5. Namespace memory records by tenant in the same database.
6. Return `404` when an authenticated tenant requests another tenant's run, avoiding cross-tenant existence disclosure.
7. Reference credentials through an existing Kubernetes Secret; never render secret values in the chart.
8. Use one replica, a ReadWriteOnce PVC, and `Recreate` deployment strategy while SQLite is the runtime store.
9. Refuse Helm rendering when persistence is enabled with more than one replica.

## Consequences

### Positive

- Run and approval state survives service restart.
- Tenant isolation is enforced at authentication, persistence, and memory boundaries.
- The package fails readiness when authentication is not configured.
- No external identity or database credentials are fabricated.

### Trade-offs

- API keys identify a tenant, not an individual human. `reviewer` remains an auditable tenant-supplied label until user-level identity is integrated.
- SQLite is a single-writer deployment and does not provide high availability.
- API-key rotation currently requires updating the Secret and restarting the workload.
- The next scale milestone requires a shared database and a managed identity provider or signed token verifier.

## Rejected alternatives

- Trusting `X-Tenant-ID`: rejected because the caller could select another tenant.
- Unauthenticated local mode in production: rejected; API endpoints return `503` when auth is unconfigured.
- Two SQLite replicas sharing a PVC: rejected because it creates unsafe concurrency and rollout behavior.
- Migrating to `agency_swarm`: rejected as unrelated to the security and persistence problem and unsupported by demonstrated value.
