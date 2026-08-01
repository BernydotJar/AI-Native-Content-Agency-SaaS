# INC-039 Requirements — GCP Pilot Deployment Readiness

## Goal

Make the existing GCP foundation capable of producing a reviewed Cloud SQL + Cloud Run pilot plan without creating resources, publishing images, adding secret versions, or exceeding the operator's hard monthly cost ceiling.

## Requirements

1. Keep all deployment resources disabled by default and preserve a zero-resource default plan.
2. Model one zonal PostgreSQL 15 Cloud SQL instance with automatic backups, point-in-time recovery, bounded storage growth, deletion protection, no authorized public networks, and an exact database name.
3. Connect Cloud Run to Cloud SQL through the platform Unix-socket integration and grant only `roles/cloudsql.client` to the runtime service account.
4. Keep migration credentials out of the Cloud Run service. Require an explicit, separately executed schema/role initialization receipt before `enable_cloud_run=true` can plan.
5. Require an immutable Artifact Registry digest and pinned numeric Secret Manager versions for the database URL, individual identity credentials, audit checkpoint signing keyring, and active audit key ID.
6. Do not require X, Instagram, social-token or media-signing credentials while those capabilities remain disabled. Optional capability credentials may still be supplied as pinned secrets.
7. Require a reviewed monthly estimate, explicit cost-review approval, and an authorized monthly cap before Cloud SQL can be enabled. Reject any estimate above the cap.
8. Preserve `min_instance_count=0`, `max_instance_count<=2`, app login, and all model/social/political/paid-effect switches false for the pilot profile.
9. Add executable positive and negative Terraform tests plus a repository-level fail-closed verifier.
10. Record that the current 4,000 COP/month cap cannot authorize the reviewed minimum Cloud SQL estimate; no apply, image publication, secret mutation, or spend may occur in this increment.

## External boundary

This increment proves deployment configuration only. `INC-006` continues to own real staging workload execution and runtime observation. Cloud resource creation, database role/schema mutation, secret versions, image publication, public ingress, and traffic remain separate effectful gates.
