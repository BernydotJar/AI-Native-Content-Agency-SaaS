# Current Program State

Updated: 2026-07-28

## Exact repository state

- Workspace: `7759306b-d1ea-40ed-92dc-b78424c749ba`
- Active branch: `agent/inc-036-trend-pilot`
- Current local parent: `37aede9789b16842f0ee47f47d87ba8863f0938d`
- INC-034 remote branch: `agent/inc-034-modern-onboarding-trends-remote`
- INC-034 draft PR: #27
- INC-034 exact-head workflow: `30390791007`, 8/8 SUCCESS
- INC-035 remote branch: `agent/inc-035-social-runtime-recovery`
- INC-035 remote HEAD: `37aede9789b16842f0ee47f47d87ba8863f0938d`
- INC-035 draft PR: #28, stacked on INC-034
- INC-035 exact-head workflow: `30393061103`, 8/8 SUCCESS
- INC-036 delivery base: `agent/inc-035-social-runtime-recovery`
- INC-036 local implementation commit: `9f9efce2104c9e9cba47e149de339fd3e4e4bfd5`
- Audited Cloud Sandbox `git_push`: blocked by its isolated nested-Docker `iptables`
  initialization; the repository-owned Git Data publisher remains the verified fallback.
- New external publication, paid media, model effect, cloud apply, release or merge: none

## Current product result

CampaignOS provides:

- an outcome-oriented campaign workspace and eight-station orchestration map;
- individual username/password login backed by server-derived roles and HttpOnly sessions;
- server-side provider, integration and social-account configuration;
- encrypted X and Instagram OAuth connections in persistent SQLite;
- automatic connection-state backups and recoverable Quick/Named Cloudflare tunnel modes;
- four no-key research lanes for Guatemala: current searches, AI, marketing and business;
- safe HTTPS evidence disclosure for research signals;
- one-click conversion from a signal to an editable X/Instagram pilot brief;
- explicit review-only labels before and after pilot execution;
- fail-closed publication, political publication and paid-media controls.

## INC-036 live pilot

The production bundle and installed runtime wheel were updated without changing the
public hostname. A real Chromium session used the public UI to log in, select the AI lane,
open evidence, prepare a brief and execute a governed internal run.

```text
run_id=run-ce573811a46d6f06
campaign_goal=trend_response_pilot
status=awaiting_greenlight
platforms=x,instagram
artifacts=7
copy_decks=1
copy_platforms=x,instagram
greenlight=none
social_publication_intents=0
```

No X credits were required because research uses Google Trends/Google News RSS and the
pilot ended before any external provider publication boundary.

## Verification

- Backend: 323 PASS; 25 PostgreSQL-only skips expected.
- Frontend: 58 PASS.
- Focused trend, workspace and output tests: 39 PASS.
- Oxlint: zero warnings/errors.
- Production build: PASS.
- Automated Chromium 320 px reflow, keyboard, focus, reduced-motion and accessibility
  tree gates: PASS.
- Live authenticated research API:
  - `general`: HTTP 200, Google Trends RSS, 8 signals, 24 evidence links;
  - `ai`: HTTP 200, Google News RSS, 8 signals, 8 evidence links;
  - `marketing`: HTTP 200, Google News RSS, 8 signals, 8 evidence links;
  - `business`: HTTP 200, Google News RSS, 8 signals, 8 evidence links.
- Live public Chromium trend-pilot flow: PASS.
- Runtime restart preserved two encrypted social connections exactly.
- SQLite integrity: `ok`.

## Runtime state

- Public URL: `https://offerings-council-guided-requiring.trycloudflare.com`
- Local health: HTTP 200.
- Public health: HTTP 200.
- Tunnel: Quick Tunnel, running.
- Database: `/workspace/.local/ai-native-content-agency-local.sqlite3`.
- Social backup watcher: running.
- Latest backup: available and includes both connections.
- X: connected as `@beesheep` with `tweet.read`, `tweet.write`, `users.read`.
- Instagram: connected as `@beesheep2` with professional basic/content-publish scopes.
- Social publication: `false`.
- Political publication: `false`.
- Political paid media: `false`.
- External effects enabled: `false`.

The Quick Tunnel is suitable for this laboratory pilot but remains ephemeral. Named
Cloudflare Tunnel support is implemented and is the durable option when a stable hostname
and token are available.

Release recommendation: `DENY_RELEASE`

Cloud recommendation: `DENY_APPLY`

## Exact resume condition

Continue evaluating the research-to-draft workflow in the UI. Review evidence and copy,
but do not approve Greenlight, enable publication switches or create a provider post
without a separate explicit authorization. A future production-like callback should use
a named Cloudflare Tunnel before relying on the connection for long-lived operations.
