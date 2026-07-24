# Current Operational State

Updated: 2026-07-24
Program phase: active
Release recommendation: `DENY_RELEASE`
Cloud recommendation: `DENY_APPLY`

## Repository and delivery truth

- Root: `/workspace`
- Repository: `BernydotJar/AI-Native-Content-Agency-SaaS`
- Active branch: `agent/inc-020-social-publication-authority`
- Current implementation: `8eb0cf7dee9b3400351a8b7d603a94666253f1e7`
- Parent program checkpoint: `ca79d79d83346ca4b275a54787647cfdbd5c07c1`
- Active branch remote / PR / exact-head CI: pending
- Latest known published product base remains `agent/inc-016-cinematic-runtime-ux@9c9c548e188c0c4a22154531a41b655d943e14b7`, draft PR `#10`, run `29956435978`, eight of eight jobs successful
- Real model calls, X/Instagram publication, cloud deployment, registry publication, billing and spend: not performed

## Active increment

### INC-020 — Exact-once social publication authority

Status: `review`, local gates pass, remote pending
Owner: Distributed Systems Integration Engineer / Security Reviewer
External effects during verification: MockTransport only; socket guard proves zero real provider HTTP

#### Implemented

- Default-disabled X `POST /2/tweets` and Instagram `/media` then `/media_publish` adapters.
- SQLite/PostgreSQL schema v3 durable publication intents and bounded receipts.
- Exact tenant/account/channel/run/artifact/media/Greenlight/budget binding.
- Unique binding authority across compatible idempotency keys and replicas.
- Pending, succeeded, failed, unknown and revoked states.
- Unknown outcomes block retry and require idempotent admin reconciliation.
- Disconnect and Greenlight revocation invalidate unused pending authority.
- Server-derived approved copy/media; browser cannot inject post text or media URL.
- Admin-only HttpOnly-session/CSRF mutation routes and destructive confirmation dialog.
- Deterministic audit event repair on replay after receipt success/audit failure.
- Critical unknown-outcome metric, alert and incident response contract.
- Helm/Terraform Secret references and publication flag false by default.
- Runtime-before-store lock ordering closing a reproducible async worker/read deadlock.

#### Exact local evidence

```text
Locked Python wheel                       PASS — 226 tests, 19 PostgreSQL skips
PostgreSQL shared runtime                 PASS — 226/226, schema v3
PostgreSQL least privilege                PASS — non-owner runtime grant matrix
Frontend                                  PASS — 38/38
Oxlint / TypeScript / Vite                PASS
Chromium accessibility                    PASS
Chromium social output                    PASS
Chromium cross-site OAuth                 PASS — MockTransport only
Chromium async topology                   PASS — 7 stations, 14 checkpoints
Chromium publication                      PASS — 0 calls before confirm; 1 after; replay stays 1
Buildah non-root package                  PASS
Installed-image publication effect        PASS — MockTransport + socket guard
K3s/Helm/Terraform plan/apply/destroy     PASS — SQLite and PostgreSQL
Operability                               PASS — 4 SLOs, 8 alerts, 9 exercises
Actionlint / Gitleaks / whitespace        PASS
Clean-source supply chain                 PASS — source 8eb0cf7, registry_publication=false
Real provider publication                 NOT_RUN
Real credentials/tokens                   NOT_USED
Push / PR / exact-head CI                 PENDING
```

The producer/critic/verifier record is `program/reports/inc-020-review.md`.

## Remaining product boundaries

### INC-015 — Durable model effect authority

Status: `pending`

The bounded five-provider gateway remains disconnected from campaign runs. Model inference still requires durable request/economic binding, fencing, result/receipt persistence, replay reuse and unknown-outcome reconciliation before any credentials, prompt transfer or spend are authorized.

### Instagram media production

The publication authority requires an approved `publication_media` artifact with HTTPS URL and SHA-256. The current deterministic runtime does not create a real retrievable media asset, so Instagram publication remains blocked even when an account is connected.

## Open global HIGH release findings

- `F-004` staging/cloud runtime observation — external.
- `F-007` accountable human accessibility evidence — human.
- `F-008` production scheduler/KMS/off-host backup/alerts — external.
- `F-010` approved retention/deletion/legal hold/data-subject workflow — human/legal.
- `F-011` semantic/adversarial model evaluations — pending.
- `F-034` model inference durable authority — INC-015.

Open CRITICAL findings: `0`.

## Human/external gates

- Publish current stacked branches and obtain exact-head eight-job CI.
- Register exact X and Meta callback URLs and authenticate authorized sandbox accounts.
- Approve current provider terms, privacy, account scope and one sandbox post per channel.
- Record/reconcile sandbox receipts before any production review.
- Approve retention/deletion/legal-hold/token-handling policies.
- Authorize provider egress/spend, production deployment, cloud apply and merge.
- Complete independent accessibility and PR review.

## Ready work

1. Publish `agent/inc-020-social-publication-authority` when the Cloud Sandbox push wrapper permits Git execution.
2. Resume INC-015 durable model-effect authority with provider execution still disabled.
3. Add real approved media storage/rendering only as a separately governed increment.
4. Reserve broad product E2E and any real sandbox effects for the dependency-closed release candidate.

## Exact continuation condition

Continue from `8eb0cf7dee9b3400351a8b7d603a94666253f1e7` plus its program checkpoint. Preserve `DENY_RELEASE`, `DENY_APPLY`, `active_external_providers=0`, social publication disabled by default, model execution disabled and zero spend. Do not perform a real provider request without explicit authorization and current provider/privacy review.
