output "resource_creation_enabled" {
  description = "Whether this configuration is allowed to create bootstrap resources."
  value       = var.enable_bootstrap
}

output "cloud_run_enabled" {
  description = "Whether a Cloud Run service is included in the plan."
  value       = var.enable_cloud_run
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
