# INC-012 Implementation Checkpoint Review

Date: 2026-07-21
Branch: `agent/production-readiness`
Parent checkpoint: `a9f063fc7db531a86822b58f603473a71247a903`
Foundation implementation commit: `df7fc7f878d8beb34fc956746a6bdfe34794f9f0`
Effective implementation head: `23bfee60f8536d2fcd7e3c5ca20636103f9401c8`
Remote branch head at review: `a9f063fc7db531a86822b58f603473a71247a903`
Status: `PARTIAL — IMPLEMENTED_LOCAL_STATIC_REVIEW_ONLY`

## Review contract

```yaml
task_id: INC-012
workstream_id: WS-07
producer: Security Reviewer / Data Engineer
critic: Production Security Reviewer
fixer: Backend/Data Engineer
independent_verifier: pending exact-worktree execution
objective: >
  Separate PostgreSQL schema migration authority from application runtime
  authority and prove a non-owner least-privilege runtime role without
  weakening shared state, tenant isolation, migration or recovery.
external_effects: NONE
human_gates:
  - persistent database role creation or credential rotation
  - persistent schema migration
  - external infrastructure or spend
  - merge
  - production deployment
```

## Implemented behavior

### Schema authority

- `PostgresRuntimeDatabase` accepts explicit `initialize|validate` modes.
- Its default is `validate`.
- `initialize` retains the advisory-locked schema creation path and validates the committed result.
- `validate` performs read-only catalog, relation-type, required-column, sequence and schema-version checks.
- Application `RuntimeService` rejects `initialize` before creating a database connection.
- Readiness reuses the same read-only schema validation contract.
- The packaged `agency-runtime-schema` command is the only repository entry point intended to initialize schema.
- SQLite-to-PostgreSQL migration now requires a pre-initialized target and uses `validate`.

### Connection hardening

- PostgreSQL URL options remain allow-listed; caller-controlled `search_path` is rejected.
- Every pg8000 application connection sets and commits `search_path=pg_catalog,public` before entering the pool.
- Connection setup failure closes the raw connection.
- Schema objects are created and validated explicitly in `public`.

### Least-privilege verifier contract

The rewritten ephemeral verifier is designed to prove:

- distinct bootstrap, migration and runtime login identities;
- migration and runtime are both non-superuser and lack `CREATEDB`, `CREATEROLE`, `REPLICATION` and `BYPASSRLS`;
- migration owns disposable databases and runtime objects;
- runtime owns zero database/schema/table/sequence/view objects;
- runtime receives `CONNECT` without `TEMPORARY`, schema `USAGE` without `CREATE`, exact table DML and exact sequence usage;
- runtime cannot create permanent or temporary tables, alter/drop/truncate objects, update schema metadata, grant itself privilege or assume the migration role;
- absent, incompatible, missing-relation, wrong-relation-type and missing-column schema states fail closed;
- migration and restore use migration authority while application reads use runtime authority;
- full shared-state tests are invoked with the runtime URL and a separately named migration URL only where the test intentionally mutates schema metadata.

### Deployment contract

- Helm exposes `runtime.storage.postgresql.schemaMode: validate`.
- Helm rejects `initialize` for long-running pods.
- Terraform exposes a validate-only `postgresql_schema_mode` and passes it to Helm.
- Application Deployments receive only the runtime URL Secret; no migration credential or migration Job was added.
- Production package and local infrastructure verification scripts now assert the validate-only setting.

### Operator documentation

- PostgreSQL persistence documentation now distinguishes migration and runtime authority.
- A new schema/role rollout runbook documents exact grants, initialization, validation, cutover, restore, rollback and human gates.
- Backup/restore documentation now requires restore under migration authority followed by runtime grants and runtime validation.
- ADR, operations, implementation-audit, README and threat-model claims were reconciled.

## Critic findings and repairs

| ID | Severity | Finding | Repair | State |
|---|---|---|---|---|
| C-012-01 | HIGH | Every `PostgresRuntimeDatabase` construction initialized schema, so application startup held DDL authority. | Added explicit modes; runtime defaults/restricts to `validate`; initialization moved to packaged operator command. | repaired in code; execution pending |
| C-012-02 | HIGH | The initial CLI draft referenced symbols/constructor arguments not implemented by the adapter. | Added stable schema constants/error/mode normalization and corrected constructor contract. | repaired statically |
| C-012-03 | HIGH | The original verifier inserted role checks before creating separate roles and could not prove non-owner operation. | Reordered the ephemeral cluster flow and added distinct role/database/grant setup. | repaired in script; execution pending |
| C-012-04 | HIGH | Helm could reject initialize while direct FastAPI environment configuration still allowed it. | `RuntimeService` now rejects application mode other than `validate` before connecting. | repaired statically |
| C-012-05 | MEDIUM | Relation-name existence alone could accept a view in place of a required table. | Validate PostgreSQL relkind and add wrong-type fixture. | repaired in code; execution pending |
| C-012-06 | MEDIUM | Same-version schema corruption could omit required columns while passing relation checks. | Added explicit required-column contract and missing-column fixture. | repaired in code; execution pending |
| C-012-07 | HIGH | Implicit `$user,public` resolution could permit object shadowing. | Reject URL search-path control and fix every connection to `pg_catalog,public`. | repaired in code; execution pending |
| C-012-08 | MEDIUM | Denying schema CREATE did not itself prove denial of temporary objects or role/GRANT escalation. | Revoke database TEMPORARY, encode exact privilege matrix and add negative temp/SET ROLE/GRANT cases. | repaired in verifier; execution pending |
| C-012-09 | MEDIUM | Task ownership and operator documentation did not cover all required CLI, Helm, Terraform and recovery paths. | Expanded bounded task paths and created rollout/recovery documentation. | repaired |
| C-012-10 | HIGH | `initialize` committed DDL before applying the complete schema contract, so an incompatible existing version could leave partial tables. | Validation now executes on the same advisory-locked transaction before commit; an incompatible-database fixture requires metadata preservation and no partial runtime table. | repaired statically; PostgreSQL execution pending |

No CRITICAL finding was identified in the static review. `F-009` remains HIGH/open because implementation has not yet been executed against its exact commit.

## Static validation executed

These checks do not constitute the required behavioral or integration gates.

| Check | Result | Scope and limitation |
|---|---|---|
| Python AST parse | PASS | Modified runtime, CLI, tests and migration script parse; no import/test execution |
| Bash `-n` | PASS | PostgreSQL, production-package and local-infrastructure verification scripts parse; commands were not executed |
| setup.cfg parse | PASS | `agency-runtime-schema` entry point is present |
| JSON/CSV/JSONL parse | PASS | Program records parse; program validator was not run |
| HCL delimiter balance | PASS | Basic brace balance only; Terraform binary was unavailable, so fmt/validate/plan were not run |
| obvious secret marker review | PASS | Added/modified text reviewed for common token/private-key markers; full secret scanner was not run |
| `git diff --check` / commit whitespace | PASS | No whitespace error in implementation commit |
| local implementation commits | PASS | foundation `df7fc7f878d8beb34fc956746a6bdfe34794f9f0` and atomic repair `23bfee60f8536d2fcd7e3c5ca20636103f9401c8` created |
| push / remote SHA / PR / CI | NOT_RUN | Deliberately withheld to avoid triggering tests after the user's explicit instruction |

## Required gates not run

```text
python3 -m unittest backend.tests.test_postgres_schema_cli -v
./scripts/verify-postgresql-runtime.sh
./scripts/verify-python-locks.sh
./scripts/verify-production-package.sh
./scripts/verify-local-infrastructure.sh
npm run validate:program
npm run lint
npm test
npm run build
actionlint
full secret scan
remote exact-head CI
```

No result from `a9f063f` is reused as evidence for effective local head `23bfee6`.

## External and human boundaries

No persistent role, credential, database, schema, Secret, Kubernetes resource, Terraform resource, endpoint or traffic was created or changed. No merge, deployment, publication, provider activation or spend occurred.

Persistent rollout remains gated on:

- authorized database/environment selection;
- managed migration/runtime credential creation;
- reviewed saved infrastructure/release plan;
- backup and rollback evidence;
- security/release approval;
- explicit apply/deployment authorization.

## Exact continuation condition

When test execution is authorized:

1. run focused schema/connection tests;
2. run the complete ephemeral PostgreSQL role, grant, DDL-denial, migration and restore gate;
3. repair every failure at root cause;
4. run locked-wheel, package, Helm/Terraform/local-infrastructure and frontend/program regressions;
5. run exact secret/workflow/supply-chain gates;
6. update evidence from `NOT_RUN` to observed results;
7. create a verification/checkpoint commit;
8. push normally, verify remote SHA, update draft PR `#3` and inspect exact-head CI;
9. keep `F-009` open until those checks and an appropriately authorized environment prove the same boundary.
