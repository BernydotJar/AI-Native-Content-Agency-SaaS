output "resource_creation_enabled" {
  description = "Whether this configuration is allowed to create bootstrap resources."
  value       = var.enable_bootstrap
}

output "cloud_run_enabled" {
  description = "Whether a Cloud Run service is included in the plan."
  value       = var.enable_cloud_run
}

output "monthly_budget_name" {
  description = "Billing budget resource name after bootstrap apply."
  value       = var.enable_bootstrap ? google_billing_budget.project[0].name : null
}

output "artifact_registry_repository" {
  description = "Docker repository path after bootstrap apply."
  value = var.enable_bootstrap ? format(
    "%s-docker.pkg.dev/%s/%s",
    var.region,
    var.project_id,
    var.artifact_repository_id,
  ) : null
}

output "runtime_service_account" {
  value = var.enable_bootstrap ? google_service_account.runtime[0].email : null
}

output "deployer_service_account" {
  value = var.enable_bootstrap ? google_service_account.deployer[0].email : null
}

output "workload_identity_provider" {
  value = var.enable_bootstrap ? google_iam_workload_identity_pool_provider.github[0].name : null
}

output "cloud_run_uri" {
  value = var.enable_cloud_run ? google_cloud_run_v2_service.app[0].uri : null
}

output "cloud_sql_enabled" {
  description = "Whether the bounded Cloud SQL pilot is included in the plan."
  value       = var.enable_cloud_sql
}

output "cloud_sql_connection_name" {
  description = "Cloud SQL connection name used by the Cloud Run Unix socket integration."
  value       = var.enable_cloud_sql ? google_sql_database_instance.app[0].connection_name : null
}

output "cloud_sql_database_name" {
  description = "Application database name inside Cloud SQL."
  value       = var.enable_cloud_sql ? google_sql_database.app[0].name : null
}

output "reviewed_monthly_cost_estimate_units" {
  description = "Reviewed monthly estimate in billing-account currency units; not a guarantee or hard cloud shutdown."
  value       = var.reviewed_monthly_cost_estimate_units
}

output "authorized_monthly_cost_cap_units" {
  description = "Operator-authorized hard monthly cap used by the Terraform planning interlock."
  value       = var.authorized_monthly_cost_cap_units
}

output "cost_review_receipt_sha256" {
  description = "Hash of the reviewed cost evidence bound into the plan."
  value       = var.cost_review_receipt_sha256
}

output "schema_initialization_receipt_sha256" {
  description = "Hash of the separately executed schema and role initialization receipt."
  value       = var.schema_initialization_receipt_sha256
}
