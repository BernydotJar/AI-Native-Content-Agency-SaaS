# INC-010 Requirements — Semantic, Adversarial and Exact-Tree Evaluation

## Mode

SHIP.

## Problem

The repository has deterministic political-content checks and many focused negative tests, but it lacks one versioned semantic/adversarial corpus, one fail-closed evaluator and one exact-tree evidence artifact. Traceability rows EVAL-003, EVAL-004 and EVAL-005 therefore remain incomplete or missing.

## Requirements

- Evaluate the real deterministic campaign artifacts produced by `agency_runtime`; do not use an unrelated toy output format.
- Verify claim-map integrity, verified-reviewer provenance, visible source and locator citations, disclosure presence and reviewer separation.
- Detect bounded instruction-injection patterns in untrusted campaign and evidence text in English and Spanish.
- Detect unsupported guarantees, fabricated unanimity, unsafe legal-compliance assertions and unsupported numeric claims.
- Treat malformed, oversized, duplicate, unknown and inconsistent inputs as failures.
- Keep evaluation deterministic, offline and free of model, provider, browser, credential, network, publication and spending authority.
- Persist a machine-readable report containing the exact source commit, Git tree, corpus digest, evaluator digest and per-case result.
- Require a distinct verifier implementation to compare the generated report with the corpus expectations and exact Git tree.
- Integrate the gate into the existing production-readiness workflow.
- Preserve `DENY_RELEASE`, `DENY_APPLY` and every existing human/external gate.

## Acceptance Criteria

- A grounded political fixture passes.
- Missing or unknown claim mappings fail.
- Unverified claims and missing reviewer identities fail.
- Hidden or altered citations fail.
- Pending legal review, missing disclosure and non-separated reviewers fail.
- English and Spanish instruction-injection fixtures fail.
- Guarantee, unanimity, universal-legal-compliance and unsupported-number fixtures fail.
- Corpus and report mutation tests fail closed.
- Repeated runs produce byte-identical semantic payloads except for the exact commit/tree fields.
- Exact-head CI passes the semantic evaluator and independent verifier.
- EVAL-003, EVAL-004 and EVAL-005 receive traceable evidence before the node closes.

## Non-Goals

- No probabilistic model-as-judge.
- No external benchmark download or network access.
- No jurisdiction-specific legal conclusion.
- No real campaign approval, publication, provider execution, deployment or release.
- No replacement of the existing Graph Harness runtime.
