# INC-013 Product Workspace Review

Updated: 2026-07-22
Implementation commit: `a89907f`
Branch: `agent/inc-013-product-workspace`
Status: `review`

## Objective

Replace the primary demo-oriented frontend with one durable tenant-scoped workspace,
add truthful server-derived provider configuration, and make the local full-stack path
usable without enabling paid inference or external effects.

## Producer result

- Replaced the 1,600-line demo-first `App` with a mission-first workspace.
- Removed 5,778 lines of unreachable legacy frontend, including the parallel
  simulation runtime, mock dashboards and duplicated production panel.
- Preserved the eight-station topology and derived its state from the durable run.
- Moved appearance to Settings and the tenant credential to a one-time modal.
- Added applied run context instead of presenting memory internals as a user task.
- Added Operational Fabric derived from provider, integration and station state.
- Added exact server-side contracts for OpenAI, Anthropic, DeepSeek, Moonshot/Kimi
  and Llama.
- Added the loopback-only `npm run start:local` path for SPA + FastAPI + SQLite.

## Critic findings and repairs

| Finding | Severity | Repair | Result |
|---|---:|---|---|
| Theme selection occupied the primary mission hierarchy. | HIGH UX | Moved all themes to a focus-managed Settings dialog. | CLOSED |
| Tenant credential remained a large permanent panel despite one-time use. | HIGH UX/security | Added progressive connection modal; field is removed after exchange/close. | CLOSED |
| Memory UI taught Observe/Store/Search/Recall instead of showing applied context. | MEDIUM UX | Replaced it with evidence, Scholar decisions, strategy, risk and output counts. | CLOSED |
| Tool Fabric presented attractive mock cards as if they were usable capabilities. | HIGH product truth | Replaced cards with server provider readiness, reviewed integrations and run station outputs. | CLOSED |
| Static `npm run preview` was easy to mistake for the full product. | HIGH operability | Added `npm run start:local`; documented preview as visual-only. | CLOSED |
| Settings/connection dialogs initially did not fully trap and restore focus. | HIGH accessibility | Added shared modal focus trap, Escape close and bidirectional Tab tests. | CLOSED |
| Static preview 404 during session restoration surfaced a false “run not found”. | MEDIUM UX | Treat absent same-origin API during visual preview as disconnected state. | CLOSED |
| Public claims policy required copy from the retired simulator. | HIGH compliance | Migrated to a truthful local-runtime/no-publication/no-spend disclosure and rescanned active surfaces. | CLOSED |
| Legacy demo components remained in the repository after the new shell compiled. | HIGH maintainability | Removed the parallel frontend, assets and exclusive tests. | CLOSED |
| Provider readiness could be confused with real inference. | HIGH product truth | API/UI/runbook state that readiness is configuration evidence only; execution remains disabled. | CONTROLLED / NEXT INCREMENT |

## Local verifier evidence

```text
Program validator                       PASS — 79 requirements, 13 tasks
Compliance validator                    PASS — DENY_RELEASE, 0 active providers
Locked Python wheel                      PASS — 136 tests, 11 PostgreSQL skips
PostgreSQL shared runtime                PASS — 136/136
Frontend                                 PASS — 26/26 active tests
Oxlint / TypeScript / Vite               PASS
Bundle                                   PASS — JS 258.29 kB, CSS 69.75 kB
Chromium 320px/reflow/focus/motion/AX     PASS
Integrated local product smoke           PASS — SPA/session/providers/run
Buildah non-root package                 PASS
Packaged provider registry               PASS — five providers, no secrets
K3s/Helm/Terraform plan/apply/destroy     PASS — agentless control plane
Actionlint                               PASS
Gitleaks history/worktree                PASS — zero leaks
Whitespace                               PASS
Real provider inference                  NOT_RUN / NOT_IMPLEMENTED
External publication/media/ads           NOT_RUN / DISABLED
Final cross-product E2E                   DEFERRED TO FINAL PROGRAM GATE
```

## Exact limitations

- The backend orchestrator still uses deterministic local tools for research, media,
  ads, browser and packaging.
- Provider configuration does not create HTTP clients, issue requests or spend money.
- No user-selectable provider routing exists yet.
- No provider effect receipt, outbox, timeout/rate-limit policy or privacy approval
  exists yet.
- Human accessibility review, production backup controls and cloud observation remain
  external blockers inherited from the program.

## Verifier decision

The product-workspace slice is suitable for publication to a feature branch. Keep
`INC-013=review` until a clean-source supply-chain gate, remote SHA equality, draft PR
and eight-job exact-head CI pass. Do not describe this increment as real model
execution; that requires a separate authorized provider-gateway increment.
