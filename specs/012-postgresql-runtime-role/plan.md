# Plan

1. Add an ephemeral verifier precondition that rejects the current superuser/owner runtime model and observe RED.
2. Add explicit `initialize|validate` schema modes and strict schema validation to the adapter/runtime.
3. Add a packaged schema operator command with environment-only URL handling.
4. Create migration/runtime roles and exact grants in the ephemeral PostgreSQL gate.
5. Execute the complete shared-state suite using the non-owner runtime URL.
6. Add negative ownership/schema CREATE/DDL/TRUNCATE tests and missing/incompatible schema tests.
7. Update Helm and operations/persistence/security documentation.
8. Run locked wheel, PostgreSQL/recovery, Helm, frontend/program and critique gates.
9. Persist evidence, commit, push, verify SHA, update draft PR and inspect exact-commit CI.
