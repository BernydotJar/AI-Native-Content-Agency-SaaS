# INC-020 Social Publication Authority Review

Updated: 2026-07-24
Implementation commit: `8eb0cf7dee9b3400351a8b7d603a94666253f1e7`
Branch: `agent/inc-020-social-publication-authority`
Status: `review`
Release: `DENY_RELEASE`
Real provider publication: `NOT_RUN`

## Objective

Allow an administrator to publish an exact approved X or Instagram output only after a
server-derived account/artifact/media/Greenlight binding has been persisted as a durable
intent, while preventing duplicate external effects after replay, crash or ambiguous
provider outcomes.

## Delivered

- SQLite and PostgreSQL schema v3 publication intents with a unique tenant/binding digest.
- X `POST /2/tweets` and Instagram `/media` then `/media_publish` adapters.
- Fixed provider hosts, one attempt, bounded response bytes/time and sanitized errors.
- Pending, succeeded, failed, unknown and revoked states with bounded receipts.
- Different idempotency keys reuse one exact effect; incompatible bindings conflict.
- Unknown outcomes block automatic retry and require admin reconciliation.
- Reconciliation requires its own digest-only idempotency key and evidence binding.
- Account disconnect and Greenlight revocation invalidate unused pending authority.
- Admin-only HttpOnly-session/CSRF publication and reconciliation routes.
- Server-derived approved copy/media; browser text or media URL is never authority.
- Destructive confirmation naming channel, account, artifact, media and Greenlight.
- Low-cardinality metrics, unknown-outcome alert and incident runbook.
- Default-disabled app, Helm and Terraform configuration with server-side Secret refs.
- Installed-image MockTransport effect smoke with socket guard and zero real provider HTTP.

## Critic findings closed

| Finding | Severity | Resolution |
|---|---:|---|
| Account connection could be mistaken for publication authority. | HIGH | Publication requires admin confirmation, enabled server flag, exact connected account, approved artifact/media and current Greenlight fence. |
| Different command keys could duplicate one economic effect. | HIGH | `(tenant_id, binding_digest)` is unique; compatible keys replay one durable receipt. |
| Provider success followed by receipt failure could duplicate a post. | HIGH | The intent exists before HTTP; uncertain outcomes become `unknown` and cannot retry automatically. |
| Receipt success followed by audit failure could leave missing evidence. | HIGH | Success audit IDs are deterministic; replay repairs the event without another provider call. |
| Manual reconciliation was not replay-safe. | HIGH | It now requires a digest-only idempotency key and exact evidence binding; identical evidence replays and drift conflicts. |
| Worker/store lock inversion could freeze run reads after prior inline work. | HIGH | Runtime resolution now precedes the durable run lock; deterministic order and full reproduction tests pass. |
| Package evidence proved only disabled mode. | MEDIUM | The installed image runs a test-only stdin fixture with MockTransport and socket guard; the fixture is not copied into the image. |

## Exact verification

```text
Locked Python wheel                         PASS — 226 tests, 19 PostgreSQL skips
PostgreSQL shared runtime                   PASS — 226/226, schema v3
PostgreSQL least privilege                  PASS — non-owner runtime grant matrix
Frontend                                    PASS — 38/38
Oxlint / TypeScript / Vite                  PASS
Chromium accessibility                      PASS
Chromium social output                      PASS
Chromium cross-site OAuth                   PASS — MockTransport only
Chromium async topology                     PASS — 7 stations, 14 checkpoints
Chromium publication confirmation           PASS — 0 calls before confirm, 1 after, replay stays 1
Buildah non-root package                    PASS
Installed-image publication effect          PASS — MockTransport + socket guard
Helm/Terraform/K3s lifecycle                PASS — SQLite and PostgreSQL
Operability                                 PASS — 4 SLOs, 8 alerts, 9 exercises
Actionlint / Gitleaks / whitespace          PASS
Clean-source supply chain                   PASS — source 8eb0cf7, no registry publication
Real X/Instagram publication                NOT_RUN
Real provider credentials/tokens            NOT_USED
Cloud deployment / spend                    NOT_RUN
Remote push / exact-head CI                 PENDING
```

## Remaining boundary

The implementation is locally review-ready, not production-authorized. Enabling
`AGENCY_SOCIAL_PUBLICATION_ENABLED=true`, registering callbacks, using real accounts,
publishing a sandbox post, accepting current provider terms/pricing/privacy, merging,
deploying or spending all remain explicit human/external gates. Instagram also remains
blocked until a real approved `publication_media` artifact exists.
