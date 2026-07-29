# INC-010 Design — Semantic, Adversarial and Exact-Tree Evaluation

## Architecture

1. `agency_runtime.semantic_evals` owns strict typed evaluation of a bounded artifact bundle.
2. `program/evals/semantic-adversarial-corpus.json` owns versioned positive and adversarial cases.
3. `scripts/verify-semantic-evals.py` creates real runtime artifacts, applies declared bounded mutations, evaluates every case and writes the canonical report.
4. `scripts/verify-semantic-evals-independent.py` does not import the evaluator. It independently checks corpus expectations, report hashes, exact commit/tree binding, case cardinality and absence of skipped or unknown cases.
5. Unit tests mutate corpus and artifact fields to prove fail-closed behavior.
6. The production-readiness workflow runs the evaluator before the broad test suite and uploads no sensitive content.

## Data Boundary

The evaluator receives only deterministic artifact content and reviewer identifiers already present in local test fixtures. It records rule identifiers and bounded field paths, not campaign secrets or credentials. Reports contain no provider responses, tokens or network data.

## Localized Graph Repair

`INC-010` previously depended on `INC-008`, whose remaining work is explicitly manual accessibility review. Semantic-eval implementation does not consume that approval. The technical dependency is changed to `INC-021`, while `INC-008` remains a separate blocked release node. This allows safe engineering completion without claiming accessibility approval.

## Failure Behavior

- Unknown schema, unexpected keys, invalid identifiers, duplicate claims, unbounded text or unsupported mutations fail the command.
- A case whose actual result differs from its expected result fails the command.
- An exact-tree mismatch fails independent verification.
- A failing CI gate records Graph Harness failure and localized repair for `INC-010` only.

## Files

- `backend/agency_runtime/semantic_evals.py`
- `backend/tests/test_semantic_evals.py`
- `program/evals/semantic-adversarial-corpus.json`
- `scripts/verify-semantic-evals.py`
- `scripts/verify-semantic-evals-independent.py`
- `.github/workflows/production-readiness.yml`
- `package.json`
- `program/**`
- `specs/010-semantic-adversarial-evals/**`
