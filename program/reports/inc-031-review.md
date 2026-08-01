# INC-031 Independent Verification

Date: 2026-07-31
Candidate commit: `30974c7698382d04a11cf4765b0fef0690762328`
Rollback commit: `fe75c5f563e97cda38f4fe0a7c05f9c455000474`
Graph revision: 0
Decision: TECHNICAL PASS; exact-head remote CI and merge remain pending.

## Independent results

- workload rollback report validation: PASS;
- real OCI rollback: PASS, RTO 1,863 ms <= 30,000 ms;
- locked installed wheel: 387 tests PASS;
- PostgreSQL 15 runtime: 387 tests PASS, schema-history v1-v9 matrix PASS, cleanup PASS;
- frontend: 58 tests PASS, lint PASS, build PASS;
- production package: PASS with Buildah;
- API contract, semantic evals, compliance, operability and Graph Harness validation: PASS;
- OCI/provider authority: external side effects disabled;
- Git diff check: PASS.

The implementation tree is clean and the report contains no credential material. Candidate and rollback workloads use the same port and database directory without overlapping writers. The original run remains readable, a new run is writable after rollback, and the final audit chain and head verify independently.

Remote exact-head CI and GitHub review are intentionally not claimed by this report; they will be recorded after publication.
