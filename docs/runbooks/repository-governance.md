# Single-Owner Repository Governance Runbook

## Canonical policy

`program/repository-governance.json` is the desired protected-branch state. `npm run validate:governance` proves that its required checks exactly match the eight jobs in `.github/workflows/production-readiness.yml` and that superseded GitHub work maps to terminal or externally blocked Graph Harness nodes.

The repository has one owner. It therefore requires no approving review and no last-push approval. It still requires a pull request, all current strict checks, resolved review conversations, linear history and admin enforcement. Force pushes and branch deletion remain disabled.

## Safe apply

1. Pass exact-head CI for the policy change.
2. Read and archive the current branch protection.
3. Patch only required review and required status-check subresources.
4. Read back the full protection object and compare every governed field to the committed policy.
5. If readback differs, restore the archived settings and record a failed close gate.

## Superseded work closure

Historical PRs are closed, never merged. Each receives a comment linking its canonical graph node and explaining whether the node is done or blocked only by external evidence. Historical branches, commits, comments and artifacts are retained. The founding issue is closed only after all requirements are represented by current nodes and blockers.

## Boundaries

This policy does not authorize deployment, release, cloud apply, secret mutation, provider effects, spend or legal approval. `DENY_RELEASE` and `DENY_APPLY` remain authoritative.
