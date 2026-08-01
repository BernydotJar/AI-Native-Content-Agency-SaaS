# INC-031 Critic / Red Team Review

Date: 2026-07-31
Reviewed implementation: `30974c7698382d04a11cf4765b0fef0690762328`
Decision: PASS WITH NON-PRODUCTION LIMITATIONS

## Adversarial checks

The critic inspected the contract validator, OCI bundle generation, writer handoff, report validator, database-chain verification and cleanup paths. Focused tests were rerun with `PYTHONOPTIMIZE=1` so invariants do not depend on assertions.

The verifier correctly rejects:

- a rollback target equal to the candidate;
- incompatible runtime schema versions;
- API path drift;
- RTO above the configured bound;
- writable-root security drift;
- credential material in the report;
- a dirty worktree unless explicitly allowed for development.

The independent report replay confirmed that the candidate and rollback commits are exact, the source was clean, the pre-switch audit head is unchanged after the switch, the post-switch write advances the chain, and SQLite integrity is `ok`.

## Findings

No blocking implementation finding remains. Historical localized repairs retained in the design are: corrected graph dependencies, replacement of Docker/VFS with Buildah vfs/chroot, and use of the absolute Buildah mountpoint for the read-only OCI rootfs.

## Residual limitations

This is local loopback control evidence. It does not establish production network failover, managed-database failover, cross-zone RTO, off-host backup availability, Cloud Run revision traffic migration or authorization to mutate production traffic. The embedded identity and audit keys are deterministic test fixtures only and are not production credentials.
