# INC-025 Requirements — Public Media Signing Keyring

## Mode

SHIP.

## Problem

Public publication-media capabilities are currently generated with one process-wide HMAC secret. Durable records persist only the token digest, so replay of an existing media binding depends on whichever secret is active after restart. Rotating the secret can therefore make an otherwise valid durable binding unreplayable, while retaining one key indefinitely prevents controlled rotation.

## Requirements

- Configure an exact, bounded signing-key map and one active key identifier without storing key material in the repository, database, logs, responses, Terraform state, or Graph Harness evidence.
- Persist the signing key identifier that generated each publication-media capability.
- Generate new capabilities only with the configured active key.
- Reconstruct a replayed capability with the exact persisted key identifier, even after another key becomes active.
- Fail closed when a durable unexpired binding references a key that is no longer configured.
- Preserve the existing opaque token format and public lookup semantics so active URLs are not silently invalidated.
- Migrate SQLite and PostgreSQL records created before this feature to an explicit `legacy` key identifier.
- Support a bounded legacy single-key configuration during migration, while rejecting ambiguous simultaneous legacy and keyring configuration.
- Wire the keyring through local execution, Helm and Terraform using references to pre-existing secrets only.
- Keep publication, provider deletion, infrastructure apply, credential creation and all external effects disabled.

## Acceptance Criteria

- A record created with key `media-v1` replays byte-for-byte after restart with `media-v2` active while both keys remain configured.
- A new record after rotation is bound to `media-v2`.
- Removing `media-v1` while an active durable record references it causes a safe, non-secret 503 on replay and performs no provider effect.
- Legacy SQLite and PostgreSQL rows load as key identifier `legacy` and replay with the explicit legacy configuration.
- Invalid IDs, malformed JSON, duplicate/ambiguous configuration, missing active key, weak key material and partial configuration fail application startup.
- Mixed-key replicas read the same durable records and produce the same capability for the same binding.
- Locked-wheel tests, PostgreSQL tests, package/Helm/Terraform gates, security review and exact-head CI pass.
- `DENY_RELEASE`, `DENY_APPLY` and default-off publication flags remain unchanged.

## Non-Goals

- No real publication or media upload to a provider.
- No post-publication provider deletion or rights-withdrawal effect.
- No production secret creation, rotation execution, infrastructure apply or deployment.
- No change to legal retention, deletion, legal-hold or jurisdiction decisions.
