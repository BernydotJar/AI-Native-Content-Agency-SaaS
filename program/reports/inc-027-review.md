# INC-027 Role-Separated Review

Date: 2026-07-30
Graph revision: 3
Decision: PASS for local review; exact-head CI pending.

## Producer

Implemented a durable authenticated request quota at the existing principal boundary. The producer added domain-separated SHA-256 principal and tenant buckets, atomic SQLite/PostgreSQL counters, schema v8, safe 429 responses, `Retry-After`, low-cardinality metrics and non-secret local/Helm/Terraform configuration.

## Critic / Red Team

The critic attempted:

- repeated permission denials to amplify the audit ledger;
- bearer/session switching for one subject;
- multiple principals under one tenant;
- partial multi-bucket consumption;
- malformed and dependency-invalid configuration;
- replica splitting;
- migration, backup and restore drift;
- tenant/subject disclosure through storage and metrics.

Results: request 11 is rejected before denial auditing when the limit is 10; audit rows remain exactly 10; bearer/session share one principal bucket; the tenant bucket spans principals; atomic rejection leaves both counters unchanged; only bucket digests are stored; metric labels are bounded to `allowed|rate_limited`.

## Fixer

Three failures were localized by Graph Harness:

1. PostgreSQL gate found stale schema-v7 restoration and 27-node assertions. Repaired only those contracts; revision advanced to 1.
2. New PostgreSQL test used a mapping API on a raw DB-API connection. Repaired the test cursor; revision advanced to 2.
3. Installed-image verifier expected the old exact health document. Repaired its explicit quota health/readiness assertions; revision advanced to 3.

No unrelated node or evidence was invalidated.

## Security and Privacy Reviewer

- Raw tenant, subject, session, key and API-key values do not enter quota rows or metric labels.
- Quota consumption occurs only after successful authentication and before CSRF/authorization denial auditing.
- A rejection writes no recursive denial event.
- PostgreSQL locks bucket digests in sorted order and checks all buckets before any upsert.
- One compact row per active bucket bounds storage growth; expired rows are cleaned during consumption.
- Configuration values are non-secret and validated consistently across runtime, runner, Helm and Terraform.

## Independent Verifier

- focused SQLite/API quota tests: 8 PASS;
- locked wheel: 357 PASS, 26 PostgreSQL-only skips;
- PostgreSQL 15.18: 356 PASS, schema v8, migration, least privilege, backup/restore PASS;
- non-root OCI package: PASS; real provider HTTP false;
- K3s/Helm/Terraform plan/apply/destroy: PASS; no secret values in Terraform state;
- frontend: 58 PASS; lint and production build PASS;
- program, graph, governance, compliance and operability validators: PASS.

## Limitations

No production traffic profile, production rollout, persistent staging observation or quota tuning occurred. Exact-head CI and retained remote evidence are required before node closure. Release, deployment and effect authority remain denied.

## Revision 4 supply-chain repair

A refreshed vulnerability database classified `CVE-2026-11940` and `CVE-2026-11972` as fixable because Python 3.15.0b4 appeared. The product remains on stable Python 3.13.14: 3.15.0b4 is a pre-release outside the supported runtime line. Both findings require attacker-controlled tar processing, while the runtime imports no `tarfile`, accepts no tar archive and exposes no extraction path. Exact baseline exceptions expire on 2026-08-21 and a source-level test fails if any tarfile import or extraction call is introduced. A stable compatible image or any new tar surface requires immediate reevaluation.

## Post-ready review repair — revision 5

After PR #36 was retargeted to the squashed `main` ancestry, the automated review found two valid gaps on the historical head:

1. successful `POST /api/v1/sessions` authentication did not consume the authenticated-request quota, allowing repeated durable session/audit creation outside the principal and tenant buckets;
2. `require_principal` published tenant identity to `request.state` before quota consumption, so the structured completion log for a quota-rejected request could contain the raw tenant ID.

The localized repair introduces one shared quota-consumption helper and a separate identity-publication helper. Bearer, browser-session and session-creation authentication now consume the same durable principal/tenant buckets before identity is made visible to request logging. A valid key with a mismatched username is also charged before returning the generic authentication failure. Regression coverage proves that session creation is the tenth shared request and that the following 429 completion log contains no `tenant_id`, tenant name or subject identifier.

Graph Harness invalidated only `INC-027`, advanced it to revision 5 and preserved every unrelated node. No provider, deployment, secret, cloud or release effect was enabled.
