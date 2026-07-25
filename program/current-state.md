# Current Program State

Updated: 2026-07-25

## Exact repository state

- Workspace: `7759306b-d1ea-40ed-92dc-b78424c749ba`
- Active branch: `agent/inc-023-political-compliance-mode`
- Current committed checkpoint: `628fb23a73b9ac3d1f34b7f3efffbe580a7f9f45`
- INC-023 implementation: present in the worktree; implementation commit and remote head pending
- Nested containers created: none; count remains zero
- Real Instagram/X publication, ad activation, model call, cloud apply or spend: none

## Closed stacked increments

- PR #13, Campaign Intelligence, merged normally into `agent/inc-020-social-publication-authority` at merge commit `cce712e86b356cf9c4a2dca087f8af078101915e`.
- PR #14, Publication Media and Verified Publication, merged normally into `agent/inc-021-campaign-intelligence` at merge commit `7522164240b8090fe70ec51525a6a247e4a558c8`.
- PR #14 exact head `b5d63f65c52c886a1855f20aff8593ca398383ac` passed all eight `production-readiness` jobs in run `30164438593` before merge.
- These stacked merges close the increments but do not merge the complete stack to protected `main`. Main still requires its own cumulative PR, current required checks and an eligible independent approval.

## INC-023 implementation evidence

The local implementation adds:

- `publication_mode=organic|paid` with commercial default `organic`;
- independent default-off switches for political content, general social publication, political publication and paid political planning;
- server-side separation between legal/electoral reviewer and Greenlight approver;
- `political_compliance_record` included in the approved Greenlight artifact envelope;
- SHA-256 bindings for disclosure and claim/source/locator evidence;
- schema v6 nullable `confirmation_hash` in SQLite/PostgreSQL exact-once publication intents;
- exact final phrase `PUBLICAR POLITICA <run_id> <channel_id>` checked before intent reservation;
- persistence of only the confirmation SHA-256, never the raw phrase;
- paid political mode rejected by the organic publication endpoint before intent or provider HTTP;
- typed political confirmation UI and paid-mode blocked state;
- `.env`, Helm and Terraform switches that all default to false;
- political publication runbook with neutral sandbox and rollback procedure.

## Local verification receipt

- TDD RED captured before implementation.
- Focused political backend: 8 tests PASS.
- Broad backend compatibility: 75 tests PASS before the final paid-creation test was added.
- Hash-locked installed wheel: 285 tests PASS, 25 PostgreSQL-only skips.
- Frontend: 45 tests PASS.
- Lint: 0 warnings, 0 errors.
- Production build: PASS.
- Program validator: PASS with 87 requirements and 23 tasks.
- Compliance validator: PASS and still returns `DENY_RELEASE`.
- Backup/schema CLI/political operability family: 27 tests PASS before the final paid-creation test was added.
- PostgreSQL executable gate could not run locally because `/usr/lib/postgresql/15/bin/postgres` is absent. No container or data mutation occurred; exact-head CI owns this gate.
- Terraform, Helm and OpenTofu binaries are absent locally. Static configuration contracts pass; executable validation remains delegated to exact-head CI.

## Safety and review decision

- All external effects remain disabled by default.
- Paid political advertising is not implemented and cannot use the organic endpoint.
- Automated role-separated review does not constitute jurisdiction-specific legal advice, campaign authorization or provider-policy approval.
- One neutral sandbox post on `@beesheep2` remains blocked until INC-023 has an implementation commit, draft PR, exact-head 8/8 CI, distinct code review, exact account/content/media confirmation and a bounded rollback window.

Release recommendation: `DENY_RELEASE`

Cloud recommendation: `DENY_APPLY`

## Exact resume condition

Complete final local regression after the paid-creation gate, freeze and commit INC-023, publish the exact branch, open a draft PR against `agent/inc-022-governed-media-verification`, pass all eight exact-head CI jobs, repair any failure, complete a distinct review, then separately authorize and execute the neutral sandbox publication.
