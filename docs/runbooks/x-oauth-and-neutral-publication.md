# X OAuth and Neutral Publication Runbook

## Purpose

This runbook governs one neutral, organic, text-only X sandbox publication. It does not authorize campaign persuasion, paid media, production rollout or repeated unattended posting.

## X application prerequisites

The tenant must have an approved X Developer App with:

- OAuth 1.0a enabled;
- Read and Write app permissions;
- the exact callback URL registered;
- an API Key and API Key Secret stored only in server-side environment variables.

Required runtime variables:

```dotenv
AGENCY_X_CONSUMER_KEY=<server-side secret>
AGENCY_X_CONSUMER_SECRET=<server-side secret>
AGENCY_X_REDIRECT_URI=https://<active-origin>/api/v1/social-channels/x/oauth/callback
```

Do not paste these values into chat, manifests, receipts, Git or browser storage.

## OAuth flow

CampaignOS implements three-legged OAuth 1.0a:

1. `POST https://api.x.com/oauth/request_token` with the exact callback;
2. browser authorization at `https://api.x.com/oauth/authorize`;
3. callback with `oauth_token` and `oauth_verifier`;
4. `POST https://api.x.com/oauth/access_token`;
5. encrypted server-side storage of the user access token and secret.

The request-token secret is encrypted while pending. Callback state is single-use and expires after ten minutes. A replay or cross-session callback fails closed.

## Neutral content

The first governed X test uses this deterministic text:

```text
Una propuesta verificable para prueba técnica en cuenta de laboratorio en X.

CampaignOS propone: Validar publicación exact-once y verificación posterior sin pauta

Fuente: Runbook neutral (X-1).

Prueba técnica. No corresponde a una campaña electoral.

No se requiere acción.
```

Properties:

- 276 characters;
- no electoral call to action;
- no paid media;
- no targeting;
- no media attachment;
- SHA-256 `582e6e4137624526250a0feab6abf0a4a9b502e453f703f42dcc7a8956170f96`.

## Governed sequence

1. Keep general and political publication switches false.
2. Confirm exact X username, account ID and `tweet.write` scope.
3. Run `scripts/neutral_x_publication.py prepare` with a new operation ID.
4. Require a completed run, Critique publication eligibility, independent Greenlight and a political compliance record in the approved envelope.
5. Inspect the exact text hash and the 15-minute execution window.
6. Enable only general and political organic publication.
7. Type the exact phrase `PUBLICAR POLITICA <run_id> x`.
8. Execute once with the prepared idempotency binding.
9. Require create response plus independent `GET /2/tweets/{id}` verification.
10. Disable both publication switches even when X rejects or the outcome is ambiguous.

## Read-after-write contract

A create response is not sufficient for `succeeded`. CampaignOS signs and performs a second OAuth 1.0a request to retrieve the new Post with `author_id` and `created_at` fields. The durable receipt is verified only when:

- provider Post ID is numeric and matches the lookup;
- provider text exactly matches the approved copy;
- `author_id` matches the connected account;
- timestamp is timezone-aware;
- permalink is canonical `https://x.com/<username>/status/<id>`;
- content SHA-256 matches the approved artifact.

A mismatch, 5xx, timeout or malformed lookup becomes `unknown`. It is never retried automatically.

## Rollback and deletion

Closing local switches does not delete a published Post. Provider deletion is a separate external effect requiring explicit account, Post ID, evidence-retention decision and operator approval. Unknown outcomes must be reconciled before any replacement Post.
