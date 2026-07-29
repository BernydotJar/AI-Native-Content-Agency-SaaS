# INC-025 Design — Public Media Signing Keyring

## Decision

Introduce a repository-owned `PublicMediaSigningKeyring` value object. It validates an immutable map of key IDs to 32-byte keys and an active key ID. The public capability remains the existing URL-safe HMAC-SHA256 signature; the durable media row gains `public_signing_key_id` so replay selects the original key rather than the current active key.

## Configuration

Preferred configuration:

- `AGENCY_PUBLIC_MEDIA_SIGNING_KEYS_JSON`: JSON object of key ID to base64url-encoded 32-byte key.
- `AGENCY_PUBLIC_MEDIA_ACTIVE_SIGNING_KEY_ID`: exact active key ID.

Migration-only compatibility:

- `AGENCY_PUBLIC_MEDIA_SIGNING_KEY`: existing raw UTF-8 key, represented internally as key ID `legacy`.

The preferred and legacy forms are mutually exclusive. Base URL and a valid keyring must be configured together. Runtime status exposes only whether media delivery is configured.

## Persistence and Migration

- SQLite adds `public_signing_key_id TEXT NOT NULL DEFAULT 'legacy'` using an idempotent schema migration.
- PostgreSQL runtime schema advances from v6 to v7 and adds the same non-null column with a legacy default.
- New records persist the active key ID.
- Existing records deserialize as `legacy`.
- No key material or token plaintext enters durable storage.

## Replay and Rotation

1. A new binding is signed with the active key and stores that key ID.
2. A replay loads the durable record and signs with its stored key ID.
3. The generated token digest must equal the durable token digest.
4. A missing historical key fails closed before returning a capability or touching a provider.
5. Operators retain an old key for the maximum media TTL plus the bounded retry/replay window, then verify no active durable record depends on it before removal.

## Production Packaging

- Local runner validates preferred or legacy configuration without printing values.
- Helm reads keyring JSON and active ID only from a pre-existing Secret and accepts a base URL/TTL as non-secret values.
- Terraform passes Secret names/data-key names into Helm; key material never enters Terraform variables or state.
- The legacy key remains available only as an explicit migration input and is not the recommended deployment path.

## Security Review

- Key IDs use a bounded allowlist pattern.
- Key material must decode to exactly 32 bytes in preferred configuration.
- Errors never include raw configuration or secret material.
- `repr` and status surfaces reveal active key ID/count at most, never keys.
- Database tampering of the key ID fails validation or replay.
- Existing public lookup remains digest-based and generic-404.

## Files You May Touch

- `.env.example`
- `backend/agency_runtime/api.py`
- `backend/agency_runtime/publication_media_signing.py`
- `backend/agency_runtime/publication_media_store.py`
- `backend/agency_runtime/publication_media_postgres.py`
- `backend/agency_runtime/postgres.py`
- `backend/tests/**publication_media*`
- `backend/tests/test_graph_harness_adapter.py`
- `backend/tests/test_local_product_runner.py`
- `backend/tests/test_neutral_instagram_publication_script.py`
- `backend/tests/test_postgres_runtime.py`
- `backend/tests/test_postgres_schema_cli.py`
- `backend/tests/test_program_state.py`
- `docs/runbooks/publication-media.md`
- `docs/OPERATIONS.md`
- `infra/helm/ai-native-content-agency/**`
- `infra/terraform/**`
- `scripts/manage-runtime-backup.py`
- `scripts/run-local-product.sh`
- `scripts/neutral_instagram_publication.py`
- `scripts/verify-postgresql-runtime.sh`
- `scripts/verify-production-package.sh`
- `scripts/verify-local-infrastructure.sh`
- `program/**`
- `specs/025-public-media-signing-keyring/**`

## Files You Must Not Touch

- production secrets or `.env.local`
- provider account state
- legal/privacy approvals
- unrelated product UI and campaign behavior

## Verification

- focused keyring, migration, replay and tamper tests;
- locked installed-wheel backend suite;
- PostgreSQL shared-state/schema v7 suite;
- Graph Harness/program/compliance/operability validation;
- frontend regression gates;
- OCI/Helm/Terraform/supply-chain/workflow gates;
- exact-head GitHub Actions artifact and independent review.
