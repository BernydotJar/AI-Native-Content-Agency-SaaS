output "project_id" {
  value = var.project_id
}

output "region" {
  value = var.region
}

output "project_provisioning_mode" {
  value = var.project_provisioning_mode
}

output "project_provenance_sha256" {
  description = "Digest of the versioned create/adopt decision consumed by downstream review."
  value       = sha256(jsonencode(local.project_provenance))
}

output "state_bucket_name" {
  value = google_storage_bucket.terraform_state.name
}

output "workload_identity_providers" {
  value = module.github_wif.provider_names
}

output "github_service_account_emails" {
  value = module.github_wif.service_account_emails
}

output "github_attribute_condition" {
  value = module.github_wif.attribute_condition
}

output "github_attribute_mapping" {
  value = module.github_wif.attribute_mapping
}

output "github_workflow_ref" {
  value = module.github_wif.workflow_ref
}

output "github_immutable_repository_identity" {
  value = module.github_wif.immutable_repository_identity
}

output "initial_backend_migration_command" {
  description = "Run only after the bucket exists and the saved bootstrap plan passed independent review."
  value       = "terraform init -migrate-state -backend-config=bucket=${google_storage_bucket.terraform_state.name} -backend-config=prefix=bootstrap"
}
