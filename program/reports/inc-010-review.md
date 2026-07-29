# INC-010 Review — Semantic, Adversarial and Exact-Tree Evaluation

Updated: 2026-07-29  
Implementation commit: `b726ae5854bb5406b819c815f3acf66d933acf40`  
Exact implementation tree: `d842e2cd4e56fb7546e28272c217cd8819a74c8a`  
Graph revision: `1`  
Decision: `PASS_FOR_REVIEW`; exact-head CI and closure remain pending.

## Producer

Implemented a deterministic offline evaluation layer over the real `agency_runtime` political campaign artifacts:

- strict typed bundle validation with bounded text, exact fields and unique claim IDs;
- verified claim-map, source, locator and disclosure checks;
- fact, legal, producer and Greenlight reviewer separation;
- English and Spanish instruction-injection detection;
- unsupported guarantee, unanimity, universal legal-compliance and numeric-claim checks;
- runtime Critique Agent integration that changes `publication_eligible` to false;
- a versioned 16-case adversarial corpus;
- an implementation-independent report verifier;
- strict commit/tree, corpus digest and evaluator digest binding;
- CI artifact retention for the machine-readable report;
- no model-as-judge, network call, credential, provider, publication or spend authority.

## Critic / Red Team

The critic found and closed two implementation-slice findings:

| Finding | Severity | Resolution |
|---|---:|---|
| Workflow/package changes invalidated reviewed compliance hashes. | HIGH integrity | Updated only the reviewed workflow/package evidence digests; compliance again passes with `DENY_RELEASE`. |
| The locked verifier permitted dirty-tree evaluation by default. | HIGH evidence | Dirty mode is now explicit through `SEMANTIC_EVAL_ALLOW_DIRTY=1`; CI and normal execution remain strict. |

Additional negative coverage proves rejection of unknown and missing claim mappings, unverified claims, hidden citations, missing legal review/disclosure, reviewer conflicts, instruction injection, unsupported overclaims, unsupported numbers, external authority and manipulated reports.

Open CRITICAL/HIGH findings in the INC-010 slice: **0**.

## Independent Verification

Exact clean-tree evidence at `b726ae5854bb5406b819c815f3acf66d933acf40`:

```text
semantic_evals=pass cases=16
semantic_independent_verifier=pass cases=16
source_tree=d842e2cd4e56fb7546e28272c217cd8819a74c8a
worktree_dirty=false
external_effects_observed=0
locked-wheel backend tests=332 PASS, 25 PostgreSQL-only skips
frontend tests=58 PASS
Oxlint=0 warnings, 0 errors
TypeScript/Vite production build=PASS
program/graph/compliance/operability=PASS
release_decision=DENY_RELEASE
```

The independent verifier does not import the semantic evaluator. It checks exact report schemas, case/result cardinality, required categories, corpus and evaluator digests, commit/tree binding, canonical findings/metrics, zero effects and tamper negatives.

## Residual Boundaries

- GitHub Actions exact-head `container`, PostgreSQL, Helm, Terraform, workflow and supply-chain jobs remain the remote arbiter.
- Local production-package execution stopped before build because this workstation does not contain `helm`; no product defect or external mutation occurred.
- Semantic rules are deterministic policy checks, not jurisdiction-specific legal advice or complete human editorial review.
- Manual accessibility, privacy/legal decisions, persistent staging observation and release authorization remain separate blocked nodes.
