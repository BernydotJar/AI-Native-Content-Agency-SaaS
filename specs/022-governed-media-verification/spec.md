# INC-022 — Governed Publication Media and Verified Instagram Receipt

Status: approved
Owner: Orchestrator
Date: 2026-07-25

## Problem

Instagram OAuth and exact-once publication intent exist, but a run cannot produce an approved `publication_media` artifact. The existing authority publishes immediately after container creation and treats the returned media ID as success without waiting for the container or independently reading the published media.

## Primary platform evidence

The official Meta Instagram API collection documents that:

- image publishing creates a media container from a publicly reachable image URL;
- container status must be queried until `status_code=FINISHED` before publishing;
- `media_publish` returns the published media ID;
- media objects expose fields such as caption, media type, permalink, timestamp and username for independent verification.

Sources inspected 2026-07-25:

- Meta official Instagram API Postman collection, Content Publishing folder;
- Meta official Instagram API Postman request for container status;
- Meta official Instagram API Postman media reference requests.

## Scope

### task_id: INC-022
### workstream_id: WS-08
### role

Media Engineer / Backend Engineer / Data Engineer / Security Reviewer / Red Team / Independent Verifier

### objective

Create a durable immutable JPEG media vault, bind a media artifact to a run before Greenlight, serve the exact bytes through an opaque public URL, wait for Instagram container completion and persist a read-after-write verified receipt.

### allowed_paths

- `backend/agency_runtime/publication_media.py`
- `backend/agency_runtime/publication_media_store.py`
- `backend/agency_runtime/publication_media_postgres.py`
- `backend/agency_runtime/api.py`
- `backend/agency_runtime/postgres.py`
- `backend/agency_runtime/social_publication.py`
- `backend/agency_runtime/social_publication_store.py`
- `backend/requirements*.in`
- `backend/requirements*.lock`
- `backend/setup.cfg`
- `backend/tests/test_publication_media*.py`
- `backend/tests/test_social_publication*.py`
- `backend/tests/fixtures/publication-media-320x400.jpg`
- `src/lib/runtimeApi.ts`
- `src/components/CampaignOutputPanel.tsx`
- `src/components/CampaignOutputPanel.test.tsx`
- `src/components/PublicationConfirmationDialog.tsx`
- `.env.example`
- `infra/**`
- `scripts/**`
- `program/**`
- `specs/022-governed-media-verification/**`

### prohibited_paths/actions

- `.env.local` or credentials;
- real Instagram/X publication;
- cloud resource creation or spend;
- carousel/reel publication;
- background retries after unknown provider outcome;
- mutable external URLs without byte/hash ownership.

## Media Vault contract

Input endpoint:

`POST /api/v1/runs/{run_id}/publication-media/instagram`

- session + CSRF + `social:publish` required;
- raw body `image/jpeg` only;
- `Idempotency-Key` required;
- `X-Media-Alt-Text-Base64` required (base64url of UTF-8 alt text);
- `X-Media-Rights-Confirmed: true` required;
- run must be `awaiting_greenlight` and have no active Greenlight;
- maximum 8 MiB;
- decoded dimensions must be 320–1440 px and exact 4:5 portrait for this increment;
- Pillow must fully decode and verify the image;
- SHA-256 is calculated by the server;
- media bytes, dimensions, metadata, rights-attesting subject and opaque token digest are durable in SQLite/PostgreSQL;
- the run receives exactly one `publication_media` artifact for Instagram;
- same idempotency/binding replays, changed binding conflicts;
- public route returns exact immutable bytes until expiry and no tenant metadata.

Configuration:

- `AGENCY_PUBLIC_MEDIA_BASE_URL`: required for upload, HTTPS except explicit test/local loopback;
- `AGENCY_PUBLIC_MEDIA_TTL_SECONDS`: default 86400, bounded 900–604800;
- publication remains disabled by default.

## Verified Instagram publication contract

1. reserve exact-once durable intent;
2. `POST /{account_id}/media`;
3. persist `container_id` before subsequent calls;
4. poll `GET /{container_id}?fields=status_code,status`;
5. publish only when `status_code=FINISHED`;
6. provider terminal error becomes failed; poll exhaustion/transport ambiguity becomes unknown;
7. `POST /{account_id}/media_publish`;
8. `GET /{media_id}?fields=id,caption,media_type,permalink,timestamp,username`;
9. verify ID, account username, exact caption hash, `IMAGE`, HTTPS Instagram permalink and parseable timestamp;
10. only then complete the durable intent with `verification_status=verified`.

The receipt must contain hashes and provider metadata, never raw caption, tokens or media bytes.

## TDD acceptance criteria

- invalid/truncated JPEG, wrong MIME, oversized bytes, wrong dimensions, missing alt text and missing rights are rejected;
- exact bytes and metadata survive SQLite restart and PostgreSQL shared state;
- public token is opaque, tenant-safe and expiry-aware;
- upload before Greenlight produces one approved-candidate artifact; upload after Greenlight is denied;
- media hash in artifact matches stored bytes;
- container `IN_PROGRESS -> FINISHED` publishes once;
- container `ERROR` fails without `media_publish`;
- poll exhaustion is unknown and blocks retry;
- post read mismatch is unknown and requires reconciliation;
- verified receipt includes permalink/timestamp/username and caption/media hashes;
- X behavior remains unchanged;
- frontend permits JPEG selection, alt text and rights confirmation but never silently enables publication.

## Human gates

- rights/consent attestation;
- accessibility review;
- candidate/campaign/legal approval for political content;
- explicit general and political publication enablement;
- one separately authorized sandbox post;
- production object-storage/retention/privacy review;
- merge, deployment and release.
