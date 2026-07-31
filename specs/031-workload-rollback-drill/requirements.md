# INC-031 Requirements — Local Workload Rollback Drill

## Goal

Execute a real local application-image rollback on a stable endpoint while preserving the active schema-v9 database and tenant data.

## Requirements

1. Build the candidate image and one exact previously verified compatible image from immutable Git commits.
2. Run both images as non-root, read-only workloads with all provider/model/publication effects disabled.
3. Use one private SQLite database volume and never run both application writers concurrently.
4. Create and read tenant state through the candidate image before failure.
5. Stop the candidate, start the rollback image on the same host/port, and measure time until readiness recovers.
6. Prove the pre-rollback run and audit chain remain readable, then create a new run after rollback.
7. Prove no database restore, replacement, schema downgrade, secret mutation, provider call, cloud resource, or external effect occurred.
8. Produce a deterministic JSON report bound to source/rollback commits, image IDs, database hash, request IDs, RTO and verification results.
9. Reject a rollback commit that is missing, not an ancestor, declares a different schema, or lacks the current API paths needed by the drill.
10. Exact-head CI passes; production rollback remains separately human-gated.

## Lifecycle dependency note

The node depends only on completed runtime, persistence and QA capabilities (`INC-002`, `INC-019`, `INC-024`). `INC-005`, `INC-030`, and their exact-head evidence are authoritative inputs but remain human-blocked at close, so they cannot be executable graph dependencies.

## Builder/runtime separation

Buildah vfs/chroot constructs immutable images and mounts isolated working root filesystems. `runc` executes each OCI bundle with the absolute Buildah mountpoint and `root.readonly=true`, non-root user 10001, no Linux capabilities, `noNewPrivileges`, tmpfs `/tmp`, private bind-mounted SQLite `/data`, and host networking restricted by the application to a loopback port. This avoids daemon storage-driver limitations without weakening runtime controls.
