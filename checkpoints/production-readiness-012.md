# Production readiness checkpoint 012

- **Date:** 2026-07-21
- **Branch:** `agent/production-readiness`
- **Pull request:** `#3`
- **Increment:** CI gate remediation after authenticated GitHub verification
- **Production deployment or publication:** none

## Acceptance decision

The CI remediation increment is accepted locally. Each failure from workflow run `29845294648` was reproduced, classified as a technical defect, corrected, and verified through the same repository entrypoints used by CI.

## Remediated defects

### Workflow lint

- Cause: the installer mapped `x86_64` to a nonexistent upstream asset and pinned an obsolete release.
- Fix: install checksum-verified `actionlint 1.7.12` and map `x86_64`/`amd64` to the upstream `amd64` archive.

### PostgreSQL shared state

- Cause: `initdb` created the default CI operating-system role while the verifier connected as the configured runtime user.
- Fix: initialize PostgreSQL with `--username="$POSTGRES_RUN_USER"`.
- Additional corrections discovered by full-gate execution:
  - dry-run migration output now reports `status=validated`;
  - replay protection asserts the migrator's current empty-target error contract.

### Supply-chain license policy

- Cause: Syft surfaced three permissive licenses using non-SPDX or ambiguous metadata strings.
- Fix: add exact package/version/reported-license mappings to reviewed normalized licenses, require a recorded reason, reject denied or unapproved normalized licenses, and fail stale mappings.

## Verification evidence

```text
gh_auth=pass
pull_request_draft=pass
actionlint_version=1.7.12
actionlint_checksum=pass
actionlint_workflow_validation=pass
supply_chain_policy_tests=7/7 pass
failing_ci_sbom_policy_recheck=pass
license_policy_errors=0
reviewed_license_mappings_used=3
postgresql_backend_tests=51/51 pass
postgresql_version=15.18
postgresql_role_initialization=pass
migration_dry_run=pass
migration_apply=pass
migration_counts=pass
migration_failure_totals=pass
migration_replay_guard=pass
wheel_install=pass
pip_check=pass
cleanup=pass
git_diff_check=pass
```

## External action boundary

Normal feature-branch push and draft PR maintenance are authorized. No merge, protected-branch mutation, production deployment, package publication, image publication, external infrastructure creation, spending, force-push, or destructive migration was performed.
