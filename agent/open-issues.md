# Open Issues

Updated: 2026-07-19T03:59:19Z

## Local review limitations

- Independent review gate: collaboration credits were exhausted, so the final producer/critic/evaluator audit is role-separated but sequential. A different human or independent agent must review the draft PR before merge and must independently approve any future exact cloud plan.
- Interactive visual QA: the required in-app browser runtime exposed zero browser instances. Rerun browser-level inspection when that runtime is available.

All executable local application, container, dependency, migration, contract and CI gates are green. No local CRITICAL or HIGH implementation finding remains open.

## Externally blocked GCP work

- GCP-002 through GCP-011: real permission/policy/quota/cost preflight, hierarchy selection, remote state, immutable registry image, saved plans, exact dev apply, post-apply denial/smoke and second no-change plan.
- Exact resume condition: make at least one intended billing account visible with `open=True`, explicitly authorize the intended parent/project/region, and provide a different independent reviewer for the resulting saved plan.
- Never inherit or mutate `meridian-hr-crm`.

No staging/production apply, external publication, Meta Ads activation, spend, merge or release is authorized. Current cloud recommendation is `DENY_APPLY`.
