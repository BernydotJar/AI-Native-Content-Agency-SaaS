# Capacity Assumptions

Status: reviewed starting assumptions; load/soak and persistent staging evidence remain required.

## Application and database

- The PostgreSQL application ceiling is `replicas * poolMaxSize` connections, plus migration/backup/operator connections.
- Default shared topology: two replicas and `poolMaxSize=10`, for a theoretical application ceiling of 20 database connections.
- Keep at least 20% database connection headroom for migration, backup, monitoring and incident work.
- Request body hard limit defaults to 1 MiB and must not be raised without memory/concurrency testing.
- SQLite remains single-replica only.

## Audit and idempotency growth

Every governed mutation writes an audit event. Durable idempotency receipts also store the exact committed run response document. Capacity planning must model:

```text
monthly audit bytes = commands_per_month * average_receipt_bytes
backup bytes        >= live database bytes + index/format overhead
```

No compaction or destructive retention is authorized until privacy/legal policy is approved. Alert on database growth and backup duration in the target environment.

## Latency and availability

- API p95 target: at most one second over 15 minutes.
- API availability target: 99.9% over 30 days.
- Readiness target: 99.95% over 30 days.
- Backup freshness: last validated backup no older than 25 hours.

These are objectives, not observed production performance. Load, soak, failover and quota evidence remain required before release.
