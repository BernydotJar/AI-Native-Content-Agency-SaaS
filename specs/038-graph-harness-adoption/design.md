# INC-038 Design — Graph Harness SDLC Adoption

## Approach

Pin Graph Harness SDLC as `vendor/graph-harness-sdlc`. A repository-owned adapter projects existing JSON-compatible task ledgers into `graph-harness.project.v1`; the canonical framework validates and derives `graph-harness.state.v1` from the append-only event ledger.

## Files You May Touch

- `.gitmodules`
- `vendor/graph-harness-sdlc` gitlink
- `.github/workflows/production-readiness.yml`
- `package.json`, `package-lock.json`
- `scripts/verify_graph_harness.py`
- `backend/tests/test_graph_harness_adapter.py`
- `program/**`
- `specs/038-graph-harness-adoption/**`
- `README.md`, `AGENTS.md`, `RTK.md`

## Files You Must Not Touch

- application runtime source under `backend/agency_runtime/**`
- product UI under `src/**`
- infrastructure resource definitions
- secrets and `.env.local`

## Data Contracts

- `program/task-ledger.yaml` and `program/task-graph.yaml`: domain authority.
- `program/graph-harness.project.json`: deterministic generated projection.
- `program/graph-harness.events.jsonl`: append-only execution authority.
- `program/graph-harness.state.json`: deterministic derived projection.
- `program/graph-harness.lock.json`: exact framework repository and revision.

## Failure Behavior

Any mismatch fails CI. Repair uses framework revision increments and descendant invalidation; unaffected evidence remains valid.

## Verification

- `python3 scripts/validate-program-state.py`
- `python3 scripts/verify_graph_harness.py`
- adapter unit tests
- workflow lint
- existing production-readiness workflow
