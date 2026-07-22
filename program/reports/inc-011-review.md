# INC-011 — Release compliance, privacy and third-party review

Date: 2026-07-22
Branch: `agent/inc-011-release-compliance`
Stacked base: `agent/inc-009-browser-video-contracts@83cde2a2d8c11e063f938ad5fc3dc68863462646`
Implementation commit: `1843aa93c7675c6f5f10254ee3b7cffc020f9fd5`
Status: `EXACT_REMOTE_CI_PASS — HUMAN_PRIVACY_LEGAL_BLOCKED`
External effects: none

## Review contract

```yaml
task_id: INC-011
workstream_id: WS-11
producer: Privacy / Compliance Engineer
critic: Security, Supply-chain and Claims Reviewer
fixer: Compliance Engineer
independent_verifier: locked wheel, PostgreSQL, non-root package, Chromium and ephemeral infrastructure gates
objective: >
  Reconcile licenses, third parties, provider/data decisions, public claims and
  release authority without inventing jurisdiction, retention or legal approval.
human_gates:
  - privacy/legal reviewer approval
  - security reviewer approval
  - business/data owner approval
  - merge, release, cloud apply, destructive data action or external effects
```

## Delivered controls

- `compliance/third-party-inventory.json` cross-checks:
  - 19 direct npm packages with exact lock versions and licenses;
  - four direct Python runtime packages with exact hash-lock versions/licenses;
  - two digest-pinned OCI bases;
  - eight SHA-pinned GitHub Actions;
  - exact MIT `video-use` candidate, `reviewed_disabled`;
  - zero active external providers.
- `compliance/privacy-decision-register.json` preserves operating entity,
  jurisdiction and controller/processor role as `UNKNOWN`; seven policy scopes
  remain unapproved with null retention and no destructive implementation.
- `compliance/public-claims-policy.json` scans ten public surfaces and rejects
  unsupported production, compliance/certification, legal approval, guaranteed
  security, live research, automatic publication and unqualified autonomy copy.
- `compliance/release-decision.json` requires `DENY_RELEASE`, `DENY_APPLY`, no
  effects, no destructive action and no implied legal/independent approval.
- `scripts/verify-release-compliance.py` validates live manifests, locks,
  digests, SHAs, licenses, provider state, privacy unknowns, disclosures, copy and
  unresolved HIGH findings with no non-stdlib dependency.
- CI, production-package and supply-chain gates execute the validator.
- Public UI copy now says local sandbox/simulation rather than autonomous/live.
- Detailed review and notices are in `docs/compliance/`.

## Human decisions deliberately not fabricated

| Decision | Current value | Required evidence |
|---|---|---|
| Operating entity | `UNKNOWN` | accountable entity and customer scope |
| Jurisdiction | `UNKNOWN` | applicable law/region determination |
| Controller/processor role | `UNKNOWN` | approved role analysis and policy source |
| Retention | unapproved / null | start event, duration, class, exception and approval |
| Deletion/correction | not implemented | scope, identity proof, propagation and audit rules |
| Legal hold | not implemented | precedence, authority, release and audit rules |
| Provider terms | `UNKNOWN` | contract/DPA, region, subprocessors, training, retention, deletion |
| Privacy/legal approval | false | named reviewer and exact policy/version/date |

No deletion, legal-hold, provider, deployment or release action was executed.

## Critic findings and repairs

| ID | Severity | Finding | Repair | State |
|---|---|---|---|---|
| C-011-01 | HIGH | Green CI/license SBOM could be mistaken for legal/privacy approval. | Machine release decision remains `DENY_RELEASE`; docs and README explicitly deny legal/regulatory approval. | closed |
| C-011-02 | HIGH | A provider or invented retention could silently become enabled/approved. | Exact UNKNOWN/unapproved/null/false invariants plus negative mutation tests. | closed |
| C-011-03 | HIGH | Public copy implied autonomous/live operations unsupported by the sandbox. | Replaced copy and added ten-surface prohibited-claim scan with required disclosures. | closed |
| C-011-04 | MEDIUM | Inventory could drift from package manifests, locks, images, Actions or candidate commit. | Exact hashes, version/license comparisons, setup.cfg/package.json reconciliation and mutation tests. | closed |
| C-011-05 | MEDIUM | Nested schema additions could smuggle authority into provider/claims records. | Exact nested-key validation and duplicate/source-document guards. | closed |

No CRITICAL or open code-level HIGH remains in the repository-local slice.
`F-010` remains HIGH/open because accountable policy and legal decisions do not
exist. `F-011` remains HIGH/open because static copy scanning is not semantic
prompt-injection, groundedness, citation or legal-overclaim evaluation.

## Local verification

```text
Compliance validator                       PASS — DENY_RELEASE
Direct/build/candidate components           PASS — 33
Active external providers                   PASS — 0
Open human decision records                 PASS — 8
Public claim surfaces                       PASS — 10
Negative compliance mutations               PASS — 9
Locked Python wheel                         PASS — 127 tests, 11 PostgreSQL skips
PostgreSQL shared state                     PASS — 127/127
Frontend tests                              PASS — 66/66
Oxlint / TypeScript / Vite                   PASS
Real Chromium accessibility regression      PASS
Python lock regeneration                    PASS — byte-identical
Operability                                 PASS — 4 SLOs, 7 alerts, 8 exercises
Buildah non-root package                    PASS — compliance gate included
K3s/Helm/Terraform plan/apply/destroy        PASS — agentless control plane
Actionlint                                  PASS
Gitleaks full history                       PASS — zero leaks
Whitespace                                  PASS
Provider/destructive/release action          NOT_RUN BY DESIGN
```

## Evidence boundary

The gate proves inventory/repository consistency, disabled providers, explicit
unknowns, static public copy and fail-closed release denial. It is not legal
advice, regulatory certification, an approved privacy policy, provider contract,
semantic content evaluation, production observation or authorization to release.

## Delivery boundary

```text
specified: yes
implemented: 1843aa93c7675c6f5f10254ee3b7cffc020f9fd5
tested_local: yes
postgresql_verified_local: yes
package_verified_local: yes
infrastructure_verified_local: yes, agentless control plane only
committed: yes
pushed: 8820b1d50085363a160634a4d81b02d69a6424b4
pull_request: draft #9, clean and mergeable
remote_exact_head_ci: GitHub Actions 29880157199, 8/8 PASS
privacy_legal_approval: false
release_allowed: false
external_effects: none
```

## Blocker

`BLK-PRIVACY-001` remains authoritative. Resume only after the three accountable
reviewer roles record exact entity/customer scope, jurisdiction, role, policy
source/version/effective date, retention/deletion/correction/legal-hold/backup
rules and provider terms. Any implementation must then be independently tested
on the exact tree; destructive execution remains separately human-gated.
