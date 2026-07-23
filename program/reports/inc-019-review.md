# INC-019 Social OAuth and Encrypted Account Connection Review

Updated: 2026-07-23
Implementation commit: `e3bca9c95a3080e1e7677454996d9ad56469b4f4`
Branch: `agent/inc-019-social-oauth-publication`
Status: `review`

## Objective

Make X and Instagram account connection usable without placing social secrets or tokens
in the browser, Git, API responses, logs or audit payloads.

## Implemented

- X OAuth 1.0a three-legged flow: request token, authorize and access token.
- Instagram Authorization Code flow with Professional-account validation.
- AES-GCM encrypted token storage with versioned key IDs, tenant/channel AAD and rotation.
- Single-use, expiring OAuth state bound to tenant, browser session and channel.
- SQLite and PostgreSQL schema v2 stores with atomic callback consumption.
- Cross-replica callback replay protection and least-privilege PostgreSQL grants.
- Admin-only OAuth start/disconnect with HttpOnly session and CSRF.
- Connected account metadata without token disclosure.
- Server-side token bootstrap for existing X/Instagram tokens; partial groups fail startup.
- `.env.local` auto-loading, tracked-file refusal and a fresh 32-byte key generator.
- Helm/Terraform references to a pre-existing Secret; no secret values in Terraform state.
- Settings UI with Connect/Disconnect, callback return notice and encrypted-storage status.
- No publication route; external publication remains disabled.

## Critic findings

| Finding | Severity | Resolution |
|---|---:|---|
| OAuth tokens could be persisted in plaintext or rebound across tenants. | CRITICAL design | AES-GCM with tenant/channel AAD; wrong tenant/tampering fails closed; raw tokens absent from SQLite/API/audit. |
| OAuth callback could replay or be consumed by another session. | HIGH | SHA-256 state/token lookup, ten-minute expiry and atomic single-use consume bound to tenant/session/channel. |
| Simultaneous PostgreSQL callbacks could both succeed. | HIGH | `UPDATE ... RETURNING` atomic consume; two-store race proves one success and one unavailable. |
| Bootstrap could accept partial or unencrypted token groups. | HIGH | Exact required groups, explicit tenant, app/callback and encryption keys; application startup fails otherwise. |
| Concurrent replicas could duplicate bootstrap audit. | MEDIUM | Deterministic event ID serialized by the durable command lock. |
| Provider responses could be unbounded or reflect secrets. | HIGH | Streaming 1 MiB bound, no redirects/proxies/retries and fixed sanitized public errors. |
| UI could invite users to paste tokens in the browser. | HIGH UX | No token fields; admin receives provider OAuth redirect or uses server-side `.env.local`/Secret bootstrap. |
| Account connection could be mistaken for publication readiness. | HIGH product | `publishing_available=false`, no publish route and INC-020 records exact-once publication as separate work. |

## Verification

```text
Locked Python wheel                         PASS — 183 tests, 14 PostgreSQL skips
PostgreSQL shared runtime                   PASS — 183/183
PostgreSQL schema                           PASS — v2, migration, grants, backup/restore
Frontend                                    PASS — 35/35
Oxlint / TypeScript / Vite                  PASS
Chromium accessibility                      PASS
Chromium X/Instagram output                 PASS
Buildah non-root package                    PASS
OAuth routes governed                       PASS
Social publication routes absent            PASS
K3s/Helm/Terraform plan/apply/destroy       PASS
Actionlint                                  PASS
Gitleaks history/worktree                   PASS — zero leaks
Compliance                                  PASS — DENY_RELEASE, 0 active providers
Real X/Meta OAuth or publication             NOT_RUN
Real credentials/tokens                     NOT_USED
```

## Exact remaining boundary

INC-020 must persist a publication intent before any X/Instagram post request, bind it to
the exact tenant/account/run/artifact/media/Greenlight fence, persist the provider receipt
before success and block uncertain outcomes without automatic retry. Until then the
`Publicar` action remains disabled.
