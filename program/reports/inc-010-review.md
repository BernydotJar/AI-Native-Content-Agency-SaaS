# INC-010 Review — Semantic, Adversarial and Exact-Tree Evaluation

Updated: 2026-07-29
Implementation base: `b726ae5854bb5406b819c815f3acf66d933acf40`
Exact-head repair commit: `ddac3777d933005706f6e5f5d78e52de13a71437`
Exact repaired tree: `1c5276bc46cd6f6da51fa7b9d3b39f3c4a8faab7`
Graph revision: `2`
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

Exact clean-tree repair evidence at `ddac3777d933005706f6e5f5d78e52de13a71437`:

```text
semantic_evals=pass cases=16
semantic_independent_verifier=pass cases=16
source_tree=1c5276bc46cd6f6da51fa7b9d3b39f3c4a8faab7
expected_source_commit=ddac3777d933005706f6e5f5d78e52de13a71437
worktree_dirty=false
external_effects_observed=0
locked-wheel backend tests=333 PASS, 25 PostgreSQL-only skips
frontend tests=58 PASS
Oxlint=0 warnings, 0 errors
TypeScript/Vite production build=PASS
program/graph/compliance/operability=PASS
release_decision=DENY_RELEASE
```

The independent verifier does not import the semantic evaluator. It checks exact report schemas, case/result cardinality, required categories, corpus and evaluator digests, commit/tree binding, canonical findings/metrics, zero effects and tamper negatives.

## Rejected Remote Evidence and Repair

GitHub Actions run `30471479970` passed all eight jobs but is deliberately not accepted as exact-head closure evidence. Its uploaded semantic report named synthetic merge `6b28cf529144a0424a26ebf235ae0ee20d068461` as `source_commit`, not PR head `5d087ed3a1c03c072014ce7faa11a503866ccea6`. Graph Harness recorded a `close-gate` failure and invalidated only `INC-010`.

Revision 2 forces all eight jobs to check out and assert `${{ github.event.pull_request.head.sha || github.sha }}`. The semantic evaluator and independent verifier additionally require `SEMANTIC_EVAL_EXPECTED_COMMIT == HEAD`. A mismatch test fails closed.

## Residual Boundaries

- GitHub Actions exact-head `container`, PostgreSQL, Helm, Terraform, workflow and supply-chain jobs remain the remote arbiter.
- Local production-package execution stopped before build because this workstation does not contain `helm`; no product defect or external mutation occurred.
- Semantic rules are deterministic policy checks, not jurisdiction-specific legal advice or complete human editorial review.
- Manual accessibility, privacy/legal decisions, persistent staging observation and release authorization remain separate blocked nodes.

## Revision 3 review repair

The prior close evidence was invalidated after two valid PR review findings. The repair restores the original broad prohibited-claim coverage and upgrades the versioned corpus so every result is bound to exact finding codes, finding count and metrics. Tampered codes, counts and metrics are now negative tests. Local installed-wheel and repository gates pass; remote exact-head evidence remains pending.
