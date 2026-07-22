# INC-009 — Browser/video integration contract review

Date: 2026-07-21
Branch: `agent/inc-009-browser-video-contracts`
Stacked base: `agent/inc-008-accessible-themes@6d904792d2b6e8b3d97fdd88ccf2e077d0bfb792`
Implementation commit: `61da89cd5bcc36fc5d99b97dd429d73fbb331959`
Status: `PASS — REVIEWED_DISABLED`
External effects: none

## Review contract

```yaml
task_id: INC-009
workstream_id: WS-08
producer: Integration and Security Engineer
critic: Security, Privacy and Supply-chain Reviewer
fixer: Integration Engineer
independent_verifier: locked wheel, PostgreSQL, non-root package and ephemeral infrastructure gates
objective: >
  Evaluate browser/video integration candidates, preserve exact source evidence
  and define future fail-closed authority contracts without installing or
  executing third-party code or enabling any external effect.
human_gates:
  - merge
  - any provider credential or external media disclosure
  - any activation, publication or spend
```

## Reviewed upstream source

- repository: `browser-use/video-use`
- exact commit: `92c2b34e44c205cbc2acae7f6ca7c1c219d5dd66`
- license: MIT
- reviewed files: 33, each recorded by SHA-256
- installation/helper execution: none
- media/provider calls: none

The review found no release tags, merged dependency lock, SECURITY.md, repository
CI workflow or protected default branch at the reviewed commit. Upstream PR #93
proposes a path-containment fix and PR #108 proposes a lockfile; neither is part
of the pinned source.

## Delivered behavior

- Immutable package manifest with exact commit, file hashes, license, findings,
  capabilities, binaries, provider host and activation requirements.
- Strict dependency-free manifest loader that rejects field drift, malformed
  timestamps/repositories/commits/digests, ambiguous collection types, invalid
  findings and any enabled effect flag.
- Review-only invocation model with exact operation, tenant/campaign/workspace,
  idempotency, Greenlight, fence, path, secret, egress, untrusted-input, size,
  duration, retry and zero-cost contracts.
- Explicit future execution-receipt shape; construction remains impossible.
- Authenticated, tenant-derived, read-only API:
  - `GET /api/v1/integrations`
  - `GET /api/v1/integrations/{integration_id}`
- No POST/execute/render/transcribe/upload/download/credential endpoint.
- Non-root package smoke verifies the manifest and GET-only OpenAPI boundary.

## Blocking upstream/product findings

| ID | Severity | Finding | Disposition |
|---|---|---|---|
| VIDEO-USE-001 | HIGH | `render.py` permits absolute/parent-traversal paths. | Activation denied until a patched exact commit is reviewed. |
| VIDEO-USE-002 | HIGH | Transcription uploads extracted audio to ElevenLabs. | Activation denied pending provider/privacy/data-transfer approval. |
| VIDEO-USE-003 | HIGH | No product tenant, Greenlight, idempotency, fence, receipt, cost or revocation contract. | Product-owned isolated adapter/outbox required before effects. |
| VIDEO-USE-004 | MEDIUM | No merged lock, CI, security policy or protected default branch. | Pin/scan dependencies and binaries independently. |
| VIDEO-USE-005 | MEDIUM | Skill instructions request persistent memory and autonomous shell/subagents. | Remove ambient authority through worker isolation. |

These are activation blockers, not active runtime vulnerabilities: no upstream
code or dependency is installed or reachable from the selected runtime.

## Critic findings and repairs

| ID | Severity | Finding | Repair | State |
|---|---|---|---|---|
| C-009-01 | HIGH | A named integration could be mistaken for executable authority. | All effect flags false, no executor route, execute/receipt methods always fail. | closed |
| C-009-02 | HIGH | Caller paths/secrets/egress could escape a future worker boundary. | Canonical roots, encoded/parent/absolute rejection, exact secret refs and operation-specific hosts. | closed |
| C-009-03 | MEDIUM | Manifest strings could masquerade as sequences and weaken validation. | Exact structural validation plus negative mutation tests. | closed |
| C-009-04 | MEDIUM | Package smoke initially required only 404 while FastAPI safely returned 405. | Accept only safe 404/405 and verify the public error body/OpenAPI has GET only. | closed |
| C-009-05 | LOW | New authenticated review reads changed the historical auth-success metric. | Updated the deterministic package expectation from two to four successful authentications. | closed |

No CRITICAL or open code-level HIGH remains in this slice. The reviewed upstream
HIGH findings remain explicit prerequisites for a separate future activation
increment.

## Local verification evidence

```text
Exact upstream tree/hash comparison         PASS — 33/33 files
Locked Python wheel                         PASS — 118 tests, 11 PostgreSQL skips
PostgreSQL shared-state gate                PASS — 118/118
Frontend regression                         PASS — 66/66
Oxlint                                      PASS — 0 warnings/errors
TypeScript/Vite production build            PASS
Real Chromium accessibility regression      PASS
Python lock regeneration                    PASS — byte-identical
Operability contracts                       PASS — 4 SLOs, 7 alerts, 8 exercises
Buildah non-root production package         PASS
Integration manifest in production image    PASS
Integration OpenAPI GET-only                PASS
Integration execution disabled              PASS
K3s/Helm/Terraform plan/apply/destroy        PASS — agentless control plane
Actionlint                                  PASS
Gitleaks full Git history                    PASS — zero findings
Whitespace                                  PASS
External calls/media/rendering               NOT_RUN BY DESIGN
```

## Evidence boundary

The gates prove the pinned review data, fail-closed contract and absence of an
execution route. They do not prove provider suitability, privacy/legal approval,
media quality, external idempotency, worker isolation, network enforcement or a
real provider receipt. Those controls require a separate reviewed implementation
and explicit human authorization.

## Delivery boundary

```text
specified: yes
implemented: 61da89cd5bcc36fc5d99b97dd429d73fbb331959
tested_local: yes
postgresql_verified_local: yes
package_verified_local: yes
infrastructure_verified_local: yes, agentless control plane only
committed: yes
pushed: f59fcbe792c5f4e28d904fc1e1a17442b9340ec7
pull_request: draft #8, clean and mergeable
remote_exact_head_ci: GitHub Actions 29878783817, 8/8 PASS
integration_activated: no
external_effects: none
```
