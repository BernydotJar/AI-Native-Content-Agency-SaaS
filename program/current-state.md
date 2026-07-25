# Current Program State

Updated: 2026-07-25

## Exact repository state

- Workspace: `7759306b-d1ea-40ed-92dc-b78424c749ba`
- Branch: `agent/inc-021-campaign-intelligence`
- Implementation commit: `6ebbd634bd32408db0a7678289b0f906cda014c0`
- Base OAuth hardening commit: `bd9532eb16bbb40351621b7e98e84dda158cba1e`
- Protected branches modified: no
- Merge/release/deployment performed: no
- Nested containers created: none; count remains zero
- Real social publication/model call/cloud apply/spend: none

## Product evidence

- Instagram Business Login completed against the configured professional account and the connection is persisted with encrypted server-side tokens.
- OAuth callbacks require `state`, are bound to tenant/session/channel, and error redirects disclose no provider secrets.
- Durable run checkpoints, Greenlight, model-effect authority and social publication authority remain present and default-disabled where effectful.
- INC-021 replaces the generic mixed-language campaign fixture with structured political campaign intelligence:
  - jurisdiction, office, candidate, locality, problem, proposal, CTA and disclosure;
  - claim source/locator, verification state and authenticated human reviewer;
  - explicit legal-review state and authenticated reviewer;
  - Spanish channel variants with claim mapping;
  - accessible Instagram carousel plan;
  - Critique Agent fail-closed decision;
  - separate `AGENCY_POLITICAL_PUBLICATION_ENABLED=false` authority.

## Verification receipt

- Locked backend wheel: 261 tests PASS; 23 PostgreSQL-only SKIP because `AGENCY_TEST_DATABASE_URL` is absent.
- OAuth focused family: 18 PASS; 2 PostgreSQL-only SKIP.
- Frontend: 39 tests PASS.
- Lint: 0 warnings, 0 errors.
- Production frontend build: PASS.
- Diff/secret scans: PASS, zero findings.
- Nested Docker containers: zero.

## Truthful limitations

- Exact source SHA `25f2ef0c19d89f008a87aa1daa79b1ca9a1df9a1` is published on `agent/inc-021-campaign-intelligence`.
- Draft PR #13 remains open and unmerged.
- GitHub Actions run `30149528848` passed all eight exact-head jobs, including PostgreSQL, OCI, Helm, Terraform and supply chain.
- The local K3s/Terraform apply-destroy verifier was not run because it creates an auxiliary control plane and its pinned CLIs were not loaded.
- Campaign claims are only as authentic as the accountable human/source review; the software does not make legal or factual determinations independently.
- No `publication_media` artifact is generated yet.
- The current Instagram receipt contract does not independently read the post after `media_publish` or store a verified permalink.
- No release, cloud target, paid campaign or real post is authorized.

## Program decision

Release recommendation: `DENY_RELEASE`
Cloud recommendation: `DENY_APPLY`

- INC-021: `done`
- INC-022: `pending`, next ready task
- Global release: `DENY_RELEASE`
- Cloud apply: `DENY_APPLY`

## Exact resume condition

Begin INC-022 from exact verified head `25f2ef0c19d89f008a87aa1daa79b1ca9a1df9a1`: governed `publication_media`, safe HTTPS delivery, Instagram container processing, read-after-write verification, permalink/receipt reconciliation and UI states. External publication remains separately human-gated.
