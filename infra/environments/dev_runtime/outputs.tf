output "environment" {
  value = "dev"
}

output "project_id" {
  value = var.project_id
}

output "bootstrap_project_id" {
  value = data.terraform_remote_state.foundation.outputs.bootstrap_project_id
}

output "region" {
  value = data.terraform_remote_state.foundation.outputs.region
}

output "foundation_project_provenance_sha256" {
  value = data.terraform_remote_state.foundation.outputs.project_provenance_sha256
}

output "github_repository_owner_id" {
  value = data.terraform_remote_state.foundation.outputs.github_repository_owner_id
}

output "github_repository_id" {
  value = data.terraform_remote_state.foundation.outputs.github_repository_id
}

output "cloud_run_service_name" {
  value = module.cloud_run.service_name
}

output "cloud_run_service_uri" {
  value = module.cloud_run.service_uri
}

output "migration_job_name" {
  value = module.cloud_run.migration_job_name
}

output "cloud_run_invoker_iam_disabled" {
  value = module.cloud_run.invoker_iam_disabled
}

output "runtime_service_account_email" {
  value = data.terraform_remote_state.foundation.outputs.runtime_service_account_email
}

output "foundation_artifact_repository" {
  value = data.terraform_remote_state.foundation.outputs.artifact_repository
}

output "foundation_budget_enabled" {
  value = data.terraform_remote_state.foundation.outputs.budget_enabled
}

output "foundation_notification_channel_ids" {
  value = data.terraform_remote_state.foundation.outputs.notification_channel_ids
}

output "foundation_notification_channel_provenance_sha256" {
  value = data.terraform_remote_state.foundation.outputs.notification_channel_provenance_sha256
}

output "cloud_sql_connection_name" {
  value = data.terraform_remote_state.foundation.outputs.cloud_sql_connection_name
}
