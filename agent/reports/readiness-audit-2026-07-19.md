# Production Foundation V1 — Readiness Audit

Audit timestamp: 2026-07-19T19:08:21Z

Committed HEAD: `34c3489ac39f5a69a3b782cde9171486d3e8be91`

Working state: repaired source increment remains uncommitted

Draft PR: `#2`; tracking issue: `#1`

## Executive verdict

| Scope | Verdict | Reason |
|---|---|---|
| Local application implementation | `PASS_LOCAL` | Backend, contracts, migrations, frontend and live transport gates are green. |
| Real PostgreSQL boundary | `PASS_LOCAL` | Fresh migrations, same-key single execution, cross-tenant denial and application recreation passed. |
| Terraform code and policy | `PASS_LOCAL` / `DENY_APPLY` | Four critic code findings are repaired and role-separated review is green; no eligible target or real plan exists. |
| Executable evaluation evidence | `PASS_REPAIR`; final result pending | Tamper/governance negatives and Docker gates pass; checked-in results remain intentionally stale until the final source commit. |
| Current-tree GitHub CI | `NOT_RUN` | The prior green run evaluates only `34c3489`, not this source tree. |
| GitHub deploy eligibility | `FAIL_CLOSED` | Required checks/environments exist, but variables are absent and the sole collaborator cannot satisfy non-self review. |
| GCP dev deployment | `BLOCKED_BY_EXTERNAL_DEPENDENCY` / `DENY_APPLY` | Six billing accounts are closed; targets, parent, region, plan, cost and reviewer evidence are absent. |
| Release | `DENY_RELEASE` | Exact-tree eval result, commit/push, CI and final evaluation are still required. |

This audit approves neither merge nor release nor cloud apply.

## Verified repair increment

### Application and concurrency

- FastAPI `/api/v1` owns mission, run, artifact/evidence, decision, audit and idempotency state.
- Alembic `0003_approval_idempotency` binds each decision directly to its command key and fails closed on unsafe legacy provenance.
- A deterministic tenant/key transaction owner precedes replay and provider work. PostgreSQL uses transaction-local `lock_timeout=5000ms` plus `pg_advisory_xact_lock`; isolated SQLite uses `BEGIN IMMEDIATE`.
- A prior evaluator passed 12/12 approval races and 12/12 start races with one durable command and exactly one seven-tool workflow. Six timeout negatives proved rollback and redacted 503 behavior.
- The root real-PostgreSQL gate then applied migrations 0001–0003 on a fresh volume, returned two equal 201 responses with one run/idempotency/audit and seven tool records, denied cross-tenant reads/approval, recreated the application, and removed its exact volume.
- Current backend evidence remains 58 pytest cases plus seven legacy unittest subtests, Ruff, mypy over 15 modules, OpenAPI drift and migration round-trip gates.

### Browser and container lifecycle

- The served React SPA uses real FastAPI/PostgreSQL transport with no `page.route`, fetch interception or mocked network.
- A first fresh restart run exposed a process-control defect: `docker compose start app` traversed the completed migration service and returned nonzero even though the durable row recovered. The failure and cleanup are recorded.
- The corrected app-only restart gate passed approval, rejection and exact restart restoration 3/3 in five seconds on a new owned volume, then removed only that generated project/volume.
- Both runtime and integration images execute as UID 10001. `httpx2` is absent from the default/final runtime and present only in the hash-locked, non-deployed `postgres-integration` stage.
- Frontend evidence remains 47 unit/component tests plus lint, typecheck, OpenAPI mapping and build.

### Terraform critic repairs

- The runtime service-account member must have exactly `roles/cloudsql.client`, `roles/cloudsql.instanceUser`, `roles/logging.logWriter` and `roles/monitoring.metricWriter`; missing or extra roles fail.
- Runtime planning accepts only the exact foundation `agency-images/app@sha256` path. The Cloud SQL Auth Proxy equals one source-reviewed release/digest. Post-apply compares application, migration and proxy images by container name.
- Registry cleanup keeps 20 recent versions and the immediate predecessor bearing `rollback-current`. Planning binds the current digest; only after exact attestation, authentication and granular preflight may apply recheck it and move the tag.
- The apply identity's tag role has exactly `artifactregistry.tags.create` and `artifactregistry.tags.update`; it cannot upload/delete artifacts or mutate repository policy.
- Post-apply compares all three WIF providers/claims, all phase impersonation policies, plan/apply state-prefix bindings, complete repository IAM, the 16-permission runtime role and the two-permission tag role.
- `PLATFORM_SKIP_EVAL_RESULTS=1 scripts/validate_platform.sh` passed nine configuration validates, 24 Terraform mock tests, 65 platform script tests, 61 static controls, repository integrity, YAML, Compose and diff checks. Result remains `DENY_APPLY`.

### Evaluation and governance

- Nineteen eval/governance tests reject fabricated all-PASS reports, altered catalog/source/aggregate/gate claims, stale commits, blank ownership, cycles, phase disorder and active write conflicts.
- The catalog maps all 52 requirements to 28 executable gates, including the fresh PostgreSQL and live UI/API/PostgreSQL gates.
- Governance currently validates 38 typed tasks, a 23-edge ordered critical path, 41 unique findings, 67 evidence items, 31 risks, the mandatory phase chain and zero active write-lock conflicts.
- `agent/eval-results.json` is intentionally not current. The required lifecycle is: commit source; run the full harness against that source commit; add only the generated result; validate and commit that result separately.

## External and process blockers

1. The repaired source tree is not committed or pushed; run `29672994585` is historical only.
2. Exact-tree GitHub Actions and `EVAL-INC-004` have not run.
3. The deploy workflow is not on `main`, all required Actions variables are absent, and the one collaborator cannot be both dispatcher and protected reviewer.
4. Interactive visual/accessibility QA is unavailable because the required in-app browser exposed no browser instance; Playwright behavior does not close that manual gate.
5. Six visible billing accounts are closed. Candidate project `ai-native-content-agency-saas` is billing-disabled, unlabeled, unadopted and has unknown provenance/role; it cannot silently serve both bootstrap and dev.
6. No parent, region, distinct target IDs, permissions/quota result, saved plan JSON, price estimate, plan critique or `ALLOW_DEV_APPLY` exists.

## Exact next gates

1. Finish documentation/trace updates and commit source without `agent/eval-results.json`.
2. Run the full strict harness against that source commit; every local gate must pass even though external requirements remain blocked.
3. Commit only the bound eval result, push, and obtain the exact four required GitHub checks.
4. Run the final evaluator on the exact committed/CI tree, preserving `DENY_RELEASE` and `DENY_APPLY` wherever external evidence is absent.
5. Update PR `#2` and issue `#1`; keep the PR draft and unmerged.

## Cost and effects

- GCP mutation: none.
- External publication, advertising activation or spend: none.
- Observed cloud infrastructure cost: `$0` from this work.
- Docker resources were local and disposable; owned test volumes were removed.
- Future Cloud SQL, Cloud Run, registry, storage, logging and egress costs remain unknown until an authorized target-region plan exists.
