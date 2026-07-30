# INC-028 Remote Review and External Custody Gate

Date: 2026-07-30
PR: `#37`
Exact head: `73fd7b7f83cecd87d7ad37a60ff43c7693ec7a42`
GitHub Actions: `30527647518`

## Remote evidence

- all eight production-readiness jobs passed;
- retained semantic report binds source and expected commit to the exact head, with 20/20 cases, clean worktree and zero external effects;
- retained supply-chain policy passes with 33 packages and exactly three Python compatibility exceptions;
- provenance SHA-256: `32ba84346f15083ef024c529387d52068d9f1106f186ab8916921993fd67438c`;
- zero unresolved PR review threads.

## Completed technical scope

- per-tenant audit hash chain and durable head;
- mutation, deletion, truncation and reordering detection;
- PostgreSQL schema v9 and cross-replica serialization;
- deterministic legacy backfill and SQLite-to-PostgreSQL migration;
- signed tenant checkpoint endpoint and strict externalized keyring;
- installed-image HMAC verification;
- Secret refs only in Helm/Terraform and no key material in plan/state.

## External and human gates

1. PR #37 is stacked on PR #36, which is stacked on human-gated PR #35. Merge authority and live branch-protection changes are not granted.
2. No immutable off-host checkpoint destination exists.
3. No production KMS/HSM custody, key rotation or retention approval exists.
4. No legal non-repudiation acceptance is granted.

The code scope is verified, but `F-012` remains `BLOCKED_EXTERNAL` and the node cannot pass close-gate or become `done`.

## Resume condition

- explicitly authorize and apply the committed single-owner branch-protection policy;
- merge PRs #35, #36 and #37 in dependency order with exact-head CI after any changed head;
- provision an approved immutable off-host checkpoint destination;
- provision approved KMS/HSM-backed signing custody and rotation;
- retain and independently verify a production/staging checkpoint;
- record accountable security/privacy/legal acceptance before release.

`DENY_RELEASE`, `DENY_APPLY` and all effect kill switches remain unchanged.
