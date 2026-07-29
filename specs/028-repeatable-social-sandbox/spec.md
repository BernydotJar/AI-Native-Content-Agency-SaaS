# INC-028 — Repeatable Neutral Social Sandbox

## Objective

Prove that the governed social-publication path can execute a second distinct Instagram sandbox Post and can apply equivalent exact-once and read-after-write authority to X.

## Instagram acceptance criteria

1. Content variant `repeatability-v2` differs from the first sandbox Post.
2. Caption remains neutral and contains no electoral call to action or paid media.
3. JPEG is a distinct 1080×1350 immutable artifact.
4. A new operation, run, Greenlight and intent are required.
5. Execution remains blocked until `@beesheep2` is freshly authorized.
6. One provider effect must produce a verified receipt and switches must close automatically.

Frozen candidate hashes before provider preparation:

- caption SHA-256: `aeb1f60552617105983d4d824005593b10284a25e61b676a8dbbe14cab40327d`
- media SHA-256: `6354500371bccee532930e5fa37084ed56dda5e251f3ebfbcd99bfa3516ba9ea`

## X acceptance criteria

1. OAuth 1.0a API key/secret and exact callback are server-side only.
2. Neutral text is at most 280 characters and has no electoral call to action.
3. Prepare uses two authenticated subjects and independent Greenlight.
4. Execute reserves one intent before provider HTTP.
5. Create uses `POST /2/tweets`.
6. Success requires signed lookup of the created Post and exact text/author/timestamp verification.
7. Mismatch or ambiguity becomes durable `unknown` with no automatic retry.
8. Receipt omits tokens, secrets, text and raw confirmation.
9. Switches close after the bounded window.

## Current external gates

- Instagram requires a fresh interactive OAuth authorization because the prior bounded credential expired.
- X requires an approved Developer App API Key and Secret; none exists in the workstation.
- `DENY_RELEASE` and `DENY_APPLY` remain unchanged.
