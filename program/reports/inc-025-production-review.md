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
