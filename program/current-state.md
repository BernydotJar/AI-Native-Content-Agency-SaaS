# Current Operational State

Updated: 2026-07-23
Program phase: active
Release recommendation: `DENY_RELEASE`
Cloud recommendation: `DENY_APPLY`

## Repository and delivery truth

- Root: `/workspace`
- Repository: `BernydotJar/AI-Native-Content-Agency-SaaS`
- Active branch: `agent/inc-019-social-oauth-publication`
- Published product base: `agent/inc-016-cinematic-runtime-ux@9c9c548e188c0c4a22154531a41b655d943e14b7`
- Published base evidence: draft PR `#10`, GitHub Actions run `29956435978`, eight of eight jobs successful
- Campaign output/resource replay implementation: `9b0b65927fe9609e1f55835728332bb3e2aa09ca`
- X/Instagram readiness implementation: `93c5f55852dc60409d231eca948c20d74a871aa0`
- OAuth/encrypted account implementation: `e3bca9c95a3080e1e7677454996d9ad56469b4f4`
- Active branch remote: pending publication
- Active draft PR and exact-head CI: pending
- Real X/Instagram OAuth, token exchange and publication: not performed
- Real model calls, cloud deployment, registry publication, billing and spend: not performed

## Active increment

### INC-019 — Tenant-owned X and Instagram account connection

Status: `review`
Owner: Integration Engineer / Security Reviewer
External effects during verification: none; all provider HTTP used `httpx.MockTransport`

#### Implemented

- X OAuth 1.0a request-token, authorization and access-token contracts.
- Instagram Authorization Code contract with Professional-account validation.
- AES-GCM token encryption with versioned key IDs, tenant/channel AAD and key rotation.
- Single-use ten-minute OAuth state bound to tenant, browser session and channel.
- SQLite/PostgreSQL schema v2 stores and atomic PostgreSQL callback consumption.
- Admin-only OAuth start/disconnect using HttpOnly session and CSRF.
- Connected-account metadata without access-token disclosure.
- Server-side bootstrap for existing X/Instagram tokens; partial groups fail startup.
- `.env.local` loading, tracked-file refusal and 32-byte key generator.
- Helm/Terraform references to a pre-existing Secret; no values enter Terraform state.
- Settings UI with Connect/Disconnect and callback-return status.
- No publication route; `publishing_available=false` remains authoritative.

#### Local evidence

```text
Program validator                         PASS — 79 requirements, 20 tasks
Compliance validator                      PASS — DENY_RELEASE, 0 active providers, 35 components
Locked Python wheel                       PASS — 183 tests, 14 PostgreSQL skips
PostgreSQL shared state                   PASS — 183/183
PostgreSQL schema/grants                  PASS — v2, non-owner runtime, migration and restores
Frontend                                  PASS — 35/35
Oxlint / TypeScript / Vite                PASS
Chromium accessibility                    PASS
Chromium X/Instagram output               PASS
Buildah non-root package                  PASS
OAuth routes governed                     PASS
Social publication routes absent          PASS
K3s/Helm/Terraform plan/apply/destroy     PASS
Actionlint                                PASS
Gitleaks history/worktree                 PASS — zero leaks
Operability                               PASS — 4 SLOs, 7 alerts, 8 exercises
Real provider OAuth/publication           NOT_RUN
Real credentials/tokens                   NOT_USED
Clean-source supply chain                 PENDING FOR PROGRAM CHECKPOINT
Push / PR / exact-head CI                 PENDING
```

#### Critic decision

Account connection is ready for operator testing after branch publication and provider
callback registration. It must not be described as publication readiness. The exact
producer/critic/verifier record is `program/reports/inc-019-review.md`.

## Explicit product boundaries

### INC-015 — Durable model effect authority

Status: `pending`

DeepSeek is configured and the bounded gateway exists, but model inference is not attached
to campaign runs. Durable model intent/fence/receipt and replay protection remain required.

### INC-018 — Durable asynchronous run execution

Status: `pending`

The topology currently receives terminal station state because orchestration is
synchronous. Fake progress is prohibited; queued workers, leases and durable checkpoints
remain required.

### INC-020 — Exact-once social publication authority

Status: `pending`

Accounts can be connected and tokens are encrypted, but X `POST /2/tweets` and Instagram
`/media` → `/media_publish` are deliberately absent. Publication requires durable intent,
fence, exact artifact/media/Greenlight binding, receipt and unknown-outcome reconciliation.

## Open global HIGH release findings

- `F-004` staging/cloud runtime observation — external.
- `F-007` accountable human accessibility evidence — human.
- `F-008` production scheduler/KMS/off-host backup/alerts — external.
- `F-010` approved retention/deletion/legal hold/data-subject workflow — human/legal.
- `F-011` semantic/adversarial model evaluations — pending.
- `F-034` model inference durable authority — INC-015.
- `F-037` truthful asynchronous station progress — INC-018.
- `F-039` exact-once social publication — INC-020.

Open CRITICAL findings: `0`.

## Human/external gates

- Register exact X and Meta callback URLs.
- Authenticate authorized X and Instagram Professional sandbox accounts.
- Approve one sandbox publication per channel only after INC-020 passes.
- Approve privacy/retention/token-handling policy and current provider terms/pricing.
- Authorize provider egress/spend, production deployment and merge.
- Complete independent accessibility and PR review.

## Ready work

1. Commit this INC-019 program checkpoint.
2. Run clean-source supply chain with `registry_publication=false`.
3. Push `agent/inc-019-social-oauth-publication`, verify exact remote SHA, create a stacked draft PR and require eight-job CI.
4. After exact CI passes, provide the user pull, `.env.local`, callback-registration and authentication steps.
5. Resume INC-020 with mock transports; do not publish a real post until durable authority and explicit authorization exist.

## Exact continuation condition

Start from `e3bca9c95a3080e1e7677454996d9ad56469b4f4` plus the program checkpoint. Preserve
`DENY_RELEASE`, `DENY_APPLY`, `active_external_providers=0`, publication disabled and zero
real provider calls. Publish and verify INC-019 before requesting user authentication.
