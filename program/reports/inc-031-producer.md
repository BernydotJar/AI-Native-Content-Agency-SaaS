# INC-031 Producer Report — Deterministic Workload Rollback

Date: 2026-07-31
Implementation commit: `30974c7698382d04a11cf4765b0fef0690762328`
Implementation tree: `7330233437630cb8086f9ff71d710987d941ac5d`
Rollback commit: `fe75c5f563e97cda38f4fe0a7c05f9c455000474`
Rollback tree: `3cb641d61411c19fe305d9144d10edf768ac6931`

## Produced capability

INC-031 adds a bounded local rollback orchestrator that builds exact candidate and rollback OCI images, runs them sequentially on one loopback endpoint and one private SQLite volume, measures readiness recovery, and proves application rollback without database rollback.

Both workloads run as UID/GID 10001 with a read-only root filesystem, empty Linux capability sets, `noNewPrivileges`, a noexec tmpfs, and all model, provider, social, political and paid-media effects disabled. The candidate is fully stopped before the rollback workload starts.

## Producer evidence

- real Buildah/runc rollback drill: PASS;
- candidate startup: 622 ms;
- measured local RTO: 1,863 ms, bounded by 30,000 ms;
- original run and audit head preserved across the switch;
- post-rollback run creation: PASS;
- SQLite `integrity_check=ok`;
- final tenant runs: 2;
- final audit events: 2 with a verified SHA-256 chain;
- report SHA-256: `bd088127abea09c5835b2f06579550947b0c46f292e28036ab5a7a9feb3e194d`;
- source dirty: false;
- database restore/replacement: false;
- external effects: 0.

No production traffic, database, secret, provider, registry or cloud resource was changed.
