# INC-031 Design — Local Workload Rollback Drill

## Candidate and rollback artifacts

The candidate is the exact checked-out HEAD. `contracts/workload-rollback-v1.json` pins a previously verified ancestor commit whose runtime declares PostgreSQL schema v9 and supports the same durable run/audit API. Both source trees are exported with `git archive` and built independently with Buildah vfs/chroot.

## Workload sequence

1. Start candidate image on a fixed loopback port with a private bind-mounted SQLite file.
2. Wait for `/readyz`, create one tenant run and record the audit checkpoint.
3. Terminate the candidate process and record the failure timestamp.
4. Start the rollback image on the same port and same database volume.
5. Poll readiness; record rollback RTO at first successful response.
6. Read the original run and audit checkpoint, then create a second run.
7. Stop the rollback workload and run SQLite integrity plus audit-chain verification from the installed current wheel.

The previous and candidate writers never overlap. No data restore occurs; application rollback and data rollback remain separate authorities.

## Report

The generated report contains no credentials. It binds exact commits, source trees, image IDs, candidate/rollback readiness, run IDs, audit head/count before and after, RTO milliseconds, database SHA-256 after clean shutdown, and `external_effects=0`.

## Lifecycle dependency note

The node depends only on completed runtime, persistence and QA capabilities (`INC-002`, `INC-019`, `INC-024`). `INC-005`, `INC-030`, and their exact-head evidence are authoritative inputs but remain human-blocked at close, so they cannot be executable graph dependencies.

## Builder/runtime separation

Buildah vfs/chroot constructs immutable images and mounts isolated working root filesystems. `runc` executes each OCI bundle with the absolute Buildah mountpoint and `root.readonly=true`, non-root user 10001, no Linux capabilities, `noNewPrivileges`, tmpfs `/tmp`, private bind-mounted SQLite `/data`, and host networking restricted by the application to a loopback port. This avoids daemon storage-driver limitations without weakening runtime controls.
