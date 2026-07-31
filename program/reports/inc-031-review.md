# INC-031 Role-Separated Review

Date: 2026-07-31
Candidate commit: `3d74f892735ecc533bd9fea21aa3307dfd167fc3`
Rollback commit: `6fc3d73d73ee75d2f5fdbd5f3fe41e9368f9e9a7`
Graph revision: 0 on the rebuilt stack
Decision: PASS for technical review; exact-head CI and merge remain pending.

## Objective and result

The drill proves application-image rollback without database rollback. It builds two immutable OCI images from exact Git commits, runs each with UID/GID 10001, read-only root filesystems, no Linux capabilities and `noNewPrivileges`, and gives only `/tmp` plus a private SQLite data directory write authority.

The candidate created a tenant run and one audit event. After the candidate stopped completely, the prior compatible image started on the same loopback endpoint and same SQLite volume. The prior run remained readable, its status was unchanged, the durable audit head matched, and a new run succeeded after rollback.

Measured local RTO: **1,271 ms** against a 30,000 ms bound. SQLite `integrity_check` returned `ok`; two tenant runs and two linked audit events remained. No database restore, replacement or schema downgrade occurred. External effects: `0`.

## Historical localized repairs

The earlier development iteration exposed three issues, each confined to INC-031:

1. lifecycle dependencies pointed at technically complete but human-blocked nodes; the spec now depends only on completed capabilities and treats other evidence as inputs;
2. Docker/VFS could not build or load the full image; Buildah vfs/chroot now constructs the image;
3. runc rejected a symlink rootfs; OCI bundles now use the absolute Buildah mountpoint with `root.readonly=true`.

The rebuilt execution starts at Graph revision 0 because historical event projections were intentionally not copied into the repaired stack. These repairs remain documented evidence, not synthetic current events.

## Exact-tree verification

- workload rollback: PASS, RTO 1,271 ms, report SHA-256 `4fddf51abf3ae19bbf2e9c8ee63161dedba7abff25836c9dfc6773099ef2e6e3`;
- locked installed wheel: 386 tests PASS, 27 PostgreSQL-only skips;
- PostgreSQL 15.18: 386 tests PASS, schema v9, historical v1-v9 matrix, migration, least privilege, backup/restore PASS;
- API contract and semantic adversarial gates: PASS;
- OCI package: PASS, non-root, provider/model/social effects disabled;
- supply chain: PASS, `source_dirty=false`, offline signature PASS, registry publication false;
- frontend: 58 tests PASS, zero lint findings, production build PASS;
- Helm/K3s/Terraform: SQLite and PostgreSQL plan/apply/destroy PASS, Secret values absent from state, cleanup PASS;
- repository governance, compliance and operability: PASS;
- release/cloud decisions: `DENY_RELEASE` / `DENY_APPLY`.

## Remaining human gates

PR #40 exact-head CI and review are pending. Merge ordering #38 -> #39 -> #40 is not authorized by this increment. Any rollback or traffic change outside local loopback, production restore, production key/secret operation, release or deployment requires separate accountable authorization.
