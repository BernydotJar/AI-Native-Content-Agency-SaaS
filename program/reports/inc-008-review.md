# INC-008 — Accessible themes and accessibility evidence review

Date: 2026-07-21
Branch: `agent/inc-008-accessible-themes`
Stacked base: `agent/inc-007-operator-journey@dad71025bf14281930b8fafa2edae81e2a7c6c84`
Identity/entitlement commit: `f63a58648eec0579d53a007c8ed83ff376b95727`
Theme/browser commit: `8ecf77e7f58789d1e5b47826b595b172bac6fa89`
Status: `CHECKPOINT_COMPLETED_AUTOMATED — MANUAL_REVIEW_BLOCKED`
External effects: none

## Review contract

```yaml
task_id: INC-008
workstream_id: WS-06
producer: Frontend Engineer / Identity Engineer
critic: Accessibility and Security Reviewer
fixer: Frontend Engineer
independent_verifier: locked backend, PostgreSQL, real Chromium and package gates
objective: >
  Deliver four accessible politically neutral themes and a premium theme that
  fails closed behind a server-owned entitlement, while preserving honest
  boundaries between automation and manual accessibility evidence.
human_gates:
  - independent manual screen-reader review
  - rendered contrast and visual review
  - 400 percent zoom/reflow and representative viewport review
  - merge
  - production deployment
```

## Delivered behavior

### Theme system

- Named blue, red, green and orange free themes.
- Named premium theme with visible paid-entitlement explanation.
- Semantic background, panel, text, muted, border, accent and on-accent tokens.
- Executable contrast-ratio contract for every theme.
- `aria-pressed`, visible text and live announcements; no selected state depends only on color.
- Premium stays focusable/discoverable but uses `aria-disabled=true` and refuses activation when unauthorized.
- Theme stays in memory only; no browser storage.
- Theme never changes role, permission, Greenlight, risk or political recommendation.

### Server-owned premium entitlement

- Exact allowlist contains only `theme:premium`.
- Individual identities may carry an optional entitlement array.
- Duplicate, unknown, non-string and non-array entitlements fail closed.
- Simultaneously active keys for one tenant/subject must share role and entitlements.
- Inactive historical keys do not block entitlement rotation.
- Session creation, session restoration and `/me` return current entitlements.
- The SPA refreshes `/me` with audit/mutation refreshes and falls back to blue when premium disappears.
- Entitlement is absent from SQLite/session rows, audit payloads and browser storage.
- Billing, checkout, invoicing and DRM are explicitly not implemented.

### Browser accessibility gate

A dependency-free CDP harness launches the production Vite bundle in real Chromium and verifies:

- 320 CSS px viewport without horizontal overflow;
- five theme targets at least 44 CSS px;
- skip link is first and transfers focus to `main`;
- keyboard activation of a free theme;
- premium remains locked without entitlement;
- reduced-motion media emulation produces zero View Transition calls;
- accessibility tree exposes five named buttons plus selected/disabled states;
- preview and Chromium process groups are removed after success or failure.

CI uploads the generated JSON and screenshot for human review. The screenshot is not classified as a visual PASS.

## Critic findings and repairs

| ID | Severity | Finding | Repair | State |
|---|---|---|---|---|
| C-008-01 | MEDIUM | Four unlabeled accent dots had no semantic theme, selected-state text or product contract. | Added typed named catalog, semantic tokens, live status and contrast tests. | closed |
| C-008-02 | HIGH | A frontend boolean could self-grant premium and survive server revocation. | Added exact server-owned entitlement, session identity refresh and free-theme fallback. | closed |
| C-008-03 | MEDIUM | Skip link changed the fragment but did not focus `main`. | Made `main` programmatically focusable and proved transfer in Chromium. | closed |
| C-008-04 | MEDIUM | Entitlement could be mistakenly persisted or logged. | Kept it in active identity authority and responses only; database-byte and audit-surface reviews pass. | closed |
| C-008-05 | MEDIUM | Automated AX/screenshot output could be reported as manual accessibility approval. | Evidence and protocol explicitly retain human gates and `F-007`. | controlled/open human gate |
| C-008-06 | LOW | Early browser probes could leave descendants or fixed ports behind. | Dynamic ports, detached process groups, bounded teardown and listener check. | closed |

No CRITICAL or open code-level HIGH remains within the slice. `F-007` remains HIGH/open because the human evidence is not executed.

## Verification evidence

```text
Frontend tests                              PASS — 66/66
Oxlint                                      PASS — 0 warnings, 0 errors
TypeScript/Vite production build            PASS
Theme token contrast contracts              PASS — all five themes
Real Chromium 320px reflow                  PASS
Real Chromium skip-link focus               PASS
Real Chromium keyboard theme activation     PASS
Real Chromium premium lock                  PASS
Real Chromium reduced motion                PASS
Real Chromium accessibility tree            PASS
Locked Python wheel                         PASS — 107 tests, 11 PostgreSQL-only skips
PostgreSQL shared-state gate                 PASS — 107/107
SQLite entitlement persistence check        PASS — absent
Buildah non-root production package         PASS
Helm and operability contract               PASS
Local K3s/Terraform plan/apply/destroy       PASS
Actionlint                                  PASS
Gitleaks current worktree                   PASS — zero findings
git diff --check                            PASS
Manual screen-reader review                 NOT_RUN
Rendered contrast/visual review             NOT_RUN
Human 400% zoom/reflow review               NOT_RUN
```

## Evidence boundary

The real-browser gate is stronger than jsdom and proves browser behavior at its encoded scope. It does not reproduce a human screen reader, cognitive review, physical device, rendered contrast inspection or 400% zoom session. `docs/accessibility/manual-review-protocol.md` is the exact continuation procedure.

## Delivery boundary

```text
specified: yes
implemented: f63a586 + 8ecf77e
tested_local: yes
postgresql_verified_local: yes
browser_verified_local: yes
package_verified_local: yes
reviewed_local: yes
manual_accessibility_review: no
committed: yes
pushed: yes — 3a0e545182b3595e6094298a487da7c3e355a42a
remote_sha_verified: yes
draft_pr: yes — #7
exact_head_ci: yes — run 29876402303, 8/8
accessibility_artifact: yes — retained through 2026-08-20
merged: no
deployed: no
```

## Exact continuation condition

Repository automation and delivery are complete. Keep INC-008 blocked until an accountable human executes `docs/accessibility/manual-review-protocol.md` against the exact production bundle and repairs or accepts every material finding under release policy.
