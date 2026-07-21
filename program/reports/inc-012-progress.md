# INC-012 Verification Review

Date: 2026-07-21
Branch: `agent/production-readiness`
Exact verified implementation commit: `612e03c1a90f644a8cd26fde785f3980491bab9d`
Remote branch at review: `a9f063fc7db531a86822b58f603473a71247a903`
Status: `LOCAL_VERIFIED_PENDING_PUSH_CI`

## Review contract

```yaml
task_id: INC-012
workstream_id: WS-07
producer: Security Reviewer / Data Engineer
critic: Production Security Reviewer
fixer: Backend/Data Engineer
independent_verifier: exact local gate suite
objective: >
  Separate PostgreSQL schema migration authority from application runtime
  authority and prove a non-owner least-privilege runtime role without weakening
  shared state, tenant isolation, migration, recovery or deployment contracts.
external_effects: NONE
```

## Implemented boundary

- Runtime is restricted to `validate`; explicit operator CLI owns `initialize`.
- Initialization uses one advisory-locked transaction for DDL, metadata and validation.
- Validation checks schema, relkind, required columns, sequence and exact version.
- Application connections fix `search_path=pg_catalog,public` before entering the pool.
- Migration/runtime identities are distinct, non-superuser and non-role-creating.
- Runtime owns zero application objects, has CONNECT without TEMPORARY and USAGE without CREATE.
- Runtime grants are exact per table/sequence; no blanket ownership or ALL PRIVILEGES.
- Helm/Terraform expose only validate mode and the runtime Secret to application pods.
- Migration and restore use migration authority and are verified using runtime reads afterward.

## Critic findings resolved

| Finding | Severity | Resolution | Evidence |
|---|---|---|---|
| Implicit runtime DDL authority | HIGH | Explicit initialize/validate boundary; app rejects initialize before connect | PostgreSQL gate and schema CLI tests |
| Partial DDL on incompatible initialize | HIGH | Validation moved into the same transaction | incompatible initialize rollback marker |
| Unsafe object resolution | HIGH | fixed `pg_catalog,public`; URL override rejected | connection tests and runtime `SHOW search_path` |
| Relation-name-only validation | MEDIUM | relkind and required columns checked | wrong-type and missing-column guards |
| psql role variables were not expanded | HIGH harness defect | quoted client substitution moved to heredocs | exact passing role inventory |
| GRANT exit code could misclassify a no-op | MEDIUM harness defect | warning and authoritative ACL are both checked | grant escalation marker |
| Package gate expected old enumerating 403 | HIGH verification drift | exact uniform public error and bounded denial audit required | Buildah package smoke |
| Secret fixtures triggered a generic scanner | MEDIUM | ambiguous source patterns removed; only exact historical fingerprints retained | Gitleaks worktree/range PASS |

## Executed evidence

| Gate | Result | Observed |
|---|---|---|
| `./scripts/verify-postgresql-runtime.sh` | PASS | PostgreSQL 15.18; 85/85; roles, ownership, grants, schema guards, atomic rollback, denials, migration and restores |
| `./scripts/verify-python-locks.sh` | PASS | agency-runtime 0.7.0; pip check; 85 tests, 8 expected PostgreSQL skips |
| `npm run validate:program` | PASS | version 0.7.0; 79 requirements; 12 tasks; 27 required files |
| frontend lint/tests/build | PASS | 0 lint findings; 33/33; production build |
| `./scripts/verify-production-package.sh` | PASS | Helm guards and Buildah non-root live runtime smoke |
| `./scripts/verify-local-infrastructure.sh` | PASS | Terraform 1.15.8, Helm 4.2.0 and K3s 1.36 plan/apply/destroy for both storage modes |
| `actionlint` | PASS | workflow syntax and expressions |
| Gitleaks 8.30.1 | PASS | worktree and 31-commit `origin/main..HEAD` range |
| `./scripts/verify-supply-chain.sh` | PASS | clean source, pinned bases, SBOM, Grype/license policy, provenance and offline Cosign verification |
| `git diff --check` | PASS | no whitespace defects |

## Evidence limitations

- PostgreSQL and K3s resources were disposable; no persistent environment changed.
- Agentless K3s proves API/admission and Terraform lifecycle, not pod scheduling.
- Cosign used an ephemeral offline key and made no registry publication.
- Five accepted supply-chain HIGH findings remain under an expiring baseline dated 2026-08-21.
- Push and exact-head CI remain pending; prior `a9f063f` CI is not reused.
- Staging/cloud observation remains a separate external gate.

## Release decision

```yaml
INC_012: REVIEW
F_009: IN_PROGRESS
SEC_013: weak_evidence
push: PENDING
exact_head_ci: PENDING
persistent_environment_observation: NOT_RUN
release: DENY_RELEASE
cloud_apply: DENY_APPLY
```

## Exact continuation

Commit the program checkpoint, push the exact branch, verify the remote SHA, update PR `#3`, require all eight exact-head jobs and repair any failure. Close `F-009` and `INC-012` only after that evidence. Merge is authorized only after those conditions are true; deployment and external infrastructure remain prohibited.
