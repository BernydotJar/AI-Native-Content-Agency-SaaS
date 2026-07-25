# Governed Publication Media Runbook

## Safety defaults

- `AGENCY_PUBLIC_MEDIA_BASE_URL` and `AGENCY_PUBLIC_MEDIA_SIGNING_KEY` must be configured together.
- `AGENCY_PUBLIC_MEDIA_TTL_SECONDS` defaults to 86400 and must remain between 900 and 604800.
- `AGENCY_SOCIAL_PUBLICATION_ENABLED=false` and `AGENCY_POLITICAL_PUBLICATION_ENABLED=false` remain the safe defaults.
- Helm reads the signing key only from an existing Kubernetes Secret.

## Upload and approval

1. Operator selects one JPEG 4:5 image and supplies meaningful alt text.
2. Operator confirms rights/consent.
3. Runtime fully decodes the JPEG, validates dimensions/size and calculates SHA-256.
4. Bytes and metadata are persisted before a `publication_media` artifact is added to the run.
5. Human Greenlight approves the exact copy and media artifact hashes.

## Revocation

- Before Greenlight: use the authenticated media-revocation command. The artifact is removed and origin access returns 404. Cache propagation is bounded to five minutes.
- After Greenlight: revoke the Greenlight first. Do not assume local media revocation deletes a provider post.
- After provider publication: inspect the durable receipt/permalink, determine provider state and execute a separately authorized deletion/reconciliation procedure.

## Signing-key rotation

The current contract uses one active HMAC signing key. Existing public lookups use stored token digests and remain valid until expiry, but deterministic replay of an active binding expects the key that generated it.

Safe rotation procedure:

1. stop new uploads or deploy a keyring-capable release;
2. retain the previous key for at least maximum media TTL plus the retry/reconciliation window;
3. wait for all active pre-Greenlight bindings to expire or revoke them;
4. rotate the Secret and restart workloads;
5. verify upload, replay and public lookup in staging;
6. remove the old key only after evidence confirms no active binding requires it.

## Unknown provider outcome

Never retry automatically after `media_publish` or an ambiguous response. The intent remains `unknown`; inspect provider state, compare account/media/caption hashes and reconcile with a distinct admin command.

## Incident evidence

Retain:

- run, artifact and Greenlight IDs;
- provider container/post IDs;
- binding, caption and media hashes;
- verification status/request ID/permalink/timestamp;
- audit actor/request ID;
- no raw access tokens, signing keys, captions or media bytes in logs.
