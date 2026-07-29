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
