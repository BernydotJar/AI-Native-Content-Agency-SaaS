# Current Operational State

Updated: 2026-07-21
Program phase: active
Release recommendation: DENY_RELEASE
Cloud recommendation: DENY_APPLY

## Repository truth at session start

- Root: `/workspace`
- Branch: `agent/production-readiness`
- Baseline HEAD: `b9e88fe91dd6db7894dcf5825ca63c2294f52377`
- Remote branch HEAD at baseline: same SHA
- Working tree at baseline: clean
- Upstream: not configured
- Draft PR: `#3`, open against `main`
- Baseline PR checks: eight of eight successful at run `29850087928`
- Merge: not authorized and not performed

## Parallel implementation

PR `#2` (`feat/production-foundation-v1`) remains open and unmerged. It contains an alternate SQLAlchemy/Alembic control plane and a static GCP/Cloud Run path. Its head is `583a47c5d5f0f03cfafcba8db21a85372666d09e`; the latest inspected rollup contains a failed platform job. Earlier commits have historical green evidence. None of that branch is runtime evidence for PR #3.

The selected architecture on this branch remains `backend/agency_runtime`. Controls from PR #2 may be ported only through bounded specs and same-scope regression. Closing, merging or superseding either PR remains a human architecture decision.

## Increments completed in this working tree

### INC-001 — Trustworthy baseline and version contract

- Created operational `program/` state, 12-workstream ledger, DAG, risk/finding/evidence registers, 78-row traceability and completion audit.
- Added a stdlib fail-closed validator plus six negative tests for missing/drifting/duplicate/cyclic state.
- Added the validator to the `verify` CI job.
- Normalized npm, Python, FastAPI, health/readiness, metrics, OCI and Helm version surfaces at `0.7.0`.
- Reconciled README and implementation-audit claims with the selected runtime and actual deployment boundary.
- Recorded `DENY_APPLY`: no GCP target, plan/apply, endpoint or runtime observation exists.

### INC-002 — SQLite/PostgreSQL backup and restore

- Added `agency-runtime-backup.v1` manifests with strict fields, 64 KiB maximum, byte size, SHA-256, UTC timestamp, backend validation and private file modes.
- SQLite uses the online backup API, integrity checks, atomic installation, sidecar guard and explicit replacement.
- PostgreSQL uses controlled libpq environment, custom-format `pg_dump`, archive listing, empty-target guard and transactional `pg_restore`.
- Ambient `PG*` variables and `.pgpass` authority are disabled; URL/password do not enter argv/output; command timeouts are bounded.
- Added 11 unit/adversarial tests and an executable recovery runbook.
- Extended the PostgreSQL gate to restore representative SQLite and PostgreSQL state and verify run/audit/session/rate-limit/memory equivalence through application persistence classes.

Detailed review: [`program/reports/inc-001-002-review.md`](reports/inc-001-002-review.md).

## Exact validation observed after critic repairs

- `npm run validate:program`: PASS — version `0.7.0`, 78 requirements, 11 tasks, 22 required files.
- `python3 -m unittest backend.tests.test_program_state -v`: PASS — 6/6.
- `python3 -m unittest backend.tests.test_backup_restore -v`: PASS — 11/11.
- `npm run lint`: PASS — zero warnings/errors.
- `npm test -- --reporter=dot`: PASS — 33/33 in 10 files.
- `npm run build`: PASS.
- `./scripts/verify-python-locks.sh`: PASS — hash-locked wheel `0.7.0`, `pip check`, 68 tests with seven PostgreSQL-only skips.
- `./scripts/verify-postgresql-runtime.sh`: PASS — 68/68 including shared-state tests, migration, replay guard, both restore drills and cleanup.
- `git diff --check`: PASS.

These are working-tree/local results until committed and pushed. Remote CI for the new tree is not yet evidence.

## Findings closed by the increments

- Stale frontend version `0.0.0` versus runtime/chart `0.7.0`.
- README/audit claims that backend transport, PostgreSQL or individual identity were absent.
- Absence of executable program-state drift detection.
- Absence of repository SQLite/PostgreSQL backup/restore tooling and local restore evidence.
- Ambient libpq credential/configuration authority in the new backup tool.
- Silent overwrite/non-empty-target recovery paths.

## Remaining global HIGH findings

1. No selected-architecture threat model or privacy model.
2. Mutable API commands lack durable idempotency-key replay; duplicate delivery can produce conflict rather than the committed response.
3. No authorized staging/cloud workload execution or runtime observation.

## Remaining material gaps

- scheduled, encrypted, immutable/off-host backups and a restore exercise in an authorized environment;
- application/data rollback drill against immutable image/schema compatibility;
- SLOs, alert rules, alert exercise, incident response and tracing decision;
- managed identity, SSO/MFA and lifecycle provisioning;
- retention/deletion policy and accountable privacy/legal review;
- Greenlight revocation before any future external effect;
- complete loading/empty/partial/degraded/conflict/read-only UX;
- four political themes and a truly entitlement-gated premium theme;
- manual keyboard, screen-reader, contrast, zoom/reflow and reduced-motion evidence;
- semantic/adversarial eval harness;
- versioned external adapters, including any `browser-use/video-use` evaluation;
- GCP or other cloud target, cost/permission plan, apply, endpoint smoke and no-drift evidence.

## Active increment

`INC-003` — selected-architecture threat model, privacy model, data classification and executable adversarial repairs.

## Human gates

- merge either PR;
- publish a release/image/package externally;
- select or create external infrastructure and incur spend;
- apply persistent infrastructure;
- replace or delete persistent data;
- enable browser/video automation, real media generation, publishing, ads or spend;
- approve retention, legal or sensitive privacy decisions;
- approve production deployment.
