# Acceptance Checklist

Verification status: `NOT_RUN_ON_CURRENT_WORKTREE`. Checkboxes remain open until exact-commit gates execute.

- [ ] Migration and runtime identities are distinct.
- [ ] Runtime is non-superuser and cannot create databases/roles.
- [ ] Runtime owns no database, schema, table or sequence.
- [ ] Runtime lacks schema CREATE and table TRUNCATE.
- [ ] CREATE/ALTER/DROP/TRUNCATE negative tests fail safely.
- [ ] Runtime DML/application suite passes.
- [ ] Validate mode performs no DDL and rejects absent/incompatible schema.
- [ ] Migration, replay, backup/restore and tenant isolation remain green.
- [ ] URLs/passwords do not enter argv/log/evidence.
- [ ] Helm defaults to validate and rejects invalid values.
- [ ] Production role creation/migration remains human-gated.
