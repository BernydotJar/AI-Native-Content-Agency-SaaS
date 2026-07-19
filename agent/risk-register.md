# Risk Register

Updated: 2026-07-19T03:59:19Z

| ID | Severity | Risk | Mitigation / gate | Status |
|---|---|---|---|---|
| RISK-001 | Critical | Two active sources of run truth diverge. | Default integrated UI to backend; legacy timers require explicit demo mode. | Closed by tests, live smoke and CI |
| RISK-002 | High | Approval replay or artifact mutation bypasses intent. | Canonical hash/policy, transactions, locks, constraints and adversarial tests. | Closed by role-separated verification |
| RISK-003 | High | Development identity is mistaken for production authentication. | Production startup rejects header auth and SQLite; dev Cloud Run requires IAM invocation. | Mitigated for dev; production auth deliberately deferred |
| RISK-004 | High | Terraform creates public, destructive, broad-IAM or costly resources. | Static veto, private IAM, bounded resources, saved-plan critique and exact-plan gate. | Open externally; `DENY_APPLY` |
| RISK-005 | Medium | Inline execution is described as fully durable. | Documentation and contracts claim command-boundary durability only. | Accepted V1 limitation |
| RISK-006 | Medium | Cloud SQL creates ongoing cost. | Small dev tier, required delivery channel, budget and cost review before plan. | Unproven and blocked before spend |
| RISK-007 | Medium | Local container topology is not exercised. | Live Compose migration/HTTP/restart smoke plus CI Compose smoke. | Closed |
| RISK-008 | Medium | Dependency/provider drift invalidates delivery. | Hash locks, multi-platform provider checksums, pinned actions/images and advisory scans. | Mitigated; local and CI gates pass |
| RISK-009 | Medium | UI visual regression escapes nonvisual tests. | Component tests, build, exact-image HTTP smoke and required browser QA when available. | Open limitation; browser runtime unavailable |
| RISK-010 | Medium | A lost mutable-command response is mistaken for failure. | UI reports unknown outcome and retries only the exact payload/key or refreshes state. | Closed; regression tested |
| RISK-011 | High | Cross-tenant identifiers form valid application objects but invalid ownership chains. | Composite tenant foreign keys plus PostgreSQL negative tests. | Closed |
| RISK-012 | High | Runtime deploy identity can mutate unrelated Cloud Run or registry resources. | Exact 19-permission custom role and repository-scoped Artifact Registry reader. | Closed statically; real IAM preflight blocked |
| RISK-013 | Medium | A job-wide database URL contaminates hermetic migration unit tests. | Scope PostgreSQL URL to integration steps and delete inherited URL inside SQLite migration tests. | Closed; local contamination probe and CI pass |
| RISK-014 | Medium | Interval polling overlaps a terminal response and emits an extra request. | Sequential recursive timeout, cancellation and terminal-response stop. | Closed; eight repeated focused runs and CI pass |
| RISK-015 | High | Test tooling contains a known vulnerability. | Python 3.10 minimum, pytest `>=9.0.3,<10`, regenerated exact locks and current audits. | Closed; pytest 9.1.1 and zero known vulnerabilities |
| RISK-016 | Medium | Role-separated self-review is mistaken for independent approval. | Explicitly label audit provenance and require a different reviewer before merge/cloud apply. | Open process limitation |
