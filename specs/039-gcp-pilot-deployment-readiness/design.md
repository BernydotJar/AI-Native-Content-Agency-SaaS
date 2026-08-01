# INC-039 Design — GCP Pilot Deployment Readiness

## Resource topology

The pilot topology is one zonal PostgreSQL 15 Cloud SQL instance and one Cloud Run v2 service. Cloud Run reaches PostgreSQL through the managed Cloud SQL Unix socket mounted at `/cloudsql`; the database exposes no authorized public client network. The runtime service account receives only `roles/cloudsql.client` plus the existing per-secret access grants.

Terraform creates the instance and application database but never creates database passwords, users, roles, grants, or secret payloads. Those values and mutations stay outside Terraform state.

## Schema authority

Long-running Cloud Run starts with `AGENCY_POSTGRES_SCHEMA_MODE=validate`. A boolean receipt input records that the separately authorized migration procedure created the migration/runtime roles, initialized the exact schema, applied least-privilege grants, and validated through the runtime credential. Terraform refuses to plan Cloud Run without this receipt; it never changes startup to `initialize`.

## Cost authority

`enable_cloud_sql` requires:

- an explicit cost-review approval;
- a positive reviewed monthly estimate in billing-account currency;
- a positive authorized monthly cap;
- the estimate not exceeding the cap;
- the alerting budget not exceeding the same cap.

This is a planning interlock, not a cloud-enforced hard shutdown. The current reviewed minimum exceeds 4,000 COP/month, so the real environment must remain disabled.

## Secret contract

Always-required pilot secrets are the runtime database URL, individual identity credentials, audit checkpoint signing keyring, and active key ID. Social OAuth, provider, and public-media credentials are optional while their corresponding capabilities remain disabled. Every injected secret version is numeric; `latest` is rejected.

## Verification

Terraform tests prove the zero-resource default, cost-cap denial, immutable image and migration-receipt denial, bounded Cloud SQL topology, Cloud Run socket attachment, least privilege, and the effects-off minimal-secret profile. A Python verifier inspects the HCL contract so CI fails if cost, secret, effect, or persistence guards are removed.
