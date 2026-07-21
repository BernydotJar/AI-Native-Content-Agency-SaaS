# Documentation Evidence Register

| Document | Current authority | Evidence boundary |
|---|---|---|
| `AGENTS.md` | execution policy | governs repository actions, not product behavior |
| `program/constitution.md` | program principles | normative |
| `program/current-state.md` | operational state | must be updated at every checkpoint |
| `program/architecture.md` | selected architecture | must match code and tests |
| `docs/IMPLEMENTATION_AUDIT.md` | historical implementation audit | contains stale baseline rows and must be reconciled |
| `docs/OPERATIONS.md` | runtime operations | alert section is recommendation, not exercised evidence |
| `docs/POSTGRESQL_PERSISTENCE.md` | PostgreSQL behavior and limits | repository backup/restore drill is proven; provisioning, scheduling, encryption and failover remain external |
| `docs/runbooks/runtime-backup-restore.md` | executable recovery procedure | local SQLite/PostgreSQL contract; persistent restore and deployment controls remain human/external gates |
| `docs/LOCAL_INFRASTRUCTURE_VALIDATION.md` | local infra gate | proves K3s API/admission, not pod scheduling |
| `checkpoints/*` | immutable historical checkpoints | may be superseded by current program state |
| PR #2 documents | donor evidence on another branch | not evidence for PR #3 until ported and reverified |

Known documentation repairs in `INC-001`:

- remove README claims that the SPA has no backend transport;
- remove claims that PostgreSQL is unimplemented;
- align version claims at `0.7.0`;
- distinguish local package/K3s evidence from deployment;
- point readers to `program/current-state.md` for live status.
