# INC-019 — Tenant-owned X and Instagram OAuth with governed publication

## Problem

A tenant can prepare and approve channel copy, but the product has no tenant-owned social
account authorization or durable publication receipt. App credentials identify the SaaS
application; they do not authorize posting for every customer account.

X can publish text directly. Instagram publishing requires a Professional account and a
media asset (image, reel, or carousel) in addition to the caption. The product must expose
that distinction before any external effect exists.

## Objective

1. Expose secret-free server configuration readiness for X and Instagram.
2. Make copy, media, Greenlight, account, and publication readiness visible per channel.
3. Add tenant-bound OAuth authorization and encrypted token storage.
4. Publish an approved artifact exactly once using a durable intent/fence/receipt boundary.

## Actors

- Tenant admin configures the app and connects/disconnects social accounts.
- Operator prepares copy and media but cannot authorize publication.
- Approver grants/revokes Greenlight for exact artifact/channel versions.
- Publisher executes a durable channel-specific publication intent.

## Current readiness states

- `missing_credentials`
- `missing_redirect_uri`
- `ready_for_authentication`
- `connected`
- future: `publishing_available`

## Security and correctness invariants

1. Consumer/app secrets, access tokens, and refresh tokens never enter frontend storage,
   API responses, audit payloads, screenshots, or logs.
2. OAuth state/PKCE or OAuth 1.0a temporary credentials are single-use, expiring, and
   tenant/session-bound.
3. Callback identity is verified before encrypted token storage.
4. Tokens are encrypted with a deployment-provided key/KMS abstraction and versioned.
5. Publication binds tenant, account, run, artifact version, text/media hash, channel, and
   Greenlight fencing token.
6. A durable publication intent exists before the provider request.
7. Provider response ID/usage is persisted before success is returned.
8. Unknown outcomes block retry and require reconciliation.
9. Greenlight revocation or account disconnect invalidates unused authority.
10. Rate-limit, quota, and spend errors are sanitized and observable.
11. Instagram cannot be marked publishable without a rendered supported media asset.

## Channel contracts

### X

- App configuration: Consumer Key/Secret or compatible OAuth client aliases.
- User context required.
- Create-post protocol: `POST /2/tweets`.
- Text-only publication is permitted by the product contract.

### Instagram

- App configuration: Instagram App ID/Secret.
- Instagram Professional account (Business or Creator) required.
- Permissions: `instagram_business_basic` and
  `instagram_business_content_publish` for Instagram Login.
- Publish protocol: create `/media` container, then call `/media_publish`.
- A public/retrievable image, reel, or carousel asset is required before publication.

## UX

- Account and app readiness live in Settings/Admin.
- Each output card shows Copy → Asset → Greenlight → Account → Publication.
- Instagram displays a square channel preview and an explicit missing-media state.
- `Publicar` remains disabled until every channel-specific requirement is true.
- A future destructive confirmation names the account, channel, and exact post/media.

## Non-goals of the readiness slice

- Asking users to paste secrets in the browser.
- Issuing OAuth redirects before encrypted token storage and state persistence exist.
- Posting during CI.
- Automatic publication without an explicit approval/action.
- Assuming provider pricing or terms are stable.
