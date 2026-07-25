# Skill and External Tool Usage Register

| Date | Tool/skill | Purpose | Supply-chain or prompt-injection review | Result |
|---|---|---|---|---|
| 2026-07-21 | Cloud Sandbox MCP | persistent repository inspection, editing, test execution, Git/GitHub verification | Existing authorized connector; no new package or MCP installation | Active |
| 2026-07-21 | `gh` in workspace | inspect PRs, CI, issues, releases, and remote SHAs | Auth already present; token value not exposed or copied | PASS |
| 2026-07-21 | `browser-use/video-use` | external integration candidate review | Exact commit `92c2b34e44c205cbc2acae7f6ca7c1c219d5dd66`; 33 hashes; no installation/helper/media/provider execution; HIGH activation findings retained | PASS — `reviewed_disabled` |
| 2026-07-22 | release compliance validator | reconcile locks/licenses/providers/privacy/claims/release authority | stdlib-only local code; no provider, legal service or new package; nine fail-closed mutation tests | PASS — `DENY_RELEASE` |
| 2026-07-25 | `skills/hooks-copy.md` | INC-021 hook, evidence mapping and copy QA rules | Repository-owned text under project license; no installer, executable code, telemetry or external service | INVOKED — inputs mapped into spec/tests |
| 2026-07-25 | `skills/platform-instagram.md` | INC-021 carousel, alt-text and channel QA rules | Repository-owned text under project license; no installer, executable code, telemetry or external service | INVOKED — inputs mapped into spec/tests |

## Detailed invocation records

- task_id: INC-021
  skill: `skills/hooks-copy.md`
  source: repository-owned skill file
  version_or_commit: `6ebbd634bd32408db0a7678289b0f906cda014c0`
  license: project repository license; no third-party asset copied
  invoked_at: 2026-07-25
  inputs: political brief contract, claim ledger, Spanish channel variants, critique requirements
  generated_outputs: hook/body/CTA structure, source-visible copy, prohibited-promotion checks
  validations: political runtime/API tests; full locked wheel; frontend tests/build
  result: PASS
  limitations: deterministic rules do not replace human fact, language, legal or campaign review

- task_id: INC-021
  skill: `skills/platform-instagram.md`
  source: repository-owned skill file
  version_or_commit: `6ebbd634bd32408db0a7678289b0f906cda014c0`
  license: project repository license; no third-party asset copied
  invoked_at: 2026-07-25
  inputs: Instagram carousel requirements, dimensions, alt text, publication readiness
  generated_outputs: non-rendered 1080x1350 carousel plan, slide purposes, alt text and rights-status gate
  validations: political runtime tests; frontend output tests; full locked wheel
  result: PASS
  limitations: no rendered bytes, object storage, reachable media URL or real publication; INC-022 owns those controls

- task_id: INC-022
  skill: `skills/platform-instagram.md`
  source: repository-owned skill file
  version_or_commit: `ea306fdec61842557d7d8c84f9423347e08825ab`
  license: project repository license; no third-party asset copied
  invoked_at: 2026-07-25
  inputs: Instagram media dimensions, accessibility, preview and publication readiness
  generated_outputs: INC-022 JPEG 4:5 media-vault contract and verified-publication acceptance criteria
  validations: pending TDD implementation
  result: IN_PROGRESS
  limitations: single IMAGE only; carousel/reel deferred; no real publication authorized

- task_id: INC-022
  skill: Pillow image validation dependency review
  source: PyPI verified project `Pillow==12.3.0`, upstream tag `python-pillow/Pillow@bb1d8e8ab8d29048624d96e3ee53cecf7c13d13d`
  version_or_commit: `12.3.0`
  license: MIT-CMU
  invoked_at: 2026-07-25
  inputs: dry-run wheel resolution for CPython 3.11 Linux ARM64
  generated_outputs: no install yet; dependency decision for real JPEG decode/verify
  validations: `pip install --dry-run --no-deps Pillow==12.3.0`; wheel available; no transitive dependency
  result: APPROVED_FOR_BOUNDED_USE
  limitations: native image decoder attack surface; enforce byte/dimension limits, full verification and pinned hashes
