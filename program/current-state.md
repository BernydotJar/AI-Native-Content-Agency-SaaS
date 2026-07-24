# Current Operational State

Updated: 2026-07-24
Program phase: active
Release recommendation: `DENY_RELEASE`
Cloud recommendation: `DENY_APPLY`

## Repository and delivery truth

- Root: `/workspace`
- Repository: `BernydotJar/AI-Native-Content-Agency-SaaS`
- Active branch: `agent/inc-015-model-effect-authority-v2`
- Current implementation: `6eb7fa070bcbe71c840ca316fc86d369d9d1691b`
- Parent checkpoint: `74d5cfad0b6c99debb0a3120f495e6aef46bc732`
- Remote branch / PR / exact-head CI: pending push from this checkpoint
- Latest known published product base: `agent/inc-016-cinematic-runtime-ux@9c9c548e188c0c4a22154531a41b655d943e14b7`, draft PR `#10`
- Real model calls, X/Instagram publication, cloud deployment, registry publication, billing and spend: not performed

## Completed local increments relevant to the reported symptoms

- Cross-site X/Instagram OAuth callbacks preserve the HttpOnly session through `SameSite=Lax`; exact callback URLs and safe failure phases are visible (`6d5e59b`).
- Asynchronous runs persist 14 real checkpoints, so topology cards derive movement from backend state instead of timers (`3cc304d`).
- Social publication has default-disabled exact-once authority and reconciliation (`8eb0cf7`).
- Model operations now have default-disabled exact-once authority (`6eb7fa0`).

## Active increment

### INC-015 — Durable model effect authority

Status: `review`, local implementation committed, remote CI pending

Implemented:

- SQLite/PostgreSQL schema v4 model-effect intents and bounded receipts.
- Intent before provider HTTP, unique effect binding and one fenced executor.
- Compatible replay with zero second provider call.
- `unknown` blocking and idempotent administrator reconciliation.
- Stable model-completion attachment and deterministic audit repair.
- Server-owned provider/model/prompt construction and cost cap.
- Admin HttpOnly-session + CSRF mutation boundary.
- Helm/Terraform provider Secret references and both model flags false by default.
- MockTransport/socket-guard package fixture; no real provider HTTP.

Evidence boundary:

```text
Locked Python wheel                       PASS — 245 tests, 23 PostgreSQL-only skips
Focused API / SQLite contracts            PASS
MockTransport socket guard                PASS — real_provider_http=false
PostgreSQL v4 exact-head rerun             PENDING CI — not repeated by operator instruction
Installed-image/package rerun              PENDING CI — not repeated by operator instruction
Helm/Terraform/supply-chain rerun           PENDING CI — not repeated by operator instruction
Real provider request                      NOT_RUN
Real credentials / prompt transfer / spend NOT_USED
```

The producer/critic/verifier record is `program/reports/inc-015-review.md`.

## Remaining product boundaries

- Instagram still requires a real approved `publication_media` artifact with retrievable HTTPS media before an authorized sandbox post.
- Semantic/adversarial model evaluation remains owned by `F-011` / INC-010.
- Real provider terms, privacy, account scope, budget, deployment and release approval remain human gates.

## Open global HIGH release findings

- `F-004` staging/cloud runtime observation — external.
- `F-007` accountable human accessibility evidence — human.
- `F-008` production scheduler/KMS/off-host backup/alerts — external.
- `F-010` retention/deletion/legal-hold/data-subject workflow — human/legal.
- `F-011` semantic/adversarial model evaluations — pending.

Open CRITICAL findings: `0`.

## Exact continuation condition

Push `6eb7fa070bcbe71c840ca316fc86d369d9d1691b`, observe exact-head CI, and reconcile any failing gate without enabling model or
social external effects. Preserve `DENY_RELEASE`, `DENY_APPLY`,
`active_external_providers=0`, social publication false, both model flags false and zero spend.
