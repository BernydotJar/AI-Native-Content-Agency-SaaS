# Plan

1. Extend audit writes with an optional deterministic event ID and tenant-scoped event lookup.
2. Implement a service-level command receipt helper using request fingerprints and the existing transactional audit ledger.
3. Require `Idempotency-Key` on run and Greenlight business mutations.
4. Add persisted Greenlight fencing/revocation fields and an exact future-effect authorization guard.
5. Add SQLite/API RED tests, then PostgreSQL concurrency/replay tests.
6. Update the TypeScript client and operator console contract.
7. Run focused, cross-workstream, package, infrastructure, secret and supply-chain gates.
