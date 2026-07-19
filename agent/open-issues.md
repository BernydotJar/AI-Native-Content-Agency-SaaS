# Open Issues

## Mandatory closure

- TASK-CRITIQUE-001: issue the independent read-only cloud critique for the exact tree.
- TASK-SEC-REVIEW-001: re-audit the repaired Python lock and final application/platform tree.
- EVAL-INC-001: issue an independent production-readiness and apply recommendation.
- GOV-007: create focused commits, push the feature branch, create a draft PR and update issue `#1` after the gates settle.
- Interactive visual QA: the required in-app browser runtime exposed zero browser instances; rerun when that runtime is available.

## Externally blocked GCP work

- GCP-002 through GCP-011: real permission/policy/quota/cost preflight, hierarchy selection, remote state, immutable registry image, saved plans, exact dev apply, post-apply denial/smoke and second no-change plan.
- Resume only when at least one accessible billing account reports `open=True`, then explicitly select the intended parent/project/region and run the full preflight. Never inherit or mutate `meridian-hr-crm`.

No staging/production apply, external publication, Meta Ads activation or spend is authorized. Current recommendation is `DENY_APPLY`.
