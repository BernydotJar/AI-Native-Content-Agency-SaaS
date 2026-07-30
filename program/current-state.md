# Current Program State

Updated: 2026-07-29

## Exact repository state

- Workspace: `7759306b-d1ea-40ed-92dc-b78424c749ba`
- Active branch: `agent/inc-037-gcp-staging-bootstrap`
- Local checkpoint before the applied-infrastructure receipt: `a389fc9c2421b5a8dd66da752491f5f14ee295cd`
- Remote INC-037 implementation commit before this receipt: `c88b5a1f763ac76420754d7283a4d4a490d6fc00`
- INC-037 draft PR: #30, stacked on INC-036 PR #29
- INC-034 draft PR: #27
- INC-035 draft PR: #28
- INC-036 draft PR: #29
- Audited Cloud Sandbox `git_push` remains blocked by nested-Docker `iptables` setup;
  the repository-owned Git Data publisher is the verified delivery fallback.
- Social publication, political publication, paid media, model effects, release and merge:
  none.

## INC-037 GCP staging foundation

The operator explicitly authorized project billing and the reviewed bootstrap apply.
The authenticated target is project `ai-native-content-agency-saas`, project number
`970393454298`, region `us-central1`.

Applied control-plane foundation:

- project billing enabled;
- monthly project budget: COP 64,000;
- current-spend alerts: 5%, 25% and 100%, or COP 3,200, COP 16,000 and COP 64,000;
- ten required Google APIs enabled and managed by Terraform;
- Artifact Registry repository `campaignos` in `us-central1`;
- active cleanup policies: delete versions older than 30 days and retain at least the
  five most recent versions;
- distinct runtime and deployer service accounts;
- GitHub Workload Identity Federation without service-account keys;
- OIDC restricted to `BernydotJar/AI-Native-Content-Agency-SaaS` and
  `refs/heads/main`;
- eight empty Secret Manager containers;
- runtime Secret Manager access granted per secret, never project-wide.

Verified absent:

- Cloud Run services;
- Cloud SQL, GKE and Compute Engine resources;
- secret values or versions;
- user-managed service-account keys;
- images in Artifact Registry;
- runtime publication or model effects.

Terraform state contains 38 managed/data entries. The latest local persistent backup is
`.local/gcp-state-backups/terraform-20260729T010938Z.tfstate`, SHA-256
`8b7c04994ace29c3ab25eae94d81f76f63755e0ba4d34baba15c888b5a84f891`.

## Image publication path

The Cloud Sandbox Docker daemon is ARM64 and cannot reliably register the binfmt layers
required for a Cloud Run-compatible `linux/amd64` image. No image was built or pushed
from the workstation.

A new manual GitHub workflow prepares the safe image path:

- manual `workflow_dispatch` only;
- boolean operator confirmation required;
- `main` only, enforced by both GitHub and GCP WIF conditions;
- Google authentication through short-lived OIDC credentials;
- all actions pinned by full commit SHA;
- image tag equals the exact Git commit SHA;
- SBOM and provenance enabled;
- no Cloud Run deployment, Terraform apply, secret read or `latest` tag authority.

The workflow cannot be executed successfully before the stacked changes reach `main`.
Merge remains separately authorized.

## Current product result

CampaignOS provides:

- an outcome-oriented campaign workspace and eight-station orchestration map;
- individual username/password login backed by server-derived roles and HttpOnly sessions;
- server-side provider, integration and social-account configuration;
- encrypted X and Instagram OAuth connections in persistent SQLite;
- automatic connection-state backups;
- four no-key research lanes for Guatemala: current searches, AI, marketing and business;
- safe HTTPS evidence disclosure for research signals;
- one-click conversion from a signal to an editable X/Instagram pilot brief;
- explicit review-only labels before and after pilot execution;
- fail-closed publication, political publication and paid-media controls.

## INC-036 live pilot

```text
run_id=run-ce573811a46d6f06
campaign_goal=trend_response_pilot
status=awaiting_greenlight
platforms=x,instagram
artifacts=7
copy_decks=1
copy_platforms=x,instagram
greenlight=none
social_publication_intents=0
```

Research used Google Trends and Google News RSS and stopped before any provider
publication boundary. No X credits were required.

## Verification

- Backend: 323 PASS; 25 PostgreSQL-only skips expected.
- Frontend: 58 PASS.
- Oxlint: zero warnings/errors.
- Production build: PASS.
- Terraform `fmt`, `validate` and 3 fail-closed tests: PASS.
- Authenticated bootstrap and recovery plans: exact, create/update-only and audited.
- GCP bootstrap apply: complete.
- Artifact cleanup policy update: complete.
- Actionlint: PASS.
- Manual GCP image workflow static authority gate: PASS.
- Secret versions: 0.
- User-managed service-account keys: 0.
- Cloud Run services: 0.
- Cloud SQL instances: 0.

## Runtime state

- Local health: HTTP 200 at last runtime check.
- Public health: unavailable; the ephemeral Quick Tunnel hostname expired.
- Database: `/workspace/.local/ai-native-content-agency-local.sqlite3`.
- Social backup watcher: running at last runtime check.
- X: connected as `@beesheep` in the local encrypted database.
- Instagram: connected as `@beesheep2` in the local encrypted database.
- Social publication: `false`.
- Political publication: `false`.
- Political paid media: `false`.
- External model effects: `false`.

Release recommendation: `DENY_RELEASE`

Cloud recommendation: `DENY_APPLY`

`DENY_APPLY` now means no additional cloud mutation beyond the explicitly authorized and
completed INC-037 bootstrap receipt. In particular, do not deploy Cloud Run, create a
database, upload secret values or publish an image without the next reviewed gate.

## Exact resume condition

Finish validation and publish the INC-037 receipt to PR #30. Then obtain explicit merge
authorization for the stacked PRs. After the approved changes reach `main`, manually run
the image publisher with confirmation. A separate database and secret-migration decision
must precede any Cloud Run deployment or stable OAuth callback cutover.

## 2026-07-29 — Graph Harness SDLC adoption

- Protected `main` cumulative head before this increment: `c8b177c9b615b7b14e726d52c9d94f121ab9b64a`.
- Active feature branch: `feature/graph-harness-adoption-v1`.
- Canonical framework revision: `1bebce3db35303072049233786464bb01163c98b`.
- Graph nodes: 25.
- Graph events: 15.
- `INC-038` derived status: `review`.
- Passed gates: spec, implementation, production and review.
- Intentionally open gate: close.
- Local program, graph, lint, 58 frontend tests and production build: PASS.
- Exact-head CI, human closure and merge: pending.
- No product runtime, UI, database schema, cloud resource, secret, social effect, model effect or publication authority changed.

### Localized repair after exact-head run 30427783709

- Failed gates: backend test discovery in `verify` and `postgresql-shared-state`.
- Root causes: stale fixed task count (`24`) and missing submodule initialization in the PostgreSQL checkout.
- Graph action: `failure.recorded`, `INC-038` invalidated, revision advanced from 0 to 1; no other node was invalidated.
- Repair: task cardinality expectation updated to 25, adapter import made explicit, PostgreSQL job initializes the pinned gitlink.
- Graph events after repair: 30.
- Derived state after repair: `INC-038=review`; close gate remains open.

## 2026-07-29 — INC-038 closed through Graph Harness

- Framework PR #1 merged as `1bebce3db35303072049233786464bb01163c98b`.
- Application pre-closure exact-head run `30465318928` passed 8/8 jobs.
- Graph Harness events: 49; `INC-038` revision: 2; derived status: `done`.
- All five gates pass, including `close-gate`.
- Release decision remains `DENY_RELEASE`; deployment and external effects remain unauthorized.

## 2026-07-29 — Integrated review backlog closure

- Closed at increment scope: `INC-003`, `INC-015`, `INC-017`, `INC-018`, `INC-019`, `INC-020`.
- Evidence base: protected `main` `afb52ffdcdf85f7ed4236be6fe5102d4fbf763a3`, run `30466498822`, 8/8 jobs successful.
- Graph Harness event count: 92.
- Remaining program state: 20 done, 4 blocked, 1 pending.
- `DENY_RELEASE`, `DENY_APPLY`, default-off external effects and all human/external gates remain unchanged.

## 2026-07-29 — INC-010 semantic/adversarial evaluation in review

- Active branch: `feature/semantic-adversarial-evals-v1`.
- Implementation commit: `b726ae5854bb5406b819c815f3acf66d933acf40`.
- Exact implementation tree: `d842e2cd4e56fb7546e28272c217cd8819a74c8a`.
- Graph Harness revision: 1 after localized critic/fixer repair.
- Semantic corpus: 16/16 expectations met over real runtime artifacts.
- Independent verifier: PASS; dirty=false; report/digest/case/effect tampering rejected.
- Locked installed wheel: 332 backend tests PASS; 25 PostgreSQL-only skips.
- Frontend: 58 tests, lint and production build PASS.
- Program, graph, compliance and operability: PASS.
- External effects observed: 0.
- Exact-head CI and close gate: pending.
- Manual accessibility, legal/privacy, persistent staging and release gates remain blocked and unchanged.

### INC-010 localized repair after run 30471479970

- All eight jobs reported success, but independent artifact inspection rejected the run as close evidence.
- The semantic report was bound to GitHub's synthetic PR merge `6b28cf529144a0424a26ebf235ae0ee20d068461`, whose parents were `main` `77251315e112d1651ab512f7c4de2deaeaa5dfce` and PR head `5d087ed3a1c03c072014ce7faa11a503866ccea6`.
- Graph Harness recorded a `close-gate` failure, invalidated only `INC-010`, advanced its revision from 1 to 2 and preserved every unrelated node.
- Repair: all eight jobs now check out and assert `${{ github.event.pull_request.head.sha || github.sha }}`; the semantic evaluator and independent verifier also require `SEMANTIC_EVAL_EXPECTED_COMMIT` to equal `HEAD`.
- Local repair evidence: 333 backend tests PASS, 16/16 semantic cases, expected-SHA mismatch negative PASS, actionlint and all governance gates PASS.
- A new remote exact-head run is required before closure.

## 2026-07-29 — INC-010 closed through exact-head Graph Harness evidence

- PR #33 exact-head candidate: `6e69b8eb13a6196bba8db3c2039ab4dc09609aa0`.
- GitHub Actions run `30476446123` passed 8/8 jobs.
- Every job asserted checkout of the pull-request head rather than the synthetic merge ref.
- Remote semantic artifact SHA-256: `2e95ab94dae1b43b7dc273567d0dfc84cf7c247cc7686043ee7ec7f0ad535850`.
- Artifact binding: `source_commit == expected_source_commit == 6e69b8eb13a6196bba8db3c2039ab4dc09609aa0`; tree `b3b6e6057ef7b36ede0ee9716b6b790c35cb7a21`.
- Semantic results: 16/16 expectations met, worktree clean, external effects 0.
- Graph Harness revision: 2; implementation, production, review and close gates PASS.
- `INC-010` canonical and derived status: `done`.
- The prior synthetic-merge run `30471479970` remains preserved as rejected evidence.
- `DENY_RELEASE`, `DENY_APPLY`, disabled effect flags and all accessibility/legal/staging human gates remain unchanged.

### INC-010 revision 3 — localized PR review repair

- PR #33 review identified two valid findings after the previous close checkpoint:
  - P1: generic prohibited claims such as `garantiza`, `el mejor`, `sin duda` and `100%` could evade the narrowed overclaim list.
  - P2: the independent verifier accepted altered finding codes, inflated counts or changed metrics when the aggregate verdict remained `FAIL`.
- Graph Harness recorded a `review-gate` failure, invalidated only `INC-010`, advanced it to revision 3 and preserved all unrelated nodes.
- Fixer restored the broader prohibited-claim coverage and upgraded the corpus contract to `agency.semantic-adversarial-corpus.v2`.
- Corpus v2 contains 20 cases and binds exact verdict, finding codes, finding count and metrics for every case.
- Local reproducible evidence: 20/20 semantic cases PASS, independent verifier PASS, 334 locked-wheel backend tests PASS, 58 frontend tests PASS, lint/build/actionlint/program/graph/compliance/operability PASS, external effects 0.
- Exact-head CI, remote artifact inspection, review-thread resolution and close gate are pending.

### INC-010 revision 3 closed

- Exact-head run `30480645671` passed 8/8 jobs at `cf8f8c351b48f22b2755d285193ff5b6f76e00d8`.
- Retained corpus v2 artifact SHA-256: `2d7a61f5a8978fccdc24fe7b54111c295963c7dafcba58a8fb33b26cbafd9836`.
- Semantic expectations: 20/20; external effects: 0.
- Both P1/P2 PR review findings were repaired, answered and resolved.
- Graph Harness revision 3: implementation, production, review and close gates PASS; `INC-010=done`.
- Program state: 21 done, 4 blocked, 0 ready.
- `DENY_RELEASE` and `DENY_APPLY` remain unchanged.


## 2026-07-29 — INC-025 public-media signing keyring local review

- Branch: `agent/graph-completion-audit-v1`.
- Graph Harness revision: 2 after two localized verifier repairs; unrelated nodes preserved.
- Preferred configuration: bounded key-ID to base64url 32-byte key map plus active key ID.
- Legacy single-key mode preserves exact historical HMAC bytes and is mutually exclusive with keyring mode.
- SQLite and PostgreSQL schema v7 persist `public_signing_key_id`; old rows migrate to `legacy`.
- Old binding replay remains byte-for-byte stable while a new key is active; new bindings use the active key; premature historical-key removal fails closed.
- Local evidence: 341 locked-wheel tests PASS; 341/341 PostgreSQL tests PASS; 58 frontend tests, lint/build/program/graph/compliance/operability PASS.
- OCI non-root package, Helm preferred/legacy guards, Terraform/K3s SQLite and PostgreSQL plan-apply-destroy PASS; signing values remain outside Git and Terraform state.
- Clean-source supply-chain provenance, exact-head CI, Graph Harness close gate and merge remain pending.
- Provider publication/deletion, production Secret mutation, deployment, spend, legal approval and all real external effects remain unauthorized.


## 2026-07-29 — INC-025 exact-tree implementation checkpoint

- Implementation commit: `bf32be4b697f8c12bc476f204fbfa2ddc55c5399`.
- Exact tree: `76eaaa464aa485d66318cd3b493f4dcaae8da6f5`.
- Graph Harness revision: 2; local implementation, verification, production and review evidence ready to record.
- 341 locked-wheel tests and 341/341 PostgreSQL schema-v7 tests PASS.
- OCI/Helm/Terraform/K3s PASS; ephemeral resources destroyed; external effects 0.
- Clean-source supply chain PASS: 33 packages evaluated, policy/provenance/offline Cosign verified, registry publication false.
- Exact-head CI, close gate and merge remain pending. `DENY_RELEASE` and `DENY_APPLY` remain unchanged.


## 2026-07-29 — INC-025 closed through Graph Harness

- Exact PR head: `7f56f711abc5d13fb609e2fee5b04176ea4c4319`.
- GitHub Actions run `30500998431` passed 8/8 jobs.
- Remote provenance `3ffcb74b2c8f62fdb8710799375145f3e2d70e60b578c918a2f60bb6bf66f112` and policy `1497bd6b65756988ef36877e132c5619b5d1f0b4b3a0f8d80c5fdfbddf356adb` were inspected; 33 packages evaluated.
- Semantic artifact `6c872912a227341c396905c1dd39a3b2b70ca63482eb85cb8451d977997d21b6` is exact-head, clean, 20/20 and zero-effects.
- Graph Harness revision 2 close gate: PASS; node status: `done`.
- Production Secret rotation, deployment, publication/deletion and legal approval remain unauthorized.


## 2026-07-30 — INC-026 repository-governance local review

- Active branch: `agent/repository-governance-reconciliation-v1`.
- Graph Harness revision: 0; status: `running`.
- Canonical single-owner policy requires all eight current jobs and no impossible second-person approval.
- Release blockers are derived exactly from unresolved HIGH findings; F-011 and F-046 are closed, F-050 remains provider-deletion/legal.
- Issue #1 and PRs #2–#11 are audited as superseded; none may be merged or deleted.
- Local evidence: 347 backend tests, 58 frontend tests, governance/program/graph/compliance/operability, workflow lint and focused adversarial tests PASS.
- Clean implementation commit, exact-head CI, live policy readback and remote non-destructive closure remain pending.
- `DENY_RELEASE`, `DENY_APPLY` and all production/external-effect gates remain unchanged.


## 2026-07-30 — INC-026 exact-tree review

- Implementation commit: `7810f302ef2a4c32332139e9ea95e668b55cc225`; tree `e10684bed75168775e1df5e5e412512a04ce8408`.
- Graph status pending transition to review after evidence recording.
- 347 backend and 58 frontend tests PASS; governance/program/graph/compliance/operability/workflow PASS.
- Clean supply-chain provenance `c03cad30f9167059b90c2cbb7ef7488ea305ca9883a6089b668a03a01c731891`; policy `1497bd6b65756988ef36877e132c5619b5d1f0b4b3a0f8d80c5fdfbddf356adb`; source dirty false.
- Exact-head CI, live branch-protection apply/readback, superseded remote closure and close gate remain pending.

## INC-026 repository governance reconciliation

- Exact-head PR #35 run `30521828441` passed all eight production-readiness jobs on `679e59dd128055529d1df16e7a6aff0b283a0bcb`.
- Retained supply-chain and semantic artifacts bind that clean SHA; external effects observed: `0`.
- Historical PRs #2-#11 and issue #1 are closed as superseded; none was merged and no branch was deleted.
- Live `main` protection remains unchanged: one approving review, last-push approval and four obsolete required checks.
- `INC-026` is `blocked` pending explicit human authority to change branch protection / merge policy.

## INC-027 authenticated request quota

- Status: `blocked`, revision 4; exact-head run `30525081524` passed 8/8 on `3e23089afb99e066211762e831dbd75d1275f6da`; only parent PR #35 and explicit merge/branch-protection authority remain.
- Durable hashed principal and tenant fixed-window buckets execute after authentication and before CSRF/authorization auditing.
- The first configured requests pass; the next returns safe HTTP 429 with `Retry-After` and adds no denial-audit row.
- PostgreSQL schema v8 shares quota across replicas; migration, least privilege, backup/restore, OCI, Helm, Terraform and K3s evidence pass.
- Four localized repairs affected only INC-027: stale schema/cardinality assertions, raw DB-API test access, obsolete package health assertions and two newly fixable Python tarfile findings.
- Supply chain passes with `source_dirty=false`; three exact Python compatibility exceptions expire on 2026-08-21 and the runtime tarfile-surface guard passes.
- Release and cloud recommendations remain `DENY_RELEASE` and `DENY_APPLY`.

## INC-028 audit ledger integrity

- Status: `blocked`, revision 4; exact-head run `30527647518` passed 8/8 on `73fd7b7f83cecd87d7ad37a60ff43c7693ec7a42`; only stacked merge authority and immutable/KMS/legal custody remain.
- SQLite and PostgreSQL schema v9 maintain per-tenant SHA-256 chains plus durable heads, detecting field mutation, deletion, truncation and reordering.
- PostgreSQL serializes only same-tenant appends and verifies the chain across replicas.
- Existing rows backfill deterministically; SQLite-to-PostgreSQL migration recomputes hashes and backup/restore preserves events plus heads.
- Optional HMAC-SHA256 checkpoints expose event count, head event/hash, key ID and signature only to `audit:read` identities.
- Helm/Terraform use Secret refs only; package and K3s gates prove no signing material in render or Terraform state.
- Four localized repairs affected only INC-028: canonical base64url enforcement, AuditWrite/AuditEvent model placement, schema-v9 restoration and API fixture creation.
- Immutable off-host custody, KMS/HSM and legal non-repudiation remain external; `DENY_RELEASE` and `DENY_APPLY` are unchanged.
