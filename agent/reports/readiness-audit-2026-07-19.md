# Production Foundation V1 — Readiness Audit

Audit timestamp: 2026-07-19T22:29:41Z

Latest committed implementation repair: `6ac004e71673521ae601523c85c7561cf3cfa6bd`

Working state: focused source commits exist locally; this refreshed governance audit is pending its source commit

Draft PR: `#2`; tracking issue: `#1`

## Executive verdict

| Scope | Verdict | Reason |
|---|---|---|
| Local application implementation | `PASS_LOCAL` | Backend, contracts, migrations, frontend and live transport gates are green. |
| Real PostgreSQL boundary | `PASS_LOCAL` | Fresh migrations, same-key single execution, cross-tenant denial and application recreation passed. |
| Terraform code and policy | `PASS_LOCAL` / `DENY_APPLY` | Four critic code findings are repaired and role-separated review is green; no eligible target or real plan exists. |
| Executable evaluation evidence | `PASS_LOCAL_THEN_STALE`; full rerun pending | A committed-source harness reached 37 PASS, 15 BLOCKED, zero failed/not-run; the subsequent CI-only source repair intentionally invalidates that result. |
| Current-tree GitHub CI | `FAIL_FOUND_AND_REPAIRED`; rerun pending | Run `29703195255` passed frontend/security and exposed canonical Ruff plus shallow result-provenance defects; focused local fixes are green. |
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
- `PLATFORM_SKIP_EVAL_RESULTS=1 scripts/validate_platform.sh` passed nine configuration validates, 24 Terraform mock tests, 65 platform script tests, 63 static controls, repository integrity, YAML, Compose and diff checks. Result remains `DENY_APPLY`.

### Evaluation and governance

- Nineteen eval/governance tests reject fabricated all-PASS reports, altered catalog/source/aggregate/gate claims, stale commits, blank ownership, cycles, phase disorder and active write conflicts.
- The catalog maps all 52 requirements to 28 executable gates, including the fresh PostgreSQL and live UI/API/PostgreSQL gates.
- The first full committed-source harness passed live Docker/Playwright, fresh PostgreSQL, functional backend, image, platform, repository-integrity and dependency gates. It failed closed on three B905 findings and 20 scripts outside canonical backend formatting; six external gates remained blocked.
- `TASK-HARNESS-RUFF-FIXER-016` made all unequal `zip` calls explicitly `strict=False` and applied the canonical backend Ruff configuration. Exact lint/58-file formatting, 19 evaluator/governance tests and the complete source-only platform gate now pass.
- Run `29703195255` then proved that backend CI had omitted the canonical Ruff config and platform checkout depth one hid the recorded source parent. Commit `6ac004e` fixes both and adds deterministic controls for their exact invariants.
- Governance currently validates 40 typed tasks, a 25-edge ordered critical path, 44 unique findings, 73 evidence items, 31 risks, the mandatory phase chain and zero active write-lock conflicts.
- `agent/eval-results.json` is intentionally not current. The required lifecycle is: commit source; run the full harness against that source commit; add only the generated result; validate and commit that result separately.

## External and process blockers

1. CI repair `6ac004e` plus this governance update are not pushed; run `29703195255` is exact only for the superseded result commit and remains useful failure evidence.
2. A regenerated exact-tree result, the next four-job GitHub Actions run and `EVAL-INC-004` remain pending.
3. The deploy workflow is not on `main`, all required Actions variables are absent, and the one collaborator cannot be both dispatcher and protected reviewer.
4. Interactive visual/accessibility QA is unavailable because the required in-app browser exposed no browser instance; Playwright behavior does not close that manual gate.
5. Six visible billing accounts are closed. Candidate project `ai-native-content-agency-saas` is billing-disabled, unlabeled, unadopted and has unknown provenance/role; it cannot silently serve both bootstrap and dev.
6. No parent, region, distinct target IDs, permissions/quota result, saved plan JSON, price estimate, plan critique or `ALLOW_DEV_APPLY` exists.

## Exact next gates

1. Commit this CI-finding governance update without `agent/eval-results.json`.
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
