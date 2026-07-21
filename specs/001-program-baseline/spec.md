# 001 — Trustworthy Program Baseline and Version Contract

Status: done
Owner: Orchestrator

## Problem

The repository has strong local implementation evidence but no current `program/` source of truth, a stale frontend version, contradictory documentation, and two divergent production-foundation PRs. CI green cannot answer whether the product is deployed, operable, accessible, or globally production-ready.

## Purpose

Create an auditable operational baseline that fails closed when required program artifacts, evidence, statuses, task dependencies, or product versions drift.

## Actors and journeys

- **Operator:** reads one current state document and knows what is runnable and what remains sandboxed.
- **Reviewer:** maps every global requirement to evidence and identifies open CRITICAL/HIGH findings.
- **Release reviewer:** verifies one exact commit, version, PR, CI, and human gates without trusting historical claims.
- **Maintainer:** changes version or program state and receives a deterministic validation failure when surfaces disagree.

## Functional requirements

1. Create the required persistent program artifacts and a completion audit.
2. Inventory all global Definition-of-Done domains in a traceability CSV.
3. Record PR #2 as a parallel donor branch and PR #3 as the selected runtime branch.
4. Normalize npm, Python, FastAPI, metrics, OCI, and Helm version to `0.7.0`.
5. Expose runtime version through health/readiness and metrics.
6. Add a stdlib-only validator for required files, JSON/JSONL/CSV schemas, task graph integrity, status vocabulary, traceability uniqueness, and version consistency.
7. Run that validator in local tests and GitHub Actions.
8. Repair README claims that contradict the selected runtime or deployment evidence.

## Non-functional requirements

- no network access is required for validation;
- validation completes in under five seconds on the repository;
- errors name the exact file and invariant;
- validator uses only Python standard library;
- generated state is deterministic and UTF-8;
- no secret, token, cloud identifier, or personal path is recorded.

## Invariants

- every task dependency references an existing task and the graph is acyclic;
- every traceability row uses an allowed completion classification;
- requirement IDs are unique;
- every open CRITICAL/HIGH finding has an owner;
- all version surfaces equal the canonical runtime version;
- `program/current-state.md` cannot claim GCP deployed without runtime evidence;
- human gates remain explicit.

## States and failures

- **valid:** all artifacts parse and invariants pass;
- **invalid schema:** malformed JSON/JSONL/CSV or missing fields;
- **drift:** version or requirement evidence mismatch;
- **conflict:** duplicate requirement/task IDs or cyclic dependencies;
- **stale:** current-state source commit is older than the exact release candidate; reported as a release blocker, not silently accepted.

## Security, privacy, tenant and accessibility boundaries

This increment does not process customer content or tenant data. Program evidence must not include credentials, raw tokens, secrets, personal filesystem paths, or campaign payloads. Documentation remains accessible Markdown with logical headings and plain-language status vocabulary.

## Acceptance criteria

- `python3 scripts/validate-program-state.py` exits 0;
- mutation tests prove missing files, duplicate IDs, cycles, invalid statuses, and version drift fail;
- npm lint/tests/build pass;
- locked Python wheel/tests pass;
- README no longer contradicts PostgreSQL/frontend transport/cloud status;
- `git diff --check` passes;
- exact files/evidence are recorded in program state.

## Out of scope

- merging either PR;
- GCP plan/apply or any external infrastructure;
- production deployment;
- replacing the selected backend;
- activating external integrations.
