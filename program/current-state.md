# Current Operational State

Updated: 2026-07-23
Program phase: active
Release recommendation: `DENY_RELEASE`
Cloud recommendation: `DENY_APPLY`

## Repository and delivery truth

- Root: `/workspace`
- Repository: `BernydotJar/AI-Native-Content-Agency-SaaS`
- Active branch: `agent/inc-018-durable-run-execution`
- Active implementation: `3cc304d10b64b8cb32bffeee52f36e583c46f844`
- Published product base: `agent/inc-016-cinematic-runtime-ux@9c9c548e188c0c4a22154531a41b655d943e14b7`
- Published base evidence: draft PR `#10`, GitHub Actions run `29956435978`, eight of eight jobs successful
- Campaign output/resource replay: `9b0b65927fe9609e1f55835728332bb3e2aa09ca`
- X/Instagram OAuth plus callback repair: `6d5e59b` with program checkpoint `908bbd2`
- Durable asynchronous station execution: `3cc304d10b64b8cb32bffeee52f36e583c46f844`
- Active branch remote, draft PR and exact-head CI: pending; Cloud Sandbox `git_push` fails before Git while starting Docker/iptables
- Real model calls, social publication, cloud deployment, registry publication, billing and spend: not performed

## Active increment

### INC-018 — Durable asynchronous run execution

Status: `review`
Owner: Distributed Systems Engineer / Runtime Critic
External effects during verification: none

#### Implemented

- SPA requests `Prefer: respond-async`; new runs return durable `queued` state with `202 Accepted` and `Location`.
- Worker loop uses the shared run store as queue authority and persists a lease before work.
- Every claim increments a monotonic fencing token and attempt counter.
- CEO, Research, Strategist, Growth, Writer, Media and Risk each expose real `processing` and `ready` checkpoints.
- Publisher becomes `waiting_greenlight` only after Risk is durable and ready.
- Active leases block replacement workers; expired leases recover after restart with a higher fence.
- PostgreSQL serializes two replicas without duplicate station artifacts.
- UI polls only while the durable run is queued/running; no client timer invents progress.
- Existing synchronous API and CLI contracts remain compatible.

#### Local evidence

```text
Program validator                         PASS — 79 requirements, 20 tasks
Compliance validator                      PASS — DENY_RELEASE, 0 active providers, 35 components
Locked Python wheel                       PASS — 196 tests, 15 PostgreSQL skips
PostgreSQL shared state                   PASS — 196/196
SQLite crash/lease recovery               PASS
PostgreSQL two-worker fencing             PASS
Frontend                                  PASS — 36/36
Oxlint / TypeScript / Vite                PASS
Chromium accessibility                    PASS
Chromium social output/OAuth regression   PASS
Chromium asynchronous topology            PASS — 7 stations, 14 checkpoint values
Final browser fencing token               PASS — 14
Buildah image async smoke                 PASS — 202, fences 1..14, Greenlight
K3s/Helm/Terraform plan/apply/destroy     PASS
Actionlint / Gitleaks                     PASS
Operability                               PASS — 4 SLOs, 7 alerts, 8 exercises
Clean-source supply chain                 PASS — source 3cc304d, registry_publication=false
Push / PR / exact-head CI                 BLOCKED by Cloud Sandbox wrapper before Git
```

#### Critic decision

`F-037` is closed locally. The map now visualizes persisted execution checkpoints rather
than a terminal response or simulated browser progress. This does not provide authority
for model inference, media rendering, budget spend or social publication. Exact evidence
is recorded in `program/reports/inc-018-review.md`.

## Other active product boundaries

### INC-019 — Tenant-owned X and Instagram account connection

Status: `review`, remote pending

OAuth state, encrypted token storage, account metadata, disconnect and cross-site callback
behavior are implemented. Exact callback URLs are visible in Settings. Real provider
authorization remains operator-controlled and publication remains disabled.

### INC-015 — Durable model effect authority

Status: `pending`

The bounded model gateway exists, but inference is not attached to runs. Provider spend
requires a durable intent, request binding, fence, result/receipt persistence and
unknown-outcome reconciliation before activation.

### INC-020 — Exact-once social publication authority

Status: `pending`

Accounts can be connected, but X `POST /2/tweets` and Instagram `/media` then
`/media_publish` are deliberately absent. Publication requires an exact artifact/media/
account/Greenlight binding, durable intent, provider receipt and reconciliation.

## Open global HIGH release findings

- `F-004` staging/cloud runtime observation — external.
- `F-007` accountable human accessibility evidence — human.
- `F-008` production scheduler/KMS/off-host backup/alerts — external.
- `F-010` approved retention/deletion/legal hold/data-subject workflow — human/legal.
- `F-011` semantic/adversarial model evaluations — pending.
- `F-034` model inference durable authority — INC-015.
- `F-039` exact-once social publication — INC-020.

Open CRITICAL findings: `0`.

## Human/external gates

- Push current branches, create/update stacked draft PRs and obtain exact-head eight-job CI.
- Register exact X and Meta callback URLs and authenticate authorized sandbox accounts.
- Approve one sandbox publication per channel only after INC-020 passes and explicit authorization is given.
- Approve privacy/retention/token-handling policy and current provider terms/pricing.
- Authorize provider egress/spend, production worker deployment, cloud apply and merge.
- Complete independent accessibility and PR review.

## Ready work

1. Publish `agent/inc-018-durable-run-execution` when the Cloud Sandbox push wrapper is repaired or the user pushes from an authenticated local checkout.
2. Implement INC-020 exact-once social publication with mock transports and no real post.
3. Implement INC-015 durable model-effect authority before attaching any provider to campaign runs.
4. Reserve broad product E2E and any authorized sandbox external effects for the final dependency-closed release candidate.

## Exact continuation condition

Continue from `3cc304d10b64b8cb32bffeee52f36e583c46f844` plus the program checkpoint. Preserve
`DENY_RELEASE`, `DENY_APPLY`, `active_external_providers=0`, publication disabled, provider
execution disabled and zero spend.
