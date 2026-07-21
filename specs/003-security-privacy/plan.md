# Plan

1. Map trust boundaries, data flows, stored fields, logs, metrics, error paths and tenant predicates for the selected runtime.
2. Write failing API and frontend tests for uniform public errors, validation redaction, security headers, denial audit and cross-instance PostgreSQL durability.
3. Add a strict public error contract and sanitized exception handlers.
4. Add standalone tenant-scoped audit writes to SQLite/PostgreSQL and record authenticated authorization/CSRF denials.
5. Add low-cardinality denial metrics and frontend error-code support.
6. Write selected-architecture threat, privacy and data-classification/retention records.
7. Run focused tests, full frontend, locked wheel, PostgreSQL/recovery and program gates.
8. Perform producer-independent critique for metadata leakage, audit flooding, sensitive logs, tenant crossing and unsupported privacy claims.
9. Repair findings, update evidence/state, commit, push, verify remote SHA, update draft PR and inspect exact-commit CI.
