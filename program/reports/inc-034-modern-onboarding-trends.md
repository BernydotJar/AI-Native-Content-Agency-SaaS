# INC-034 Modern Onboarding and Trend Research

Date: 2026-07-28

## Objective

Convert the primary CampaignOS surface from a technical runtime console into a clear,
modern campaign workspace while preserving the existing governed execution and social
account controls.

## Implemented product changes

- Replaced the technical hero copy with an outcome-oriented campaign entry point and
  direct links to campaign creation and the eight-station flow.
- Made the top session state actionable. Signed-out users can open a username/password
  form without scrolling to the command section.
- Kept server-derived identity, role, tenant and permissions authoritative. The password
  is exchanged for an HttpOnly session and cleared from the browser form.
- Replaced the unexplained `Greenlight visible` label with `Aprobación manual`; the
  required compliance disclosure now explains that Greenlight is a human approval bound
  to an exact version.
- Added previous/next navigation and an explicit station counter to the eight-station
  orchestration map.
- Added an authenticated, read-only Guatemala trend radar backed by Google Trends RSS.
  It requires no API key, enables no publication or spend, and never fabricates fallback
  results.
- Centralized the five model providers in one selector with a progressive
  `Configurar proveedor` panel. Credentials remain server-side and are never requested
  or enumerated through the public provider API.
- Kept `Video Use` visible as `Revisada · deshabilitada`.
- Preserved the existing X and Instagram account-management surfaces.
- Corrected the local launcher database default from ephemeral `/tmp` storage to the
  persistent `.local/ai-native-content-agency-local.sqlite3` workspace volume.
- Added no autoplay music. Audio remains outside this increment.

## Safety and truthfulness

- Social, political publication and paid-media switches are not changed by this
  increment and were verified `false` after runtime restart.
- Trend requests are constrained to one allowlisted HTTPS destination, do not follow
  redirects, ignore environment proxies, enforce a response-size limit and fail closed.
- Provider readiness continues to mean configuration evidence only, not live inference,
  approved spend or automatic run integration.
- No provider credential value or credential environment name was added to the public
  provider response.
- Compliance remains `DENY_RELEASE` and cloud apply remains unauthorized.

## Verification evidence

```text
Locked backend wheel: 313 tests PASS; 25 PostgreSQL-only skips expected
Frontend: 54 tests PASS
Oxlint: 0 warnings, 0 errors
Production build: PASS
Automated Chromium 320 px reflow/accessibility/modern-workspace gate: PASS
Program validator: PASS
Release compliance validator: PASS
Diff check: PASS
Real local trend endpoint: HTTP 200, Google Trends RSS, 8 verified items
Persistent local database after migration: 196608 bytes; process path verified
Second API restart: session/audit/social row counts preserved exactly
```

Focused coverage includes:

- username mismatch rejection and generic authentication failure;
- username/password browser session creation;
- trend parser allowlist, bounds and invalid-document failure;
- authenticated trend API and sanitized provider failure;
- locked, loaded and unavailable radar UI states;
- actionable top login control;
- eight-station previous/next navigation;
- centralized DeepSeek selection/configuration guidance;
- reviewed-disabled Video Use status;
- persistent local database defaults in both local launchers;
- focus returning to the top login trigger after modal closure.

## Runtime recovery finding

The previous local launcher defaulted SQLite to
`/tmp/ai-native-content-agency-local.sqlite3`. Replacing the workstation runtime
removed that filesystem and therefore removed the prior OAuth connection rows. No
recoverable database containing those rows remained in `/workspace`, `/home` or `/tmp`.
The new runtime reported both X and Instagram as `not_connected`; no disconnect or OAuth
mutation was executed during INC-034.

The current database was migrated with SQLite's backup API into `.local/` and the API
process was restarted against that exact persistent path. Previous X and Instagram
connections require new interactive authorization after a stable public callback is
available. Logs and receipts are not treated as token recovery material.

The local runtime is healthy. The account-less Cloudflare quick tunnel process was able
to register, but two newly issued hostnames did not resolve through DNS from the
workstation and the previous hostname was unavailable. The unresolved tunnel was stopped
to avoid leaving an unverified public route active. Public health is therefore not
claimed.

## Remote delivery fallback

The audited Cloud Sandbox `git_push` operation failed before contacting GitHub because
its isolated ownership helper starts a nested Docker daemon with fixed `iptables`
initialization that this workstation is not permitted to perform. Recreating the runtime,
normalizing workspace ownership and starting a no-iptables daemon in the active
workstation did not change that isolated helper.

The implementation was therefore published through GitHub's Git Data API using the
already authenticated `gh` client in the persistent workspace. The remote commit
`57dd2dc08408d7bcd1acc90a7eeb96cc6fa8e31f` is based on
`ecd72ece9a97fc0587d88277be876c386cfb4263` and updates exactly the 25 implementation,
test, runbook and product files in scope before this delivery checkpoint. A recursive
remote-tree comparison verified all 25 blob SHAs and file modes against the validated
local worktree with zero mismatches.

## Pull request and exact-head CI

Draft PR #27 targets `agent/inc-022-governed-media-verification`. Its first exact-head
workflow found one stale browser-fixture assumption: the political authority verifier
filled only the old credential field after the product login changed to username plus
password. Commit `296c8e3a2791586d893b680cd6af38913156958a` updated that test contract and
was reproduced locally end to end.

Workflow `30390791007` then completed with 8/8 successful jobs: verify, python-locks,
PostgreSQL shared state, container, workflow lint, Helm, Terraform and supply chain.

## Remaining operational gate

Restore a stable HTTPS callback before any future interactive social authorization. No
external social post is required or authorized by this increment.
