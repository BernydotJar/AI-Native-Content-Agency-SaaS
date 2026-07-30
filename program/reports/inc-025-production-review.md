# INC-025 Production Review — Public Media Signing Keyring

Updated: 2026-07-29  
Decision: `PASS_FOR_CLEAN_TREE_VERIFICATION`; release and deployment remain denied.

## Architecture and Compatibility

The capability token stays URL-safe HMAC-SHA256 over the existing canonical tuple. New rows persist the active key ID; replay selects the row's historical key. Legacy configuration uses the exact prior UTF-8 bytes, so existing capability digests remain valid. SQLite migration and PostgreSQL schema v7 label pre-keyring rows `legacy`.

## Failure and Recovery

- Invalid or partial configuration fails before application startup.
- A missing historical key produces a generic service-unavailable response and no replacement signature.
- Rotation is add → deploy → activate → verify → wait through TTL/reconciliation window → prove zero dependent rows → remove.
- Rollback restores the prior active ID while both keys remain present.
- Database rollback must retain the key-ID column; dropping it would make mixed-key replay ambiguous.

## Deployment Boundary

Helm and Terraform carry only a pre-existing Secret name and data-key names. The keyring JSON and active ID never enter Git or Terraform state. The local K3s verifier applies and destroys both SQLite and PostgreSQL releases with Secret refs. Production Secret mutation, rollout, object-storage/CDN observation and unattended rotation require explicit human approval.

## External Effects

No provider publication, deletion, model request, cloud apply, credential mutation or spend occurred. Post-publication provider deletion remains blocked under OI-016 and INC-011 because it requires legal retention/deletion decisions, account authority and an authorized sandbox effect.

## Remaining Evidence

Clean-source SBOM/vulnerability/license/provenance/signature verification and exact-head GitHub Actions are required before Graph Harness `close-gate` can pass.


## Exact-Tree Production Evidence

- Implementation commit: `bf32be4b697f8c12bc476f204fbfa2ddc55c5399`
- Git tree: `76eaaa464aa485d66318cd3b493f4dcaae8da6f5`
- Locked wheel: 341 PASS; 25 PostgreSQL-only skips without a server.
- PostgreSQL 15.18: 341/341 PASS; schema v7; migration and backup/restore PASS.
- Frontend: 58 PASS; lint and production build PASS.
- OCI/Helm/Terraform/K3s: PASS; external effects false; all ephemeral resources destroyed.
- Supply chain: 33 packages evaluated; policy PASS; source dirty false; provenance SHA-256 `6584d7e803ab0b49a1b9ec8a957fd7107591047526fe23d202d2db2d2b531f4d`; OCI archive SHA-256 `62f3ed1a4093c616022f099c710fc0131d33bf5fdd4caecc875ed4073728b08a`; offline Cosign verification PASS; registry publication false.
- Remaining gate: exact-head GitHub Actions and retained artifact inspection.
