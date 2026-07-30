# INC-026 Requirements — Repository Governance Reconciliation

## Mode

SHIP.

## Problem

The repository is operated by one owner, but protected `main` still requires an approval from another identity and four historical status-check names that no longer exist. Ten historical stacked pull requests and the founding issue remain open even though their implementation is integrated, superseded, or represented by explicit external blockers. The release-compliance verifier also hard-codes a stale HIGH-finding set, leaving completed findings open and hiding the current provider-deletion blocker.

## Requirements

- Persist an exact single-owner repository-governance policy for protected `main`.
- Require pull requests, strict current CI checks, linear history, resolved conversations, admin enforcement, no force pushes and no branch deletion.
- Set required approving reviews to zero and disable last-push approval because no second maintainer identity exists.
- Validate that the policy's required status checks exactly match the workflow job IDs.
- Derive release blockers from every unresolved HIGH finding rather than a hard-coded list.
- Close F-011 and F-046 using their merged Graph Harness evidence; retain F-050 only for post-publication deletion/legal authority.
- Map issue #1 and PRs #2–#11 to canonical graph nodes and prove that they are integrated, superseded, or blocked only by current external gates.
- Close superseded issue/PR records with explanatory comments; do not merge or delete historical branches.
- Apply the persisted branch-protection policy to the live repository only after exact-head CI and verify the resulting live state.
- Preserve `DENY_RELEASE`, `DENY_APPLY`, all real external-effect controls, and the four blocked graph nodes.

## Acceptance Criteria

- The policy and workflow job set are identical and deterministic.
- Release decision `blocked_findings` equals the exact set of unresolved HIGH findings.
- F-011 and F-046 are closed with merged evidence; F-050 remains unresolved only for provider deletion/legal authority.
- PRs #2–#11 and issue #1 are remotely closed, with no historical PR merged and no branch deleted.
- Live `main` protection exactly matches the committed single-owner policy.
- A future PR with all eight checks and resolved conversations no longer requires an impossible second-person approval.
- Program, Graph Harness, compliance, workflow, locked-wheel and exact-head CI gates pass.

## Non-Goals

- No production deployment, release, secret mutation, cloud apply, publication or provider deletion.
- No closure of INC-005, INC-006, INC-008 or INC-011.
- No resurrection or wholesale merge of the discarded PR #2 architecture.
- No deletion of historical branches, tags, commits, comments or audit evidence.
