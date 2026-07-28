# INC-036 — Free trend research and governed UI pilot

Updated: 2026-07-28

## Objective

Turn the existing read-only Guatemala trend list into an evidence-backed editorial pilot
that can be exercised end to end through CampaignOS without X API credits, external model
inference, social publication, paid media or cloud spend.

Implementation commit: `9f9efce2104c9e9cba47e149de339fd3e4e4bfd5`

## Product result

CampaignOS now exposes four fixed, no-key research lanes:

- current Google Trends searches for Guatemala;
- artificial-intelligence news related to Guatemala;
- marketing and audience news related to Guatemala;
- business and entrepreneurship news related to Guatemala.

The backend accepts only `general`, `ai`, `marketing` and `business`. Destinations and
queries are fixed in code, responses are bounded, redirects are rejected and only safe
HTTPS evidence links are returned.

Each signal can now disclose its supporting articles and create an editable pilot brief.
The generated brief selects X and Instagram, sets budget to zero, records the source as an
unverified evidence claim and explicitly instructs CampaignOS not to publish. The command
surface and output panel both label the run as a review-only trend pilot.

## Real runtime pilot

The installed wheel and production web bundle were updated in place while retaining the
existing Quick Tunnel, persistent SQLite database and backup watcher. A headless Chromium
operator then completed the real public workflow:

1. username/password login;
2. selection of the AI research lane;
3. loading eight Google News RSS signals;
4. opening an HTTPS evidence article;
5. pressing **Preparar piloto**;
6. verifying the prefilled title, objective, audience and X/Instagram selection;
7. pressing **Ejecutar campaña**;
8. observing the review-only output and two disabled publication buttons.

The resulting internal run is `run-ce573811a46d6f06`. It is
`awaiting_greenlight`, has `campaign_goal=trend_response_pilot`, contains seven artifacts
and one copy deck with X and Instagram variants. No Greenlight was issued and
`social_publication_intents` remains empty.

## Live source evidence

The deployed authenticated endpoint returned HTTP 200 for all four lanes:

```text
general  Google Trends RSS  8 signals  24 evidence links
ai       Google News RSS    8 signals   8 evidence links
marketing Google News RSS   8 signals   8 evidence links
business Google News RSS    8 signals   8 evidence links
```

The pilot selected the current AI signal about Guatemalans' practical questions around
using artificial intelligence. That signal remains evidence to review, not an automatically
verified claim.

## Safety state after the pilot

```text
social connections: 2
X: @beesheep
Instagram: @beesheep2
SQLite integrity: ok
social publication intents: 0
social publication enabled: false
political publication enabled: false
political paid media enabled: false
public health: HTTP 200
backup watcher: running
```

No post, ad, model effect, cloud apply, release or merge was executed.

## Validation evidence

```text
Backend: 323 PASS; 25 PostgreSQL-only skips expected
Frontend: 58 PASS
Focused trend/UI/output tests: 39 PASS
Oxlint: 0 warnings, 0 errors
Production build: PASS
Chromium 320 px reflow/accessibility gates: PASS
Live authenticated API, four research lanes: PASS
Live public Chromium trend-pilot workflow: PASS
Persistent SQLite and two OAuth connections after restart: PASS
Publication intents after pilot: 0
```

Release recommendation: `DENY_RELEASE`

Cloud recommendation: `DENY_APPLY`
