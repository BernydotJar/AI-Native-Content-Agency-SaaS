# Current Operational State

Updated: 2026-07-21T21:43:50Z
Program phase: active
Release recommendation: `DENY_RELEASE`
Cloud recommendation: `DENY_APPLY`

## Repository and delivery truth

- Root: `/workspace`
- Repository: `BernydotJar/AI-Native-Content-Agency-SaaS`
- Active branch: `agent/inc-004-idempotency`
- Stacked base: `agent/production-readiness@c52684b66da42e11af11ecdf3a48ea1d9ae7b818`
- Exact locally verified INC-004 implementation: `f3fb67d382f34ec40ed9f2bb18b02a3dc65c1546`
- Active branch remote: absent; push pending after the checkpoint commit containing this document
- PR `#3`: ready, eight of eight jobs green at `c52684b`, normal merge blocked by `REVIEW_REQUIRED`
- Merge: authorized by the user, attempted normally, not performed; no admin bypass or auto-merge was used
- Deployment, persistent infrastructure, package publication and spend: not authorized and not performed

## Completed checkpoint

### INC-012 — PostgreSQL migration/runtime authority separation

Status: `done`

Exact published head `c52684b` and GitHub Actions run `29869283309` preserve the non-owner PostgreSQL runtime boundary. `F-009` is closed. Persistent environment observation remains separate under `F-004`, `SEC-013` and `BLK-GCP-001`.

## Active increment

### INC-004 — Durable command idempotency and Greenlight fencing

Status: `review`
Owner: Backend Engineer / Security Critic
External effects: none

Exact local commit `f3fb67d` implements:

- required bounded `Idempotency-Key` for run create and Greenlight approve/reject/revoke;
- tenant- and operation-scoped deterministic command receipt IDs derived from a SHA-256 key digest;
- canonical request fingerprints binding operation, resource, authenticated subject and payload;
- exact committed-response replay without persisting or returning the raw key;
- uniform `409 idempotency_conflict` for incompatible key reuse;
- transactional mutation plus receipt in SQLite and PostgreSQL;
- PostgreSQL advisory locking on a dedicated connection, outside the application pool transaction;
- compatible and incompatible cross-replica race handling with provider/package execution once;
- authenticated subject binding for decision/revocation identity, ignoring client attribution text;
- Greenlight revocation, fencing-token increment, Publisher blocking and stale-effect rejection;
- exact future-effect guard over Greenlight ID, token, artifact IDs/hashes, channel and budget;
- browser retry-key retention after ambiguous failures and invalidation after brief changes;
- accessible Greenlight revocation state/control;
- OpenAPI header and revoke endpoint contracts;
- ADR, operator documentation, threat-model and spec updates.

## Exact local verification at `f3fb67d`

```text
Focused idempotency/fencing                 PASS — 9/9
Locked Python wheel                         PASS — 97 tests, 11 PostgreSQL-only skips
PostgreSQL multi-replica/recovery            PASS — 97/97
Frontend lint/tests/build                    PASS — 0 findings, 35/35, build
Production package                          PASS — Buildah non-root live smoke
Helm/Terraform/K3s                          PASS — both storage modes
Workflow lint                               PASS
Gitleaks worktree                           PASS — no leaks
Supply chain                                PASS — clean source, SBOM, policy, provenance, Cosign offline
TypeScript/Python/shell static validation    PASS
Whitespace                                  PASS
```

Evidence limitations:

- the active branch is not yet pushed and has no exact-head CI;
- session issuance is deliberately not idempotent because replay would require recoverable session/CSRF secrets;
- a crash before the transactional receipt may repeat deterministic local sandbox work; no external effect exists today;
- any future external provider requires a durable outbox, provider idempotency token, receipt and revocation contract;
- receipt snapshots increase audit-ledger growth and retention load;
- no persistent database, cloud resource, traffic or external provider was changed.

`F-002` remains HIGH/IN_PROGRESS until the published exact head passes CI. `ENG-005` and `SEC-012` are `weak_evidence` pending remote verification.

## Open global HIGH release findings

1. **F-002 — Durable command idempotency and Greenlight revocation/fencing.** Local remediation verified; push and exact CI pending.
2. **F-004 — Authorized staging/cloud runtime observation.** Owner: `INC-006`; externally gated.
3. **F-007 — Manual accessibility evidence.** Owner: `INC-008`.
4. **F-008 — Production backup scheduling, encryption/KMS, immutable off-host retention and alerts.** Owner: `INC-005`.
5. **F-010 — Retention, deletion, legal hold and data-subject workflow.** Owner: `INC-011` plus accountable human reviewers.
6. **F-011 — Semantic/adversarial evaluation harness.** Owner: `INC-010`.

Open CRITICAL findings: zero.

## Exact blockers

### BLK-PR-REVIEW-001

- Category: human decision / repository policy
- Evidence: PR `#3` is mergeable and 8/8 green, but GitHub reports `REVIEW_REQUIRED`; no eligible review exists.
- Attempted resolution: normal merge after explicit user authorization; GitHub rejected it.
- Independent work remaining: yes; INC-004 is executing on a stacked branch.
- Resume condition: an eligible independent reviewer approves PR `#3`, then the authorized normal merge may proceed.

### BLK-GCP-001

- Category: credential / permission / infrastructure / human decision
- Evidence: no authorized target, billing, reviewed saved plan/apply or runtime endpoint.
- Independent work remaining: yes.
- Resume condition: explicit authorized target, billing, preflight, reviewed saved plan, independent approval and spend/apply authorization.

### BLK-PRIVACY-001

- Category: human decision / legal review / data
- Evidence: jurisdiction, operating entity, customer role and effective retention/deletion/legal-hold policy remain unknown.
- Independent work remaining: yes.
- Resume condition: identified jurisdiction/entity/customer, approved source/version/effective date and accountable privacy/legal, security and business reviewers.

## Ready work

1. Commit this INC-004 checkpoint, push `agent/inc-004-idempotency`, verify remote SHA and create a stacked draft PR against `agent/production-readiness`.
2. Require all eight exact-head CI jobs and repair failures.
3. Close `F-002`, `ENG-005`, `SEC-012` and INC-004 only after exact-head CI passes.
4. Continue `INC-005`, `INC-010` and `INC-008` independently of review/cloud/privacy blockers.

## Exact continuation condition

Resume from the checkpoint commit directly above `f3fb67d382f34ec40ed9f2bb18b02a3dc65c1546`. Push normally, verify the remote ref, create the stacked draft PR with base `agent/production-readiness`, inspect all exact-head checks and repair every failure. Do not retarget or merge the stacked PR until PR `#3` is merged. Production and GCP remain `DENY_RELEASE` / `DENY_APPLY`.
