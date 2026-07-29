# ADR 0007: Use PostgreSQL for shared durable runtime state

- **Status:** Accepted
- **Date:** 2026-07-21
- **Decision owners:** Runtime and platform maintainers

## Context

The initial runtime persisted runs, audit events, browser sessions, authentication failures and memories in SQLite. That design is useful for local execution and one-replica packaging, but a SQLite file is not a safe coordination boundary for independently scheduled application replicas. In particular, horizontal replicas require shared session revocation, shared rate limiting, serialized Greenlight decisions and a common audit ledger.

The existing deployment chart also exposed a contradiction: increasing the replica count could create multiple application processes without a shared transactional state backend.

The repository supply-chain policy denies LGPL dependencies. The first PostgreSQL prototype used Psycopg, whose selected packages were identified as LGPL-3.0-only by package metadata. Weakening the policy would have changed an established acceptance criterion for convenience.

## Decision

Add PostgreSQL as an explicit shared-state backend while retaining SQLite as the default local and single-replica backend.

When `AGENCY_DATABASE_URL` is configured, one `PostgresRuntimeDatabase` owns a bounded pool and provides PostgreSQL implementations for:

- run state and transactional audit writes;
- audit-ledger reads;
- browser sessions;
- authentication-rate-limit buckets;
- tenant-scoped memories.

Use `pg8000` instead of weakening the license policy. Pin the driver and transitive dependency graph by hash.

Separate schema authority from runtime authority. An explicit `agency-runtime-schema initialize` command, executed with a migration/operator credential, initializes schema version `1` under a PostgreSQL advisory transaction lock. Long-running application processes default to `validate`, perform only read-only relation/version checks and fail startup when schema is absent, incomplete or incompatible. Helm and Terraform permit only `validate` for application pods.

Use transactions, row locks, uniqueness constraints and optimistic run versions to preserve cross-replica consistency. A committed Greenlight decision cannot be replaced by another replica.

Expose only the name and key of a pre-provisioned Kubernetes Secret through Helm and Terraform. The database URL is not a Terraform input and therefore is not stored in Terraform state by this module.

Reject horizontal replicas in SQLite mode. Permit rolling multi-replica deployment and a PodDisruptionBudget only in PostgreSQL mode.

Provide an offline SQLite-to-PostgreSQL utility that is dry-run by default, requires an empty target, copies all supported runtime tables in one transaction and rejects replay to a non-empty target.

## Consequences

### Positive

- Sessions, rate limits, run state, audits and memories are consistent across replicas.
- PostgreSQL transactions bind a business-state mutation to its audit event.
- Startup detects absent, incomplete or unsupported schema instead of executing DDL or rewriting metadata.
- A compromised runtime credential is not an object owner and cannot initialize, alter, drop or truncate runtime schema.
- SQLite remains a lightweight local path and existing default behavior remains available.
- The driver remains compatible with the repository license policy.
- Terraform state contains Secret references, not database credentials.

### Negative

- Operators must provision, secure, back up and monitor PostgreSQL separately.
- Operators must manage a distinct migration credential, execute schema rollout before application rollout and review exact DML grants for every schema change.
- Each replica consumes up to its configured pool maximum.
- The SQLite migration requires a write outage and does not provide continuous synchronization or reverse migration.
- Schema upgrades beyond version `1` require a future migration framework and ADR.
- A pure-Python driver and repository-owned small pool increase the amount of connection lifecycle code that must be tested and maintained.

## Alternatives considered

### Continue with SQLite and one replica

Rejected as the only production topology because it cannot provide horizontal availability or shared revocation/rate limiting. It remains supported for local and explicitly single-replica use.

### Mount one SQLite file into multiple replicas

Rejected. Shared filesystem access does not turn SQLite into an application-level distributed coordination service, and filesystem locking semantics vary across volume implementations.

### Use Psycopg and add LGPL to the allowlist

Rejected. The dependency was technically suitable, but changing the established license control was unnecessary because a permissively licensed driver passed the required PostgreSQL contract.

### Provision PostgreSQL inside this Terraform module

Rejected. Database lifecycle, backup, high availability and credentials are infrastructure- and provider-specific. This repository consumes an approved endpoint through an existing Secret rather than pretending to manage that lifecycle safely.

### Build online dual-write migration

Rejected for this increment. Dual writes introduce ordering, retry and reconciliation failure modes. The current system has an explicit offline cutover utility with a smaller, verifiable safety boundary.

## Verification

The acceptance gate must demonstrate:

- installation of the backend wheel using only hash-locked dependencies;
- complete backend tests against a real local PostgreSQL server;
- two runtime instances sharing runs, audits, sessions, rate limits and memories;
- concurrent Greenlight conflict protection;
- fail-closed URL, pool and schema-version validation;
- dry-run and applied SQLite migration with source-to-target count equality;
- rejection of migration replay;
- Helm positive and negative guards for backend/replica/PDB combinations;
- Terraform validation without database credentials in state;
- license and vulnerability policy checks on the rebuilt production image.
