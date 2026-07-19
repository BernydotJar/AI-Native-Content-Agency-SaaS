output "service_name" {
  value = google_cloud_run_v2_service.application.name
}

output "service_uri" {
  value = google_cloud_run_v2_service.application.uri
}

output "invoker_iam_disabled" {
  value = google_cloud_run_v2_service.application.invoker_iam_disabled
}

output "migration_job_name" {
  value = google_cloud_run_v2_job.migrations.name
}
