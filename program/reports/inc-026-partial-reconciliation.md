# INC-026 Partial Reconciliation and Human Gate

Date: 2026-07-30
Candidate head: `679e59dd128055529d1df16e7a6aff0b283a0bcb`
PR: `#35`
Exact-head CI: `30521828441` — eight of eight jobs passed.

## Completed evidence

- Supply-chain policy PASS with 33 packages and clean-source provenance.
- Semantic artifact binds exact source/expected commit, reports a clean worktree and zero external effects.
- No unresolved PR review threads.
- PRs #2 through #11 are closed as superseded, never merged, with branches and artifacts retained.
- Issue #1 is closed as superseded by the canonical Graph Harness program.

## Blocked gate

The live `main` protection still requires one approving review, last-push approval and four obsolete checks. The committed policy requires the eight current workflow jobs and no impossible second-person approval for this single-owner repository.

The sandbox rejected the attempted protection update before execution. No branch-protection field changed. Because branch-protection and merge authority are human-gated, no bypass or alternate mutation path was used.

## Resume condition

An accountable human must explicitly authorize:

1. changing `main` required reviews from one to zero;
2. disabling last-push approval;
3. replacing the four obsolete contexts with the eight current production-readiness jobs;
4. merging PR #35 after a final exact-head run.

After authorization, apply only the two differing protection subresources, verify exact readback with `scripts/verify-repository-governance.py --protection-json`, record closure evidence, rerun exact-head CI and merge without deleting historical branches.

`DENY_RELEASE`, `DENY_APPLY`, all effect kill switches and all legal/privacy gates remain unchanged.
