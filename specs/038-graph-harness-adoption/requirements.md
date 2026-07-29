# INC-038 Requirements — Graph Harness SDLC Adoption

## Mode

SHIP.

## Requirements

- Use the canonical `BernydotJar/Graph-harness-sdlc` runtime at an exact immutable commit.
- Preserve `program/task-ledger.yaml` and `program/task-graph.yaml` as application-domain sources.
- Generate a typed Graph Harness project projection deterministically from those sources.
- Persist approvals, evidence, gates, transitions, failures, repairs, and checkpoints in the framework event ledger.
- Reject framework revision drift, projection drift, event-chain corruption, stale evidence, dependency cycles, and illegal transitions.
- Keep merge, release, deployment, spending, secret changes, and external effects human-gated.
- Keep INC-038 in `review` until exact-head CI and explicit close approval.

## Acceptance Criteria

- The framework is a pinned gitlink, not copied runtime code.
- Application validation executes the framework implementation directly.
- The adoption node reaches `review` only after spec, implementation, production, and review gates pass.
- The close gate remains open.
- Existing product behavior and effect flags are unchanged.

## Non-Goals

- No campaign, OAuth, provider, publication, database-schema, cloud, or UI behavior changes.
- No deployment or release.
