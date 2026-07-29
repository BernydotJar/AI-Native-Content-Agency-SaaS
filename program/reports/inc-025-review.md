# INC-025 Role-Separated Review — Public Media Signing Keyring

Date: 2026-07-29  
Branch: `agent/graph-completion-audit-v1`  
Graph Harness revision: 2  
Program state: `running`; exact-head CI pending

## Producer

Status: PASS for the implemented scope.

Delivered:

- immutable bounded `PublicMediaSigningKeyring` with preferred and migration-only legacy configuration;
- durable `public_signing_key_id` in SQLite and PostgreSQL schema v7;
- active-key signing for new media and historical-key replay for existing bindings;
- exact legacy HMAC compatibility without changing existing opaque URLs;
- fail-closed behavior when a historical key is removed too early;
- local runner, Helm and Terraform Secret-reference configuration;
- staged rotation, legacy migration and rollback runbook.

## Critic / Red Team

Status: PASS after two localized repairs.

Findings and repairs:

1. Deriving the legacy key through SHA-256 would have changed old capability tokens. Repaired by preserving the exact historical UTF-8 HMAC key bytes.
2. The PostgreSQL harness restored schema metadata to v6 and the local runner could invoke `fail` before definition. Repaired across schema tests, backup validation and runner ordering; schema v7 now passes end to end.
3. The OCI smoke used unsafe shell quoting for a model-effect JSON body. Repaired with canonical Python JSON and `--data-binary`; the full image smoke now passes.
4. Static Secret-reference claims were insufficient. Repaired by rendering preferred/legacy Helm modes and applying both SQLite and PostgreSQL Terraform plans to an ephemeral K3s API while asserting key values are absent from plan/state.

Adversarial cases:

- partial, duplicate, malformed, weak or ambiguous keyring configuration → startup failure;
- old-key removal with a live durable binding → generic 503, no substitute signature;
- legacy and preferred configuration together → startup/render failure;
- random/expired/revoked public capability → generic 404 remains unchanged;
- Secret values in Helm/Terraform state → negative assertions;
- mixed-key restart → old URL stable, new row bound to new key ID.

## Security Reviewer

Status: PASS for repository-local implementation.

- Preferred key material must decode to exactly 32 bytes.
- Key IDs are bounded and allowlisted; duplicate JSON keys are rejected.
- Raw key material is absent from durable rows, API responses, logs, Graph Harness evidence and Terraform state.
- Durable rows store only the key ID and existing token digest.
- Token format and public digest lookup are unchanged.
- Missing historical authority fails closed instead of silently using the active key.
- Production Secret creation/rotation and workload rollout remain human-gated.

## Independent Verifier

Status: PASS for local deterministic scope.

- locked installed wheel: 341 tests PASS, 25 PostgreSQL-only skips without server;
- PostgreSQL 15 integration: 341/341 PASS, schema v7, migration and backup/restore PASS;
- frontend: 58 tests PASS, lint zero, production build PASS;
- Graph Harness, program, compliance and operability: PASS;
- OCI UID 10001 package and full HTTP smoke: PASS;
- Helm keyring/legacy/default-disabled guards: PASS;
- Terraform/K3s SQLite and PostgreSQL plan-apply-destroy: PASS, cleanup PASS;
- external provider HTTP/publication/deletion: not run and still disabled.

## Release Gate

Decision: `PASS_FOR_CLEAN_TREE_VERIFICATION`; global decision remains `DENY_RELEASE` and `DENY_APPLY`.

Exact resume condition: commit the implementation, run clean-source supply-chain provenance and all strict exact-tree gates, record Graph Harness review evidence, publish a PR, pass exact-head CI and inspect retained artifacts before the close gate.


## Exact-Tree Verification

- Implementation commit: `bf32be4b697f8c12bc476f204fbfa2ddc55c5399`
- Git tree: `76eaaa464aa485d66318cd3b493f4dcaae8da6f5`
- Locked wheel: 341 PASS; 25 PostgreSQL-only skips without a server.
- PostgreSQL 15.18: 341/341 PASS; schema v7; migration and backup/restore PASS.
- Frontend: 58 PASS; lint and production build PASS.
- OCI/Helm/Terraform/K3s: PASS; external effects false; all ephemeral resources destroyed.
- Supply chain: 33 packages evaluated; policy PASS; source dirty false; provenance SHA-256 `6584d7e803ab0b49a1b9ec8a957fd7107591047526fe23d202d2db2d2b531f4d`; OCI archive SHA-256 `62f3ed1a4093c616022f099c710fc0131d33bf5fdd4caecc875ed4073728b08a`; offline Cosign verification PASS; registry publication false.
- Remaining gate: exact-head GitHub Actions and retained artifact inspection.
