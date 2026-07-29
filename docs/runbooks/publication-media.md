# Governed Publication Media Runbook

## Safety defaults

- `AGENCY_PUBLIC_MEDIA_BASE_URL` and exactly one signing mode must be configured together.
- Preferred mode uses `AGENCY_PUBLIC_MEDIA_SIGNING_KEYS_JSON` plus `AGENCY_PUBLIC_MEDIA_ACTIVE_SIGNING_KEY_ID`.
- Migration-only mode uses `AGENCY_PUBLIC_MEDIA_SIGNING_KEY`; never configure it with the preferred keyring variables.
- `AGENCY_PUBLIC_MEDIA_TTL_SECONDS` defaults to 86400 and must remain between 900 and 604800.
- `AGENCY_SOCIAL_PUBLICATION_ENABLED=false` and `AGENCY_POLITICAL_PUBLICATION_ENABLED=false` remain the safe defaults.
- Helm reads signing configuration only from a pre-existing Kubernetes Secret. Terraform receives only the Secret name and data-key names.

Preferred Secret values:

```text
public-media-signing-keys.json       # {"media-v1":"<base64url-32-byte-key>","media-v2":"..."}
public-media-active-signing-key-id   # media-v2
```

Do not place either value in Git, Helm values, Terraform variables, command lines, logs or evidence records.

## Upload and approval

1. Operator selects one JPEG 4:5 image and supplies meaningful alt text.
2. Operator confirms rights/consent.
3. Runtime fully decodes the JPEG, validates dimensions/size and calculates SHA-256.
4. The active signing key ID, token digest, bytes and metadata are persisted before a `publication_media` artifact is added to the run.
5. Human Greenlight approves the exact copy and media artifact hashes.

## Revocation

- Before Greenlight: use the authenticated media-revocation command. The artifact is removed and origin access returns 404. Cache propagation is bounded to five minutes.
- After Greenlight: revoke the Greenlight first. Do not assume local media revocation deletes a provider post.
- After provider publication: inspect the durable receipt/permalink, determine provider state and execute a separately authorized deletion/reconciliation procedure. Provider deletion remains a legal and external-effect gate.

## Rotation-safe keyring procedure

The durable media row records the key ID that generated its capability. New bindings use the active key; replay uses the stored historical key. Existing opaque URL format and token digests remain unchanged.

1. Generate a new 32-byte random key outside the repository and encode it as unpadded base64url.
2. Add the new key ID/value to the existing keyring Secret while retaining every key referenced by an unexpired durable media record.
3. Deploy the expanded keyring with the previous active key unchanged and verify readiness.
4. Change only `public-media-active-signing-key-id` to the new key ID and restart/roll the workload.
5. In staging, prove:
   - replay of an old binding returns the exact prior URL;
   - a new binding persists the new key ID;
   - public lookup returns the exact approved bytes;
   - no provider publication is enabled by the rotation.
6. Retain the old key for at least the maximum media TTL plus the bounded retry/reconciliation window.
7. Query durable state for unexpired, non-revoked records using the old `public_signing_key_id`. Remove the old key only when the count is zero and the change is approved.

Removing a required historical key is intentionally fail-closed: replay returns a generic service-unavailable response and never signs with a substitute key.

## Legacy migration

Existing schema rows migrate to `public_signing_key_id=legacy`. During the migration window:

1. Configure the original raw secret only as `AGENCY_PUBLIC_MEDIA_SIGNING_KEY`.
2. Upgrade SQLite or initialize PostgreSQL schema v7.
3. Verify an existing capability and a different-idempotency replay.
4. Introduce a preferred keyring only after legacy bindings have expired/revoked, or include a reviewed migration that preserves the exact legacy HMAC bytes.
5. Do not configure legacy and preferred modes simultaneously.

## Rollback

- Before removing an old key, rollback consists of restoring the prior active key ID; both keys remain present.
- After an accidental removal, immediately re-add the exact prior key under the same ID and roll the workload. Do not generate a replacement under the old ID.
- Database rollback must preserve `public_signing_key_id`; dropping the column would make mixed-key replay ambiguous.
- Any production Secret mutation or workload rollout requires the configured human deployment gate.

## Unknown provider outcome

Never retry automatically after `media_publish` or an ambiguous response. The intent remains `unknown`; inspect provider state, compare account/media/caption hashes and reconcile with a distinct admin command.

## Incident evidence

Retain:

- run, artifact and Greenlight IDs;
- public signing key ID, never key material;
- provider container/post IDs;
- binding, caption and media hashes;
- verification status/request ID/permalink/timestamp;
- audit actor/request ID;
- no raw access tokens, signing keys, captions or media bytes in logs.
