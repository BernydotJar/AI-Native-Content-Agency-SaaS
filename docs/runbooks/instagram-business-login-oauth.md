# Instagram Business Login OAuth Runbook

## Purpose

This runbook records the production behavior required to connect an Instagram Professional account through Instagram Business Login without exposing credentials or leaving a misleading connected state.

It covers authentication and credential lifecycle only. It does not authorize publication, paid media, cloud deployment or account changes.

## Required configuration

The runtime requires:

```dotenv
AGENCY_INSTAGRAM_APP_ID=<server-side>
AGENCY_INSTAGRAM_APP_SECRET=<server-side>
AGENCY_INSTAGRAM_REDIRECT_URI=https://<public-origin>/api/v1/social-channels/instagram/oauth/callback
AGENCY_INSTAGRAM_GRAPH_API_VERSION=v24.0
```

The callback must match the app configuration exactly. Quick-tunnel hostnames can expire; verify public DNS and HTTP before starting OAuth.

## Browser and callback controls

1. Start OAuth only from an authenticated browser session with CSRF protection.
2. Bind `state` to tenant, session and channel with a bounded expiry.
3. Use `SameSite=Lax; Secure; HttpOnly` for the browser session so the top-level OAuth return carries the cookie.
4. Consume each state once. Never replay a callback code or state.
5. Request `Accept-Encoding: identity`, read bounded raw bytes, remove compression/length headers and only then parse JSON. This avoids provider compression-decoding failures observed during the initial integration.
6. Never log callback codes, state values, access credentials, provider bodies or capability URLs.

## Instagram credential lifecycle

After the authorization-code exchange, CampaignOS applies these paths in order:

### Initial credential is already long-lived

When the initial response contains a valid `expires_in` of at least 86,400 seconds, CampaignOS:

1. skips the extension request;
2. validates the professional profile through the pinned Graph version;
3. encrypts the credential server-side;
4. stores the explicit expiry.

### Extension is supported

CampaignOS requests extension with:

- `GET https://graph.instagram.com/access_token`;
- `grant_type=ig_exchange_token` and `client_secret` as parameters;
- the initial credential in `Authorization: Bearer`;
- an empty request body.

On success it validates the professional profile with the extended credential, encrypts it and stores the returned expiry.

### Extension is unsupported for Instagram Login

The production account returned this exact bounded tuple:

```text
HTTP 400
provider code 100
provider type IGApiException
phase instagram_long_lived_token_exchange
```

For this tuple only, CampaignOS may use the initial credential after successfully validating that the account is Professional (`BUSINESS`, `CREATOR` or `MEDIA_CREATOR`). The credential:

- remains encrypted server-side;
- is never written to logs or receipts;
- receives a local maximum lifetime of 3,300 seconds (55 minutes);
- becomes `not_connected` after expiry and requires a fresh OAuth flow.

No fallback is allowed for code `190`, malformed responses, network failures, personal accounts or any other provider tuple.

## Revocation and expiry

When Meta returns provider code `190`, or when `token_expires_at` is in the past:

1. block before a new publication intent or provider request whenever expiry is known locally;
2. remove the encrypted connection when invalidity is discovered from the provider;
3. revoke only unused pending intents;
4. preserve failed/succeeded intents for audit;
5. emit `social.reauthorization_required` or `social.disconnected`;
6. show `not_connected` and make OAuth start available.

## Verified recovery sequence

The recovery that succeeded on 2026-07-27 was:

1. remove the invalid encrypted connection after repeated `401 / 190 / OAuthException` read-only probes;
2. merge and deploy the callback, expiry and invalidation repairs;
3. isolate long-lived-exchange failures by phase and safe provider metadata;
4. compare against the earlier working callback implementation;
5. identify the unsupported extension tuple `400 / 100 / IGApiException`;
6. add the bounded 55-minute fallback;
7. pass local wheel/frontend/program/compliance gates and exact-head CI;
8. restart the runtime after merge so Python loads the reviewed package;
9. invalidate old OAuth states;
10. complete a fresh interactive `Allow` flow;
11. verify account ID `27525095797156898` and username `beesheep2` before any publication authority is enabled.

## Operational checks

Before asking an operator to repeat OAuth, confirm:

```text
connection_state=not_connected
oauth_start_available=true
publishing_available=false
pending OAuth states=0
public callback HTTP=200
runtime process started after the reviewed merge
installed package hash matches the checkout
```

After connection, confirm only safe fields:

```text
connection_state=connected
account_username=beesheep2
account_id=27525095797156898
token_expires_at=<present>
scopes include instagram_business_content_publish
```

Do not copy callback URLs containing `code` or `state` into tickets, chat or documentation.
