# Authenticated Request Quota Runbook

## Purpose

The runtime bounds authenticated request and denial-audit amplification with two durable fixed-window counters:

- one opaque bucket for tenant + authenticated subject;
- one opaque bucket for the tenant aggregate.

Only SHA-256 bucket digests and counters are stored. Tenant IDs, subjects, key IDs, session IDs and API keys are not stored in quota rows or exposed as metric labels.

## Configuration

| Variable | Default | Allowed range |
|---|---:|---:|
| `AGENCY_AUTHENTICATED_REQUEST_MAX_PER_PRINCIPAL` | 600 | 10–100000 |
| `AGENCY_AUTHENTICATED_REQUEST_MAX_PER_TENANT` | 6000 | principal limit–1000000 |
| `AGENCY_AUTHENTICATED_REQUEST_WINDOW_SECONDS` | 60 | 1–3600 seconds |

The same values are available as Helm `runtime.auth.authenticatedRequest*` settings and Terraform `authenticated_request_*` variables. They are non-secret.

## Behavior

Successful authentication is followed by atomic consumption of both buckets. The quota is checked before CSRF and permission authorization, so a rejected request returns HTTP 429 with `Retry-After` and does not append another denial-audit event. Browser sessions and bearer credentials for the same tenant/subject share a principal bucket.

PostgreSQL schema v8 enforces the limit across replicas with transaction-scoped advisory locks and row locks. SQLite uses one transaction under the process store lock. Expired rows are removed while consuming quota.

## Monitoring

`agency_authenticated_request_quota_total{outcome="allowed|rate_limited"}` contains no identity labels. Investigate sustained `rate_limited` growth alongside HTTP 429 rates and capacity signals. Do not add tenant, subject, path input or credential labels.

## Tuning

1. Confirm whether legitimate clients burst within one minute or continuously exceed the quota.
2. Prefer client backoff and request consolidation before increasing limits.
3. Preserve tenant headroom above the principal limit.
4. Change one environment at a time and observe 429 rate, latency, database lock time and audit-row growth.
5. Roll back to the prior values if database contention or abuse increases.

Quota tuning is not release authority and does not enable any provider effect.

## Recovery

A mistaken low limit is reversible by increasing the configured value and restarting/rolling the workload. Existing window rows expire automatically; deleting quota rows is unnecessary and should not be performed in production without a separate destructive-data approval.
