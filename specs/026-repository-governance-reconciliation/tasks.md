# INC-026 Tasks — Repository Governance Reconciliation

1. Add the node and bounded spec to Graph Harness.
2. Persist the exact single-owner branch-protection policy.
3. Add deterministic policy/workflow/superseded-work validation to CI.
4. Replace hard-coded release blockers with exact unresolved-HIGH derivation.
5. Reconcile stale findings, risks, traceability and release documentation.
6. Audit issue #1 and PRs #2–#11 against current graph/main evidence.
7. Publish and pass exact-head CI.
8. Apply and read back live branch protection.
9. Comment on and close superseded issue/PR records without merging or deleting branches.
10. Record close evidence, run final CI and merge.

## Stop Conditions

- any historical branch contains useful unrepresented functionality;
- live protection cannot be restored or verified;
- closure would delete evidence or merge superseded code;
- any action would alter production, secrets, billing, provider state or legal approvals.
