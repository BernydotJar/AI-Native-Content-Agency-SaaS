# Risk Register

Updated: 2026-07-24

| ID | Severity | Risk | Current control | Status |
|---|---|---|---|---|
| R-001 | HIGH | Two divergent production backends become concurrent authorities. | PR #3 runtime selected; PR #2 treated as donor; no wholesale merge. | Open, controlled |
| R-002 | HIGH | Documentation/CI imply a GCP deployment that does not exist. | Cloud state recorded as `DENY_APPLY`; runtime observation required. | Open external |
| R-003 | HIGH | Production backup may be stale, unencrypted, mutable or unavailable off-host. | Exact local `6a885827b7e89d06111c87c34293250eab196d47` proves validated private freshness signals, stale/missing alerts and restores; scheduler, KMS/encryption, immutable off-host retention and real delivery remain absent. | External production controls required |
| R-004 | HIGH | Duplicate or ambiguous mutable requests create conflicting state. | Exact head `bc01fa7b54341865f848c0754884cc83f660a0c7` passed local race/replay gates and eight-job CI run `29871278876` using digest-only transactional receipts and advisory command locks. | Controlled in code and delivery |
| R-005 | HIGH | Static identity configuration is treated as enterprise production IAM. | RBAC/session/key rotation documented; SSO/MFA/lifecycle remain explicit gaps. | Open |
| R-006 | HIGH | Tenant or identity metadata leaks through errors, logs, metrics, or audit visibility. | Route-template logs, low-cardinality metrics, uniform cross-tenant 404, tenant-scoped audit. Privacy review still missing. | Open review |
| R-007 | HIGH | Greenlight is replayed, stale, revoked or mistaken for publication. | Exact head `bc01fa7b54341865f848c0754884cc83f660a0c7` passed authenticated-subject, artifact, channel, budget, revocation and fencing gates plus CI. External effects remain disabled pending provider-specific receipts. | Controlled for current sandbox |
| R-008 | HIGH | Alerts and SLOs are claimed from instrumentation only. | Evidence vocabulary separates instrumentation/test/observation/exercise. | Open |
| R-009 | HIGH | Agentless K3s is mistaken for workload execution. | Documentation states API/admission only; OCI smoke is separate. | Controlled |
| R-010 | MEDIUM | Version drift makes artifacts and evidence ambiguous. | Version normalization and executable consistency gate. | In progress |
| R-011 | MEDIUM | Manual accessibility defects escape automation. | Existing semantics/reduced-motion CSS; manual gate remains explicit. | Open |
| R-012 | MEDIUM | Five supply-chain HIGH exceptions expire without remediation. | Exact, expiring baseline with policy tests. | Open until 2026-08-21 |
| R-013 | MEDIUM | Future browser/video automation introduces prompt injection, path escape, media disclosure or uncontrolled side effects. | Exact `video-use` source/hashes reviewed; strict review-only plan; authenticated GET-only registry; no executor; all effect flags false. | Controlled while disabled; separate activation review required |
| R-014 | MEDIUM | Audit retention or deletion violates customer/privacy expectations. | No silent deletion; policy and human-gated destructive path required. | Open |

| R-015 | HIGH | PostgreSQL runtime role could initialize/own schema rather than operating with exact non-owner grants. | Exact head `1002d077564618623fe00f27ffae23c2b410aca8` passed local least-privilege gates and eight-job CI run `29868899218`. Persistent staging observation remains under R-002/F-004. | Controlled in code and delivery |
| R-016 | HIGH | Retention, deletion, legal hold and data-subject handling are undefined across primary data, telemetry and backups. | Privacy/classification model records UNKNOWN and prohibits silent destructive automation. | Human/legal + implementation gate |
| R-017 | HIGH | Semantic prompt injection, groundedness, harmful-use and legal-overclaim regressions can escape deterministic tests. | All external effects remain disabled; INC-010 owns the eval harness. | Open |
| R-018 | MEDIUM | Frontend role gating is mistaken for an authorization boundary or hides server-side denial evidence. | `4f10122` keeps backend authorization authoritative, exposes bounded request correlation, supports tenant-scoped run lookup and tests server-denial recovery. | Controlled in code; manual UX/accessibility review pending INC-008 |
| R-019 | HIGH | A paid visual theme is mistaken for RBAC, billing proof or DRM, or remains active after entitlement revocation. | Exact allowlisted server identity entitlement, active-session `/me` refresh, immediate free-theme fallback, no storage/persistence, and explicit billing/DRM limitations. | Controlled in code; billing remains absent |
| R-020 | MEDIUM | Automated browser and AX-tree evidence is mistaken for human screen-reader or visual accessibility approval. | Evidence artifacts and protocol label human screen-reader, rendered contrast, 400% zoom and visual review `NOT_RUN`; F-007 remains open. | Human review required |
| R-021 | HIGH | Green technical/SBOM/license gates are mistaken for legal, privacy or regulatory approval. | Exact machine decision `DENY_RELEASE`; all authority flags false; README/dossier disclaim legal certification; nine negative compliance tests. | Controlled in repository; accountable approval absent |
| R-022 | HIGH | Public copy overstates autonomous/live/production behavior or automatic publication. | Ten-surface claims scan, required sandbox disclosures and corrected local-simulation copy; semantic generated-content review remains under R-017/F-011. | Static copy controlled; semantic review open |

| R-023 | HIGH | Provider configuration readiness is mistaken for successful inference or authorization to spend. | Exact GET-only registry, no clients/network calls, UI/runbook disclosure and `DENY_RELEASE`; provider execution requires a separate gated increment. | Controlled while execution disabled |
| R-024 | MEDIUM | Static Vite preview is mistaken for the full-stack product. | `npm run start:local` serves SPA + FastAPI + SQLite on loopback; README labels preview visual-only; integrated smoke passes. | Controlled locally |
| R-025 | MEDIUM | A second legacy frontend reintroduces demo mocks or divergent authority. | `a89907f` removes 5,778 lines of unreachable simulation/dashboard code; one App/runtime path remains. | Controlled in code; preserve deletion |

| R-026 | HIGH | A provider call succeeds but local persistence fails, causing a replay to duplicate spend. | Gateway remains disconnected; INC-015 requires persisted intent, fencing, receipt-before-completion and unknown-state reconciliation. | Open, execution disabled |
| R-027 | HIGH | Protocol-ready status is mistaken for active inference or approval to transfer prompts/spend. | API/UI expose durable receipt and automatic integration as false; no completion route; package and compliance gates enforce zero active providers. | Controlled while disabled |
| R-028 | MEDIUM | Sandbox push tooling prevents exact remote delivery evidence for local INC-013/014 commits. | Clean local commits, git integrity, explicit blocker and no bypass; official connector repair required. | Tooling blocked |

| R-029 | HIGH | OAuth tokens leak, cross tenants or replay through a second callback. | INC-019 uses AES-GCM tenant/channel AAD, expiring session-bound state, atomic consume and no token-bearing API/log/audit fields. | Controlled locally; exact remote CI pending |
| R-030 | HIGH | Account connection is mistaken for authority to publish or incur provider cost. | `8eb0cf7` requires enabled server flag, admin confirmation, exact account/artifact/media/Greenlight binding, durable intent/fence/receipt, compatible replay and unknown reconciliation; defaults remain disabled. | Controlled locally; real sandbox/production authorization pending |
| R-031 | MEDIUM | Server-side token bootstrap is partially configured or enters Terraform state. | Exact required groups fail startup; Terraform receives only Secret/key names; package/infra gates scan for values. | Controlled locally |

| R-032 | HIGH | Worker and API lock order freezes durable run reads. | `8eb0cf7` resolves tenant runtime before acquiring the durable run lock; deterministic lock-order, prior-inline reproduction and installed-image checkpoint tests pass. | Closed locally; remote CI pending |
