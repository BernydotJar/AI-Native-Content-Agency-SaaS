# Skill and External Tool Usage Register

| Date | Tool/skill | Purpose | Supply-chain or prompt-injection review | Result |
|---|---|---|---|---|
| 2026-07-21 | Cloud Sandbox MCP | persistent repository inspection, editing, test execution, Git/GitHub verification | Existing authorized connector; no new package or MCP installation | Active |
| 2026-07-21 | `gh` in workspace | inspect PRs, CI, issues, releases, and remote SHAs | Auth already present; token value not exposed or copied | PASS |
| 2026-07-21 | `browser-use/video-use` | external integration candidate review | Exact commit `92c2b34e44c205cbc2acae7f6ca7c1c219d5dd66`; 33 hashes; no installation/helper/media/provider execution; HIGH activation findings retained | PASS — `reviewed_disabled` |
| 2026-07-22 | release compliance validator | reconcile locks/licenses/providers/privacy/claims/release authority | stdlib-only local code; no provider, legal service or new package; nine fail-closed mutation tests | PASS — `DENY_RELEASE` |
| 2026-07-25 | `skills/hooks-copy.md` | INC-021 hook, evidence mapping and copy QA rules | Repository-owned text under project license; no installer, executable code, telemetry or external service | INVOKED — inputs mapped into spec/tests |
| 2026-07-25 | `skills/platform-instagram.md` | INC-021 carousel, alt-text and channel QA rules | Repository-owned text under project license; no installer, executable code, telemetry or external service | INVOKED — inputs mapped into spec/tests |
