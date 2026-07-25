# Current Program State

Updated: 2026-07-25

## Exact repository state

- Workspace: `7759306b-d1ea-40ed-92dc-b78424c749ba`
- Branch: `agent/inc-022-governed-media-verification`
- INC-022 implementation commit: `3d8ed72332d29b161a48c1201e627a9c016ec6ac`
- Exact verified parent: `ea306fdec61842557d7d8c84f9423347e08825ab`
- Protected branches modified: no
- Remote branch / PR for INC-022: pending
- Merge/release/deployment performed: no
- Nested containers created: none; count remains zero
- Real Instagram/X publication, model call, cloud apply or spend: none

## Product evidence

- INC-021 campaign intelligence remains complete and exact-head verified.
- INC-022 adds a bounded single-image Instagram workflow:
  - Pillow-verified JPEG, exact 4:5, 320–1440 px, maximum 8 MiB;
  - server-calculated SHA-256, UTF-8 alt text and authenticated rights attestation;
  - immutable SQLite/PostgreSQL Media Vault with tenant isolation and idempotent replay;
  - opaque HMAC capability URL; only its digest is stored for public lookup;
  - public delivery with generic 404, ETag, max-age at most 300 seconds, expiry and revocation;
  - operator upload and pre-Greenlight removal in the production UI;
  - durable binding of exact media bytes into the Greenlight artifact envelope;
  - pre-provider revalidation of byte hash, MIME, expiry and revocation;
  - Instagram container polling until `FINISHED`;
  - `media_publish` only after finished processing;
  - independent GET of published media and verification of ID, account, caption hash, media type, permalink and timestamp;
  - durable receipt/history and safe permalink recovery after reload;
  - unknown outcomes remain blocked and require reconciliation.

## Local verification receipt

- Locked backend wheel: 277 tests PASS; 0 PostgreSQL-only tests SKIP locally because `AGENCY_TEST_DATABASE_URL` is absent.
- Frontend suite: 0 tests PASS.
- Lint: 0 warnings, 0 errors.
- Production build: PASS.
- Focused Media Vault, publication, schema v5, backup and local-runner families: PASS.
- Secret/diff/scope scans: PASS before implementation commit.
- Nested Docker containers: zero.

## Truthful limitations

- INC-022 exact SHA is not yet published or evaluated by remote CI.
- PostgreSQL v5 multi-replica, OCI, Helm, Terraform and supply-chain exact-head gates remain pending.
- No real Meta container or post was created; provider behavior is verified through bounded MockTransport contracts and official primary documentation.
- Media deletion from an already published Instagram account is not automated by this increment. Post-Greenlight rights withdrawal requires revoking approval, assessing provider state and an explicit deletion/reconciliation workflow.
- Signing-key rotation is operationally safe only when the previous key is retained through the maximum capability TTL and active retry window. A keyring migration remains future work before independent live rotation.
- The local SQLite BLOB vault is suitable for demonstration; production scale requires an authorized durable object-storage/retention design while preserving the same byte/hash contract.
- JPEG IMAGE only; carousel/reel child-level exact-once protocols are deferred.
- Human media-rights, accessibility, privacy, legal, campaign and provider-policy reviews remain required.

## Program decision

Release recommendation: `DENY_RELEASE`
Cloud recommendation: `DENY_APPLY`

- INC-021: `done`
- INC-022: `review`
- Global release: `DENY_RELEASE`
- Cloud apply: `DENY_APPLY`

## Exact resume condition

Publish `agent/inc-022-governed-media-verification` at exact commit `3d8ed72332d29b161a48c1201e627a9c016ec6ac`, pass all exact-head CI jobs, repair any failure, complete a distinct accountable review, then mark INC-022 done. A real sandbox post requires a separate explicit authorization naming the account, content/media, timing and acceptance/rollback criteria.
