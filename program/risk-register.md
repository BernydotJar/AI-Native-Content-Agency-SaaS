# Risk Register

Updated: 2026-07-21

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
| R-013 | MEDIUM | Future browser/video automation introduces prompt injection or uncontrolled side effects. | No integration activation; adapter evaluation and human gate required. | Controlled |
| R-014 | MEDIUM | Audit retention or deletion violates customer/privacy expectations. | No silent deletion; policy and human-gated destructive path required. | Open |

| R-015 | HIGH | PostgreSQL runtime role could initialize/own schema rather than operating with exact non-owner grants. | Exact head `1002d077564618623fe00f27ffae23c2b410aca8` passed local least-privilege gates and eight-job CI run `29868899218`. Persistent staging observation remains under R-002/F-004. | Controlled in code and delivery |
| R-016 | HIGH | Retention, deletion, legal hold and data-subject handling are undefined across primary data, telemetry and backups. | Privacy/classification model records UNKNOWN and prohibits silent destructive automation. | Human/legal + implementation gate |
| R-017 | HIGH | Semantic prompt injection, groundedness, harmful-use and legal-overclaim regressions can escape deterministic tests. | All external effects remain disabled; INC-010 owns the eval harness. | Open |
| R-018 | MEDIUM | Frontend role gating is mistaken for an authorization boundary or hides server-side denial evidence. | `4f10122` keeps backend authorization authoritative, exposes bounded request correlation, supports tenant-scoped run lookup and tests server-denial recovery. | Controlled in code; manual UX/accessibility review pending INC-008 |
