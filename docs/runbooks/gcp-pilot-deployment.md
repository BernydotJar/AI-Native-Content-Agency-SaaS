# GCP pilot deployment

## Current decision

**DENY_APPLY.** The authorized ceiling is **4,000 COP per month**. The reviewed
`db-f1-micro` compute lower bound is **24,609 COP per month** before SSD storage,
backup storage, Cloud Run usage, Artifact Registry, Secret Manager operations, taxes,
or exchange-rate movement. The repository may validate configuration, but operators
must not create Cloud SQL, publish an image, add secret versions, expose ingress, or
apply a deployment under the current cap.

The machine-readable evidence is `infra/gcp/pilot-cost-review.json`. Any later cost
review must replace it with current source evidence, compute an all-in estimate, obtain
an explicit cap that covers that estimate, and bind the approval through
`cost_review_receipt_sha256`.

## Authority boundaries

Terraform models the pilot but does not create database users, passwords, roles,
grants, secret payloads, or image bytes. The service always starts with
`AGENCY_POSTGRES_SCHEMA_MODE=validate`; it never acquires migration authority at
startup.

The following are separate effectful gates:

1. raising the authorized monthly cap after a fresh all-in cost review;
2. authenticating the exact GCP project and billing account;
3. approving a saved Terraform plan;
4. applying Cloud SQL and its database container;
5. creating migration/runtime roles and applying schema v9;
6. adding numeric Secret Manager versions;
7. publishing a linux/amd64 image and pinning its digest;
8. applying Cloud Run and, separately, public invocation;
9. observing staging and accepting or rolling back the revision.

No one gate implies another.

## Validated topology

The plan-ready profile contains:

- one `POSTGRES_15` Cloud SQL instance in `us-central1`;
- `ZONAL` availability and the reviewed minimum shared-core tier;
- 10 GiB PD-SSD with a finite 20 GiB autoresize ceiling;
- automatic backups, seven retained backups, seven days of transaction logs, and PITR;
- deletion protection enabled;
- Cloud SQL connector enforcement required and no authorized direct client networks;
- one application database named `agency`;
- a runtime service account with `roles/cloudsql.client`, not database administration;
- Cloud Run attached through the managed `/cloudsql` Unix socket;
- `min_instance_count=0` and `max_instance_count<=2`;
- all model, provider, social, political, publication, and paid-media effects false.

The deployer has infrastructure administration needed by Terraform. It is not the
application runtime identity.

## Preflight without cloud effects

```bash
python3 scripts/verify-gcp-pilot-readiness.py
terraform -chdir=infra/gcp fmt -check -recursive
terraform -chdir=infra/gcp init -backend=false
terraform -chdir=infra/gcp validate
terraform -chdir=infra/gcp test
```

The current cost evidence intentionally returns `DENY_APPLY`. Passing these commands
means the configuration is internally consistent; it is not permission to deploy.

## Fresh cost review and saved-plan gate

Before any future plan with `enable_cloud_sql=true`:

1. refresh Cloud SQL compute, SSD, backup, egress, Cloud Run, registry and secret costs;
2. use the billing-account currency and a documented exchange rate if conversion is
   required;
3. include expected idle and demonstration traffic;
4. write the all-in estimate and exclusions into reviewed evidence;
5. obtain an authorized cap greater than or equal to the all-in estimate;
6. hash the approved evidence and set `cost_review_receipt_sha256` to that lowercase
   SHA-256;
7. set `reviewed_monthly_cost_estimate_units`,
   `authorized_monthly_cost_cap_units`, and `monthly_budget_units` consistently;
8. create a saved plan and review its exact resources, identities, region and amount.

A Google Cloud budget is an alerting control, not an automatic hard shutdown. The
operator's cap remains a stop condition enforced before apply.

## Database role and schema receipt

After Cloud SQL exists, use a short-lived administrative channel. Do not put the
administrator password in Terraform, Git, chat, command history, or a Cloud Run
revision.

Follow `docs/runbooks/postgresql-schema-rollout.md` to:

1. create distinct migration and runtime roles;
2. initialize or migrate the exact application database to schema v9;
3. apply least-privilege runtime grants;
4. validate the schema through the runtime credential;
5. record the instance connection name, database, schema version, migration tool
   digest, validation result and timestamp without credential material;
6. hash that receipt and set `schema_initialization_receipt_sha256`.

Cloud Run refuses planning without a valid receipt hash, and the receipt hash is stored
as revision metadata. The service remains in `validate` mode.

## Minimal pinned secrets

With all external capabilities disabled, Cloud Run requires exactly these secret
classes:

- `AGENCY_DATABASE_URL`;
- `AGENCY_IDENTITY_CREDENTIALS_JSON`;
- `AGENCY_AUDIT_CHECKPOINT_SIGNING_KEYS_JSON`;
- `AGENCY_AUDIT_CHECKPOINT_ACTIVE_KEY_ID`.

Each reference uses a numeric Secret Manager version; `latest` is rejected. The runtime
service account receives access only to secret containers actually injected into the
revision. X, Instagram, social-token, public-media and provider credentials remain
optional and must not be added merely to satisfy deployment.

The PostgreSQL URL must target the managed Unix socket at the exact Cloud SQL connection
name and use the runtime role. Verify its form out of band without printing its password.

## Immutable image and Cloud Run review

Only a `linux/amd64` Artifact Registry image pinned by `@sha256:` may be supplied.
Before applying Cloud Run, verify:

- image provenance and digest;
- schema and cost receipt hashes;
- four numeric secret versions;
- runtime identity and `roles/cloudsql.client` only;
- scale-to-zero and the two-instance ceiling;
- app login credential separation;
- effects-off environment values;
- public invocation is still false unless separately approved.

Public invocation exposes the application endpoint; application login is not a
substitute for the separate ingress approval.

## Verification and rollback after a future authorized apply

A future staging exercise must verify login, a durable run, Greenlight, audit-chain
continuity, restart persistence, and revision rollback while retaining the same
PostgreSQL database. Record exact revision, image digest, schema version, RTO, health
checks and audit head.

Rollback changes Cloud Run traffic or revision only. Do not restore, replace, downgrade,
or reverse-migrate the database as part of workload rollback. If schema compatibility
is not proven, stop and invoke the database incident procedure instead.
