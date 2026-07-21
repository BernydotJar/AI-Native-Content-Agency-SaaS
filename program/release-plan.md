# Release Plan

Current target version: `0.7.0`
Current recommendation: `DENY_RELEASE`

## Candidate release boundary

Version `0.7.0` may become a reviewable sandbox release only after all deterministic local/CI gates pass and documentation no longer overstates cloud, integration, backup, alert, or accessibility evidence. It is not a production release merely because its image, chart, Terraform, and PR are green.

## Required release evidence

- version consistency across npm, Python, API, metrics, OCI, and Helm;
- frontend lint/tests/build;
- hash-locked wheel build, `pip check`, complete backend tests;
- SQLite and PostgreSQL runtime checks;
- backup and restore drills with verified manifests;
- tenant isolation, RBAC, session/CSRF, rate-limit, concurrency, and denial tests;
- container runtime smoke as non-root;
- Helm/Terraform validation with scope limitations stated;
- supply-chain SBOM, vulnerability, license, provenance, and signature gates;
- program traceability and completion audit validation;
- zero open CRITICAL/HIGH code findings for the release scope;
- independent review of exact commit and evidence.

## Rollback compatibility

- Application rollback must use an immutable prior image digest and prove compatibility with the active schema.
- SQLite rollback requires a verified pre-change backup and an explicit destructive-data human gate before replacement.
- PostgreSQL rollback is forward-repair preferred; restoring a database requires an approved recovery point, empty/isolated target validation, and human authorization.
- No automatic schema downgrade, Terraform destroy, public ingress, or credential change is included.

## Human gates

- merge PR;
- publish external image/package or release;
- choose cloud account/project/region and incur cost;
- apply infrastructure outside the local ephemeral sandbox;
- execute destructive restore or migration against persistent data;
- enable real publishing, media generation, browser automation, ads, or spend;
- approve legal/privacy decisions requiring accountable human review.
