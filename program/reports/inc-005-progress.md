# INC-005 Verification Review

Date: 2026-07-21
Branch: `agent/inc-005-operability`
Base: `agent/inc-004-idempotency@d228656b40e456c249477ee3b01e376ae3cfb46f`
Exact verified implementation commit: `6a885827b7e89d06111c87c34293250eab196d47`
Status: `LOCAL_VERIFIED_PENDING_PUSH_CI_AND_EXTERNAL_GATES`

## Outcome

All safe local operability work is implemented and verified. Persistent monitoring/paging, production backup scheduling/KMS/off-host retention and staging workload/incident evidence remain external blockers and are not claimed.

```yaml
increment: INC-005
workstream: WS-09
status: REVIEW
implementation_head: 6a885827b7e89d06111c87c34293250eab196d47
push: PENDING
exact_head_ci: PENDING
F_008: OPEN
production_status: DENY_RELEASE
cloud_status: DENY_APPLY
external_effects: NONE
```

## Proven local boundary

- Four SLOs and exact 30-day error budgets validate fail-closed.
- Request latency is a cumulative bounded-label Prometheus histogram.
- Seven alerts have exact catalog/rule parity, owners, objectives and runbook anchors.
- Eight deterministic scenarios cover healthy state and every alert.
- Readiness detects failed or absent probes; backup detects stale and absent freshness series.
- SQLite/PostgreSQL backups can atomically write private validated freshness metrics.
- Helm/Terraform render rules only by opt-in for an existing Prometheus Operator.
- A bounded Helm upgrade/rollback restores the previous value/revision and deployed status.
- Incident, rollback, capacity and tracing decisions are explicit and versioned.

## Executed evidence

| Gate | Result | Observed |
|---|---|---|
| operability validator | PASS | 4 SLOs, 7 alerts, 8 exercises; budget/rule/metric/runbook parity and negative tests |
| focused tests | PASS | 19 operability, backup and observability tests |
| locked wheel | PASS | agency-runtime 0.7.0; 100 tests, 11 PostgreSQL-only skips |
| PostgreSQL | PASS | PostgreSQL 15.18; 101/101; freshness textfiles, migration/replay and restores |
| frontend | PASS | lint zero, 35/35 tests and production build |
| package | PASS | non-root runtime smoke, operability validator and opt-in rule render |
| local infrastructure | PASS | both storage topologies plus upgrade/rollback/config restoration and cleanup |
| workflow/secrets | PASS | actionlint and zero effective Gitleaks findings |
| supply chain | PASS | clean source, pinned bases, SBOM, Grype/license policy, provenance and offline Cosign |

## Critic findings resolved

- readiness alert now detects failed and absent probes;
- stale-backup alert evaluates each backend series rather than hiding one stale backend behind another fresh backend;
- missing backup signal has a distinct critical alert and exercise;
- textfile writer preserves operator-managed parent-directory permissions;
- rollback verifies the final Helm revision status is `deployed`;
- Prometheus rules remain opt-in and no monitoring stack is installed;
- tracing has an explicit conservative decision rather than an empty deployment claim.

## Residual blockers

- no persistent monitoring system has loaded the rules;
- no pager or human incident drill has been exercised;
- no production scheduler, encrypted immutable off-host storage, KMS/key lifecycle or approved retention exists;
- no workload/traffic rollback or measured RTO exists;
- no staging load, soak, pool saturation or failover evidence exists.

These are tracked by `F-004`, `F-008`, `BLK-GCP-001`, `BLK-BACKUP-PROD-001` and related requirements.

## Exact continuation

Commit the program checkpoint, push `agent/inc-005-operability`, verify the remote SHA and create a draft PR based on `agent/inc-004-idempotency`. Require all eight jobs. Do not close `F-008` from local evidence and do not create external monitoring, storage, KMS or scheduled resources without separate authorization.
