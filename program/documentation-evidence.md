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
| `docs/adr/0008-durable-command-idempotency-and-greenlight-fencing.md` | inbound command replay and effect fencing decision | exact local and remote evidence at `bc01fa7`; future external providers still require outbound receipts |
| `specs/004-durable-idempotency/` | INC-004 operational specification | implementation and eight-job exact-head CI pass; external effects remain out of scope |
| `program/reports/inc-004-progress.md` | INC-004 bounded review | completion evidence at `bc01fa7` with exact-head run `29871278876` |

| `ops/slo-catalog.json`, `ops/alert-catalog.json`, `ops/alert-exercises.json` | INC-005 operability contracts | exact local validation at `6a88582`; persistent monitoring/paging not observed |
| `scripts/verify-operability.py` | fail-closed SLO/rule/runbook/exercise validator | 4 SLOs, 7 alerts and 8 exercises pass locally; exact CI pending |
| `docs/runbooks/incident-response.md` and `docs/runbooks/release-rollback.md` | incident and rollback procedures | local rule linkage and control-plane rollback proven; human/staging drills pending |
| `program/reports/inc-005-progress.md` | INC-005 bounded review | local evidence at `6a88582`; external backup/monitoring gates remain open |
