# Risk Register

Updated: 2026-07-21

| ID | Severity | Risk | Current control | Status |
|---|---|---|---|---|
| R-001 | HIGH | Two divergent production backends become concurrent authorities. | PR #3 runtime selected; PR #2 treated as donor; no wholesale merge. | Open, controlled |
| R-002 | HIGH | Documentation/CI imply a GCP deployment that does not exist. | Cloud state recorded as `DENY_APPLY`; runtime observation required. | Open external |
| R-003 | MEDIUM | Local recovery works but production backups may be stale, unencrypted or unavailable off-host. | Strict tooling plus SQLite/PostgreSQL application-readable drills pass; runbook requires external encryption/retention/scheduling. | Open deployment control |
| R-004 | HIGH | Duplicate or ambiguous mutable requests create conflicting state. | Deterministic run IDs and optimistic decisions reduce some races; durable idempotency ledger is missing. | Open |
| R-005 | HIGH | Static identity configuration is treated as enterprise production IAM. | RBAC/session/key rotation documented; SSO/MFA/lifecycle remain explicit gaps. | Open |
| R-006 | HIGH | Tenant or identity metadata leaks through errors, logs, metrics, or audit visibility. | Route-template logs, low-cardinality metrics, uniform cross-tenant 404, tenant-scoped audit. Privacy review still missing. | Open review |
| R-007 | HIGH | Greenlight is replayed, stale, or mistaken for publication. | Exact artifact IDs/hashes and sandbox publisher. Client idempotency and post-approval revocation remain missing. | Open |
| R-008 | HIGH | Alerts and SLOs are claimed from instrumentation only. | Evidence vocabulary separates instrumentation/test/observation/exercise. | Open |
| R-009 | HIGH | Agentless K3s is mistaken for workload execution. | Documentation states API/admission only; OCI smoke is separate. | Controlled |
| R-010 | MEDIUM | Version drift makes artifacts and evidence ambiguous. | Version normalization and executable consistency gate. | In progress |
| R-011 | MEDIUM | Manual accessibility defects escape automation. | Existing semantics/reduced-motion CSS; manual gate remains explicit. | Open |
| R-012 | MEDIUM | Five supply-chain HIGH exceptions expire without remediation. | Exact, expiring baseline with policy tests. | Open until 2026-08-21 |
| R-013 | MEDIUM | Future browser/video automation introduces prompt injection or uncontrolled side effects. | No integration activation; adapter evaluation and human gate required. | Controlled |
| R-014 | MEDIUM | Audit retention or deletion violates customer/privacy expectations. | No silent deletion; policy and human-gated destructive path required. | Open |

| R-015 | HIGH | PostgreSQL runtime role could initialize/own schema rather than operating with exact non-owner grants. | Local `df7fc7f878d8beb34fc956746a6bdfe34794f9f0` implements initialize/validate separation, fixed search path, exact non-owner grants and negative DDL/TEMP/escalation fixtures; no behavioral gate, push/CI or persistent environment observation has run. | Open, remediation in progress |
| R-016 | HIGH | Retention, deletion, legal hold and data-subject handling are undefined across primary data, telemetry and backups. | Privacy/classification model records UNKNOWN and prohibits silent destructive automation. | Human/legal + implementation gate |
| R-017 | HIGH | Semantic prompt injection, groundedness, harmful-use and legal-overclaim regressions can escape deterministic tests. | All external effects remain disabled; INC-010 owns the eval harness. | Open |
