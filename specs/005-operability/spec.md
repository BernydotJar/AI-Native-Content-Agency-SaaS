# INC-005 — SLOs, Alerts, Backup Freshness and Rollback Operations

## Problem

The runtime exposes counters and a duration sum, but has no percentile-capable histogram, versioned SLO/error-budget contract, executable alert catalog, backup freshness signal, exercised incident path or release rollback drill. Existing operational prose cannot prove that alerts are syntactically coherent or fire for expected failure states.

## Purpose

Turn operational recommendations into deterministic artifacts and local evidence without creating external infrastructure or spending. Production backup storage, KMS, immutable retention and real paging remain external gates.

## Actors and journeys

- **On-call operator:** receives a bounded actionable alert and follows the linked runbook.
- **Release operator:** rolls a Helm release back to the previous revision and verifies the restored configuration.
- **Backup operator:** emits a scrapeable freshness metric after a successful backup.
- **Production reviewer:** checks SLO targets, error budgets, exercises, capacity assumptions and evidence boundaries.

## Functional requirements

1. Version API availability, latency, readiness and backup-freshness SLOs.
2. Publish request-duration histogram buckets suitable for `histogram_quantile`.
3. Define Prometheus alerts for fast/slow availability burn, p95 latency, readiness, authentication abuse and stale backup.
4. Every alert has severity, SLO/control owner, summary and repository runbook anchor.
5. A dependency-free validator checks SLO math, rule/catalog parity, runbook anchors and synthetic exercises.
6. Healthy synthetic input fires no alert; each failure scenario fires exactly its expected alert set.
7. Backup commands optionally write a private, atomic Prometheus textfile containing backend, success timestamp and artifact bytes.
8. The stale-backup alert uses the emitted metric and the approved maximum age.
9. Helm can render an opt-in `PrometheusRule`; it is disabled by default and requires an existing Prometheus Operator.
10. A local K3s drill installs a release, upgrades a bounded configuration value, rolls back and verifies the exact previous revision/configuration.
11. Incident and rollback runbooks distinguish detection, mitigation, restore, rollback, evidence and human gates.
12. Capacity assumptions state per-replica pool/request ceilings and audit/idempotency growth.
13. No external monitor, pager, object store, KMS, cloud resource or traffic is created.

## Non-functional requirements

- All validation uses Python standard library plus existing repository tools.
- Metrics have bounded labels only.
- Backup metric files are mode `0600`, same-directory atomic replacements and contain no URL, path, tenant, key or content.
- Alert exercises are deterministic and do not claim telemetry observation.
- Agentless K3s rollback is control-plane evidence, not workload execution evidence.

## States and failures

- `metrics_implemented` → histogram/backup textfile exists.
- `rules_validated` → structural and catalog parity pass.
- `alert_exercised` → synthetic expected alert set matches.
- `rollback_exercised` → Helm revision/configuration is restored.
- `telemetry_observed` → external staging requirement; not satisfied locally.
- `pager_exercised` → external incident-management requirement; not satisfied locally.

## Security, privacy and tenant boundaries

Metrics never label tenant, subject, campaign, request ID or idempotency key. Backup metrics expose only backend, timestamp and byte count. Runbooks prohibit credentials in commands/evidence.

## Acceptance criteria

- histogram buckets are cumulative and include `+Inf`;
- all alert expressions reference emitted or explicitly platform-owned metrics;
- SLO error-budget minutes are mathematically correct;
- every synthetic scenario produces the exact alert set;
- missing rules/runbooks/scenarios fail validation;
- successful SQLite and PostgreSQL backup paths write valid private textfiles;
- Helm alert render is valid and disabled by default;
- Helm upgrade/rollback drill restores the original setting and leaves no namespace;
- locked wheel, frontend, package, infrastructure, secret and CI gates remain green.

## Out of scope

- provisioning Prometheus, Alertmanager, PagerDuty or cloud monitoring;
- production object storage, KMS keys, retention locks or schedules;
- production traffic, deployment or destructive restore;
- declaring SLO compliance without observed telemetry.
