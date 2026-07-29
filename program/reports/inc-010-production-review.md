# INC-010 Production Review — Semantic Evaluation Gate

Updated: 2026-07-29  
Implementation commit: `b726ae5854bb5406b819c815f3acf66d933acf40`  
Decision: `PASS_FOR_REMOTE_VERIFICATION`; `DENY_RELEASE` remains mandatory.

## Security and Integrity

- Evaluation is offline and imports no network-capable client modules.
- Input schemas, key sets, lengths, identifiers, collections and mutation paths fail closed.
- Reports bind the exact Git commit/tree, corpus digest and evaluator digest.
- An independent verifier rejects report, digest, case, result, finding and effect-state tampering.
- The generated report is ignored by Git and retained as a GitHub Actions artifact, avoiding self-referential tree drift.
- Compliance inventory integrity remains enforced after workflow and package-script changes.

## Data Correctness

- The positive fixture is produced by the real deterministic eight-station runtime.
- Every platform variant must map exactly the supported claim set.
- Every mapped claim requires visible source and locator text.
- Verified status, reviewer identity, supported state and actor sets must agree.
- Runtime risk output must agree with independent semantic evaluation.

## Failure and Recovery

- A failed case makes the gate non-zero and blocks CI.
- Unknown schemas, unexpected keys, unsupported mutations and malformed reports fail before acceptance.
- Graph Harness recorded the critic failure, invalidated only `INC-010`, advanced it to revision 1 and preserved every unrelated node.
- The fixer returned the node to `running` after localized compliance and exact-tree repairs.

## Operations and Evidence

- `npm run validate:semantic-evals` runs after installation of the exact wheel.
- `scripts/verify-python-locks.sh` runs the same gate and is strict unless development explicitly opts into dirty mode.
- GitHub Actions uploads `artifacts/semantic-evals/generated` for 30 days.
- No runtime service, database migration, provider configuration, cloud resource or secret is introduced.

## Release Boundary

This increment improves release evidence but does not authorize release, deployment, political publication, provider execution or legal conclusions. Exact-head CI must pass before Graph Harness `close-gate` can pass.
