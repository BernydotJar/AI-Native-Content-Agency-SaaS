# INC-001 / INC-002 Review Record

Date: 2026-07-21
Branch: `agent/production-readiness`
Scope: trustworthy program baseline, version consistency, documentation reconciliation, SQLite/PostgreSQL backup and restore
Release effect: none
External infrastructure effect: none

## Producer result

```yaml
task_id: INC-001, INC-002
status: PASS
summary: >
  Established machine-validated program state, normalized version 0.7.0,
  repaired contradictory architecture claims, and implemented strict SQLite and
  PostgreSQL backup/restore tooling with representative ephemeral drills.
files_inspected:
  - AGENTS.md
  - checkpoints/production-readiness-012.md
  - README.md
  - backend/agency_runtime/*
  - backend/tests/*
  - scripts/verify-postgresql-runtime.sh
  - docs/OPERATIONS.md
  - docs/POSTGRESQL_PERSISTENCE.md
  - PR #2, PR #3, issue #1 and CI rollups
files_modified:
  - program/**
  - specs/001-program-baseline/**
  - specs/002-backup-restore/**
  - package.json
  - package-lock.json
  - backend/agency_runtime/version.py
  - backend/agency_runtime/api.py
  - backend/agency_runtime/observability.py
  - backend/agency_runtime/__init__.py
  - backend/tests/test_program_state.py
  - backend/tests/test_backup_restore.py
  - scripts/validate-program-state.py
  - scripts/manage-runtime-backup.py
  - scripts/verify-postgresql-runtime.sh
  - .github/workflows/production-readiness.yml
  - Dockerfile
  - README.md
  - docs/IMPLEMENTATION_AUDIT.md
  - docs/OPERATIONS.md
  - docs/POSTGRESQL_PERSISTENCE.md
  - docs/runbooks/runtime-backup-restore.md
human_gates:
  - merge
  - external release
  - production deployment
  - persistent data replacement
  - external infrastructure and spend
```

## Spec-compliance review

Result: PASS for the bounded increments.

- Required program artifacts exist and parse.
- The task graph covers all 12 workstreams, references existing tasks and is acyclic.
- Traceability contains 78 unique requirements across every required domain.
- Npm, Python package, runtime API, metrics, Helm and OCI metadata report `0.7.0`.
- README and implementation audit no longer claim that backend transport, PostgreSQL or individual identity are absent.
- Current state explicitly records `DENY_RELEASE`, `DENY_APPLY`, the parallel-branch architecture decision and the lack of GCP/staging evidence.
- SQLite backup uses the online backup API, strict checksum/integrity validation, private files and atomic installation.
- PostgreSQL backup uses custom format, removes owner/ACL data, rejects ambient libpq authority, keeps the URL/password out of argv/output and validates the archive.
- SQLite replacement is explicit and refuses WAL/SHM sidecars.
- PostgreSQL restore requires an empty operator-created target and one transaction.
- Both restored backends were verified through application persistence classes with representative state.

## Critic findings and repairs

| Finding | Severity | Resolution |
|---|---|---|
| Program state could drift silently. | HIGH | Added stdlib validator, six negative regression tests and CI gate. |
| Frontend `0.0.0` contradicted runtime/chart `0.7.0`. | MEDIUM | Normalized all surfaces and added executable version drift detection. |
| README and audit mixed legacy/no-PostgreSQL claims with current implementation. | MEDIUM | Reconciled architecture, persistence, package and cloud evidence boundaries. |
| Backup copied/live-WAL risk. | HIGH | SQLite uses `Connection.backup`; source is read-only and restored DB passes integrity. |
| Backup manifest could be altered/traversed/oversized. | HIGH | Strict fields, basename rule, 64 KiB limit, byte size, SHA-256 and backend marker. |
| PostgreSQL password/URL or ambient libpq settings could escape authority boundary. | HIGH | URL remains in named env; `PG*` is cleared; `.pgpass` is disabled; output redacts password. |
| PostgreSQL process could hang indefinitely. | MEDIUM | Added bounded 1–86,400 second command timeout, default 3,600. |
| Restore could overwrite active SQLite or non-empty PostgreSQL state. | HIGH | Explicit SQLite replace + sidecar guard; PostgreSQL zero-table guard; negative drills. |
| A post-replace directory `fsync` failure could be reported as no mutation. | MEDIUM | State-aware error reports that target was installed and requires inspection. |
| Checksum is integrity but not authenticity/encryption. | MEDIUM | Runbook states limitation; signed/encrypted off-host retention remains open. |

Open CRITICAL/HIGH findings created by this slice: zero.

## Independent verification pass

The verifier reran the exact working tree after critic repairs:

| Gate | Command | Observed result |
|---|---|---|
| Program schema/version | `npm run validate:program` | PASS; 78 requirements, 11 tasks, 22 required files, version 0.7.0 |
| Program negative tests | `python3 -m unittest backend.tests.test_program_state -v` | PASS; 6/6 |
| Backup unit/adversarial tests | `python3 -m unittest backend.tests.test_backup_restore -v` | PASS; 11/11 |
| Frontend lint | `npm run lint` | PASS; zero warnings/errors |
| Frontend interaction/runtime | `npm test -- --reporter=dot` | PASS; 33/33 in 10 files |
| Frontend bundle | `npm run build` | PASS; Vite production bundle |
| Locked Python wheel | `./scripts/verify-python-locks.sh` | PASS; agency-runtime 0.7.0, pip check, 68 tests with 7 PostgreSQL-only skips |
| Shared PostgreSQL + recovery | `./scripts/verify-postgresql-runtime.sh` | PASS; 68/68, SQLite restore, migration, replay guard, PostgreSQL non-empty guard, restore equivalence/application read |
| Patch hygiene | `git diff --check` | PASS |

## Evidence limitations

- The drills are local and ephemeral; no scheduled, encrypted, immutable or off-host backup exists.
- No authorized staging/production database, cloud target, workload scheduler, alert route or incident exercise was used.
- SHA-256 manifests are not signatures.
- A real persistent restore remains a destructive-data human gate.
- The reviewer roles were separated procedurally in one execution system; final release approval still requires a distinct accountable human.

## Release-gate decision

`INC-001`: PASS for integration into the feature branch.

`INC-002`: PASS for integration into the feature branch.

Global release: `DENY_RELEASE`; unresolved HIGH findings remain in threat/privacy, idempotency and staging evidence outside this slice.
