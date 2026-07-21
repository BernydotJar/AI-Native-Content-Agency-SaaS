# INC-004 Verification Review

Date: 2026-07-21
Branch: `agent/inc-004-idempotency`
Base: `agent/production-readiness@c52684b66da42e11af11ecdf3a48ea1d9ae7b818`
Exact verified implementation commit: `f3fb67d382f34ec40ed9f2bb18b02a3dc65c1546`
Status: `LOCAL_VERIFIED_PENDING_PUSH_CI`

## Review contract

```yaml
task_id: INC-004
workstream_id: WS-04
producer: Backend Engineer
critic: Security and Data Correctness Reviewer
fixer: Backend/Frontend Engineer
independent_verifier: SQLite/PostgreSQL/frontend/package/infrastructure/supply-chain gates
objective: >
  Add durable compatible replay, uniform incompatible conflicts and Greenlight
  revocation/fencing without enabling an external side effect.
external_effects: NONE
```

## Implemented boundary

- Business mutations require a bounded `Idempotency-Key`.
- Raw keys are SHA-256 digested and never persisted, logged or returned.
- Tenant plus operation plus key digest produces the deterministic audit receipt ID.
- Operation, resource, authenticated subject and canonical payload produce the request fingerprint.
- Mutation, exact response snapshot and receipt commit in one database transaction.
- Compatible replay returns the original document; incompatible reuse returns a sanitized 409.
- PostgreSQL uses a dedicated session advisory lock so concurrent replicas execute local provider work once without holding an application-pool transaction.
- Client reviewer text is non-authoritative; the authenticated subject is stored and audited.
- Approved Greenlight starts at fence `1`; revocation increments the fence, preserves evidence and blocks Publisher.
- Future effect authorization requires active status, exact Greenlight ID/token, artifacts, channel and budget.
- The browser retains one key through ambiguous retry and discards it when the command changes or succeeds.
- Session creation remains non-retryable because exact replay would require retaining credential material.

## Critic findings resolved

| Finding | Severity | Resolution | Evidence |
|---|---|---|---|
| Deterministic run ID returned duplicate conflict instead of replay | HIGH | durable receipt and exact response snapshot | restart/replay tests |
| Concurrent replicas could repeat package/provider work | HIGH | dedicated PostgreSQL advisory command lock | compatible race tests |
| Same key with changed content lacked stable conflict | HIGH | subject/resource/payload fingerprint and public `idempotency_conflict` | SQLite/PostgreSQL negatives |
| Raw key could become receipt material | HIGH | only digest-derived ID and fingerprint persist | SQL/audit absence tests and Gitleaks |
| Client reviewer text could impersonate another principal | HIGH | persisted reviewer/revoker is authenticated subject | RBAC identity test |
| Approved Greenlight lacked revocation/fencing | HIGH | revoke endpoint, fence increment and exact effect guard | revocation and stale-envelope tests |
| Browser retries generated new commands | MEDIUM | in-memory command-key lifecycle with payload invalidation | component retry test |
| Receipt snapshot increases audit growth | MEDIUM residual | documented capacity/retention impact | ADR 0008 and operations docs |
| Crash before receipt may repeat local deterministic work | MEDIUM residual | external effects remain disabled; future provider requires outbox/receipt | ADR 0008 and threat model |

## Executed evidence

| Gate | Result | Observed |
|---|---|---|
| focused idempotency tests | PASS | 9/9, including OpenAPI, replay, conflict, raw-key absence, revocation and effect guard |
| `./scripts/verify-python-locks.sh` | PASS | agency-runtime 0.7.0, pip check, 97 tests with 11 PostgreSQL-only skips |
| `./scripts/verify-postgresql-runtime.sh` | PASS | PostgreSQL 15.18, 97/97, cross-replica compatible/incompatible races, package-once, migration and restores |
| frontend lint/tests/build | PASS | zero lint findings, 35/35 tests, production build |
| production package | PASS | Helm guards and Buildah non-root live runtime smoke |
| local infrastructure | PASS | Terraform/Helm/K3s plan-apply-destroy for both storage modes |
| workflow and secret checks | PASS | actionlint and Gitleaks worktree with no findings |
| supply chain | PASS | clean source, pinned bases, SBOM, Grype/license policy, provenance and offline Cosign |
| static/whitespace | PASS | Python compile, TypeScript, Bash syntax and `git diff --check` |

## Evidence limitations

- The branch is local and has no remote CI yet.
- PostgreSQL/K3s resources were disposable; no persistent environment changed.
- Agentless K3s does not prove pod scheduling.
- Session issuance is deliberately excluded from replay.
- No real provider, publishing, media generation, browser automation or spend was activated.
- A future effectful provider needs durable outbound idempotency and receipts in addition to inbound command replay.
- Receipt snapshots increase database, backup and retention volume.

## Release decision

```yaml
INC_004: REVIEW
F_002: IN_PROGRESS
ENG_005: weak_evidence
SEC_012: weak_evidence
push: PENDING
exact_head_ci: PENDING
release: DENY_RELEASE
cloud_apply: DENY_APPLY
```

## Exact continuation

Commit the program checkpoint, push `agent/inc-004-idempotency`, verify the exact remote SHA and create a draft PR based on `agent/production-readiness`. Require all eight jobs. Close the finding and requirement gaps only after exact-head CI succeeds. The stacked PR cannot be merged before PR `#3` and must not bypass its required review.
