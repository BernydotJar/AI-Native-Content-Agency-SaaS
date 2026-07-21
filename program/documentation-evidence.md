# Documentation Evidence Register

| Document | Current authority | Evidence boundary |
|---|---|---|
| `AGENTS.md` | execution policy | governs repository actions, not product behavior |
| `program/constitution.md` | program principles | normative |
| `program/current-state.md` | operational state | must be updated at every checkpoint |
| `program/architecture.md` | selected architecture | must match code and tests |
| `docs/IMPLEMENTATION_AUDIT.md` | historical implementation audit | reconciled through exact local and remote INC-012 verification at `1002d07`; not a production approval |
| `docs/OPERATIONS.md` | runtime operations | alert section is recommendation, not exercised evidence |
| `docs/POSTGRESQL_PERSISTENCE.md` | PostgreSQL behavior, schema modes and limits | implementation contract and exact local non-owner gate are verified; persistent provisioning, scheduling, encryption and failover remain external |
| `docs/runbooks/postgresql-schema-rollout.md` | migration/runtime role rollout and rollback | executable operator contract; persistent role/schema/Secret/traffic mutations remain human-gated and unobserved |
| `docs/runbooks/runtime-backup-restore.md` | executable recovery procedure | exact local SQLite/PostgreSQL restore paths pass under separated authority; persistent restore remains human/external |
| `docs/LOCAL_INFRASTRUCTURE_VALIDATION.md` | local infra gate | proves K3s API/admission, not pod scheduling |
| `checkpoints/*` | immutable historical checkpoints | may be superseded by current program state |
| PR #2 documents | donor evidence on another branch | not evidence for PR #3 until ported and reverified |

Known documentation repairs in `INC-001`:

- remove README claims that the SPA has no backend transport;
- remove claims that PostgreSQL is unimplemented;
- align version claims at `0.7.0`;
- distinguish local package/K3s evidence from deployment;
- point readers to `program/current-state.md` for live status.

| `docs/security/threat-model.md` | selected-runtime security model | records implemented controls and open HIGH production gates; not release approval |
| `docs/privacy/privacy-model.md` | privacy architecture and uncertainty | jurisdiction/policy remain UNKNOWN and human-gated |
| `docs/privacy/data-classification-retention.md` | data inventory and retention decision register | no policy or destructive execution is authorized |
| `program/reports/inc-003-review.md` | bounded security/privacy review | historical bounded review at `a9f063f`; its PostgreSQL residual was subsequently closed by INC-012 at `1002d07` |
| `program/reports/inc-012-progress.md` | PostgreSQL authority implementation checkpoint | completion evidence at `1002d07` with eight-job exact-head CI run `29868899218`; persistent staging remains external |
