# INC-039 Acceptance Checklist

- [ ] Default Terraform plan creates zero resources.
- [ ] Cloud SQL cannot enable without reviewed estimate, approval and sufficient cap.
- [ ] Cloud SQL is PostgreSQL 15, zonal, backed up, PITR-enabled and storage-bounded.
- [ ] Cloud Run cannot enable without Cloud SQL, immutable digest, schema receipt and pinned minimal secrets.
- [ ] Cloud Run mounts the managed Cloud SQL socket and uses the runtime service account.
- [ ] Runtime IAM contains `roles/cloudsql.client` and no database-admin role.
- [ ] Disabled social/provider capabilities do not require provider credentials.
- [ ] Effects remain false, min instances zero and max instances at most two.
- [ ] Terraform fmt/validate/test and repository verifier pass.
- [ ] No external resource, image, secret version, traffic, provider effect or spend occurs.
