# INC-026 Design — Repository Governance Reconciliation

## Governance Policy

`program/repository-governance.json` is the canonical desired state for protected `main`:

- repository mode: `single_owner`;
- exact required checks: the eight job IDs from `production-readiness.yml`;
- strict checks, linear history, conversation resolution and admin enforcement enabled;
- approving review count zero and last-push approval disabled;
- force pushes and deletion disabled.

`scripts/verify-repository-governance.py` validates the policy, workflow job set and superseded-work mapping without network access. Live GitHub settings are applied and independently read back only at the close gate.

## Dynamic Release Blockers

`verify-release-compliance.py` derives the unresolved HIGH set from `program/critique-findings.json` and requires exact equality with `compliance/release-decision.json`. This removes hidden hard-coded drift while preserving fail-closed release denial.

## Superseded Work

`program/superseded-work.json` records issue #1 and PRs #2–#11 with graph-node mapping, historical head, disposition and remote state. PR #2 is explicitly a donor/superseded architecture. Other PRs are stacked implementation checkpoints whose canonical nodes are `done` or `blocked` only by external gates. Closure uses comments and the GitHub close action; no merge or branch deletion occurs.

## Human / External Gate

The user's explicit single-owner and merge authorization covers branch-protection reconciliation and non-destructive closure of superseded GitHub work. Production, release, secrets, spend and provider effects remain outside scope.

## Files You May Touch

- `.github/workflows/production-readiness.yml`
- `package.json`
- `backend/tests/test_graph_harness_adapter.py`
- `backend/tests/test_program_state.py`
- `backend/tests/test_release_compliance.py`
- `backend/tests/test_repository_governance.py`
- `compliance/release-decision.json`
- `compliance/third-party-inventory.json`
- `docs/compliance/release-compliance-review.md`
- `docs/runbooks/repository-governance.md`
- `program/**`
- `scripts/verify-release-compliance.py`
- `scripts/verify-repository-governance.py`
- `specs/026-repository-governance-reconciliation/**`

## Files You Must Not Touch

- product runtime and UI implementation;
- production infrastructure or secrets;
- legal/privacy approvals;
- historical Git branches or commits.

## Verification

- static policy/workflow/mapping validator;
- release blocker negative tests;
- Graph Harness/program/compliance gates;
- locked-wheel regression;
- workflow lint and exact-head CI;
- live GitHub branch-protection readback;
- remote issue/PR state readback and no-merge audit.
