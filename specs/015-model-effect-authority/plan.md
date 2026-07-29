# Plan

1. Add a canonical preflight descriptor to `ModelGateway`.
2. Add SQLite/PostgreSQL v4 model-effect intent stores and least-privilege grants.
3. Implement reserve, fenced execute, durable result/receipt, replay, unknown, revoke and reconciliation.
4. Add explicit admin-only run integration and stable `model_completion` artifact attachment.
5. Add failure injection, cross-replica races, replay repair and zero-egress tests.
6. Expose truthful provider status: durable authority available, automatic integration false.
7. Extend package, infrastructure, privacy and operability contracts.
8. Keep real credentials, egress and spend disabled pending explicit authorization.
