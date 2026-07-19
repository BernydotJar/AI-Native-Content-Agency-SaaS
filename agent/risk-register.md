# Risk Register

| ID | Severity | Risk | Mitigation / gate | Status |
|---|---|---|---|---|
| RISK-001 | Critical | Two active sources of run truth diverge. | Default integrated UI to backend; legacy timers require explicit demo mode. | Closed; independently verified |
| RISK-002 | High | Approval replay or artifact mutation bypasses intent. | Canonical hash/policy, transaction, locks, constraints and adversarial tests. | Closed; independently verified |
| RISK-003 | High | Development identity is mistaken for production authentication. | Production startup rejects header auth and SQLite; dev Cloud Run requires IAM invocation. | Mitigated for dev; production auth deliberately deferred |
| RISK-004 | High | Terraform creates public, destructive, broad-IAM or costly resources. | Static veto, private IAM, bounded resources, saved-plan critique and exact-plan gate. | Open externally; `DENY_APPLY` |
| RISK-005 | Medium | Inline execution is described as fully durable. | Documentation and contracts claim command-boundary durability only. | Accepted V1 limitation |
| RISK-006 | Medium | Cloud SQL creates ongoing cost. | Small dev tier, budget, deletion protection and cost review before plan. | Unproven and blocked before spend |
| RISK-007 | Medium | Local container topology is not exercised. | Live Compose migration/HTTP/restart smoke plus CI Compose smoke. | Closed |
| RISK-008 | Medium | Dependency/provider drift invalidates delivery. | Hash locks, multi-platform provider checksums, pinned actions/images and advisory scans. | Mitigated; gates pass |
| RISK-009 | Medium | UI visual regression escapes nonvisual tests. | Component/accessibility tests and exact-image HTTP smoke; required browser QA when available. | Open limitation; browser runtime unavailable |
| RISK-010 | Medium | A lost mutable-command response is mistaken for failure. | UI reports unknown outcome and retries only the exact payload/key or refreshes state. | Closed; regression tested |
