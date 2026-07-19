# Open Issues

Updated: 2026-07-19T19:08:21Z

## Executable before release review

- Keep every effectful provider disabled. Matching-key ownership and bounded waiting now pass repeated and real-PostgreSQL tests, but live adapters still require provider-specific auth, receipt, retry, revocation and failure semantics.
- Finish the root-owned executable eval result lifecycle. The catalog/harness repair and real PostgreSQL/browser gates pass, but `agent/eval-results.json` is intentionally stale until source documentation/governance is committed and the full final-tree harness runs.
- Commit and push the repaired tree. GitHub Actions run `29672994585` is green evidence for `34c3489`, not for the current uncommitted increment.
- Main now requires the exact four CI jobs, strict updates and protected review; force-push/deletion are disabled. Prove the current repair with exact-tree CI and keep the draft unmerged until a non-self review is available.
- `dev-build`, `dev-plan` and `dev` now accept protected branches; `dev` prevents self-review. Add a distinct eligible actor/reviewer because the sole collaborator cannot approve their own dispatch; free-text attestation is insufficient.
- Configure the twelve non-secret deployment variables only after real bootstrap/foundation outputs exist. Keep the exact apply attestation separately protected in `dev`; do not invent placeholder cloud identifiers.
- Run `EVAL-INC-004` after source commit, fresh harness output and exact current-tree CI. Role-separated local review cannot replace a genuinely distinct GitHub reviewer or cloud-plan evaluator. Until then the release result is `DENY_RELEASE`.
- Repeat manual visual, responsive and accessibility inspection when the required in-app browser exposes an instance. Live Playwright validates behavior/transport but does not close manual visual QA.

## Externally blocked GCP work

- Six visible billing accounts remain closed. No real target plan or paid resource may be created while no intended account reports `open=True`.
- Candidate project `ai-native-content-agency-saas` exists but is billing-disabled and has unknown creation provenance, parent and intended role. It is not authorized or Terraform-adopted. Explicitly decide whether it is rejected, imported as bootstrap or imported as dev, then choose a distinct second project.
- Select and authorize the parent/no-organization exception and region. Run granular permissions, effective policy, quota, regional tier and cost preflight; an Owner role alone is insufficient evidence.
- Produce saved bootstrap, foundation and runtime plans plus JSON only after eligibility. Inspect create/update/replace/destroy, IAM, public access, secrets, region, labels, provenance and monthly cost.
- Cloud critique, security review and a different independent evaluator must return `ALLOW_DEV_APPLY` for the exact plan/tree/image/attestation before any apply.
- Post-apply IAM denials, health, migrations, PostgreSQL connectivity, artifacts, logs, labels, budget delivery, smoke, measured cost and a second no-change plan cannot exist before an authorized apply.

## Exact cloud resume condition

An accessible intended billing account reports `open=True`; the parent, region, distinct bootstrap/dev IDs and candidate create/adopt decision are explicitly authorized; granular preflight succeeds; and a real saved plan can be generated without using or mutating the unrelated configured project `meridian-hr-crm`.

No staging/production apply, public ingress, billing change, deletion, external publication, Meta Ads activation, advertising spend, merge or release is authorized. Current cloud recommendation is `DENY_APPLY`.
