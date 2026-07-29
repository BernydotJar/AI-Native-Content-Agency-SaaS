# INC-017 Usable Campaign Output Review

Updated: 2026-07-22
Implementation commit: `9b0b659`
Branch: `agent/inc-017-usable-campaign-output`
Status: `review`

## Objective

Make the primary campaign journey usable: repeated missions reopen the exact durable run,
posts are visible by channel, evidence is compact and provider/integration diagnostics
live in Settings/Admin.

## Implemented

- Exact brief replay returns the existing tenant-scoped run with HTTP 200 and
  `X-Command-Replayed: true`.
- A new idempotency key receives a durable `run.reused` audit/command receipt.
- Reusing the same key for a changed payload remains a uniform 409.
- A deterministic resource lock serializes distinct keys for the same run across replicas.
- `CampaignOutputPanel` renders versioned `copy_deck` variants by channel.
- Copy-to-clipboard and honest publication readiness states.
- Context/evidence collapsed behind progressive disclosure.
- Provider and integration diagnostics moved to Settings/Admin.
- Removed the duplicate `RunContextPanel` and `OperationalFabricPanel` surfaces.
- Writer CTA no longer speaks as a sandbox demo.

## Critic findings

| Finding | Severity | Resolution |
|---|---:|---|
| Exact repeated mission surfaced a misleading generic 409. | HIGH product | Safe resource replay with explicit response header and durable audit receipt. |
| Distinct keys could race on the same deterministic run across replicas. | HIGH concurrency | Added deterministic resource lock and cross-replica test: one 201, one 200. |
| Publishable posts were hidden in generic artifact lists. | HIGH UX | Added channel post cards with hook/body/CTA and readiness. |
| Context/Fabric duplicated admin diagnostics in the primary journey. | MEDIUM UX | Removed duplicate panels; compact evidence and Settings/Admin own those concerns. |
| Map appears terminal immediately. | HIGH product | Not masked. Backend remains synchronous; transferred to INC-018 durable async execution. |
| DeepSeek appears ready but is not used by runs. | HIGH product | Not masked. F-034/INC-015 remains open for durable model-effect integration. |
| X has no tenant account connection or publication receipt. | HIGH product | Not masked. INC-019 specifies OAuth and exact-once governed publication. |

## Verification

```text
Focused replay/idempotency/security tests       PASS
Locked Python wheel                             PASS — 148 tests, 12 PostgreSQL skips
PostgreSQL shared runtime                       PASS — 148/148
Cross-replica distinct-key resource replay      PASS
Frontend                                         PASS — 29/29
Oxlint / TypeScript / Vite                       PASS
Chromium reflow/focus/keyboard/AX/reduced motion PASS
Buildah non-root package                         PASS
K3s/Helm/Terraform agentless gates               PASS
Actionlint                                       PASS
Gitleaks history/worktree                        PASS — zero leaks
Compliance                                       PASS — DENY_RELEASE, 0 active providers
External publication                             NOT_RUN / DISABLED
Final cross-product E2E                          DEFERRED TO FINAL PROGRAM GATE
```

## Limitations

- The orchestrator still executes synchronously inside `POST /runs`; no truthful
  intermediate map states are observable yet.
- The writer remains deterministic and does not call DeepSeek despite provider readiness.
- `Publicar` remains disabled because no connected social account or durable publication
  intent exists.
- X consumer/app credentials alone do not establish a tenant user-context account.

## Next work

1. INC-015 durable model-effect authority and run integration with local mock transports.
2. INC-018 durable asynchronous run worker and real station progress.
3. INC-019 tenant X OAuth, encrypted token storage and exact-once publication intent.
