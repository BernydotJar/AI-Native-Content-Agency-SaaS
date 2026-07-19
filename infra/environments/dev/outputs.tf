output "environment" {
  value = local.environment
}

output "project_id" {
  value = var.project_id
}

output "bootstrap_project_id" {
  value = var.bootstrap_project_id
}

output "region" {
  value = var.region
}

output "project_provisioning_mode" {
  value = var.project_provisioning_mode
}

output "project_provenance_sha256" {
  description = "Digest of the reviewed project create/adopt provenance."
  value       = sha256(jsonencode(local.project_provenance))
}

output "github_repository_owner_id" {
  value = var.github_repository_owner_id
}

output "github_repository_id" {
  value = var.github_repository_id
}

output "project_number" {
  value = data.google_project.target.number
}

output "artifact_repository" {
  value = module.artifact_registry.docker_repository
}

output "runtime_service_account_email" {
  value = google_service_account.runtime.email
}

output "cloud_sql_connection_name" {
  value = module.cloud_sql.connection_name
}

output "database_name" {
  value = module.cloud_sql.database_name
}

output "database_user" {
  value = module.cloud_sql.iam_database_user
}

output "runtime_plan_service_account_email" {
  value = var.runtime_plan_service_account_email
}

output "runtime_deployer_service_account_email" {
  value = var.runtime_deployer_service_account_email
}

output "budget_enabled" {
  value = module.observability.budget_enabled
}

output "notification_channel_ids" {
  value = module.observability.notification_channel_ids
}

output "notification_channel_provenance_sha256" {
  value = module.observability.notification_channel_provenance_sha256
}
