# INC-004 Completion Review

Date: 2026-07-21
Branch: `agent/inc-004-idempotency`
Base: `agent/production-readiness@c52684b66da42e11af11ecdf3a48ea1d9ae7b818`
Exact remotely verified head: `bc01fa7b54341865f848c0754884cc83f660a0c7`
GitHub Actions run: `29871278876`
Draft PR: `#4`
Status: `CHECKPOINT_COMPLETED`

## Outcome

Durable inbound command replay and Greenlight revocation/fencing are implemented, locally verified, committed, pushed and verified by exact-head CI.

```yaml
increment: INC-004
workstream: WS-04
status: CHECKPOINT_COMPLETED
implementation_head: bc01fa7b54341865f848c0754884cc83f660a0c7
remote_sha: bc01fa7b54341865f848c0754884cc83f660a0c7
pull_request: 4
ci_run: 29871278876
ci_jobs_passed: 8
ci_jobs_failed: 0
F_002: CLOSED
ENG_005: proven
SEC_012: proven
production_status: DENY_RELEASE
cloud_status: DENY_APPLY
external_effects: NONE
```

## Proven boundary

- Governed business mutations require a bounded idempotency key.
- The raw key is never persisted, logged or returned.
- Tenant, operation and key digest identify one transactional receipt.
- Operation, resource, authenticated subject and canonical payload identify compatibility.
- Compatible replay returns the original response; incompatible reuse returns uniform 409.
- SQLite replay survives restart.
- PostgreSQL compatible/incompatible races serialize without holding a pool transaction and execute package/provider work once.
- Client reviewer text is not authority; the authenticated subject is persisted and audited.
- Greenlight revocation increments its fencing token, preserves evidence and blocks Publisher.
- A future effect guard checks active state, Greenlight identity, token, artifacts, channel and budget.
- The browser reuses one key after ambiguous failure and invalidates it after command changes or success.

## Local evidence

| Gate | Result | Observed |
|---|---|---|
| focused idempotency/fencing | PASS | 9/9 including OpenAPI, replay, conflict, key absence, revocation and effect guard |
| locked wheel | PASS | agency-runtime 0.7.0; 97 tests, 11 PostgreSQL-only skips |
| PostgreSQL | PASS | PostgreSQL 15.18; 97/97; cross-replica races, package-once, migration and restores |
| frontend | PASS | lint zero, 35/35 tests and production build |
| package | PASS | Helm guards and Buildah non-root live runtime smoke |
| local infrastructure | PASS | Terraform/Helm/K3s both storage modes |
| workflow and secrets | PASS | actionlint and zero effective Gitleaks findings |
| supply chain | PASS | clean source, pinned bases, SBOM, Grype/license policy, provenance and offline Cosign |

## Remote evidence

GitHub Actions run `29871278876` completed successfully at exact head `bc01fa7`:

- `workflow-lint`;
- `verify`;
- `python-locks`;
- `postgresql-shared-state`;
- `container`;
- `helm`;
- `terraform`;
- `supply-chain`.

## Residual boundaries

- PR `#4` is intentionally draft and stacked on PR `#3`.
- Session issuance is excluded because replay would require storing recoverable session/CSRF secrets.
- Receipt snapshots increase database, audit, backup and retention volume.
- A future external provider needs outbound outbox/idempotency/receipt/revocation controls.
- No real provider, persistent environment, deployment, publication or spend occurred.
- Five unrelated HIGH release findings remain open.

## Merge gate

PR `#3` remains `REVIEW_REQUIRED` despite 8/8 checks and a normal authorized merge attempt. PR `#4` must remain draft and stacked until PR `#3` receives an eligible independent approval and merges normally. No admin bypass is authorized or appropriate.
